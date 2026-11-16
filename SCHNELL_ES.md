# Crear libros con Schnell en Windows

El programa corre en tu computadora y genera imágenes mediante Replicate.
No necesitas GPU ni una clave de OpenAI para este proveedor.

## Instalación (PowerShell, Python 3.10 o posterior)

```powershell
git clone https://github.com/DiegoTrevio/coloring-book-generator.git
cd coloring-book-generator
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Crea un token en https://replicate.com/account/api-tokens y configura la
facturación en Replicate. Guarda el token solo en el `.env` local:

```dotenv
REPLICATE_API_TOKEN=tu_token_real
```

`.env` está excluido de Git. No pegues tu token en chats, commits ni capturas.
Si ya tienes un `.env`, edítalo sin reemplazarlo.

## Primero: comprobar el libro sin gastar

```powershell
.\.venv\Scripts\python.exe kdp_book_builder.py examples/animales-30.md --provider replicate --out output --dry-run
```

## Probar cinco dibujos (usa API y genera dos cubiertas)

```powershell
.\.venv\Scripts\python.exe kdp_book_builder.py examples/animales-30.md --provider replicate --out output --limit 5 --workers 1 --yes
```

Para probar solo dibujos, añade `--skip-cover`.

## Generar los 30 dibujos

```powershell
.\.venv\Scripts\python.exe kdp_book_builder.py examples/animales-30.md --provider replicate --out output --workers 1 --yes
```

El registro permite reanudar y omitir páginas correctas. Para reemplazar páginas
específicas, añade `--regen 2,7`. Si cambias el estilo o el tema, usa otra carpeta
de salida o regenera las páginas; reanudar conserva las que ya estaban correctas.

## Qué esperar

- Schnell usa 4 pasos, PNG y proporción vertical 3:4 por defecto. Puedes elegir
  otra proporción con `--aspect-ratio`; no usa `--size` ni `--quality` de OpenAI.
- El estilo maestro del Markdown se envía con cada dibujo y cada corrección.
- Schnell no edita imágenes de referencia. Las muestras coloreadas de dibujos
  existentes se omiten automáticamente; sí genera portadas originales a color.
- Las cubiertas son imágenes separadas. Todavía debes añadir títulos y textos,
  y preparar/verificar la cubierta completa con las medidas de la imprenta.
- 30 dibujos producen **62 páginas interiores**: página de nombre, reverso en
  blanco y 30 dibujos con sus reversos en blanco.
- La salida está en `output/Animales para colorear/`: imágenes originales,
  páginas procesadas, PDF interior, informe de QA y datos editoriales.
- El procesamiento a 2550×3300 píxeles amplía la imagen: no añade detalle nativo.
- El control de QA es heurístico; revisa anatomía, líneas y composición a mano.
  Las páginas `needs_review` se incluyen en el PDF y requieren tu revisión.
- El contador de llamadas del informe original cuenta solicitudes lógicas de
  páginas, no una factura completa: no incluye todas las cubiertas ni reintentos
  internos. Consulta el consumo real en Replicate.
- Cada corrección de QA puede generar otra imagen facturable. Hay hasta 4
  generaciones por página, además de posibles reintentos por errores de red.
- La integración se verifica con respuestas simuladas; la calidad y el acceso
  real a Replicate requieren una primera prueba con tu token.

## Pruebas de desarrollo (sin API)

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
```
