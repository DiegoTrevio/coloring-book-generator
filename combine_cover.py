#!/usr/bin/env python3
"""Combine front and back cover images side by side: back (left) | front (right)."""
import sys
from pathlib import Path
from PIL import Image


def combine(cover_dir: Path, out: Path | None = None) -> Path:
    front_path = cover_dir / "front.png"
    back_path  = cover_dir / "back.png"

    if not front_path.exists():
        sys.exit(f"ERROR: front.png not found in {cover_dir}")
    if not back_path.exists():
        sys.exit(f"ERROR: back.png not found in {cover_dir}")

    front = Image.open(front_path).convert("RGB")
    back  = Image.open(back_path).convert("RGB")

    # Match heights (resize back to front's height if they differ)
    if back.size != front.size:
        ratio = front.height / back.height
        back = back.resize(
            (round(back.width * ratio), front.height), Image.LANCZOS
        )

    combined_w = back.width + front.width
    combined   = Image.new("RGB", (combined_w, front.height), (255, 255, 255))
    combined.paste(back,  (0, 0))           # back  → left
    combined.paste(front, (back.width, 0))  # front → right

    png_dest = out or (cover_dir / "cover_combined.png")
    combined.save(png_dest, format="PNG")
    print(f"✓ PNG → {png_dest}")

    try:
        import img2pdf
        pdf_dest = png_dest.with_suffix(".pdf")
        pdf_dest.write_bytes(img2pdf.convert(str(png_dest)))
        print(f"✓ PDF → {pdf_dest}")
    except Exception as exc:
        print(f"⚠ PDF export failed: {exc}")

    print(f"  Size: {combined_w} × {front.height} px")
    return png_dest


if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Try to find the cover dir automatically
        default = Path(r"D:\KPD")
        candidates = [d / "cover" for d in default.iterdir() if (d / "cover").exists()]
        if len(candidates) == 1:
            combine(candidates[0])
        else:
            sys.exit(
                "Usage: python combine_cover.py <cover_dir>\n"
                "       e.g. python combine_cover.py "
                r'"D:\KPD\My First Toddler Coloring Book Ages 1-3\cover"'
            )
    else:
        combine(Path(sys.argv[1]))
