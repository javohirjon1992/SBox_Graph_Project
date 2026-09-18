@echo off
setlocal
cd /d "%~dp0"
echo This optional helper builds a standalone Windows EXE using PyInstaller.
echo Installing/updating PyInstaller...
where py >nul 2>&1
if %errorlevel%==0 (
    py -3 -m pip install --upgrade pyinstaller
    py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name SBoxGraphDesignStudio app.py
) else (
    python -m pip install --upgrade pyinstaller
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name SBoxGraphDesignStudio app.py
)
echo.
echo If successful, the EXE is in the dist folder.
pause
