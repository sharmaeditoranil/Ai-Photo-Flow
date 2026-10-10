@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo     Ai PhotoFlow - Windows 10/11 Professional Installer
echo     Automated Build Engine for Windows x64
echo ========================================================
echo.

:: Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.9+ from https://www.python.org/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Check Node.js installation
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH!
    echo Please install Node.js LTS from https://nodejs.org/
    pause
    exit /b 1
)

echo [Step 1/5] Setting up Python virtual environment...
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat

echo [Step 2/5] Installing Python AI backend dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [Step 3/5] Compiling Python AI Backend (photoflow-backend.exe)...
pyinstaller --noconfirm --onedir --name photoflow-backend --distpath dist-backend --clean --add-data "backend\templates;backend\templates" --add-data "backend\data;backend\data" --add-data "backend\models;backend\models" backend_entry.py

if not exist "dist-backend\photoflow-backend\photoflow-backend.exe" (
    echo [ERROR] Failed to compile dist-backend\photoflow-backend\photoflow-backend.exe!
    pause
    exit /b 1
)
echo [OK] Python AI Backend compiled successfully.

echo [Step 4/5] Building React Frontend UI...
cd frontend
call npm install
call npm run build
cd ..

echo [Step 5/5] Packaging Windows Electron NSIS Installer...
call npm install
call npx electron-builder --win nsis --x64

echo.
echo ========================================================
echo  [SUCCESS] Windows Build Completed Successfully!
echo  Installer located at: dist-dmg\Ai PhotoFlow Setup 1.0.0.exe
echo ========================================================
echo.
pause
