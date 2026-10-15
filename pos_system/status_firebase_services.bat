@echo off
echo Checking Firebase Services Status...
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "from firebase_admin_client import get_db; db = get_db(); hb = db.collection('importer_heartbeats').document('main_loop').get(); print('Importer Status:', hb.to_dict() if hb.exists else 'Not found')"
) else (
    python -c "from firebase_admin_client import get_db; db = get_db(); hb = db.collection('importer_heartbeats').document('main_loop').get(); print('Importer Status:', hb.to_dict() if hb.exists else 'Not found')"
)
pause
