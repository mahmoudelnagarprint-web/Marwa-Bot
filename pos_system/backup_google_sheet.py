#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backup_google_sheet.py
──────────────────────
Backup ALL Google Sheet tabs to local JSON + CSV files before rebuild.
Creates: sheet_backups/YYYYMMDD_HHMMSS/
"""

import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SA_PATH = ROOT_DIR / "android_companion_app" / "assets" / "secrets" / "service_account.json"
SHEET_ID = "14Du-Cqxdr5r1TDVTog0hUjObAihieIHJOOhGv-scq5Q"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
BACKUP_ROOT = ROOT_DIR / "sheet_backups"


def build_sheets_service():
    from google.oauth2 import service_account as sa
    from googleapiclient.discovery import build

    creds = sa.Credentials.from_service_account_file(str(SA_PATH), scopes=SCOPES)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def get_all_tab_names(svc):
    meta = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    return [s["properties"]["title"] for s in meta.get("sheets", [])]


def read_tab_values(svc, tab_name):
    try:
        result = svc.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=tab_name,
        ).execute()
        return result.get("values", [])
    except Exception as e:
        print(f"  ⚠️ Could not read tab '{tab_name}': {e}")
        return []


def save_csv(path, values):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        for row in values:
            writer.writerow(row)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUP_ROOT / stamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Google Sheet Full Backup ===")
    print(f"Sheet ID: {SHEET_ID}")
    print(f"Backup dir: {backup_dir}")
    print()

    svc = build_sheets_service()
    tabs = get_all_tab_names(svc)
    print(f"Found {len(tabs)} tabs: {tabs}")
    print()

    manifest = {
        "sheet_id": SHEET_ID,
        "backup_at": datetime.now().isoformat(),
        "tabs": {},
        "pending_queues": {},
    }

    all_tab_data = {}
    for tab_name in tabs:
        print(f"  📥 Reading '{tab_name}'...", end=" ")
        values = read_tab_values(svc, tab_name)
        row_count = len(values) - 1 if len(values) > 1 else 0

        # Save JSON
        json_path = backup_dir / f"{tab_name}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(values, f, ensure_ascii=False, indent=2)

        # Save CSV
        csv_path = backup_dir / f"{tab_name}.csv"
        save_csv(csv_path, values)

        manifest["tabs"][tab_name] = {
            "rows": row_count,
            "total_rows_with_header": len(values),
            "json_file": f"{tab_name}.json",
            "csv_file": f"{tab_name}.csv",
        }

        all_tab_data[tab_name] = values
        print(f"{row_count} data rows ✅")

        # Small delay to avoid rate limiting
        time.sleep(0.3)

    # Check pending queues
    print()
    print("=== Checking Pending Queues ===")
    queue_tabs = [
        "telegram_inbox",
        "android_orders_queue",
        "android_payments_queue",
        "android_status_queue",
        "android_products_queue",
    ]

    for qt in queue_tabs:
        if qt not in all_tab_data:
            print(f"  ⚪ '{qt}' — not found")
            continue
        values = all_tab_data[qt]
        if len(values) < 2:
            print(f"  ⚪ '{qt}' — empty")
            manifest["pending_queues"][qt] = {"pending": 0, "failed": 0}
            continue

        headers = values[0]
        status_idx = None
        for i, h in enumerate(headers):
            if h.lower() == "status":
                status_idx = i
                break

        pending = 0
        failed = 0
        if status_idx is not None:
            for row in values[1:]:
                if status_idx < len(row):
                    s = row[status_idx].strip().lower()
                    if s == "pending":
                        pending += 1
                    elif s == "failed":
                        failed += 1

        print(f"  📋 '{qt}' — {pending} pending, {failed} failed")
        manifest["pending_queues"][qt] = {"pending": pending, "failed": failed}

        # Save pending rows separately
        if pending > 0:
            pending_path = backup_dir / f"{qt}_PENDING.json"
            pending_rows = []
            for row in values[1:]:
                if status_idx is not None and status_idx < len(row) and row[status_idx].strip().lower() == "pending":
                    row_dict = {}
                    for j, h in enumerate(headers):
                        row_dict[h] = row[j] if j < len(row) else ""
                    pending_rows.append(row_dict)
            with open(pending_path, "w", encoding="utf-8") as f:
                json.dump(pending_rows, f, ensure_ascii=False, indent=2)
            print(f"    → Saved {pending} pending rows to {qt}_PENDING.json")

    # Save manifest
    manifest_path = backup_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print()
    print(f"✅ Backup complete: {backup_dir}")
    print(f"   Manifest: {manifest_path}")

    # Return for programmatic use
    return {"success": True, "backup_dir": str(backup_dir), "manifest": manifest}


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get("success") else 1)
