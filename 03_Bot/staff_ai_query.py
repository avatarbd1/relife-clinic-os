"""
staff_ai_query.py
==================
স্টাফদের জন্য Natural Language Query ফিচার — Relife Clinic OS bot-এর অংশ।

কাজ ভাগ করা আছে দুই AI-র মধ্যে:
- Grok (xAI)      -> প্রশ্ন দেখে কোন sheet লাগবে সেটা ঠিক করে
- OpenRouter       -> sheet-এর ডেটা দেখে মানুষের ভাষায় উত্তর লেখে
"""

import os
import json
import requests

import config
import sheets

GROK_API_KEY = os.environ.get("GROK_API_KEY")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

GROK_MODEL = "grok-4.3"
OPENROUTER_MODEL = "openai/gpt-4o-mini"

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


def _call_grok(prompt: str) -> str:
    resp = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROK_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_openrouter(prompt: str) -> str:
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _pick_relevant_sheet(question: str) -> str:
    catalog_text = "\n".join(
        f"- {name}: {desc}" for name, desc in SHEET_CATALOG.items()
    )
    prompt = f"""নিচে কিছু Google Sheet-এর তালিকা ও তাদের বিষয়বস্তু দেওয়া হলো:

{catalog_text}

স্টাফের প্রশ্ন: "{question}"

শুধু সবচেয়ে প্রাসঙ্গিক sheet-এর নাম লিখুন (যেমন: 06_Payments), অন্য কিছু লিখবেন না।
"""
    sheet_name = _call_grok(prompt)

    if sheet_name not in SHEET_CATALOG:
        return None
    return sheet_name


def _summarize_answer(question: str, sheet_name: str, records: list) -> str:
    data_json = json.dumps(records, ensure_ascii=False)[:8000]

    prompt = f"""আপনি একজন ক্লিনিক assistant, স্টাফকে ডেটা বুঝিয়ে বলছেন।

স্টাফের প্রশ্ন: "{question}"

"{sheet_name}" sheet থেকে প্রাসঙ্গিক ডেটা (JSON):
{data_json}

এই ডেটা বিশ্লেষণ করে প্রশ্নের সংক্ষিপ্ত, স্পষ্ট উত্তর বাংলায় দিন। সংখ্যা/টাকার
হিসাব থাকলে স্পষ্টভাবে দেখান। যদি ডেটাতে উত্তর না থাকে, সেটা সরাসরি বলুন —
অনুমান করে উত্তর বানাবেন না।
"""
    return _call_openrouter(prompt)


def answer_staff_query(question: str) -> str:
    if not GROK_API_KEY:
        return "⚠️ AI query ফিচার এখনো সেটআপ হয়নি (GROK_API_KEY নেই)।"
    if not OPENROUTER_API_KEY:
        return "⚠️ AI query ফিচার এখনো সেটআপ হয়নি (OPENROUTER_API_KEY নেই)।"

    try:
        sheet_name = _pick_relevant_sheet(question)
        if not sheet_name:
            return (
                "দুঃখিত, আপনার প্রশ্নটা কোন তথ্যের সাথে সম্পর্কিত বুঝতে "
                "পারিনি। আরেকটু স্পষ্ট করে জিজ্ঞেস করুন।"
            )

        worksheet = sheets._worksheet(getattr(config, f"SHEET_{sheet_name.split('_', 1)[1].upper()}", sheet_name))
        records = sheets.safe_get_all_records(worksheet)

        answer = _summarize_answer(question, sheet_name, records)
        return answer

    except Exception as e:
        return f"⚠️ প্রশ্নের উত্তর দিতে সমস্যা হয়েছে: {e}"
