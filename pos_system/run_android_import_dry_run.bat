@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Running Android importer (dry-run)...
py -3.11 android_importer.py --dry-run %*
pause
