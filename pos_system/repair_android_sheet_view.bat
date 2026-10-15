@echo off
chcp 65001 >nul
echo ═══════════════════════════════════════════
echo  Elnagar POS — Repair Android Sheet View
echo ═══════════════════════════════════════════
cd /d "%~dp0"
.venv\Scripts\python.exe sync_pos_to_sheet.py --mirror-now --mark-stale
echo.
echo Done. Stale data marked, summaries updated.
pause
