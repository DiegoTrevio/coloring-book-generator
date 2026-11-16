"""Build the interior PDF from processed page images."""
from __future__ import annotations

import logging
from pathlib import Path

import img2pdf
from PIL import Image, ImageDraw, ImageFont

from .postprocess import PAGE_W_PX, PAGE_H_PX

log = logging.getLogger("kdp")

# ── "This Book Belongs To" page ───────────────────────────────────────────────

from .typography import centered


def _decorated_page(scratch_dir: Path, language="en", completion=False, title="") -> Path:
    img = Image.new("L", (PAGE_W_PX, PAGE_H_PX), 255)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((180, 180, PAGE_W_PX-180, PAGE_H_PX-180),
                           radius=85, outline=0, width=7)
    draw.rounded_rectangle((215, 215, PAGE_W_PX-215, PAGE_H_PX-215),
                           radius=65, outline=0, width=3)
    # Theme-neutral circles can also be colored in.
    for x in (380, 650, 920, 1190, 1460, 1730, 2000):
        draw.ellipse((x, 440, x+120, 560), outline=0, width=5)
    if completion:
        heading = "¡Terminaste tu libro!" if language == "es" else "You finished your book!"
        subtitle = "Reconocimiento a tu creatividad" if language == "es" else "Celebrating your creativity"
    else:
        heading = "Este libro pertenece a" if language == "es" else "This book belongs to"
        subtitle = title
    centered(draw, heading, 900, PAGE_W_PX, size=120, max_width=2050)
    if subtitle:
        centered(draw, subtitle, 1130, PAGE_W_PX, size=65, max_width=1950)
    centered(draw, "Nombre" if language == "es" else "Name", 1580, PAGE_W_PX, size=75)
    draw.line((500, 1810, PAGE_W_PX-500, 1810), fill=0, width=5)
    message = "¡Dale color a tu imaginación!" if language == "es" else "Let your imagination shine!"
    centered(draw, message, 2600, PAGE_W_PX, size=65, max_width=1950)
    out = scratch_dir / ("_completion_page.png" if completion else "_title_page.png")
    img.save(out, format="PNG", dpi=(300, 300))
    return out


def _create_title_page(scratch_dir: Path) -> Path:
    return _decorated_page(scratch_dir)


def _create_blank_page(scratch_dir: Path) -> Path:
    out = scratch_dir / "_blank_page.png"
    if not out.exists():
        Image.new("L", (PAGE_W_PX, PAGE_H_PX), 255).save(out, format="PNG")
    return out


# ── Main PDF builder ──────────────────────────────────────────────────────────

# 8.5 × 11 in in PDF points (1 pt = 1/72 in)
_PT_W = 8.5 * 72
_PT_H = 11.0 * 72


def build_pdf(
    clean_dir: Path,
    output_path: Path,
    page_ideas_ordered: list[str],
    *, language: str = "en", title: str = "", completion_page: bool = False,
) -> int:
    """
    Assemble the interior PDF.
    Layout:
      Page 1 (right-hand): "This Book Belongs To"
      Page 2:              blank
      For each drawing:    drawing page, blank page
    Returns total page count.
    """
    scratch = output_path.parent
    scratch.mkdir(parents=True, exist_ok=True)
    title_page = _decorated_page(scratch, language, title=title)
    blank_page = _create_blank_page(scratch)

    # Build ordered list of clean page paths
    drawing_pages: list[Path] = []
    for idea in page_ideas_ordered:
        path = clean_dir / idea
        if not path.is_file():
            raise FileNotFoundError(f"Missing drawing: {path}. Generate or select it before building the PDF.")
        drawing_pages.append(path)

    # Compose final page list
    pages: list[Path] = [title_page, blank_page]
    for dp in drawing_pages:
        pages.append(dp)
        pages.append(blank_page)

    if completion_page:
        pages.extend([_decorated_page(scratch, language, completion=True), blank_page])

    total = len(pages)
    log.info("PDF pages: 2 (title+blank) + %d drawings × 2 = %d total", len(drawing_pages), total)

    layout = img2pdf.get_layout_fun((_PT_W, _PT_H))
    pdf_bytes = img2pdf.convert([str(p) for p in pages], layout_fun=layout)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(pdf_bytes)
    return total
