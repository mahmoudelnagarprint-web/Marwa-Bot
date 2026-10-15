@echo off
rem Elnagar POS — Hybrid Cloud Sync daemon launcher (Level 1)
rem Activates .venv and runs cloud\supabase_sync.py in background, loops every
rem SYNC_INTERVAL_SECONDS (default 60). Does NOT touch run_app.bat / start_silent.vbs.
cd /d "%~dp0"
chcp 65001 >nul
echo Starting Hermes Sync daemon (cloud)...
if exist "cloud\supabase_sync.pid" (
    echo Stale pid file exists [cloud\supabase_sync.pid] — removing.
    del "cloud\supabase_sync.pid"
)
rem Launch hidden via pythonw and remember its PID
start "" /b ".venv\Scripts\pythonw.exe" "cloud\supabase_sync.py" --daemon
> "cloud\supabase_sync.pid" (
    for /f "tokens=1" %%p in ('powershell -NoProfile -Command "(Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*Elnagar POS*' }).Id"') do echo %%p & break
)
echo Daemon launched. Log: cloud\supabase_sync.log
