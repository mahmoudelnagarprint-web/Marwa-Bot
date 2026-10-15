@echo off
chcp 65001 >nul
echo ═══════════════════════════════════════════
echo  Elnagar POS — Mirror Google Sheet Now
echo ═══════════════════════════════════════════
cd /d "%~dp0"
.venv\Scripts\python.exe sync_pos_to_sheet.py --mirror-now
echo.
pause
