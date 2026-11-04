@echo off
REM =========================================================
REM  OFICINA EFICIENCIA - BUILD DEL EJECUTABLE DE WINDOWS
REM  Nuitka (Python compilado a C) + Inno Setup
REM  Requisitos: Python 3.11 de 64 bits e Inno Setup 6.
REM =========================================================
setlocal
set VENV=.\venv\Scripts
set /p APP_VERSION=<VERSION

echo [1/4] Instalando dependencias fijadas (runtime + build)...
%VENV%\python.exe -m pip install -r requirements.txt -r requirements-build.txt
if errorlevel 1 goto :error

echo [2/4] Avisos de terceros del runtime (THIRD_PARTY_NOTICES.txt)...
%VENV%\python.exe -m piplicenses --from=mixed --format=json --with-license-file --with-notice-file --no-license-path > build_paquetes.json
if errorlevel 1 goto :error
%VENV%\python.exe scripts\generar_avisos_terceros.py --paquetes build_paquetes.json --salida THIRD_PARTY_NOTICES.txt
if errorlevel 1 goto :error

echo [3/4] Compilando con Nuitka (la primera vez descarga su compilador de C)...
%VENV%\python.exe scripts\compilar_ejecutable.py
if errorlevel 1 goto :error

echo [4/4] Generando el instalador %APP_VERSION% con Inno Setup...
"c:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=%APP_VERSION% setup_oficina.iss
if errorlevel 1 goto :error

echo Listo. Ejecutable: build\nuitka\main_ui.dist\OficinaEficiencia_VMS.exe
echo Instalador: installer_output\setup_oficina_eficiencia_v%APP_VERSION%.exe
exit /b 0

:error
echo ERROR FATAL: el build se detuvo en el paso anterior.
exit /b 1
