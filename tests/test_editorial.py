"""Editorial settings, candidate selection and offline PDF checks."""
import json
import threading
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image, ImageDraw
import pikepdf

from kdp.book_config import BookConfig, load_config
from kdp.cli import _generate_and_qa, run
from kdp.parser import PageIdea, parse_book
from kdp.postprocess import process_page, MARGIN_PX
from kdp.pdf_builder import build_pdf
from kdp.qa import QAResult

ROOT = Path(__file__).parents[1]


def art(dest):
    image = Image.new('RGB', (600, 800), 'white')
    ImageDraw.Draw(image).rectangle((180, 220, 420, 580), outline=0, width=8)
    image.save(dest)


@pytest.mark.parametrize('name', ['animales', 'personas', 'vehiculos'])
def test_profiles_have_labels_and_subject_rules(name):
    config = load_config(ROOT / f'examples/{name}.json')
    book = parse_book(ROOT / f'examples/{name}-editorial.md')
    assert config.candidates == 3
    assert len(config.labels) == len(book.page_ideas)
    assert 'No text' in config.prompt(book.master_style_prompt)


@pytest.mark.parametrize('data', [{'candidates': 0}, {'age': 'unknown'}, {'subject': 'typo'},
                                 {'fit_art': 'yes'}, {'labels': []}, {'unknown': True}])
def test_config_rejects_bad_values(tmp_path, data):
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_config(path)


def test_fit_enlarges_art_preserves_ratio_and_margins(tmp_path):
    raw = tmp_path / 'raw.png'; art(raw)
    normal = tmp_path / 'normal.png'; fitted = tmp_path / 'fitted.png'
    process_page(raw, normal)
    process_page(raw, fitted, fit_art=True)
    with Image.open(normal) as before, Image.open(fitted) as after:
        b = before.point(lambda x: 255 if x < 128 else 0).getbbox()
        a = after.point(lambda x: 255 if x < 128 else 0).getbbox()
        assert a[2]-a[0] > b[2]-b[0]
        assert a[0] >= MARGIN_PX and a[1] >= MARGIN_PX
        assert a[2] <= 2550-MARGIN_PX and a[3] <= 3300-MARGIN_PX
        assert abs((a[2]-a[0])/(a[3]-a[1]) - (b[2]-b[0])/(b[3]-b[1])) < .01


def test_candidate_selection_and_offline_manual_override(tmp_path):
    raw = tmp_path / 'raw'; raw.mkdir()
    clean = tmp_path / 'clean'; clean.mkdir()
    gen = Mock()
    def generate(prompt, dest, **kwargs):
        art(dest)
        return True
    gen.generate.side_effect = generate
    manifest = {'pages': {}, 'stats': {}}
    results = [QAResult(['grey'], 5., 40., .1), QAResult([], 5., 1., .1), QAResult([], 5., 3., .1)]
    with patch('kdp.cli.check_image', side_effect=results):
        key, status = _generate_and_qa(PageIdea(1, 'test scene'), gen, raw, clean,
                                      manifest, threading.Lock(), 140, False, 'STYLE',
                                      BookConfig(candidates=3))
    assert gen.generate.call_count == 3
    assert status == 'ok'
    assert manifest['pages']['01']['selected'] == 2
    # Same settings resume without a generation call.
    _generate_and_qa(PageIdea(1, 'test scene'), gen, raw, clean,
                     manifest, threading.Lock(), 140, False, 'STYLE', BookConfig(candidates=3))
    assert gen.generate.call_count == 3
    # Changed art direction must not silently reuse old illustrations.
    with pytest.raises(ValueError, match='different'):
        _generate_and_qa(PageIdea(1, 'test scene'), gen, raw, clean,
                         manifest, threading.Lock(), 140, False, 'NEW STYLE')


def test_pdf_exact_pages_completion_and_no_missing_fallback(tmp_path):
    clean = tmp_path / 'clean'; clean.mkdir()
    art(clean / '01_drawing.png')
    out = tmp_path / 'interior.pdf'
    assert build_pdf(clean, out, ['01_drawing.png'], language='es',
                     title='Mi libro', completion_page=True) == 6
    with pikepdf.open(out) as pdf:
        assert len(pdf.pages) == 6
        assert list(pdf.pages[0].MediaBox) == [0, 0, 612, 792]
    with pytest.raises(FileNotFoundError):
        build_pdf(clean, tmp_path / 'missing.pdf', ['02_missing.png'])


def test_flagged_pages_block_pdf_then_select_without_api(tmp_path):
    example = ROOT / 'examples/personas-editorial.md'
    profile = ROOT / 'examples/personas.json'
    command = [str(example), '--config', str(profile), '--provider', 'replicate',
               '--out', str(tmp_path), '--limit', '1', '--skip-cover', '--yes']
    gen = Mock()
    def generate(prompt, dest, **kwargs):
        art(dest)
        return True
    gen.generate.side_effect = generate
    with patch('kdp.cli.load_api_key', return_value='fake'), patch('replicate.Client'), \
         patch('kdp.cli.SchnellGenerator', return_value=gen), \
         patch('kdp.cli.check_image', return_value=QAResult(['grey'], 5., 30., .1)):
        with pytest.raises(SystemExit, match='need review'):
            run(command)
    assert not list(tmp_path.rglob('*_interior.pdf'))
    assert list(tmp_path.rglob('review.html'))
    with patch('replicate.Client') as client, patch('kdp.cli.load_api_key') as key:
        run(command + ['--only-pdf', '--select', '1:2'])
        client.assert_not_called(); key.assert_not_called()
    manifest = json.loads(next(tmp_path.rglob('manifest.json')).read_text())
    assert manifest['pages']['01']['visual_reviewed']
    assert manifest['pages']['01']['selected'] == 2
    with pikepdf.open(next(tmp_path.rglob('*_interior.pdf'))) as pdf:
        assert len(pdf.pages) == 6


def test_cover_typography_is_repeatable_and_keeps_original(tmp_path):
    from kdp.cover_layout import layout_covers
    Image.new('RGB', (768, 1024), '#99d9e8').save(tmp_path / 'front.png')
    original = (tmp_path / 'front.png').read_bytes()
    layout_covers(tmp_path, 'Personas y profesiones', 'Descripción')
    first = (tmp_path / 'front.png').read_bytes()
    assert (tmp_path / 'front_art.png').read_bytes() == original
    assert first != original
    layout_covers(tmp_path, 'Personas y profesiones', 'Descripción')
    assert (tmp_path / 'front.png').read_bytes() == first
