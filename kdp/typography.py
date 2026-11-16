"""Portable fonts and bounded text layout for raster print pages."""
from PIL import ImageFont

FONT_PATHS = [r'C:\Windows\Fonts\arial.ttf', r'C:\Windows\Fonts\calibri.ttf',
              '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
              '/System/Library/Fonts/Supplemental/Arial.ttf', 'DejaVuSans.ttf']


def font(size):
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def centered(draw, text, y, width, size=100, max_width=2100):
    # Shrink text to fit, rather than clip long names or titles.
    chosen = font(size)
    while draw.textbbox((0, 0), text, font=chosen)[2] > max_width and size > 20:
        size -= 4
        chosen = font(size)
    box = draw.textbbox((0, 0), text, font=chosen)
    draw.text(((width - (box[2] - box[0])) / 2 - box[0], y - box[1]),
              text, font=chosen, fill=0)
