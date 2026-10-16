@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo ============================================
echo   النوتبوك الذكية - النجار برنت
echo ============================================
".venv\Scripts\python.exe" -m notebook.app --port 8100
pause