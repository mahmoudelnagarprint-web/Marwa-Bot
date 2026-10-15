@echo off
echo Running Firebase Mirror Now...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" firebase_mirror_from_pos.py --once
) else (
    python firebase_mirror_from_pos.py --once
)
pause
