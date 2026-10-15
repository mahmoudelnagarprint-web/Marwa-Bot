import time
import os
import traceback
from firebase_admin_client import get_db, now_iso
import firebase_importer

HEARTBEAT_INTERVAL = 60 # seconds
POLL_INTERVAL = 10 # seconds

def run_loop():
    print("Starting Firebase Importer Loop...")
    db = get_db()
    last_heartbeat = 0

    while True:
        try:
            current_time = time.time()
            if current_time - last_heartbeat >= HEARTBEAT_INTERVAL:
                db.collection('importer_heartbeats').document('main_loop').set({
                    'status': 'online',
                    'last_seen': now_iso()
                })
                last_heartbeat = current_time

            firebase_importer.run_import_cycle(dry_run=False)
            
        except Exception as e:
            print(f"Importer Loop Error: {e}")
            traceback.print_exc()
            try:
                db.collection('errors').add({
                    'source': 'importer_loop',
                    'error': str(e),
                    'timestamp': now_iso()
                })
            except:
                pass
                
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    run_loop()
