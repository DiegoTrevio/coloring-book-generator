# Abrir el taller de libros en Windows

## Inicio

1. Descarga la versión actualizada y extrae el ZIP en una carpeta nueva.
2. Copia tu `.env` anterior a la carpeta nueva para conservar el token de Replicate.
3. Haz doble clic en **abrir_libros.bat**.

El primer inicio prepara el entorno e instala las dependencias si faltan.
Esto requiere internet para descargar paquetes, pero no genera imágenes ni
consume API. Necesitas Python 3.10 o posterior instalado con tkinter (incluido
habitualmente en la instalación oficial de Windows).

## Preparar cualquier libro

En **Preparar libro**, carga un ejemplo de personas, animales o vehículos y
cambia título, autor, tema, edad y estilo. También puedes reemplazar todas las
escenas para crear dinosaurios, naturaleza, fantasía, arquitectura o un libro
para adultos.

Cada línea de escenas tiene este formato:

```text
Bombera | a firefighter standing beside a fire truck and a coiled hose
Astronauta | a child astronaut waving beside a rocket and one large planet
```

El texto anterior a `|` se coloca como nombre de la ilustración. El resto es la
descripción enviada al generador. Usa escenas concretas con acción, entorno y
pocos elementos grandes. Las ideas se escriben manualmente: esta ventana no
utiliza un modelo de texto para inventar un libro automáticamente.

Pulsa **Guardar como libro nuevo**. Los archivos se guardan en
`books/libro-Título/book.md` y `book.json`; las salidas quedan dentro de ese mismo
proyecto. No se sobreescriben libros existentes. Para crear una versión distinta,
añade, por ejemplo, `versión 2` al título. Para continuar un proyecto, usa
**Abrir libro guardado** y elige su `book.md`.

Los cambios del formulario deben guardarse antes de generar. Al abrir un libro
existente, sus archivos no se modifican. Sigue disponible la edición directa de
Markdown y JSON para ajustes avanzados.

## Comprobar y generar

En **Generar y revisar**:

1. Deja **Dibujos: 5** para el piloto. `0` significa todas las escenas del libro.
2. Usa **Comprobar sin gastar**. Valida el proyecto, sin generar imágenes ni
   comprobar las credenciales de Replicate.
3. Si falta el token, pulsa **Configurar token**, guarda
   `REPLICATE_API_TOKEN=tu_token` en `.env` y cierra el editor. Obtén el token en
   https://replicate.com/account/api-tokens y configura la facturación allí.
4. Pulsa **Generar imágenes (consume API)**. Tres opciones por dibujo y cinco
   dibujos implican 15 solicitudes iniciales, más posibles reintentos.
5. El avance aparece en la ventana. Espera a que finalice antes de cerrarla.

Las cubiertas están desactivadas al inicio para probar primero los dibujos.
Activa **Generar también cubiertas** cuando quieras producirlas.

## Revisar sin gastar más

Pulsa **Abrir galería de opciones**. Revisa manos, anatomía, proporciones,
contornos, composición y consistencia. La selección automática se basa en
métricas técnicas: no puede juzgar la calidad artística.

Escribe en **Elegir**, por ejemplo, `1:2,4:3`: opción 2 de la página 1 y opción 3
de la página 4. Pulsa **Reconstruir PDF sin API** para aplicar la selección.
Esta acción marca esas páginas como revisadas manualmente; elige solo dibujos
que hayas inspeccionado. Deja el campo vacío para reconstruir con las selecciones
ya guardadas.

Si el programa señala una página, bloqueará el PDF hasta que elijas una opción.
Si ninguna opción sirve, puedes regenerar páginas concretas desde la terminal
con `--regen`, como explica `EDITORIAL_ES.md`.

El botón **Abrir carpeta del libro** muestra las imágenes, la galería y la
carpeta `interior` con el PDF. Los dibujos mantienen un reverso en blanco.

## Continuar el libro completo

Abre el libro guardado, cambia **Dibujos** a `0` y vuelve a generar. Las páginas
correctas con las mismas instrucciones se omiten; las pendientes se generan.
El programa guarda el registro al terminar cada página. Una interrupción durante
una imagen todavía puede requerir repetir esa solicitud y generar otro cargo.

Si falta saldo o aparece un error de API, la ventana lo mostrará en el registro.
No pegues tokens en capturas ni compartas tu `.env`.

## Estado de validación

Se verificaron creación de proyectos, archivos de configuración, comandos de
comprobación sin API, selección y PDF mediante pruebas automatizadas. No se ha
probado esta ventana en una computadora Windows real ni se han generado nuevas
ilustraciones pagadas durante esta actualización.

Schnell no garantiza personajes recurrentes idénticos. Las historias con referencias visuales siguen requiriendo trabajo adicional.
Para unir las cubiertas separadas en un paquete de impresión, consulta IMPRESION_ES.md.

## Paquete para impresión

Usa el botón Preparar paquete de impresión después de revisar y seleccionar todas las páginas. Consulta IMPRESION_ES.md. La exportación reúne los archivos sin API y no sustituye la revisión en la imprenta.

## Comprobaciones automáticas

GitHub Actions ejecuta las pruebas en Linux y Windows. En Windows también se prueba crear la ventana, guardar un libro y ejecutar una comprobación sin API. Consulta el resultado de los checks del pull request; no equivale a validar nuevas ilustraciones pagadas ni a probar todos los equipos Windows.
