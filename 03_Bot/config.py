"""
config.py
সব সিক্রেট/সেটিং এখান থেকে লোড হয় .env ফাইল থেকে।
কখনো টোকেন/ক্রেডেনশিয়াল সরাসরি কোডে হার্ডকোড করবে না।
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ---- Telegram Bot ----
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN পাওয়া যায়নি। .env ফাইলে BOT_TOKEN=xxxxx যোগ করো "
        "(BotFather থেকে টোকেন নিয়ে)।"
    )

# ---- Google Sheets ----
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
if not GOOGLE_SHEET_ID:
    raise RuntimeError(
        "GOOGLE_SHEET_ID পাওয়া যায়নি। .env ফাইলে GOOGLE_SHEET_ID=xxxxx যোগ করো "
        "(Google Sheet-এর URL-এর /d/ এর পরের অংশটা)।"
    )

GOOGLE_CREDENTIALS_PATH = os.getenv(
    "GOOGLE_CREDENTIALS_PATH", "credentials.json"
)

# Render/cloud hosting-e file upload kora jay na, tai credentials.json-er
# পুরো content GOOGLE_CREDENTIALS_JSON env var hisebe dile eta file banie nebe.
_creds_json_env = os.getenv("GOOGLE_CREDENTIALS_JSON")
if _creds_json_env and not Path(GOOGLE_CREDENTIALS_PATH).exists():
    Path(GOOGLE_CREDENTIALS_PATH).write_text(_creds_json_env, encoding="utf-8")
if not Path(GOOGLE_CREDENTIALS_PATH).exists():
    raise RuntimeError(
        f"Google service account credential ফাইল পাওয়া যায়নি: "
        f"{GOOGLE_CREDENTIALS_PATH}\n"
        "Google Cloud Console থেকে service account বানিয়ে JSON key ডাউনলোড করে "
        "এই নামে project ফোল্ডারে রাখো, আর ওই সার্ভিস অ্যাকাউন্টের ইমেইলকে "
        "তোমার Google Sheet-এ Editor হিসেবে শেয়ার করে দাও।"
    )

# ---- Sheet tab names (আসল স্প্রেডশিটের সাথে হুবহু মিলতে হবে) ----
SHEET_DASHBOARD = "01_Dashboard"
SHEET_PATIENTS = "02_Patients"
SHEET_ATTENDANCE = "03_Attendance"
SHEET_APPOINTMENTS = "04_Appointments"
SHEET_TREATMENTS = "05_Treatments"
SHEET_PAYMENTS = "06_Payments"
SHEET_EXPENSES = "07_Expenses"
SHEET_STAFF = "08_Staff"
SHEET_INVENTORY = "09_Inventory"
SHEET_SETTINGS = "10_Settings"
SHEET_PACKAGES = "11_Packages"
SHEET_TREATMENT_PLANS = "12_Treatment_Plans"

SHEET_REPORTS = "14_Reports"

# ---- Bangladesh time helper ----
from datetime import timedelta as _td, timezone as _tz

def bd_now():
    """বর্তমান বাংলাদেশ সময় (UTC+6) naive datetime হিসেবে রিটার্ন করে।"""
    from datetime import datetime as _dt
    return _dt.now(_tz.utc).replace(tzinfo=None) + _td(hours=6)

# Salary Sheet
SHEET_SALARY = "13_Salary"

SHEET_SALARY = "13_Salary"
