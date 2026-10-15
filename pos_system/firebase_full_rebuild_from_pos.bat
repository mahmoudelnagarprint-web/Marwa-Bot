@echo off
echo Running Full Rebuild from POS DB...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" firebase_mirror_from_pos.py --once
) else (
    python firebase_mirror_from_pos.py --once
)
pause
