"""Create portable book projects from user-authored scenes, without any API."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from .book_config import BookConfig, load_config
from .parser import parse_book
from .utils import sanitize_folder_name


@dataclass
class BookProject:
    title: str
    author: str
    scenes: list[tuple[str, str]]  # caption, image description
    config: BookConfig

    def validate(self):
        if not self.title.strip() or not self.author.strip():
            raise ValueError('Escribe el título y el autor.')
        if any(c in self.title + self.author for c in '\r\n|'):
            raise ValueError('Título y autor deben estar en una sola línea, sin |.')
        if not self.scenes:
            raise ValueError('Añade al menos una escena.')
        for label, description in self.scenes:
            if not description.strip() or any(c in label + description for c in '\r\n'):
                raise ValueError('Cada escena necesita una descripción en una sola línea.')

    def save_new(self, parent: Path) -> tuple[Path, Path]:
        self.validate()
        name = sanitize_folder_name(self.title)
        if not name or name in ('.', '..'):
            raise ValueError('El título no produce un nombre de carpeta válido.')
        # Prefix prevents Windows device names such as CON, AUX or NUL.
        directory = parent / ('libro-' + name)
        directory.mkdir(parents=True, exist_ok=False)
        config = asdict(self.config)
        config['labels'] = {str(i): label for i, (label, _) in enumerate(self.scenes, 1)}
        config_path = directory / 'book.json'
        md_path = directory / 'book.md'
        style = 'Consistent professional coloring-book illustration. Clear enclosed spaces and deliberate clean outlines.'
        lines = [f'# {self.title}', '', '## Master Style Prompt', '```text', style, '```', '', '## Page Ideas']
        lines += [f'{i}. {description}' for i, (_, description) in enumerate(self.scenes, 1)]
        # Cover prompts are original art only; text is added by local layout.
        lines += ['', '## Cover', '### Front Cover', '```text',
                  f'Colorful editorial cover artwork for a coloring book about {self.config.theme}. '
                  'Cohesive attractive composition, matching the book style. Leave the top quarter empty for typography. No text, letters or logos.',
                  '```', '### Back Cover', '```text',
                  f'Matching colorful back cover artwork about {self.config.theme}. '
                  'Decoration along the edges, empty center for description and empty bottom-right for barcode. No text, letters or barcode.',
                  '```', '### Colored Sample', '```text', 'Color this exact illustration.', '```',
                  '', '## KDP Details', f'Book Title: {self.title}', f'Author: {self.author}',
                  f'Language: {"Spanish" if self.config.language == "es" else "English"}',
                  f'Reading Age: {self.config.age if self.config.age != "adult" else "18-99"}',
                  'Paper: White', 'Interior: Black & White', 'Trim: 8.5 x 11 in', 'Bleed: No bleed',
                  '', '### Description',
                  f'Un libro para colorear sobre {self.config.theme}. Personaliza esta descripción antes de publicar.',
                  '', '### Keywords', '1. libro para colorear', '2. actividades creativas',
                  '3. ilustraciones para colorear', '', '### Categories',
                  '- Editar las categorías antes de publicar']
        try:
            md_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            # Validate using the same parsers as generation, before exposing the project.
            parse_book(md_path)
            load_config(config_path)
        except Exception:
            for file in (md_path, config_path):
                file.unlink(missing_ok=True)
            directory.rmdir()
            raise
        return md_path, config_path

    @classmethod
    def read(cls, md_path: Path, config_path: Path):
        book = parse_book(md_path)
        config = load_config(config_path)
        labels = config.labels or {}
        scenes = [(labels.get(str(p.number), labels.get(f'{p.number:02d}', '')), p.idea)
                  for p in book.page_ideas]
        return cls(book.book_title, book.author, scenes, config)


def parse_scene_lines(text: str) -> list[tuple[str, str]]:
    scenes = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if '|' not in line:
            raise ValueError(f'Línea {number}: usa Nombre | descripción de la escena.')
        label, description = [part.strip() for part in line.split('|', 1)]
        if not description:
            raise ValueError(f'Línea {number}: falta la descripción.')
        scenes.append((label, description))
    return scenes


def build_command(root: Path, md: Path, config: Path, *, mode: str,
                  limit: int = 5, skip_cover: bool = True, selections: str = '') -> list[str]:
    import sys
    if mode not in ('check', 'generate', 'review', 'draft'):
        raise ValueError('Modo de ejecución desconocido')
    if type(limit) is not int or limit < 0:
        raise ValueError('La cantidad de prueba debe ser un entero no negativo.')
    command = [sys.executable, '-u', str(root / 'kdp_book_builder.py'), str(md),
               '--config', str(config), '--provider', 'replicate',
               '--out', str(md.parent / 'output'), '--workers', '1', '--yes']
    if limit:
        command += ['--limit', str(limit)]
    if skip_cover:
        command += ['--skip-cover']
    if mode == 'check':
        command += ['--dry-run']
    elif mode in ('review', 'draft'):
        command += ['--only-pdf']
        if mode == 'draft':
            command += ['--allow-review']
        if selections.strip():
            if not re.fullmatch(r'\d+:\d+(,\d+:\d+)*', selections.strip()):
                raise ValueError('Selección inválida. Ejemplo: 1:2,4:3')
            command += ['--select', selections.strip()]
    return command
