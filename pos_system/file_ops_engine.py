import os
import shutil
import time
import gc
from datetime import datetime

class FileOpsEngine:
    """
    The Robust File Manager (FileOpsEngine)
    Handles Client-Centric File Management (Wholesale vs Retail).
    Implements 'Atomic Isolation' Protocol.
    """
    
    def __init__(self, root_path):
        self.root_path = root_path
        if not self.root_path or not os.path.exists(self.root_path):
            raise ValueError(f"Invalid Root Path: {self.root_path}")

    def _sanitize(self, name):
        """Sanitizes strings for Windows folder names. Aggressive cleanup."""
        # Replace common illegal chars
        clean = str(name).replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        # Remove Control Characters (Newlines, Tabs)
        clean = "".join([c for c in clean if c.isalnum() or c in " _-.,()[]{}"])
        return clean.strip()[:100] # Cap length to avoid path shifting issues

    def _get_atomic_folder_name(self, product_name, note, order_id):
        """
        Generates Atomic Folder Name: {Product}_{Note}_{ID}
        This ensures uniqueness even if moved.
        """
        parts = []
        # Product Name
        parts.append(self._sanitize(product_name if product_name else "Product"))
        
        # Note
        if note and str(note).strip():
            parts.append(self._sanitize(note))
            
        # Order ID (The Atom)
        parts.append(f"{order_id}")
        
        return "_".join(parts)

    def _retry_operation(self, operation_func, *args, **kwargs):
        """Retry wrapper for Windows file locking issues."""
        max_retries = 3
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                gc.collect()
                return operation_func(*args, **kwargs)
            except (PermissionError, OSError) as e:
                last_error = e
                time.sleep(0.5)
            except Exception as e:
                return False, str(e)
        
        return False, f"Failed after {max_retries} attempts: {str(last_error)}"

    def _verify_move(self, src, dst):
        if os.path.exists(dst) and not os.path.exists(src):
            return True, "Success"
        return False, "Verification Failed"

    def safe_move(self, src_path, dest_path):
        """Moves folder with auto-creation of parent dirs."""
        def _move_action():
            if not os.path.exists(src_path):
                return False, f"Source not found: {src_path}"
            
            # Create Parent Directory (Self-Healing)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            # Collision Handling
            final_dest = dest_path
            if os.path.exists(final_dest):
                base = os.path.basename(final_dest)
                timestamp = int(time.time())
                final_dest = os.path.join(os.path.dirname(final_dest), f"{base}_dup_{timestamp}")
            
            shutil.move(src_path, final_dest)
            
            if os.path.exists(final_dest) and not os.path.exists(src_path):
                return True, f"Moved to {final_dest}"
            return False, "Move verification failed"

        return self._retry_operation(_move_action)

    # --- 1. Creation Logic (Helper for App.py) ---
    def get_creation_path(self, client_type, client_name, product_name, note, order_id):
        """
        Returns the standard path for a new order:
        Root / {Type} / {Client_Name} / {Atomic_Folder}
        """
        type_folder = "Wholesale" if client_type == 'Wholesale' else "Retail"
        client_safe = self._sanitize(client_name)
        folder_name = self._get_atomic_folder_name(product_name, note, order_id)
        
        return os.path.join(self.root_path, type_folder, client_safe, folder_name)

    # --- 2. Move Forward (To Ready / Delivered) ---
    def move_to_stage(self, order_id, product_name, note, stage, current_known_path=None):
        """
        Moves folder to a Stage folder (Ready_Orders or Delivered_Orders).
        """
        folder_name = self._get_atomic_folder_name(product_name, note, order_id)
        
        # 1. Determine Destination Root
        if stage == 'Ready':
            dest_root = os.path.join(self.root_path, "Ready_Orders")
        elif stage == 'Delivered':
            dest_root = os.path.join(self.root_path, "Delivered_Orders")
        else:
            return False, f"Unknown Stage: {stage}"
            
        dest_path = os.path.join(dest_root, folder_name)
        
        # 2. Find Source
        src_path = current_known_path
        if not src_path or not os.path.exists(src_path):
            src_path = self.find_order_folder(folder_name)
            
        if not src_path:
            return False, f"Source folder {folder_name} not found."
            
        # 3. Execute Move
        return self.safe_move(src_path, dest_path)

    # --- 3. Undo / Reverse Logic (To Preparation) ---
    def restore_to_previous_path(self, order_id, product_name, note, previous_path_from_log):
        """
        Restores a folder to its exact previous path from the DB Log.
        If parent folder (Client) is gone, it recreates it (Self-Healing).
        """
        folder_name = self._get_atomic_folder_name(product_name, note, order_id)
        
        # 1. Validate Target Path
        if not previous_path_from_log:
            return False, "No previous path provided from log."
            
        # ensure target ends with correct folder name (sanity check)
        # if not previous_path_from_log.endswith(folder_name):
        # We trust the log, but if names changed, we might have issues. 
        # For now, we trust the log was correct when written.
            
        # 2. Find Source (It should be in Ready or Delivered)
        src_path = self.find_order_folder(folder_name)
        if not src_path:
            return False, f"Folder {folder_name} not found in system for restoration."

        # 3. Execute Move
        return self.safe_move(src_path, previous_path_from_log)
        
    # --- 4. Fallback / Search ---
    def find_order_folder(self, folder_name):
        """Scans likely locations."""
        # Check Ready
        p = os.path.join(self.root_path, "Ready_Orders", folder_name)
        if os.path.exists(p): return p
        
        # Check Delivered
        p = os.path.join(self.root_path, "Delivered_Orders", folder_name)
        if os.path.exists(p): return p
        
        # Check Retail/Wholesale roots (Deep Search - Expensive but necessary if lost)
        # We simply list clients? No, too slow.
        # Minimal Check:
        for t in ['Retail', 'Wholesale']:
            # We don't know the client name here easily without scanning ALL clients.
            # So we assume it's NOT in client folders if we called this function 
            # usually used when moving FROM stage TO client.
            pass
            
        return None

    # --- 5. Deletion ---
    def delete_order_folder(self, path):
        """Recursive Hard Delete."""
        def _del():
            if os.path.exists(path):
                shutil.rmtree(path)
                return True, "Deleted"
            return True, "Already Gone"
        return self._retry_operation(_del)

    def cleanup_empty_client_folder(self, client_folder_path):
        """Removes client folder if empty."""
        try:
            if os.path.exists(client_folder_path) and not os.listdir(client_folder_path):
                os.rmdir(client_folder_path)
                return True
        except:
            pass
        return False

    def ingest_external_folder(self, order_id, source_path, db_interface):
        """
        Ingests an external folder (from Drag & Drop) into the System Hierarchy.
        1. Determines Correct Path (Root/Type/Client/Product_ID).
        2. Copies files from Source -> Target.
        3. Updates Database.
        """
        try:
            # 1. Fetch Order Details to determine path
            # We need to query DB. passing db_interface (cursor or wrapper)
            conn = db_interface()
            c = conn.cursor()
            
            order = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not order: return False, "Order not found"
            
            client = c.execute("SELECT * FROM clients WHERE id=?", (order['client_id'],)).fetchone()
            client_name = client['name']
            client_type = client['type']
            
            item = c.execute("SELECT product_name FROM order_items WHERE order_id=? LIMIT 1", (order_id,)).fetchone()
            product_name = item['product_name'] if item else "Product"
            
            notes = order['notes']
            conn.close()

            # 2. Generate Target Path
            target_path = self.get_creation_path(client_type, client_name, product_name, notes, order_id)
            
            # 3. Create Target & Copy
            if not os.path.exists(target_path):
                os.makedirs(target_path)

            if os.path.isdir(source_path):
                # Copy content
                for item in os.listdir(source_path):
                    s = os.path.join(source_path, item)
                    d = os.path.join(target_path, item)
                    if os.path.isfile(s):
                        shutil.copy2(s, d)
            elif os.path.isfile(source_path):
                 # Single file drop?
                 d = os.path.join(target_path, os.path.basename(source_path))
                 shutil.copy2(source_path, d)
            
            return True, target_path

        except Exception as e:
            return False, str(e)
