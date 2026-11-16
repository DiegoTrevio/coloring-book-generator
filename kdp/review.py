"""Local visual review of saved candidates. No automatic anatomy claims."""
import html
import json
from pathlib import Path


def write_review(book_dir: Path, manifest: dict) -> Path:
    cards = []
    for key, page in sorted(manifest['pages'].items()):
        candidates = []
        for i, candidate in enumerate(page.get('candidates', []), 1):
            path = 'pages_raw/' + candidate['path']
            flags = ', '.join(candidate.get('qa_flags', [])) or 'Technical checks passed'
            candidates.append(
                f'<figure><img src="{html.escape(path, quote=True)}">'
                f'<figcaption>Option {i}: {html.escape(flags)}<br>'
                f'Select: <code>--select {int(key)}:{i}</code></figcaption></figure>')
        cards.append(f'<section><h2>{html.escape(key)}: {html.escape(page.get("idea", ""))}</h2>'
                     f'<p>Status: {html.escape(page.get("status", "unknown"))}; '
                     f'selected option: {page.get("selected", "legacy")}</p>'
                     '<div class="options">' + ''.join(candidates) + '</div></section>')
    output = book_dir / 'review.html'
    output.write_text('''<!doctype html><html lang="es"><meta charset="utf-8">
<title>Revisión de ilustraciones</title><style>
body{font:16px system-ui;margin:32px;background:#f2f4f6;color:#20242a}
section{background:white;padding:20px;margin:20px 0;border-radius:12px}
.options{display:flex;flex-wrap:wrap;gap:16px}figure{margin:0;width:280px}
img{width:100%;height:370px;object-fit:contain;border:1px solid #ddd}
code{background:#eee}figcaption{padding:10px}
</style><h1>Revisión de ilustraciones</h1>
<p>Los filtros técnicos no evalúan anatomía ni consistencia artística.
Revisa manos, extremidades, rostros, composición y facilidad para colorear.
Seleccionar una opción no genera imágenes ni consume API.</p>
''' + ''.join(cards) + '</html>', encoding='utf-8')
    return output
