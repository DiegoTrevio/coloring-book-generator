"""New-book creation and GUI command construction without paid API calls."""
from pathlib import Path
import subprocess
import sys

import pytest

from kdp.book_config import BookConfig
from kdp.project import BookProject, build_command, parse_scene_lines

ROOT = Path(__file__).parents[1]


def test_custom_people_project_roundtrip_and_no_overwrite(tmp_path):
    scenes = parse_scene_lines('Bombera | a firefighter with a hose\n\nAstronauta | a child astronaut on the moon')
    project = BookProject('Mi primer libro', 'Diego Treviño', scenes,
                          BookConfig(theme='Profesiones', subject='people', candidates=3, captions=True))
    md, config = project.save_new(tmp_path)
    loaded = BookProject.read(md, config)
    assert loaded.title == project.title
    assert loaded.author == project.author
    assert loaded.scenes == scenes
    original = md.read_bytes()
    with pytest.raises(FileExistsError):
        project.save_new(tmp_path)
    assert md.read_bytes() == original


@pytest.mark.parametrize('text', ['Una idea sin separador', 'Conejo | '])
def test_scenes_need_description(text):
    with pytest.raises(ValueError):
        parse_scene_lines(text)


def test_invalid_profile_rolls_back_new_project(tmp_path):
    with pytest.raises(ValueError):
        BookProject('Libro', 'Autor', [('Uno','one animal')], BookConfig(age='unknown')).save_new(tmp_path)
    assert not list(tmp_path.iterdir())


def test_windows_device_names_are_prefixed(tmp_path):
    md, _ = BookProject('CON', 'Autor', [('Uno','a car')], BookConfig()).save_new(tmp_path)
    assert md.parent.name == 'libro-CON'


def test_gui_rebuild_command_is_offline_and_keeps_paths_separate(tmp_path):
    md = tmp_path/'a folder'/'book.md'
    config = md.with_suffix('.json')
    command = build_command(ROOT, md, config, mode='review', limit=5, selections='1:2,4:3')
    assert '--only-pdf' in command
    assert command[command.index('--select')+1] == '1:2,4:3'
    assert str(md) in command  # no shell string interpolation
    assert '--dry-run' not in command
    with pytest.raises(ValueError):
        build_command(ROOT, md, config, mode='review', selections='1:2 & echo unsafe')
    with pytest.raises(ValueError):
        build_command(ROOT, md, config, mode='generate', limit=-1)


def test_new_custom_book_dry_run_with_gui_command(tmp_path):
    md, config = BookProject('Mundos de fantasía', 'Autor', [('Dragón','a friendly dragon beside a castle')],
                              BookConfig(theme='Fantasía', subject='fantasy')).save_new(tmp_path)
    command = build_command(ROOT, md, config, mode='check')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'no API calls made' in result.stdout
    assert list(md.parent.rglob('upload_details.txt'))


def test_gui_module_import_has_no_window_or_process_side_effects():
    result = subprocess.run([sys.executable, '-c', 'import libros_app; print("import-ok")'],
                             cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'import-ok' in result.stdout
