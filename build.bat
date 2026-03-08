@echo off
echo ============================================
echo   Quest Widget - Build Script
echo ============================================
echo.

echo [1/3] Installing dependencies...
call npm install
cd backend
pip install pyinstaller
cd ..
echo.

echo [2/3] Building backend (PyInstaller)...
cd backend
pyinstaller backend.spec --noconfirm
cd ..
echo.

echo [3/3] Building Electron app...
call npx electron-builder --win
echo.

echo ============================================
echo   Build complete! Check the release/ folder
echo ============================================
pause
