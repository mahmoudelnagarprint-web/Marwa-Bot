from googleapiclient.discovery import build
import pandas as pd
import re

def get_sheet_data(service, spreadsheet_id, range_name="Form Responses 1!A1:Z"):
    """
    Reads data from the spreadsheet and returns a Pandas DataFrame.
    """
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])

    if not values:
        return pd.DataFrame()

    headers = values[0]
    data = values[1:]
    
    # Create DF
    df = pd.DataFrame(data, columns=headers)
    
    # Identify Product Column dynamically
    product_col = find_product_column(headers)
    if product_col:
        # Rename for consistency if needed, or just track it
        # For now, we'll keep original name but valid it exists
        pass
    else:
        print("Warning: Could not identify Product Name column.")

    return df, headers

def find_product_column(headers):
    """
    Finds the Product Name column based on the neighbor logic:
    It is the first non-empty column immediately to the left of the "Category" column.
    Skips ignored columns like 'Notes', 'Time', 'Timestamp'.
    """
    # Normalize headers for case-insensitive search
    valid_headers = [h.strip() for h in headers]
    
    try:
        # Find index of "Category" (or similar)
        # We look for "Category" or "Category" in Arabic "فئة" or "التصنيف" just in case, but let's stick to "Category" as per prompt
        category_idx = -1
        for i, h in enumerate(valid_headers):
            if "category" in h.lower() or "فئة" in h or "التصنيف" in h:
                category_idx = i
                break
        
        if category_idx == -1:
            return None

        # Look to the left
        ignored = ['notes', 'time', 'timestamp', 'ملاحظات', 'وقت']
        for i in range(category_idx - 1, -1, -1):
            col_name = valid_headers[i]
            if col_name and col_name.lower() not in ignored:
                return col_name
                
    except Exception as e:
        print(f"Error finding product column: {e}")
        return None
    
    return None

def update_order_status(service, spreadsheet_id, row_index, new_status, status_col_index):
    """
    Updates the status of an order in the Google Sheet.
    row_index: 0-based index from the DataFrame (needs adjustment for Sheet 1-based + header)
    """
    # Sheet row = row_index + 2 (1 for header, 1 for 0-based shift)
    sheet_row = row_index + 2
    
    # Convert column index to A1 notation (e.g., 0 -> A, 1 -> B)
    # Simple conversion for A-Z
    col_letter = chr(ord('A') + status_col_index)
    
    range_name = f"Form Responses 1!{col_letter}{sheet_row}"
    
    body = {
        'values': [[new_status]]
    }
    
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption="USER_ENTERED", body=body).execute()

