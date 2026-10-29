@echo off
chcp 65001 > nul
echo ====================================
echo  PDF Tools - Install / Update
echo ====================================
echo.
if not exist "venv\Scripts\python.exe" (
    echo [1/2] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 ( echo ERROR: Cannot create venv & pause & exit /b 1 )
) else (
    echo [1/2] venv already exists, skipping...
)
echo [2/2] Installing / updating packages...
venv\Scripts\pip install -r requirements.txt
if errorlevel 1 ( echo ERROR: Package install failed & pause & exit /b 1 )
echo.
echo ====================================
echo  Done! Run run.bat to start.
echo ====================================
pause
