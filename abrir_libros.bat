@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Preparando Python para el generador de libros...
    py -m venv .venv
    if errorlevel 1 goto :error
)
.venv\Scripts\python.exe -c "import PIL, numpy, img2pdf, dotenv, openai, replicate" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias. Esto no genera imagenes ni consume API.
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 goto :error
)
.venv\Scripts\python.exe libros_app.py
if errorlevel 1 goto :error
exit /b 0
:error
echo.
echo No se pudo iniciar. Revisa el mensaje anterior.
echo Necesitas Python 3.10 o posterior con tkinter.
pause
exit /b 1
