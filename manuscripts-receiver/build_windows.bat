@echo off
REM Build manuscripts-receiver for Windows.
REM Run this on a Windows machine with Python 3 installed.
REM
REM Usage:  build_windows.bat [version]
REM Output: dist\manuscripts-receiver.exe

setlocal
set VERSION=%~1
if "%VERSION%"=="" set VERSION=1.0

echo Building manuscripts-receiver v%VERSION% for Windows...

pip install --quiet pyinstaller aiohttp zeroconf pystray Pillow pywin32

python make_icons.py

pyinstaller --onefile --noconsole ^
    --icon icon.ico ^
    --name manuscripts-receiver ^
    --collect-all zeroconf ^
    --collect-all aiohttp ^
    --collect-all pystray ^
    --hidden-import pystray._win32 ^
    --hidden-import tkinter ^
    --add-data "JetBrainsMono-Regular.ttf;." ^
    --add-data "JetBrainsMono-Light.ttf;." ^
    receiver.py

echo.
echo Done: dist\manuscripts-receiver.exe
echo Distribute this .exe directly — no Python installation needed.
echo Double-click it to launch the system tray app.
