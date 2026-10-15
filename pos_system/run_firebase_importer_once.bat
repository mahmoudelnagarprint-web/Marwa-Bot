@echo off
echo Running Firebase Importer Once...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" firebase_importer.py
) else (
    python firebase_importer.py
)
pause
