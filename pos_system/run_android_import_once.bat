@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Running Android importer (once)...
py -3.11 android_importer.py --once %*
pause
