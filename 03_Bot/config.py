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
if not GOOGLE_SHEET_ID:
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
SHEET_PACKAGES = "11_Packages"
SHEET_TREATMENT_PLANS = "12_Treatment_Plans"
SHEET_ASSESSMENTS = "10_Assessments"
SHEET_REPORTS = "14_Reports"
SHEET_CASE_STUDIES = "15_Case_Studies"
