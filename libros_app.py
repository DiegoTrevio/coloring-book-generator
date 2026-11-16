"""Local Windows-friendly interface. Image generation runs in a child process."""
from __future__ import annotations

import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from kdp.book_config import BookConfig, STYLES, SUBJECT_RULES
from kdp.project import BookProject, build_command, parse_scene_lines
from kdp.utils import sanitize_folder_name

ROOT = Path(__file__).resolve().parent


def open_local(path: Path):
    if sys.platform == 'win32':
        os.startfile(str(path))
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(path)])


class BooksApp:
    def __init__(self, window):
        self.window = window
        window.title('Taller de libros para colorear')
        window.geometry('1140x820')
        window.minsize(960, 700)
        self.events = queue.Queue()
        self.process = None
        self.running = False
        self.project_paths = None
        self.vars = {key: tk.StringVar(value=value) for key, value in {
            'title': '', 'author': '', 'theme': '', 'subject': 'general',
            'age': '6-8', 'style': 'friendly-cartoon', 'language': 'es',
            'candidates': '3', 'limit': '5', 'selection': ''}.items()}
        self.captions = tk.BooleanVar(value=True)
        self.completion = tk.BooleanVar(value=True)
        self.covers = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='Crea un libro o abre uno existente. No se genera nada automáticamente.')
        self.path_label = tk.StringVar(value='Ningún libro guardado')

        outer = ttk.Frame(window, padding=16); outer.pack(fill='both', expand=True)
        ttk.Label(outer, text='Taller de libros para colorear', font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(outer, text='Personas, animales, vehículos y temas propios · Ilustraciones con Schnell / Replicate').pack(anchor='w', pady=(3, 12))
        tabs = ttk.Notebook(outer); tabs.pack(fill='both', expand=True)
        create = ttk.Frame(tabs, padding=12); tabs.add(create, text='1. Preparar libro')
        generate = ttk.Frame(tabs, padding=12); tabs.add(generate, text='2. Generar y revisar')
        self.tabs = tabs
        top = ttk.Frame(create); top.pack(fill='x')
        ttk.Label(top, text='Empezar con un ejemplo:').pack(side='left')
        example = ttk.Combobox(top, values=['animales', 'personas', 'vehiculos'], state='readonly', width=15)
        example.set('personas'); example.pack(side='left', padx=8)
        ttk.Button(top, text='Cargar ejemplo', command=lambda: self.load_example(example.get())).pack(side='left')
        ttk.Button(top, text='Abrir libro guardado', command=self.open_project).pack(side='right')

        grid = ttk.Frame(create); grid.pack(fill='x', pady=12)
        grid.columnconfigure(1, weight=1); grid.columnconfigure(3, weight=1)
        for row, (left, right) in enumerate([
            (('Título', 'title'), ('Autor', 'author')),
            (('Tema', 'theme'), ('Tipo de contenido', 'subject')),
            (('Edad', 'age'), ('Estilo', 'style')),
            (('Idioma editorial', 'language'), ('Opciones por dibujo', 'candidates'))]):
            for offset, (label, key) in enumerate((left, right)):
                column = offset*2
                ttk.Label(grid, text=label).grid(row=row, column=column, sticky='w', padx=(0, 8), pady=4)
                choices = {'subject': list(SUBJECT_RULES), 'age': ['3-5','6-8','9-12','adult'],
                           'style': list(STYLES), 'language': ['es','en'], 'candidates': ['1','2','3','4','5','6']}
                widget = ttk.Combobox(grid, textvariable=self.vars[key], values=choices[key], state='readonly') if key in choices else ttk.Entry(grid, textvariable=self.vars[key])
                widget.grid(row=row, column=column+1, sticky='ew', padx=(0, 16), pady=4)
        ttk.Label(create, text='Dirección artística: proporciones, trazos, ambiente y reglas comunes del libro.').pack(anchor='w')
        self.direction = tk.Text(create, height=3, wrap='word', font=('Segoe UI', 10))
        self.direction.pack(fill='x', pady=(4, 8))
        ttk.Label(create, text='Una escena por línea: Nombre | personaje o sujeto, acción y entorno').pack(anchor='w')
        self.scenes = tk.Text(create, height=10, wrap='word', font=('Segoe UI', 10))
        self.scenes.pack(fill='both', expand=True, pady=4)
        settings = ttk.Frame(create); settings.pack(fill='x', pady=6)
        ttk.Checkbutton(settings, text='Nombres bajo cada dibujo', variable=self.captions).pack(side='left')
        ttk.Checkbutton(settings, text='Reconocimiento final', variable=self.completion).pack(side='left', padx=16)
        ttk.Button(settings, text='Guardar como libro nuevo', command=self.save_project).pack(side='right')
        ttk.Label(create, text='Los cambios del formulario se guardan como un libro nuevo; abrir un libro no modifica sus archivos.').pack(anchor='w')

        ttk.Label(generate, textvariable=self.path_label, wraplength=1000).pack(anchor='w', pady=(0, 10))
        actions = ttk.Frame(generate); actions.pack(fill='x')
        ttk.Label(actions, text='Dibujos:').pack(side='left')
        ttk.Spinbox(actions, from_=0, to=500, textvariable=self.vars['limit'], width=5).pack(side='left', padx=8)
        ttk.Label(actions, text='0 = libro completo').pack(side='left')
        ttk.Checkbutton(actions, text='Generar también cubiertas', variable=self.covers).pack(side='left', padx=18)
        commands = ttk.Frame(generate); commands.pack(fill='x', pady=12)
        self.run_buttons = []
        for title, mode in [('Comprobar sin gastar', 'check'), ('Generar imágenes (consume API)', 'generate'), ('Reconstruir PDF sin API', 'review')]:
            button = ttk.Button(commands, text=title, command=lambda m=mode: self.start(m))
            button.pack(side='left', padx=(0, 8)); self.run_buttons.append(button)
        ttk.Button(commands, text='Configurar token', command=self.configure_token).pack(side='right')
        ttk.Label(generate, text='Revisión visual: abre la galería, revisa anatomía y estilo y anota tus opciones.').pack(anchor='w')
        review = ttk.Frame(generate); review.pack(fill='x', pady=8)
        ttk.Button(review, text='Abrir galería de opciones', command=lambda: self.open_output('review.html')).pack(side='left')
        ttk.Label(review, text='Elegir:').pack(side='left', padx=(18, 6))
        ttk.Entry(review, textvariable=self.vars['selection'], width=20).pack(side='left')
        ttk.Label(review, text='Ejemplo: 1:2,4:3').pack(side='left', padx=8)
        ttk.Button(review, text='Abrir carpeta del libro', command=lambda: self.open_output()).pack(side='right')
        ttk.Label(generate, text='La comprobación y selección son gratis. Generar crea hasta dibujos × opciones, más cubiertas y reintentos.\nSchnell no garantiza anatomía correcta ni personajes idénticos entre escenas.', wraplength=1000).pack(anchor='w', pady=8)
        ttk.Button(generate, text='Preparar paquete de impresión (sin API)', command=self.export_print).pack(anchor='w', pady=(0, 8))
        self.log = tk.Text(generate, height=17, wrap='word', state='disabled', font=('Consolas', 10))
        self.log.pack(fill='both', expand=True)
        ttk.Label(outer, textvariable=self.status, wraplength=1080).pack(anchor='w', pady=(10, 0))
        window.protocol('WM_DELETE_WINDOW', self.close)
        window.after(120, self.poll)
        self.load_example('personas')

    def error(self, exc):
        messagebox.showerror('Revisar', str(exc), parent=self.window)

    def fill(self, project):
        for key, value in [('title', project.title), ('author', project.author),
                           ('theme', project.config.theme), ('subject', project.config.subject),
                           ('age', project.config.age), ('style', project.config.style),
                           ('language', project.config.language), ('candidates', project.config.candidates)]:
            self.vars[key].set(str(value))
        self.direction.delete('1.0', 'end'); self.direction.insert('1.0', project.config.art_direction)
        self.scenes.delete('1.0', 'end')
        self.scenes.insert('1.0', '\n'.join(label+' | '+scene for label, scene in project.scenes))
        self.captions.set(project.config.captions); self.completion.set(project.config.completion_page)

    def load_example(self, name):
        if self.running:
            return
        try:
            self.fill(BookProject.read(ROOT/'examples'/f'{name}-editorial.md', ROOT/'examples'/f'{name}.json'))
            self.project_paths = None
            self.path_label.set('Ejemplo cargado. Personaliza el título y el autor y guarda como libro nuevo.')
            self.tabs.select(0)
        except Exception as exc:
            self.error(exc)

    def save_project(self):
        if self.running:
            return
        try:
            config = BookConfig(theme=self.vars['theme'].get().strip(), subject=self.vars['subject'].get(),
                age=self.vars['age'].get(), style=self.vars['style'].get(), language=self.vars['language'].get(),
                candidates=int(self.vars['candidates'].get()), fit_art=True, captions=self.captions.get(),
                completion_page=self.completion.get(), art_direction=self.direction.get('1.0', 'end').strip())
            project = BookProject(self.vars['title'].get().strip(), self.vars['author'].get().strip(),
                                  parse_scene_lines(self.scenes.get('1.0','end')), config)
            self.project_paths = project.save_new(ROOT/'books')
            self.path_label.set('Libro: '+str(self.project_paths[0]))
            self.status.set('Libro guardado. Empieza con “Comprobar sin gastar”.')
            self.tabs.select(1)
        except FileExistsError:
            self.error('Ya existe un libro con ese título. Abre el libro guardado o cambia el título para crear una copia.')
        except Exception as exc:
            self.error(exc)

    def open_project(self):
        if self.running:
            return
        md = filedialog.askopenfilename(title='Abrir book.md', filetypes=[('Libro Markdown','*.md')])
        if not md:
            return
        config = Path(md).with_suffix('.json')
        if not config.exists():
            path = filedialog.askopenfilename(title='Elegir el perfil JSON del libro', filetypes=[('Perfil','*.json')])
            if not path:
                return
            config = Path(path)
        try:
            self.fill(BookProject.read(Path(md), config))
            self.project_paths = (Path(md).resolve(), config.resolve())
            self.path_label.set('Libro: '+str(self.project_paths[0]))
            self.status.set('Libro abierto. La generación utiliza los archivos guardados, no los cambios del formulario.')
            self.tabs.select(1)
        except Exception as exc:
            self.error(exc)

    def configure_token(self):
        path = ROOT/'.env'
        if not path.exists():
            path.write_text('REPLICATE_API_TOKEN=\n', encoding='utf-8')
        if sys.platform == 'win32':
            subprocess.Popen(['notepad.exe', str(path)])
        else:
            open_local(path)
        self.status.set('Guarda REPLICATE_API_TOKEN=tu_token en .env y ciérralo. No se muestra ni se envía el token en la ventana.')

    def output_dir(self):
        if not self.project_paths:
            raise ValueError('Primero guarda o abre un libro.')
        project = BookProject.read(*self.project_paths)
        return self.project_paths[0].parent/'output'/sanitize_folder_name(project.title)

    def open_output(self, filename=''):
        try:
            path = self.output_dir()/filename
            if not path.exists():
                raise ValueError('Todavía no existe. Primero ejecuta la generación o reconstrucción del libro.')
            open_local(path)
        except Exception as exc:
            self.error(exc)

    def start(self, mode):
        if self.running:
            return
        try:
            if not self.project_paths:
                raise ValueError('Primero guarda o abre un libro.')
            saved = BookProject.read(*self.project_paths)
            expected = {'title': saved.title, 'author': saved.author,
                        'theme': saved.config.theme, 'subject': saved.config.subject,
                        'age': saved.config.age, 'style': saved.config.style,
                        'language': saved.config.language, 'candidates': str(saved.config.candidates)}
            changed = any(self.vars[key].get().strip() != value for key, value in expected.items())
            changed = changed or parse_scene_lines(self.scenes.get('1.0', 'end')) != saved.scenes
            changed = changed or self.direction.get('1.0', 'end').strip() != saved.config.art_direction
            changed = changed or self.captions.get() != saved.config.captions or self.completion.get() != saved.config.completion_page
            if changed:
                raise ValueError('Hay cambios sin guardar. Guarda como libro nuevo con otro título antes de generar, o vuelve a abrir el libro guardado.')
            command = build_command(ROOT, *self.project_paths, mode=mode,
                limit=int(self.vars['limit'].get()), skip_cover=not self.covers.get(),
                selections=self.vars['selection'].get())
            env = os.environ.copy(); env.update(PYTHONIOENCODING='utf-8', PYTHONUTF8='1')
            self.process = subprocess.Popen(command, cwd=ROOT, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                text=True, encoding='utf-8', errors='replace', bufsize=1)
            self.running = True
            for button in self.run_buttons: button.configure(state='disabled')
            self.status.set('Ejecutando… Puedes ver el avance aquí. Las páginas terminadas se guardan para reanudar.')
            self.append_log('\n--- Nueva ejecución ---\n')
            threading.Thread(target=self.read_process, args=(self.process,), daemon=True).start()
        except Exception as exc:
            self.error(exc)

    def read_process(self, process):
        for line in process.stdout:
            self.events.put(('line', line))
        self.events.put(('done', process.wait()))

    def append_log(self, text):
        self.log.configure(state='normal'); self.log.insert('end', text)
        self.log.see('end'); self.log.configure(state='disabled')

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == 'line':
                    self.append_log(value)
                else:
                    self.running = False; self.process = None
                    for button in self.run_buttons: button.configure(state='normal')
                    self.status.set('Proceso completado. Revisa las opciones y el PDF.' if value == 0 else
                                    'El proceso requiere atención. Revisa el mensaje final; si hay páginas señaladas, abre la galería y elige opciones.')
        except queue.Empty:
            pass
        self.window.after(120, self.poll)

    def export_print(self):
        if self.running:
            return
        try:
            if not self.project_paths:
                raise ValueError('Abre un libro guardado primero.')
            values = []
            for label in ('Ancho del lomo', 'Ancho completo de cubierta', 'Alto completo de cubierta'):
                value = simpledialog.askfloat('Medidas de la imprenta',
                    label + ' en pulgadas, según la calculadora oficial para tu número final de páginas:',
                    parent=self.window, minvalue=.001)
                if value is None:
                    return
                values.append(value)
            parent = filedialog.askdirectory(title='Elige dónde crear la carpeta paquete-impresion')
            if not parent:
                return
            from kdp.print_package import export_package
            result = export_package(*self.project_paths, spine=values[0], cover_width=values[1],
                cover_height=values[2], destination=Path(parent)/'paquete-impresion')
            self.status.set('Paquete preparado. Revisa LEEME.txt y report.json antes de publicar.')
            open_local(result)
        except Exception as exc:
            self.error(exc)

    def close(self):
        if self.running:
            messagebox.showinfo('Proceso en curso', 'Espera a que termine antes de cerrar para conservar el progreso.', parent=self.window)
            return
        self.window.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    BooksApp(root)
    root.mainloop()
