"""Post-process raw generated pages into print-ready B&W PNGs."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from .typography import centered

# ── Output dimensions (8.5 × 11 in @ 300 DPI) ────────────────────────────────
PAGE_W_PX    = 2550   # 8.5 in × 300 dpi
PAGE_H_PX    = 3300   # 11.0 in × 300 dpi
MARGIN_PX    = 150    # 0.5 in × 300 dpi — safe margin on every side
DRAW_W       = PAGE_W_PX - 2 * MARGIN_PX   # 2250
DRAW_H       = PAGE_H_PX - 2 * MARGIN_PX   # 3000

# Default B&W threshold (0–255); pixels >= threshold become white
DEFAULT_THRESHOLD = 140


def process_page(
    raw_path: Path,
    dest_path: Path,
    threshold: int = DEFAULT_THRESHOLD,
    *, fit_art: bool = False, caption: str = "",
) -> Path:
    """
    Convert *raw_path* into a print-ready PNG at *dest_path*:
      1. Grayscale
      2. Lanczos-scale to fit inside the drawing area with margins
      3. Paste centred on a white 2550×3300 canvas
      4. Threshold to pure black/white
    """
    with Image.open(raw_path) as source:
        # Composite transparent images on white, not black.
        rgba = source.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        img = background.convert("L")
    if fit_art:
        # Crop white margins only. Keep a small padding around the ink bounds.
        mask = img.point(lambda value: 255 if value < 220 else 0)
        bbox = mask.getbbox()
        if bbox:
            pad = max(4, round(min(img.size) * .015))
            left, top, right, bottom = bbox
            img = img.crop((max(0, left-pad), max(0, top-pad),
                            min(img.width, right+pad), min(img.height, bottom+pad)))
    caption_space = 220 if caption else 0
    draw_height = DRAW_H - caption_space
    scale = min(DRAW_W / img.width, draw_height / img.height)
    img = img.resize((max(1, round(img.width * scale)),
                      max(1, round(img.height * scale))), Image.Resampling.LANCZOS)
    canvas = Image.new("L", (PAGE_W_PX, PAGE_H_PX), 255)
    canvas.paste(img, ((PAGE_W_PX-img.width)//2,
                      MARGIN_PX + (draw_height-img.height)//2))
    if caption:
        centered(ImageDraw.Draw(canvas), caption,
                 PAGE_H_PX-MARGIN_PX-150, PAGE_W_PX, size=100, max_width=DRAW_W)

    # Hard threshold → pure black/white
    canvas = canvas.point(lambda p: 255 if p >= threshold else 0, "L")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(dest_path, format="PNG", optimize=False, dpi=(300, 300))
    return dest_path
