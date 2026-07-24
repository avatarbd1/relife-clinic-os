"""
staff_ai_query.py
==================
স্টাফদের জন্য Natural Language Query ফিচার — Relife Clinic OS bot-এর অংশ।

কী করে:
- স্টাফ Telegram-এ সাধারণ ভাষায় প্রশ্ন করবে (যেমন: "গত সপ্তাহে income কত হয়েছে?")
- Gemini API প্রাইমারি হিসেবে প্রশ্নটা বুঝে, কোন sheet/data লাগবে ঠিক করে
- Gemini ব্যর্থ হলে (rate limit/error) স্বয়ংক্রিয়ভাবে Groq API fallback হিসেবে ব্যবহার হয়
- relevant sheet থেকে ডেটা টেনে এনে, একই মডেল দিয়ে মানুষের ভাষায় উত্তর তৈরি করায়
- Patient-দের কোনো access নেই এই ফিচারে — শুধু স্টাফদের জন্য

নির্ভরতা:
    pip install google-generativeai requests --break-system-packages

Environment variable লাগবে:
    export GEMINI_API_KEY="আপনার-gemini-key"
    export GROQ_API_KEY="আপনার-groq-key"     (fallback, groq.com থেকে নেওয়া)
    (Render dashboard-এর Environment Variables-এ যোগ করতে হবে)
"""

import os
import json
import requests
import google.generativeai as genai

import config
import sheets  # আপনার বিদ্যমান sheets.py — _worksheet(), safe_get_all_records()


# ---------- Gemini সেটআপ (প্রাইমারি) ----------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

GEMINI_MODEL_NAME = "gemini-flash-latest"


# ---------- Groq সেটআপ (fallback) ----------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL_NAME = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _call_gemini(prompt: str) -> str:
    model = genai.GenerativeModel(GEMINI_MODEL_NAME)
    response = model.generate_content(prompt)
    return response.text.strip()


def _call_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY সেট করা নেই")
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def _call_ai(prompt: str) -> str:
    """Gemini প্রাইমারি — ব্যর্থ হলে Groq fallback।"""
    if GEMINI_API_KEY:
        try:
            return _call_gemini(prompt)
        except Exception:
            pass  # Gemini fail করলে নিচে Groq চেষ্টা হবে
    return _call_groq(prompt)


# কোন sheet-এ কী ধরনের প্রশ্নের উত্তর পাওয়া যাবে, তার একটা ম্যাপ
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


def _pick_relevant_sheet(question: str) -> str:
    catalog_text = "\n".join(
        f"- {name}: {desc}" for name, desc in SHEET_CATALOG.items()
    )
    prompt = f"""নিচে কিছু Google Sheet-এর তালিকা ও তাদের বিষয়বস্তু দেওয়া হলো:

{catalog_text}

স্টাফের প্রশ্ন: "{question}"

শুধু সবচেয়ে প্রাসঙ্গিক sheet-এর নাম লিখুন (যেমন: 06_Payments), অন্য কিছু লিখবেন না।
"""
    sheet_name = _call_ai(prompt).strip()

    if sheet_name not in SHEET_CATALOG:
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
    return _call_ai(prompt).strip()


def answer_staff_query(question: str) -> str:
    if not GEMINI_API_KEY and not GROQ_API_KEY:
        return "⚠️ AI query ফিচার এখনো সেটআপ হয়নি (কোনো API key নেই)।"

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
