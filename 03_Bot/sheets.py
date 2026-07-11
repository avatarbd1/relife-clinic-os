import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_client():
    creds = Credentials.from_service_account_file(config.CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet(tab_name, headers=None):
    client = get_client()
    spreadsheet = client.open_by_key(config.GOOGLE_SHEET_ID)
    try:
        ws = spreadsheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=10)
        if headers:
            ws.append_row(headers)
    return ws


def add_patient(name, phone, note=""):
    ws = get_sheet("Patients", headers=["Date", "Name", "Phone", "Note"])
    ws.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), name, phone, note])


def get_all_patients():
    ws = get_sheet("Patients", headers=["Date", "Name", "Phone", "Note"])
    return ws.get_all_records()


def add_appointment(patient_name, date, time, doctor):
    ws = get_sheet("Appointments", headers=["Date", "Time", "Patient", "Doctor", "Status"])
    ws.append_row([date, time, patient_name, doctor, "Pending"])


def get_today_appointments():
    ws = get_sheet("Appointments", headers=["Date", "Time", "Patient", "Doctor", "Status"])
    rows = ws.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")
    return [r for r in rows if str(r.get("Date")) == today]


def add_payment(patient_name, amount, method, note=""):
    ws = get_sheet("Payments", headers=["Date", "Patient", "Amount", "Method", "Note"])
    ws.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), patient_name, amount, method, note])


def get_today_payments():
    ws = get_sheet("Payments", headers=["Date", "Patient", "Amount", "Method", "Note"])
    rows = ws.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")
    total = 0.0
    entries = []
    for r in rows:
        if str(r.get("Date", "")).startswith(today):
            try:
                total += float(r.get("Amount", 0))
            except (TypeError, ValueError):
                pass
            entries.append(r)
    return total, entries


def add_therapy_note(therapist_name, patient_name, note):
    ws = get_sheet("TherapyNotes", headers=["Date", "Therapist", "Patient", "Note"])
    ws.append_row([datetime.now().strftime("%Y-%m-%d %H:%M"), therapist_name, patient_name, note])


def get_notes_for_therapist(therapist_name):
    ws = get_sheet("TherapyNotes", headers=["Date", "Therapist", "Patient", "Note"])
    rows = ws.get_all_records()
    return [r for r in rows if str(r.get("Therapist")) == therapist_name]


def get_sessions_for_therapist_today(therapist_name):
    ws = get_sheet("Appointments", headers=["Date", "Time", "Patient", "Doctor", "Status"])
    rows = ws.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        r for r in rows
        if str(r.get("Date")) == today and str(r.get("Doctor")) == therapist_name
    ]


def get_inventory():
    ws = get_sheet("Inventory", headers=["Item", "Quantity", "Unit", "LastUpdated"])
    return ws.get_all_records()


def update_inventory(item, quantity, unit=""):
    ws = get_sheet("Inventory", headers=["Item", "Quantity", "Unit", "LastUpdated"])
    records = ws.get_all_values()
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    for idx, row in enumerate(records[1:], start=2):
        if row and row[0] == item:
            ws.update(f"A{idx}:D{idx}", [[item, quantity, unit, today]])
            return
    ws.append_row([item, quantity, unit, today])


def get_staff_list():
    ws = get_sheet("Staff", headers=["Name", "Role", "Phone"])
    return ws.get_all_records()


def add_staff(name, role, phone):
    ws = get_sheet("Staff", headers=["Name", "Role", "Phone"])
    ws.append_row([name, role, phone])
