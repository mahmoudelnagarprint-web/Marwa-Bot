import os
import json
import datetime
import firebase_admin
from firebase_admin import credentials, firestore, storage

# Default Firebase Config
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), 'firebase_service_account.json')
# Need to know the actual storage bucket name. The prompt says: elnagarpos.firebasestorage.app
STORAGE_BUCKET = "elnagarpos.firebasestorage.app"

_db = None
_bucket = None

def _initialize_firebase():
    global _db, _bucket
    if not firebase_admin._apps:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            raise FileNotFoundError(f"Service account file not found at {SERVICE_ACCOUNT_FILE}")
        
        cred = credentials.Certificate(SERVICE_ACCOUNT_FILE)
        firebase_admin.initialize_app(cred, {
            'storageBucket': STORAGE_BUCKET
        })
        print(f"Initialized Firebase using {SERVICE_ACCOUNT_FILE}")
    
    if _db is None:
        _db = firestore.client()
    if _bucket is None:
        _bucket = storage.bucket()

def get_db():
    """Returns the Firestore client, initializing Firebase if necessary."""
    _initialize_firebase()
    return _db

def get_bucket():
    """Returns the Storage bucket client, initializing Firebase if necessary."""
    _initialize_firebase()
    return _bucket

def now_iso():
    """Returns current UTC time in ISO format."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def batch_writer():
    """Returns a new Firestore batch."""
    return get_db().batch()

def update_doc_status(collection_name, doc_id, status, error_message=None):
    """
    Update the status of a document in a queue collection.
    
    Args:
        collection_name (str): Name of the collection.
        doc_id (str): Document ID.
        status (str): New status (e.g., 'imported', 'failed', 'processing').
        error_message (str, optional): Error message if status is failed.
    """
    db = get_db()
    update_data = {
        'status': status,
        'updated_at': now_iso()
    }
    if error_message:
        update_data['error_message'] = error_message
    
    db.collection(collection_name).document(doc_id).update(update_data)
