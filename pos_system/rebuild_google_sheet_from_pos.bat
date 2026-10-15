@echo off
chcp 65001 >nul
echo ═══════════════════════════════════════════
echo  Elnagar POS — Full Rebuild Google Sheet
echo ═══════════════════════════════════════════
echo.
echo This will BACKUP then CLEAR and REBUILD the Google Sheet.
echo.
pause
cd /d "%~dp0"
.venv\Scripts\python.exe backup_google_sheet.py
echo.
echo Backup done. Now rebuilding...
echo.
.venv\Scripts\python.exe sync_pos_to_sheet.py --full-rebuild-sheet
echo.
echo ═══════════════════════════════════════════
pause
