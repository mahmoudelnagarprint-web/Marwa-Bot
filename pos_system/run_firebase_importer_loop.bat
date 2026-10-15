@echo off
title Firebase Importer Loop
echo Starting Firebase Importer Continuous Loop...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" firebase_importer_loop.py
) else (
    python firebase_importer_loop.py
)
pause
