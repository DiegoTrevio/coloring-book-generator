"""Bind an interior PDF to its exact inputs, without storing credentials."""
import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_receipt(pdf: Path, md: Path, config: Path | None, drawings: list[Path]):
    data = {'pdf': digest(pdf), 'markdown': digest(md),
            'config': digest(config) if config else None,
            'drawings': {p.name: digest(p) for p in drawings}}
    target = pdf.with_suffix('.build.json')
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    temporary.replace(target)


def verify_receipt(pdf: Path, md: Path, config: Path, drawings: list[Path]):
    try:
        data = json.loads(pdf.with_suffix('.build.json').read_text(encoding='utf-8'))
        expected = {'pdf': digest(pdf), 'markdown': digest(md), 'config': digest(config),
                    'drawings': {p.name: digest(p) for p in drawings}}
    except (OSError, ValueError):
        raise ValueError('Falta un registro de construcción válido. Reconstruye el PDF antes de exportar.') from None
    if data != expected:
        raise ValueError('El PDF está desactualizado o sus archivos cambiaron. Reconstrúyelo antes de exportar.')
