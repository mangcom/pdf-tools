@echo off
chcp 65001 > nul
echo ====================================
echo  PDF to Image Converter
echo  http://localhost:5000
echo ====================================
echo.
if not exist "venv\Scripts\python.exe" (
    echo ERROR: venv not found. Please run install.bat first!
    pause
    exit /b 1
)
set "POPPLER_PATH=%~dp0poppler\Library\bin"
set "PATH=%POPPLER_PATH%;%PATH%"
echo Poppler: %POPPLER_PATH%
echo.
start http://localhost:5000
venv\Scripts\python app.py
pause
