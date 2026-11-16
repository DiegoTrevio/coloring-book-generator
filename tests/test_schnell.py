"""Offline provider and pipeline checks. Never contact paid services."""
import io
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from kdp.cli import _generate_and_qa, load_api_key, run
from kdp.generator import SchnellGenerator
from kdp.parser import PageIdea, parse_book

EXAMPLE = Path(__file__).parents[1] / 'examples' / 'animales-30.md'


def png_bytes():
    stream = io.BytesIO()
    Image.new('RGB', (32, 48), 'white').save(stream, 'PNG')
    return stream.getvalue()


def test_schnell_file_output_and_corrective_prompt(tmp_path):
    client = Mock()
    client.run.return_value = [io.BytesIO(png_bytes())]
    dest = tmp_path / 'page.png'
    assert SchnellGenerator(client).generate('puppy', dest, qa_flags=['grey'])
    Image.open(dest).verify()
    model = client.run.call_args.args[0]
    inputs = client.run.call_args.kwargs['input']
    assert model == 'black-forest-labs/flux-schnell'
    assert inputs['aspect_ratio'] == '3:4'
    assert inputs['num_inference_steps'] == 4
    assert inputs['output_format'] == 'png'
    assert 'no grey shading' in inputs['prompt']
    assert 'quality' not in inputs


def test_schnell_empty_output_and_no_edits(tmp_path):
    client = Mock()
    client.run.return_value = []
    gen = SchnellGenerator(client)
    assert not gen.generate('puppy', tmp_path / 'page.png')
    assert not gen.edit(tmp_path / 'source.png', 'color', tmp_path / 'color.png')
    assert client.run.call_count == 1


def test_download_failure_does_not_generate_again(tmp_path):
    client = Mock()
    item = Mock()
    item.read.side_effect = OSError('download interrupted')
    client.run.return_value = [item]
    assert not SchnellGenerator(client).generate('puppy', tmp_path / 'page.png')
    assert client.run.call_count == 1


def test_replicate_key_does_not_require_openai(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('REPLICATE_API_TOKEN', 'test-token')
    assert load_api_key(tmp_path, 'replicate') == 'test-token'


def test_style_reaches_generator_even_on_regeneration(tmp_path):
    gen = Mock()
    gen.generate.return_value = True
    manifest = {'pages': {'01': {'status': 'ok'}}, 'stats': {}}
    with patch('kdp.cli.check_image', return_value=SimpleNamespace(ok=True)), patch('kdp.cli.process_page'):
        _generate_and_qa(PageIdea(1, 'puppy'), gen, tmp_path, tmp_path,
                         manifest, threading.Lock(), 140, True, 'BOLD OUTLINES')
    assert gen.generate.call_args.kwargs['prompt'].startswith('BOLD OUTLINES')
    assert manifest['pages']['01']['status'] == 'ok'


def test_example_and_dry_run_without_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('REPLICATE_API_TOKEN', raising=False)
    assert len(parse_book(EXAMPLE).page_ideas) == 30
    with patch('replicate.Client') as client:
        run([str(EXAMPLE), '--provider', 'replicate', '--dry-run', '--out', str(tmp_path)])
        client.assert_not_called()
    assert list(tmp_path.rglob('upload_details.txt'))


def test_pipeline_builds_pdf_with_fake_provider(tmp_path):
    from PIL import ImageDraw
    def generate(prompt, dest, **kwargs):
        image = Image.new('RGB', (768, 1024), 'white')
        ImageDraw.Draw(image).ellipse((180, 200, 580, 750), outline='black', width=10)
        image.save(dest)
        return True
    with patch('kdp.cli.load_api_key', return_value='test-token'), patch('replicate.Client'), \
         patch('kdp.cli.SchnellGenerator') as provider:
        provider.return_value.generate.side_effect = generate
        run([str(EXAMPLE), '--provider', 'replicate', '--limit', '1', '--skip-cover',
             '--yes', '--out', str(tmp_path)])
    pdfs = list(tmp_path.rglob('*_interior.pdf'))
    assert len(pdfs) == 1
    assert pdfs[0].read_bytes().startswith(b'%PDF-')


def test_reject_openai_settings_for_schnell():
    with pytest.raises(SystemExit) as exc:
        run([str(EXAMPLE), '--provider', 'replicate', '--quality', 'high'])
    assert exc.value.code == 2
