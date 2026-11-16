"""Offline export of a reviewed paperback book. No API requests."""
import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path

import img2pdf
import pikepdf
from PIL import Image, ImageDraw, ImageOps

from .build_receipt import verify_receipt
from .book_config import load_config
from .parser import parse_book
from .utils import sanitize_folder_name


def export_package(md_path: Path, config_path: Path, *, spine: float,
                   cover_width: float, cover_height: float, destination: Path) -> Path:
    """Use inches from the printer's calculator, checked against 8.5 x 11 trim."""
    if any(not math.isfinite(n) or n <= 0 for n in (spine, cover_width, cover_height)):
        raise ValueError('Las medidas deben ser números positivos y finitos, en pulgadas.')
    # Current interiors have fixed letter dimensions and no bleed.
    if abs(cover_width-(17 + spine + .25)) > .002 or abs(cover_height-11.25) > .002:
        raise ValueError('Las medidas no corresponden a 8.5 × 11, lomo indicado y sangrado de 0.125 pulgadas.')
    book = parse_book(md_path)
    config = load_config(config_path)
    directory = md_path.parent/'output'/sanitize_folder_name(book.book_title)
    manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    pages = manifest.get('pages', {})
    for idea in book.page_ideas:
        page = pages.get(f'{idea.number:02d}', {})
        if page.get('status') != 'ok' or not page.get('visual_reviewed'):
            raise ValueError(f'Falta revisión visual de la página {idea.number}. Elige su opción antes de exportar.')
        if not (directory/'pages_clean'/idea.filename).is_file():
            raise ValueError(f'Falta el dibujo {idea.number}.')
    interior = directory/'interior'/f'{sanitize_folder_name(book.book_title)}_interior.pdf'
    verify_receipt(interior, md_path, config_path,
                   [directory/"pages_clean"/idea.filename for idea in book.page_ideas])
    expected_pages = 2 + 2*len(book.page_ideas) + (2 if config.completion_page else 0)
    if expected_pages < 24:
        raise ValueError('El interior tiene menos de 24 páginas. Completa el libro antes de preparar la edición de impresión.')
    with pikepdf.open(interior) as pdf:
        if len(pdf.pages) != expected_pages:
            raise ValueError('El PDF no corresponde al libro completo. Reconstrúyelo con Dibujos: 0.')
        for page in pdf.pages:
            box = [float(x) for x in page.MediaBox]
            if abs(box[2]-box[0]-612) > .01 or abs(box[3]-box[1]-792) > .01:
                raise ValueError('El interior contiene páginas con dimensiones incorrectas.')
    if destination.exists():
        raise FileExistsError('Ya existe ese paquete. Elige una carpeta nueva para conservar el anterior.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        work = Path(temp)
        dpi = 300
        w, h = round(cover_width*dpi), round(cover_height*dpi)
        bleed, trim_w, trim_h = round(.125*dpi), round(8.5*dpi), round(11*dpi)
        canvas = Image.new('RGB', (w, h), 'white')
        resolutions = {}
        for name, x in [('back', bleed), ('front', round((.125+8.5+spine)*dpi))]:
            with Image.open(directory/'cover'/f'{name}.png') as source:
                source = source.convert('RGB')
                resolutions[name] = [source.width/8.5, source.height/11]
                # Extend the edge color through bleed; preserve all artwork.
                background = source.getpixel((0, 0))
                panel = Image.new('RGB', (trim_w, trim_h), background)
                fitted = ImageOps.contain(source, (trim_w-150, trim_h-150), Image.Resampling.LANCZOS)
                panel.paste(fitted, ((trim_w-fitted.width)//2, (trim_h-fitted.height)//2))
                canvas.paste(Image.new('RGB', (trim_w+2*bleed, h), background), (x-bleed, 0))
                canvas.paste(panel, (x, bleed))
        # Neutral spine; no spine text, avoiding text on narrow spines.
        draw = ImageDraw.Draw(canvas)
        draw.rectangle((bleed+trim_w, 0, round((.125+8.5+spine)*dpi)-1, h), fill='white')
        # Reserve a blank barcode area inside the back cover.
        right = bleed+trim_w-round(.25*dpi); bottom = bleed+trim_h-round(.25*dpi)
        draw.rectangle((right-600, bottom-360, right, bottom), fill='white')
        png = work/'cover.png'; canvas.save(png, dpi=(dpi,dpi))
        (work/'cover.pdf').write_bytes(img2pdf.convert(str(png), layout_fun=img2pdf.get_layout_fun((cover_width*72, cover_height*72))))
        shutil.copy2(interior, work/'interior.pdf')
        warnings = ['Verifica las medidas con la plantilla oficial y el Print Previewer; este informe no garantiza aceptación.',
                    'Revisa el corte, el lomo, los textos y el espacio reservado al código de barras antes de publicar.',
                    'Los datos editoriales deben personalizarse; este paquete no publica el libro.']
        if any(min(res) < 300 for res in resolutions.values()):
            warnings.append('Alguna cubierta tiene menos de 300 píxeles originales por pulgada: ampliar no añade detalle.')
        report = {'pages': expected_pages, 'trim_inches': [8.5,11],
                  'cover_inches': [cover_width,cover_height], 'spine_inches': spine,
                  'source_cover_ppi': resolutions, 'warnings': warnings,
                  'files': {name: hashlib.sha256((work/name).read_bytes()).hexdigest()
                            for name in ('interior.pdf','cover.pdf','cover.png')}}
        (work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        (work/'LEEME.txt').write_text('\n'.join(warnings),encoding='utf-8')
        shutil.copytree(work,destination)
    return destination
