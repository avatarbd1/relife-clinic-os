"""
staff_ai_query.py
==================
স্টাফদের জন্য Natural Language Query ফিচার — Relife Clinic OS bot-এর অংশ।

কী করে:
- স্টাফ Telegram-এ সাধারণ ভাষায় প্রশ্ন করবে (যেমন: "গত সপ্তাহে income কত হয়েছে?")
- Groq API প্রশ্নটা বুঝে, কোন sheet/data লাগবে ঠিক করে
- সেই sheet থেকে ডেটা টেনে এনে, OpenRouter API দিয়ে মানুষের ভাষায় উত্তর তৈরি করায়
- Patient-দের কোনো access নেই এই ফিচারে — শুধু স্টাফদের জন্য

Environment variable লাগবে:
    GROQ_API_KEY           (sheet বাছাইয়ের জন্য)
    OPENROUTER_API_KEY     (উত্তর লেখার জন্য)
"""

import os
import json
import requests

import config
import sheets


GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL_NAME = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL_NAME = "openai/gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _call_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY সেট করা নেই")
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": GROQ_MODEL_NAME, "messages": [{"role": "user", "content": prompt}]}
    resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_openrouter(prompt: str) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY সেট করা নেই")
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": OPENROUTER_MODEL_NAME, "messages": [{"role": "user", "content": prompt}]}
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


SHEET_CATALOG = {
    "06_Payments": (
        "আয়, payment, income, revenue, বিল, receipt সংক্রান্ত প্রশ্নের জন্য। "
        "কলাম: Receipt_No, Date, Patient_ID, Patient_Name, Department, "
        "Amount, Discount, Due, Payment_Received_By, Time, Session_Type"
    ),
    "03_Attendance": (
        "স্টাফ attendance, late, overtime, working hour সংক্রান্ত প্রশ্নের জন্য। "
        "কলাম: Date, Staff_ID, Staff_Name, Role, Check_In, Check_Out, "
        "Working_Hours, Late_Min, Overtime, Status"
    ),
    "02_Patients": (
        "রোগী registration, নতুন patient সংখ্যা সংক্রান্ত প্রশ্নের জন্য। "
        "কলাম: Patient_ID, Registration_Date, Full_Name, Total_Bill, Paid, Due, Status"
    ),
    "08_Staff": (
        "স্টাফ তালিকা, salary, role সংক্রান্ত প্রশ্নের জন্য। "
        "কলাম: Staff_ID, Full_Name, Role, Salary, Status, Joining_Date"
    ),
    "07_Expenses": (
        "খরচ, expense সংক্রান্ত প্রশ্নের জন্য।"
    ),
}


ROLE_RESTRICTED_SHEETS = {
    "Therapist": ["06_Payments"],  # income/payment তথ্য থেরাপিস্টের জন্য না
}


def _pick_relevant_sheet(question: str, role: str = "") -> str:
    allowed_catalog = {
        name: desc for name, desc in SHEET_CATALOG.items()
        if name not in ROLE_RESTRICTED_SHEETS.get(role, [])
    }
    catalog_text = "\n".join(f"- {name}: {desc}" for name, desc in allowed_catalog.items())
    prompt = f"""নিচে কিছু Google Sheet-এর তালিকা ও তাদের বিষয়বস্তু দেওয়া হলো:

{catalog_text}

স্টাফের প্রশ্ন: "{question}"

শুধু সবচেয়ে প্রাসঙ্গিক sheet-এর নাম লিখুন (যেমন: 06_Payments), অন্য কিছু লিখবেন না।
"""
    sheet_name = _call_groq(prompt).strip()
    if sheet_name not in allowed_catalog:
        return None
    return sheet_name


def _summarize_answer(question: str, sheet_name: str, records: list) -> str:
    data_json = json.dumps(records, ensure_ascii=False)[:8000]
    today_str = config.bd_now().strftime("%Y-%m-%d")
    prompt = f"""আপনি একজন ক্লিনিক assistant, স্টাফকে ডেটা বুঝিয়ে বলছেন।

আজকের তারিখ: {today_str}

স্টাফের প্রশ্ন: "{question}"

"{sheet_name}" sheet থেকে প্রাসঙ্গিক ডেটা (JSON):
{data_json}

এই ডেটা বিশ্লেষণ করে প্রশ্নের সংক্ষিপ্ত, স্পষ্ট উত্তর বাংলায় দিন। "আজকে"/"today" বা কোনো
নির্দিষ্ট দিনের কথা বললে সেটাকে উপরের আজকের তারিখের সাপেক্ষে বুঝে, ডেটার Date কলামের
সাথে মিলিয়ে ফিল্টার করে উত্তর দিন। সংখ্যা/টাকার হিসাব থাকলে স্পষ্টভাবে দেখান। যদি
কোনো নাম/তথ্যের জন্য এই sheet-এ কোনো ম্যাচিং row না পাওয়া যায়, শুধু বলুন যে এই sheet-এ
সেই নামে/তারিখে কোনো রেকর্ড পাওয়া যায়নি — কখনো এই সিদ্ধান্তে যাবেন না যে সেই ব্যক্তি
আদৌ স্টাফ/রোগী হিসেবে অস্তিত্বহীন, কারণ এই sheet-এ শুধু একটা নির্দিষ্ট বিষয়ের ডেটা আছে,
সবার তথ্য না। অনুমান করে উত্তর বানাবেন না।
"""
    return _call_openrouter(prompt).strip()


def answer_staff_query(question: str, role: str = "") -> str:
    if not GROQ_API_KEY or not OPENROUTER_API_KEY:
        return "⚠️ AI query ফিচার এখনো সেটআপ হয়নি (GROQ_API_KEY বা OPENROUTER_API_KEY নেই)।"
    try:
        sheet_name = _pick_relevant_sheet(question, role)
        if not sheet_name:
            return "দুঃখিত, এই তথ্য তোমার জন্য প্রযোজ্য না, অথবা প্রশ্নটা কোন তথ্যের সাথে সম্পর্কিত বুঝতে পারিনি।"
        worksheet = sheets._worksheet(getattr(config, f"SHEET_{sheet_name.split('_', 1)[1].upper()}", sheet_name))
        records = sheets.safe_get_all_records(worksheet)
        return _summarize_answer(question, sheet_name, records)
    except Exception as e:
        return f"⚠️ প্রশ্নের উত্তর দিতে সমস্যা হয়েছে: {e}"
