@echo off
echo Running Firebase Importer (Dry Run)...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" firebase_importer.py --dry-run
) else (
    python firebase_importer.py --dry-run
)
pause
