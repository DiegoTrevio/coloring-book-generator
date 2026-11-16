"""Add reliable typography to separate cover artwork (not a full-wrap cover)."""
import re
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw
from .typography import centered


def layout_covers(cover_dir: Path, title: str, description: str) -> None:
    for name in ('front', 'back'):
        output = cover_dir / f'{name}.png'
        original = cover_dir / f'{name}_art.png'
        if not output.exists():
            continue
        if not original.exists():
            original.write_bytes(output.read_bytes())
        with Image.open(original) as source:
            image = source.convert('RGB')
        draw = ImageDraw.Draw(image)
        w, h = image.size
        if name == 'front':
            lines = textwrap.wrap(title, width=26, break_long_words=True) or ['']
            box_height = max(round(h*.23), len(lines)*round(h*.05)+round(h*.04))
            draw.rounded_rectangle((int(w*.06), int(h*.04), int(w*.94), box_height),
                                   radius=int(w*.025), fill='white')
            for i, line in enumerate(lines):
                centered(draw, line, round(h*.075)+i*round(h*.05), w,
                         size=max(20, round(w*.055)), max_width=round(w*.82))
        else:
            text = re.sub('<[^>]+>', '', description)
            lines = textwrap.wrap(text, width=42)
            if not lines:
                continue
            # Bounded text size; refuse to silently clip a long description.
            if len(lines) > 14:
                lines = textwrap.wrap(text[:500].rsplit(' ', 1)[0] + '…', width=42)
            y = round(h*.28)
            line_height = round(h*.035)
            draw.rounded_rectangle((int(w*.07), y-int(h*.03), int(w*.93),
                                    y+len(lines)*line_height+int(h*.03)),
                                   radius=int(w*.025), fill='white')
            for i, line in enumerate(lines):
                centered(draw, line, y+i*line_height, w,
                         size=max(16, round(w*.03)), max_width=round(w*.8))
        image.save(output, format='PNG')
