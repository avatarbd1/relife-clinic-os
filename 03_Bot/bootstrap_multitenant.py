"""Create the master directory and import the current production clinic/staff.

Run once with the existing .env and credentials.json:
    python 03_Bot/bootstrap_multitenant.py --dry-run
    python 03_Bot/bootstrap_multitenant.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials


ROOT = Path(__file__).resolve().parent.parent
SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)
CLINIC_HEADERS = [
    "Clinic_ID", "Clinic_Name", "Sheet_ID", "Status", "Credential_Ref",
    "Latitude", "Longitude", "Attendance_Radius_M",
    "Attendance_Max_Accuracy_M", "Created_At", "Updated_At",
]
STAFF_HEADERS = ["Telegram_ID", "Clinic_ID", "Staff_ID", "Status", "Updated_At"]


def stop(message, error=None):
    print(f"ERROR: {message}", file=sys.stderr)
    if error:
        print(f"DETAIL: {type(error).__name__}: {error}", file=sys.stderr)
    raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")

    source_id = os.getenv("GOOGLE_SHEET_ID")
    credentials_path = Path(
        os.getenv("GOOGLE_CREDENTIALS_PATH", str(ROOT / "credentials.json"))
    ).expanduser().resolve()
    if not source_id:
        stop("GOOGLE_SHEET_ID is missing; it must point to the current clinic.")
    if not credentials_path.is_file():
        stop(f"Credentials file not found: {credentials_path}")

    try:
        credentials = Credentials.from_service_account_file(
            str(credentials_path), scopes=SCOPES
        )
        client = gspread.authorize(credentials)
        source = client.open_by_key(source_id)
        staff = source.worksheet("08_Staff").get_all_records()
    except Exception as error:
        stop("Could not validate the current production clinic sheet.", error)

    active_staff = []
    seen_ids = set()
    for row in staff:
        telegram_id = str(row.get("Telegram_ID", "")).strip()
        if not telegram_id or str(row.get("Status", "")).strip().casefold() == "inactive":
            continue
        if telegram_id in seen_ids:
            stop(f"Duplicate active Telegram_ID in 08_Staff: {telegram_id}")
        seen_ids.add(telegram_id)
        active_staff.append(row)

    print(f"Current clinic: {source.title} ({source.id})")
    print(f"Active Telegram staff mappings to import: {len(active_staff)}")
    print("Master title: Relife Clinic OS — Master Directory")
    if args.dry_run:
        print("DRY RUN OK: no spreadsheet created.")
        return

    try:
        master = client.create(
            "Relife Clinic OS — Master Directory",
            folder_id=os.getenv("CLINIC_SHEETS_FOLDER_ID") or None,
        )
        clinics_ws = master.sheet1
        clinics_ws.update_title("Clinics")
        clinics_ws.append_row(CLINIC_HEADERS)
        clinics_ws.append_row([
            "CLN_0001", source.title, source.id, "Active", "default",
            os.getenv("CLINIC_LATITUDE", ""),
            os.getenv("CLINIC_LONGITUDE", ""),
            os.getenv("ATTENDANCE_RADIUS_METERS", "200"),
            os.getenv("ATTENDANCE_MAX_ACCURACY_METERS", "100"), "", "",
        ])
        staff_ws = master.add_worksheet(
            title="Staff_Directory", rows=max(100, len(active_staff) + 10), columns=5
        )
        staff_ws.append_row(STAFF_HEADERS)
        if active_staff:
            staff_ws.append_rows([
                [
                    str(row.get("Telegram_ID", "")).strip(),
                    "CLN_0001",
                    str(row.get("Staff_ID", "")).strip(),
                    "Active",
                    "",
                ]
                for row in active_staff
            ])
        client.open_by_key(master.id).worksheet("Staff_Directory")
    except Exception as error:
        stop(
            "Master bootstrap failed. A partially-created master sheet may need review.",
            error,
        )

    print("SUCCESS: master directory created and existing staff imported.")
    print(f"MASTER_SHEET_ID={master.id}")
    print("After staging verification set MULTITENANT_ENABLED=true.")


if __name__ == "__main__":
    main()

