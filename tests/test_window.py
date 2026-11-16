"""Exercise real Tk widgets on Windows, without Replicate credentials."""
import sys
from pathlib import Path
from unittest.mock import patch
import pytest


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows Tk smoke check')
def test_window_create_example_save_and_dry_run(tmp_path):
    import time
    import tkinter as tk
    import libros_app
    root = tk.Tk()
    try:
        app = libros_app.BooksApp(root)
        app.error = lambda exc: (_ for _ in ()).throw(AssertionError(str(exc)))
        root.update()
        assert app.vars['subject'].get() == 'people'
        app.vars['title'].set('Prueba de ventana')
        app.vars['author'].set('Autor')
        # Save projects in a temp directory, but retain the repository CLI path.
        from kdp.project import BookProject
        original = BookProject.save_new
        with patch.object(BookProject, 'save_new', lambda self, parent: original(self, tmp_path)):
            app.save_project()
        assert app.project_paths and app.project_paths[0].exists()
        app.start('check')
        deadline = time.monotonic() + 30
        while app.running and time.monotonic() < deadline:
            root.update()
            time.sleep(.05)
        assert not app.running, 'Offline dry-run did not finish'
        assert 'no API calls made' in app.log.get('1.0', 'end')
    finally:
        if 'app' in locals() and app.process is not None:
            app.process.terminate()
        root.destroy()
