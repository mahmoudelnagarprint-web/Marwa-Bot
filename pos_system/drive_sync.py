from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import os
import re

def get_id_from_link(link):
    """
    Extracts the file/folder ID from a Google Drive link.
    """
    if not link:
        return None
    # match ID in .../folders/ID... or id=ID
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', link)
    if match:
        return match.group(1)
    match = re.search(r'id=([a-zA-Z0-9_-]+)', link)
    if match:
        return match.group(1)
    return None

def download_images(service, folder_link, local_base_path, category, product, client_phone):
    """
    Downloads images from the given Google Drive folder link to the local path.
    Preserves structure: Category/Product/Client_Phone/Image.jpg
    """
    folder_id = get_id_from_link(folder_link)
    if not folder_id:
        print(f"Invalid link for {client_phone}")
        return False

    # Create local directory
    # Sanitize path components to avoid OS errors with special chars
    def sanitize(name):
        return re.sub(r'[<>:"/\\|?*]', '_', str(name)).strip()

    target_dir = os.path.join(local_base_path, sanitize(category), sanitize(product), sanitize(client_phone))
    os.makedirs(target_dir, exist_ok=True)

    try:
        # List files in the folder (images only)
        query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
        results = service.files().list(q=query, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])

        if not items:
            print(f"No images found for {client_phone}")
            return True # Not an error, just empty

        for item in items:
            file_id = item['id']
            file_name = item['name']
            file_path = os.path.join(target_dir, file_name)
            
            if os.path.exists(file_path):
                # Skip if already exists (basic caching)
                continue

            request = service.files().get_media(fileId=file_id)
            fh = io.FileIO(file_path, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
        
        return True

    except Exception as e:
        print(f"Error downloading for {client_phone}: {e}")
        return False
