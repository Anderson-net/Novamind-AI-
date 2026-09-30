@echo off
setlocal
cd /d "%~dp0"

echo ===============================================
echo       NOVAMIND v5 - INICIO AUTOMATICO
echo ===============================================

where py >nul 2>nul
if %errorlevel% neq 0 (
  where python >nul 2>nul
  if %errorlevel% neq 0 (
    echo Python no esta instalado. Intentando instalarlo con winget...
    where winget >nul 2>nul
    if %errorlevel% neq 0 (
      echo No se encontro winget. Instala Python 3.11+ y vuelve a abrir este archivo.
      pause
      exit /b 1
    )
    winget install --id Python.Python.3.13 -e --source winget --accept-source-agreements --accept-package-agreements
  )
)

set PYTHON=py
where py >nul 2>nul
if %errorlevel% neq 0 set PYTHON=python

echo.
echo Instalando/actualizando componentes de NovaMind...
%PYTHON% -m pip install --upgrade pip
%PYTHON% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
  echo.
  echo No se pudieron instalar las dependencias.
  pause
  exit /b 1
)

echo.
echo Abriendo NovaMind...
start "" http://127.0.0.1:8000
%PYTHON% -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
