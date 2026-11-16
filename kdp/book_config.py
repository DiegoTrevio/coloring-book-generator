"""Validated, theme-independent editorial settings loaded from JSON."""
from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path

AGE_RULES = {
    '3-5': 'Very simple rounded shapes, thick uniform outlines, very large enclosed coloring spaces. At most two large background elements. No tiny details.',
    '6-8': 'Simple readable scenes, bold uniform outlines, large enclosed coloring spaces. At most three large background elements.',
    '9-12': 'Balanced scenes with moderate detail, clear enclosed coloring spaces and consistent outlines.',
    'adult': 'Detailed balanced compositions with clean deliberate outlines and enclosed coloring spaces.',
}
SUBJECT_RULES = {
    'people': 'Natural human anatomy. Correct limb count, clear faces, separated arms and legs, simple readable hands. Clothing and held objects must not merge with the body.',
    'animals': 'Recognizable species anatomy, correct visible limbs, clear ears and tail. Avoid fused paws or extra body parts.',
    'vehicles': 'Coherent vehicle structure and perspective, aligned wheels, clear windows and recognizable mechanical shapes.',
    'fantasy': 'Coherent imaginary anatomy, readable silhouettes and clearly separated props.',
    'general': 'Recognizable subjects, coherent structure, clearly separated objects and readable silhouettes.',
}
STYLES = {
    'friendly-cartoon': 'Friendly editorial cartoon, rounded shapes, expressive simple faces, consistent proportions and uniform bold outlines.',
    'educational': 'Clear educational illustration, recognizable accurate features, restrained detail and consistent outlines.',
    'realistic-simple': 'Simplified realistic illustration with natural proportions and clean contours, no tonal rendering.',
    'detailed': 'Detailed decorative line illustration, balanced composition and consistent precise contours.',
}


@dataclass
class BookConfig:
    theme: str = 'Custom coloring book'
    subject: str = 'general'
    age: str = '6-8'
    style: str = 'friendly-cartoon'
    language: str = 'es'
    candidates: int = 1
    fit_art: bool = True
    captions: bool = False
    completion_page: bool = False
    labels: dict[str, str] | None = None
    art_direction: str = ''

    def prompt(self, master: str) -> str:
        return '\n'.join([
            master, f'Book theme: {self.theme}.', STYLES[self.style],
            AGE_RULES[self.age], SUBJECT_RULES[self.subject], self.art_direction,
            'Use the same line weight, proportions and visual language throughout this book.',
            'Black outlines on pure white. No shading, gradients, gray washes or solid black areas except small pupils. No text, letters, logos or watermarks. Keep all subjects fully inside generous white margins.',
        ])


def load_config(path: Path | None) -> BookConfig:
    if path is None:
        return BookConfig()
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('Book configuration must be a JSON object')
    allowed = {f.name for f in fields(BookConfig)}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f'Unknown configuration fields: {", ".join(sorted(unknown))}')
    config = BookConfig(**data)
    for name, choices in [('subject', SUBJECT_RULES), ('age', AGE_RULES), ('style', STYLES)]:
        if getattr(config, name) not in choices:
            raise ValueError(f'{name} must be one of: {", ".join(choices)}')
    if config.language not in ('es', 'en'):
        raise ValueError('language must be es or en (page artwork can use any language)')
    if type(config.candidates) is not int or not 1 <= config.candidates <= 6:
        raise ValueError('candidates must be an integer between 1 and 6')
    for key in ('fit_art', 'captions', 'completion_page'):
        if type(getattr(config, key)) is not bool:
            raise ValueError(f'{key} must be true or false')
    for key in ('theme', 'art_direction'):
        if not isinstance(getattr(config, key), str):
            raise ValueError(f'{key} must be a string')
    if config.labels is not None and (not isinstance(config.labels, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in config.labels.items()
    )):
        raise ValueError('labels must map page numbers (strings) to caption strings')
    return config
