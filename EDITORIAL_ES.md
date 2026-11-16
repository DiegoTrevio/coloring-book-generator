# Libros para colorear de cualquier temática

Esta versión añade perfiles editoriales, candidatos visuales y maquetación.
La generación real usa tu API de Replicate; las pruebas de desarrollo no.

## Actualizar en Windows

Descarga el ZIP actualizado, extráelo en otra carpeta y copia **solo tu `.env`**
a esa carpeta. No publiques el token. Abre `cmd` desde la barra de dirección de
la carpeta nueva y ejecuta:

```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Usa una carpeta nueva de salida para estos perfiles; no mezcles las ilustraciones
anteriores con el nuevo estilo.

## Tres ejemplos listos

| Tipo | Ideas de páginas | Configuración |
|---|---|---|
| Animales (30 escenas) | examples/animales-editorial.md | examples/animales.json |
| Personas y profesiones (10 escenas) | examples/personas-editorial.md | examples/personas.json |
| Vehículos (10 escenas) | examples/vehiculos-editorial.md | examples/vehiculos.json |

El tema no está limitado a estos ejemplos. Puedes crear dinosaurios, fantasía,
personas, naturaleza, arquitectura o libros para adultos escribiendo tus ideas.

## Prueba inicial: cinco páginas y tres opciones por página

Primero comprueba la configuración sin usar API:

```bat
.venv\Scripts\python.exe kdp_book_builder.py examples/personas-editorial.md --config examples/personas.json --provider replicate --out output-v2 --limit 5 --skip-cover --dry-run
```

Después genera las opciones (consume API):

```bat
.venv\Scripts\python.exe kdp_book_builder.py examples/personas-editorial.md --config examples/personas.json --provider replicate --out output-v2 --limit 5 --skip-cover --workers 1 --yes
```

El perfil pide tres candidatos por dibujo: cinco páginas son 15 solicitudes
iniciales. El costo real puede incluir reintentos de red. El contador de páginas
no es una factura; consulta Replicate para el consumo total.

## Revisar y elegir

Abre `output-v2/Personas y profesiones/review.html` con tu navegador. Funciona
localmente, sin servidor. Cada página muestra sus alternativas y los avisos de QA.
La alternativa inicial se elige por sus métricas técnicas; **no se evalúan
anatomía, manos, atractivo ni continuidad de personajes automáticamente**.

Para seleccionar, por ejemplo, la opción 2 de la página 1 y la opción 3 de la
página 4, y reconstruir sin consumir API:

```bat
.venv\Scripts\python.exe kdp_book_builder.py examples/personas-editorial.md --config examples/personas.json --provider replicate --out output-v2 --limit 5 --only-pdf --select 1:2,4:3
```

Solo selecciona candidatos que hayas revisado: esta acción marca la página como
revisada manualmente y permite incluirla aunque el filtro técnico la señalara.
Las páginas señaladas bloquean el PDF por defecto. Para obtener un borrador con
ellas usa `--allow-review`. Las páginas ausentes nunca se sustituyen por blancos.
Si todas las opciones están mal, regenera esa página con `--regen 4`.

## Crear otro libro

1. Copia un par `.md` + `.json` de `examples` con otro nombre.
2. En el Markdown cambia título, autor, descripción, ideas y las instrucciones
   de portada. Escribe una escena concreta por página: protagonista, acción,
   entorno y pocos elementos grandes. No basta cambiar el título o el JSON.
3. En JSON cambia `theme`, `subject`, `age`, `style` y `art_direction`.
4. En `labels` escribe el nombre de cada dibujo por número de página. Si no
   quieres nombres, usa `captions: false`.
5. Usa una carpeta `--out` nueva, haz `--dry-run` y prueba cinco páginas.

Opciones de perfil:

- `subject`: `people`, `animals`, `vehicles`, `fantasy`, `general`.
- `age`: `3-5`, `6-8`, `9-12`, `adult`.
- `style`: `friendly-cartoon`, `educational`, `realistic-simple`, `detailed`.
- `language`: `es` o `en` para las páginas editoriales.
- `candidates`: 1 a 6. Se puede sobreescribir con `--candidates 3`.
- `fit_art`: recorta espacio blanco y ajusta proporcionalmente con márgenes.
- `captions`: añade los nombres de `labels` mediante tipografía local.
- `completion_page`: añade reconocimiento final con reverso en blanco.
- `art_direction`: reglas particulares del libro, enviadas en cada solicitud.

Las opciones de edad y estilo deben ser coherentes: `detailed` está pensado para
mayores; para pequeños usa formas sencillas y poco detalle. La selección de un
perfil no puede garantizar que el modelo siga todas las instrucciones.

Si cambias las instrucciones o el modelo, la reanudación detecta diferencias y
pide otra carpeta o `--regen`. Para cambiar solo tamaño del dibujo, etiquetas o
páginas editoriales, usa el mismo perfil con `--only-pdf`: no regenera imágenes.

## Generar el libro completo

Quita `--limit 5` y `--skip-cover` del comando de generación. Las páginas ya
correctas se conservan si las instrucciones no cambiaron. En los perfiles nuevos,
las cubiertas se generan como ilustraciones sin letras y el título y descripción
se colocan por código. `front_art.png` y `back_art.png` conservan los originales.

Son imágenes separadas de portada y contraportada, **no una cubierta completa
validada por imprenta**. El lomo, sangrado y zona de código de barras se preparan
con las medidas finales de impresión.

Con reconocimiento final: 30 dibujos generan 64 páginas interiores; 10 dibujos,
24 páginas; cinco dibujos, 14 páginas. Incluyen página de nombre, reconocimiento
y todos sus reversos en blanco. Sin reconocimiento, resta dos páginas.

## Límites de calidad

Schnell no admite imágenes de referencia ni edición en esta integración. Las
reglas compartidas ayudan al estilo, pero no garantizan que el mismo personaje
sea idéntico en diferentes escenas. Para historias con personajes recurrentes
hay que integrar y probar otro modelo que sí use referencias.

La ampliación a 300 DPI no crea detalle original. Revisa los contornos al tamaño
real y realiza una impresión de muestra antes de publicar. Revisa también los
datos editoriales del Markdown: no publiques descripciones o categorías de ejemplo.
