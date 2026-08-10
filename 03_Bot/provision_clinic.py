"""Create a clinic spreadsheet from the Relife OS template.

Usage:
    python 03_Bot/provision_clinic.py "XYZ Clinic" --dry-run
    python 03_Bot/provision_clinic.py "XYZ Clinic"

Environment variables (normally loaded from the repository's .env):
    TEMPLATE_SHEET_ID       Required. ID of the 00_Template spreadsheet.
    GOOGLE_CREDENTIALS_PATH Optional. Defaults to ./credentials.json.
    CLINIC_SHEETS_FOLDER_ID Optional. Destination folder/shared-drive folder ID.
    MASTER_SHEET_ID         Required. Master tenant directory spreadsheet ID.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials


SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)
REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy 00_Template and create a new Relife OS clinic sheet."
    )
    parser.add_argument("clinic_name", help='Clinic name, e.g. "XYZ Clinic"')
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Authenticate and validate template access, but do not copy anything.",
    )
    parser.add_argument(
        "--template-id",
        help="Override TEMPLATE_SHEET_ID from .env (normally unnecessary).",
    )
    parser.add_argument(
        "--folder-id",
        help="Override CLINIC_SHEETS_FOLDER_ID from .env.",
    )
    return parser.parse_args()


def fail(message: str, error: BaseException | None = None) -> "NoReturn":
    print(f"ERROR: {message}", file=sys.stderr)
    if error is not None:
        print(f"DETAIL: {type(error).__name__}: {error}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")

    clinic_name = " ".join(args.clinic_name.split()).strip()
    if not clinic_name:
        fail("Clinic name cannot be empty.")

    template_id = args.template_id or os.getenv("TEMPLATE_SHEET_ID")
    if not template_id:
        fail("TEMPLATE_SHEET_ID is missing from .env.")
    master_sheet_id = os.getenv("MASTER_SHEET_ID")
    if not master_sheet_id:
        fail("MASTER_SHEET_ID is missing from .env.")

    credentials_path = Path(
        os.getenv("GOOGLE_CREDENTIALS_PATH", str(REPO_ROOT / "credentials.json"))
    ).expanduser().resolve()
    if not credentials_path.is_file():
        fail(f"Credentials file not found: {credentials_path}")

    folder_id = args.folder_id or os.getenv("CLINIC_SHEETS_FOLDER_ID") or None
    new_title = f"{clinic_name} — Relife OS"

    try:
        credentials = Credentials.from_service_account_file(
            str(credentials_path), scopes=SCOPES
        )
        client = gspread.authorize(credentials)
        template = client.open_by_key(template_id)
        worksheet_names = [ws.title for ws in template.worksheets()]
        master = client.open_by_key(master_sheet_id)
        clinics_ws = master.worksheet("Clinics")
        clinic_headers = clinics_ws.row_values(1)
        clinic_rows = clinics_ws.get_all_records()
    except Exception as error:
        fail(
            "Could not authenticate or open the template. Share 00_Template with "
            "the service account and ensure Sheets + Drive APIs are enabled.",
            error,
        )

    service_account_email = credentials.service_account_email
    print(f"Template: {template.title} ({template_id})")
    print(f"New title: {new_title}")
    print(f"Service account: {service_account_email}")
    print(f"Destination folder: {folder_id or '[source/default folder]' }")
    print(f"Worksheets: {', '.join(worksheet_names)}")

    required_master_headers = {"Clinic_ID", "Clinic_Name", "Sheet_ID", "Status"}
    missing_headers = required_master_headers.difference(clinic_headers)
    if missing_headers:
        fail(
            "Master Clinics tab is missing columns: "
            + ", ".join(sorted(missing_headers))
        )

    existing_ids = {str(row.get("Clinic_ID", "")).strip() for row in clinic_rows}
    existing_names = {
        str(row.get("Clinic_Name", "")).strip().casefold() for row in clinic_rows
    }
    if clinic_name.casefold() in existing_names:
        fail(f"Clinic already exists in master directory: {clinic_name}")
    numbers = []
    for clinic_id in existing_ids:
        if clinic_id.startswith("CLN_") and clinic_id[4:].isdigit():
            numbers.append(int(clinic_id[4:]))
    clinic_id = f"CLN_{(max(numbers) + 1 if numbers else 1):04d}"
    print(f"Clinic ID: {clinic_id}")

    if args.dry_run:
        print("DRY RUN OK: authentication and template access verified; no file created.")
        return

    try:
        created = client.copy(
            template_id,
            title=new_title,
            copy_permissions=False,
            folder_id=folder_id,
            copy_comments=False,
        )

        # A copy made by these credentials normally already grants this service
        # account owner/writer access. Verify that invariant; add writer access only
        # when another identity/storage arrangement created the file.
        permissions = client.list_permissions(created.id)
        has_write_access = any(
            permission.get("emailAddress", "").casefold()
            == service_account_email.casefold()
            and permission.get("role") in {"owner", "organizer", "fileOrganizer", "writer"}
            for permission in permissions
        )
        if not has_write_access:
            created.share(
                service_account_email,
                perm_type="user",
                role="writer",
                notify=False,
            )

        # Re-open by ID so success means the bot credentials can really use it.
        client.open_by_key(created.id).worksheet(worksheet_names[0])
        master_values = {
            "Clinic_ID": clinic_id,
            "Clinic_Name": clinic_name,
            "Sheet_ID": created.id,
            "Status": "Active",
            "Credential_Ref": "default",
            "Latitude": "",
            "Longitude": "",
            "Attendance_Radius_M": 200,
            "Attendance_Max_Accuracy_M": 100,
        }
        clinics_ws.append_row(
            [master_values.get(header, "") for header in clinic_headers],
            value_input_option="RAW",
        )
    except Exception as error:
        fail(
            "Spreadsheet provisioning failed. If the error mentions storage quota, "
            "use a Google Workspace Shared Drive folder and set "
            "CLINIC_SHEETS_FOLDER_ID.",
            error,
        )

    print("SUCCESS: clinic spreadsheet created and access verified.")
    print(f"SHEET_ID={created.id}")
    print(f"CLINIC_ID={clinic_id}")
    print(f"URL=https://docs.google.com/spreadsheets/d/{created.id}/edit")


if __name__ == "__main__":
    main()

