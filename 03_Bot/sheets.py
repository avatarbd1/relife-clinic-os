"""
sheets.py
Google Sheets-কে ডেটাবেস হিসেবে ব্যবহার করার জন্য gspread wrapper।
সব read/write এই ফাইলের মধ্য দিয়ে যাবে — bot.py সরাসরি gspread ছুঁবে না,
এতে ভবিষ্যতে ডেটাবেস বদলাতে হলে (যেমন Postgres-এ migrate) শুধু এই ফাইলটাই বদলালেই হবে।
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client = None
_spreadsheet = None


def _get_client():
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(
            config.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
        )
        _client = gspread.authorize(creds)
    return _client


def _get_spreadsheet():
    global _spreadsheet
    if _spreadsheet is None:
        _spreadsheet = _get_client().open_by_key(config.GOOGLE_SHEET_ID)
    return _spreadsheet


def _worksheet(name: str):
    return _get_spreadsheet().worksheet(name)


def get_staff_by_telegram_id(telegram_id: int) -> dict | None:
    ws = _worksheet(config.SHEET_STAFF)
    records = ws.get_all_records()
    for row in records:
        if str(row.get("Telegram_ID", "")).strip() == str(telegram_id):
            if str(row.get("Status", "")).strip().lower() == "inactive":
                return None
            return row
    return None


def _next_patient_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("PT"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"PT{next_num:04d}"


def add_patient(data: dict, created_by: str) -> str:
    ws = _worksheet(config.SHEET_PATIENTS)
    patient_id = _next_patient_id(ws)
    now = datetime.now()

    row = [
        patient_id,
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        data.get("Full_Name", ""),
        data.get("Father_Husband_Name", ""),
        data.get("Phone", ""),
        data.get("Alternative_Phone", ""),
        data.get("Date_of_Birth", ""),
        data.get("Age", ""),
        data.get("Gender", ""),
        data.get("Blood_Group", ""),
        data.get("Occupation", ""),
        data.get("Address", ""),
        data.get("Department", ""),
        data.get("Diagnosis", ""),
        data.get("Therapist", ""),
        "",
        "",
        "",
        "Due",
        data.get("Total_Bill", 0),
        0,
        data.get("Total_Bill", 0),
        data.get("Referral", ""),
        data.get("Remarks", ""),
        "Active",
        created_by,
        now.strftime("%Y-%m-%d %H:%M"),
        now.strftime("%Y-%m-%d %H:%M"),
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")
    return patient_id


def get_all_patients() -> list[dict]:
    ws = _worksheet(config.SHEET_PATIENTS)
    return ws.get_all_records()


def get_patients_for_therapist(therapist_name: str) -> list[dict]:
    all_patients = get_all_patients()
    return [
        p for p in all_patients
        if p.get("Therapist", "").strip() == therapist_name.strip()
        and p.get("Status", "").strip() == "Active"
    ]


def search_patients(query: str) -> list[dict]:
    query = query.strip().lower()
    all_patients = get_all_patients()
    return [
        p for p in all_patients
        if query in str(p.get("Full_Name", "")).lower()
        or query in str(p.get("Phone", ""))
        or query in str(p.get("Patient_ID", "")).lower()
    ]
