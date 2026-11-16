# Preparar el paquete para impresión

La ventana tiene un botón **Preparar paquete de impresión (sin API)**.
Esta función es para libros de tapa blanda con lectura de izquierda a derecha,
interior de 8.5 × 11 pulgadas sin sangrado. No adapta otros tamaños ni tapa dura.

## Antes de exportar

1. Genera todo el libro con **Dibujos: 0**, incluidas las cubiertas.
2. Abre la galería y revisa todas las ilustraciones. Escribe las selecciones de
   todas las páginas en el campo Elegir (por ejemplo, `1:1,2:3,3:2`) y reconstruye
   el PDF con Dibujos: 0. La selección marca cada página como revisada por ti.
3. Revisa el PDF final, incluidos nombres y reconocimiento. Personaliza los
   datos editoriales; los textos de ejemplo no deben publicarse sin revisar.
4. Consulta el número real de páginas del PDF. Los reversos en blanco cuentan.
5. Obtén el ancho del lomo, el ancho completo y el alto completo en pulgadas en
   https://kdp.amazon.com/cover-templates usando ese número final de páginas,
   tamaño 8.5 × 11, papel y tipo de impresión correctos.

Pulsa el botón e introduce las tres medidas. Selecciona una carpeta contenedora;
el programa creará `paquete-impresion`. Si ya existe, elige otra carpeta para
conservar el paquete anterior.

## Archivos entregados

- `interior.pdf`: el interior completo, con tamaño de página comprobado.
- `cover.pdf`: una página con contraportada a la izquierda, lomo sin texto y
  portada a la derecha. Incluye 0.125 pulgadas de sangrado exterior.
- `cover.png`: la misma composición, con lienzo calculado a 300 DPI.
- `report.json`: medidas, número de páginas, resolución de origen de las cubiertas,
  advertencias y hashes SHA-256 de los archivos principales.
- `LEEME.txt`: comprobaciones visuales pendientes.

El fondo de cada cubierta se prolonga con el color de su esquina superior
izquierda. Las ilustraciones se ajustan proporcionalmente dentro de cada panel;
el lomo es blanco y no lleva texto. Se reserva un rectángulo blanco en la zona
inferior derecha de la contraportada para el código de barras. Comprueba que esa
reserva no oculte contenido importante y que el fondo resulte adecuado.

## Qué comprueba y qué falta

Se bloquea la exportación si hay ilustraciones sin revisar, archivos ausentes,
un PDF parcial, tamaños inconsistentes o menos de 24 páginas interiores. Las
medidas de cubierta deben corresponder al tamaño fijo y al lomo introducido.
El programa no comprueba que el lomo introducido corresponda al papel: por eso
debes copiarlo de la calculadora para tu edición concreta.

La exportación **no garantiza aceptación por KDP ni calidad artística**. Revisa
la plantilla oficial, el Print Previewer y una copia de prueba. No detecta texto
mal escrito, anatomía incorrecta, derechos de terceros ni todos los problemas de
impresión. Un lienzo a 300 DPI no añade detalle a las imágenes de origen.
El límite de páginas y otras condiciones de impresión dependen de la edición.

Fuentes oficiales:
- https://kdp.amazon.com/en_US/help/topic/G201857950
- https://kdp.amazon.com/en_US/help/topic/G201953020
- https://kdp.amazon.com/cover-templates

## Alternativa por terminal

```bat
.venv\Scripts\python.exe exportar_impresion.py "books\libro-Titulo\book.md" --config "books\libro-Titulo\book.json" --spine LOMO --width ANCHO_COMPLETO --height ALTO_COMPLETO --out "entrega\paquete-impresion"
```

Sustituye las tres medidas por números en pulgadas con punto decimal. La función
no hace solicitudes a Replicate ni publica archivos en Amazon.
