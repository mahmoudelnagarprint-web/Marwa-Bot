@echo off
chcp 65001 >nul
cd /d "%~dp0"
set ANDROID_IMPORT_INTERVAL_SECONDS=5
echo Starting Android Importer Loop (interval=%ANDROID_IMPORT_INTERVAL_SECONDS%s)...
py -3.11 android_importer_loop.py
