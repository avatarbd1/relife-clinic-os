"""
config.py
সব সিক্রেট/সেটিং এখান থেকে লোড হয় .env ফাইল থেকে।
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env ফাইল লোড করুন (রুট ডিরেক্টরি থেকে)
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# ---- Telegram Bot ----
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN পাওয়া যায়নি। .env ফাইলে BOT_TOKEN যোগ করো।")

# ---- Google Sheets ----
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
MASTER_SHEET_ID = os.getenv("MASTER_SHEET_ID")
MULTITENANT_ENABLED = os.getenv("MULTITENANT_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on"
}
if MULTITENANT_ENABLED and not MASTER_SHEET_ID:
    raise RuntimeError("MULTITENANT_ENABLED=true but MASTER_SHEET_ID is missing.")
if not GOOGLE_SHEET_ID and not MULTITENANT_ENABLED:
    raise RuntimeError("GOOGLE_SHEET_ID পাওয়া যায়নি।")

# credentials.json ফাইলের পাথ (রুট ডিরেক্টরিতে)
GOOGLE_CREDENTIALS_PATH = os.getenv(
    "GOOGLE_CREDENTIALS_PATH",
    str(Path(__file__).resolve().parent.parent / "credentials.json")
)

if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
    raise RuntimeError(
        f"credentials.json পাওয়া যায়নি: {GOOGLE_CREDENTIALS_PATH}"
    )

# ---- Bangladesh time helper ----
def bd_now():
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=6)))

# ---- Google Sheet Tab Names ----
SHEET_PATIENTS = "02_Patients"
SHEET_ATTENDANCE = "03_Attendance"
SHEET_APPOINTMENTS = "04_Appointments"
SHEET_TREATMENTS = "05_Treatments"
SHEET_PAYMENTS = "06_Payments"
SHEET_STAFF = "08_Staff"
SHEET_STAFF_DEPARTMENT_ACCESS = "Staff_Department_Access"
SHEET_PACKAGES = "11_Packages"
SHEET_TREATMENT_PLANS = "12_Treatment_Plans"
SHEET_ASSESSMENTS = "10_Assessments"
SHEET_REPORTS = "14_Reports"
SHEET_CASE_STUDIES = "15_Case_Studies"
SHEET_DELETE_LOG = "16_Delete_Log"
SHEET_INVENTORY = "09_Inventory"
SHEET_INVENTORY_LOG = "17_Inventory_Log"
SHEET_SALARY = "13_Salary"
SHEET_EXPENSES = "07_Expenses"
SHEET_LEARNING_PROGRESS = "18_Learning_Progress"

SHEET_CONSENT = "19_Consent"
SHEET_DATA_AUDIT = "20_Data_Audit"
SHEET_CASH_MOVEMENT = "21_Cash_Movement"

# ---- Department and access classifications ----
DEPARTMENT_PHYSIO = "Physio"
DEPARTMENT_DENTAL = "Dental"
DEPARTMENT_ALL = "All"
DEPARTMENTS = [DEPARTMENT_PHYSIO, DEPARTMENT_DENTAL, DEPARTMENT_ALL]

ROLE_DENTIST = "Dentist"
ROLE_DENTAL_ASSISTANT = "Dental_Assistant"

STAFF_ACCESS_FIELDS = [
    "Primary_Department",
    "Department_Access",
    "Clinical_Write_Scope",
    "Financial_Access",
]


# ---- Finance classifications ----
EXPENSE_TYPE_CLINIC = "Clinic Expense"
EXPENSE_TYPE_HOUSEHOLD = "Household Withdrawal"
EXPENSE_TYPE_UNCLASSIFIED = "Unclassified"
EXPENSE_TYPES = [EXPENSE_TYPE_CLINIC, EXPENSE_TYPE_HOUSEHOLD]

CASH_CUSTODIAN_RECEPTION = "Reception"
CASH_CUSTODIAN_HOME_TREASURY = "Home Treasury"
CASH_CUSTODIAN_BANK = "Bank"
CASH_CUSTODIANS = [
    CASH_CUSTODIAN_RECEPTION,
    CASH_CUSTODIAN_HOME_TREASURY,
    CASH_CUSTODIAN_BANK,
]


# ---- Attendance location verification ----
CLINIC_LATITUDE = float(os.getenv("CLINIC_LATITUDE", "0") or 0)
CLINIC_LONGITUDE = float(os.getenv("CLINIC_LONGITUDE", "0") or 0)
ATTENDANCE_RADIUS_METERS = float(os.getenv("ATTENDANCE_RADIUS_METERS", "200") or 200)
ATTENDANCE_MAX_ACCURACY_METERS = float(
    os.getenv("ATTENDANCE_MAX_ACCURACY_METERS", "100") or 100
)
