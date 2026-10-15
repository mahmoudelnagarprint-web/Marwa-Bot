import sys
import os
from pathlib import Path
from typing import List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))
from firebase_admin_client import get_db, now_iso
from sheets_queue import TelegramSheetsQueue, TAB_HEADERS

TAB_TO_COLLECTION = {
    'clients': 'clients',
    'products': 'products',
    'orders': 'orders',
    'order_items': 'order_items',
    'sync_log': 'sync_log',
    'telegram_inbox': 'telegram_orders_queue',
    'telegram_images': 'telegram_images_queue',
    'telegram_payments_queue': 'telegram_payments_queue',
    'telegram_admin_actions_queue': 'telegram_admin_actions_queue'
}

class TelegramFirebaseQueue(TelegramSheetsQueue):
    def authenticate(self) -> None:
        self.db = get_db()
        self.sheets_service = "MOCKED"

    def read_rows(self, tab_name: str, force_refresh: bool = False) -> List[Dict[str, str]]:
        collection_name = TAB_TO_COLLECTION.get(tab_name)
        if not collection_name:
            return []
            
        try:
            docs = self.db.collection(collection_name).stream()
        except Exception as e:
            print(f"Error reading from {collection_name}: {e}")
            return []
            
        rows = []
        headers = TAB_HEADERS.get(tab_name, [])
        for doc in docs:
            data = doc.to_dict()
            row = {}
            for h in headers:
                val = data.get(h, "")
                if val is None:
                    val = ""
                row[h] = str(val)
            rows.append(row)
        return rows

    def append_row(self, tab_name: str, row_data: List[Any]) -> None:
        collection_name = TAB_TO_COLLECTION.get(tab_name)
        if not collection_name:
            return
            
        headers = TAB_HEADERS.get(tab_name, [])
        doc_data = {}
        for i, h in enumerate(headers):
            if i < len(row_data):
                doc_data[h] = row_data[i]
            else:
                doc_data[h] = ""
                
        doc_data['created_at'] = now_iso()
        
        # Determine status automatically
        if tab_name in ['telegram_inbox', 'telegram_images', 'telegram_payments_queue', 'telegram_admin_actions_queue']:
            if 'status' not in doc_data or not doc_data['status']:
                doc_data['status'] = 'pending'
        
        # Set Document ID if possible to avoid duplicates
        doc_id = None
        if tab_name == 'telegram_inbox':
            doc_id = doc_data.get('queue_id')
        elif tab_name == 'telegram_images':
            doc_id = doc_data.get('image_row_id')
        elif tab_name == 'telegram_payments_queue':
            doc_id = doc_data.get('payment_queue_id')
        elif tab_name == 'telegram_admin_actions_queue':
            doc_id = doc_data.get('admin_action_queue_id')
            
        try:
            if doc_id:
                self.db.collection(collection_name).document(str(doc_id)).set(doc_data)
            else:
                self.db.collection(collection_name).add(doc_data)
        except Exception as e:
            print(f"Error appending to {collection_name}: {e}")
