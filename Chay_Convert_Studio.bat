@echo off
title Xiaomi Convert ROM Studio (X-Convert)
cd /d "%~dp0"
if exist "dist\XiaomiConvertStudio.exe" (
    start "" "dist\XiaomiConvertStudio.exe"
    exit /b
)
if exist "XiaomiConvertStudio.exe" (
    start "" "XiaomiConvertStudio.exe"
    exit /b
)
python convert_gui.py
