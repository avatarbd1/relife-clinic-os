"""
staff_ai_query.py
==================
স্টাফদের জন্য Natural Language Query ফিচার — Relife Clinic OS bot-এর অংশ।

কী করে:
- স্টাফ Telegram-এ সাধারণ ভাষায় প্রশ্ন করবে (যেমন: "গত সপ্তাহে income কত হয়েছে?")
- এই মডিউল Gemini API দিয়ে প্রশ্নটা বুঝে, কোন sheet/data লাগবে সেটা ঠিক করে
- relevant sheet থেকে ডেটা টেনে এনে, Gemini-কে আবার দিয়ে মানুষের ভাষায় উত্তর
  তৈরি করায়
- Patient-দের কোনো access নেই এই ফিচারে — শুধু স্টাফদের জন্য (roles.py-এর
  can_access() চেক দিয়ে আটকানো)

এই ফাইলটা আপনার প্রজেক্টের `sheets.py`/`config.py`/`roles.py`-এর পাশে বসবে,
এবং bot.py থেকে import হবে।

নির্ভরতা (নতুন করে ইনস্টল করতে হবে):
    pip install google-generativeai --break-system-packages

Environment variable লাগবে:
    export GEMINI_API_KEY="আপনার-key"
    (Render-এ deploy করলে, Render dashboard-এর Environment Variables-এ যোগ
    করতে হবে — .env ফাইলেও রাখা যায় স্থানীয় টেস্টের জন্য)
"""

import os
import json
import google.generativeai as genai

import config
import sheets  # আপনার বিদ্যমান sheets.py — _worksheet(), safe_get_all_records()


# ---------- Gemini সেটআপ ----------

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-flash-latest"  # ফ্রি tier-এ দ্রুত ও সাশ্রয়ী


# কোন sheet-এ কী ধরনের প্রশ্নের উত্তর পাওয়া যাবে, তার একটা ম্যাপ —
# এটা Gemini-কে বলে দেওয়া হবে যাতে সে সঠিক sheet বেছে নেয়
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
    """
    Gemini-কে জিজ্ঞেস করা হচ্ছে: এই প্রশ্নের উত্তর দিতে কোন sheet লাগবে?
    রিটার্ন করে sheet-এর নাম (যেমন "06_Payments")।
    """
    catalog_text = "\n".join(
        f"- {name}: {desc}" for name, desc in SHEET_CATALOG.items()
    )
    prompt = f"""নিচে কিছু Google Sheet-এর তালিকা ও তাদের বিষয়বস্তু দেওয়া হলো:

{catalog_text}

স্টাফের প্রশ্ন: "{question}"

শুধু সবচেয়ে প্রাসঙ্গিক sheet-এর নাম লিখুন (যেমন: 06_Payments), অন্য কিছু লিখবেন না।
"""
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    sheet_name = response.text.strip()

    # নিরাপত্তার জন্য যাচাই — Gemini যদি ভুল/অচেনা নাম দেয়
    if sheet_name not in SHEET_CATALOG:
        return None
    return sheet_name


def _summarize_answer(question: str, sheet_name: str, records: list) -> str:
    """
    আসল ডেটা (records) আর প্রশ্ন Gemini-কে দিয়ে মানুষের ভাষায় উত্তর তৈরি করানো।
    """
    # টোকেন খরচ কমাতে, খুব বড় ডেটাসেট হলে শুধু সাম্প্রতিক অংশ পাঠানো ভালো —
    # এখানে সরল রাখার জন্য সব পাঠানো হচ্ছে, প্রয়োজনে filter/limit যোগ করুন
    data_json = json.dumps(records, ensure_ascii=False)[:8000]  # সীমা রাখা হলো

    today_str = config.bd_now().strftime("%Y-%m-%d")
    prompt = f"""আপনি একজন ক্লিনিক assistant, স্টাফকে ডেটা বুঝিয়ে বলছেন।

আজকের তারিখ: {today_str}

স্টাফের প্রশ্ন: "{question}"

"{sheet_name}" sheet থেকে প্রাসঙ্গিক ডেটা (JSON):
{data_json}

এই ডেটা বিশ্লেষণ করে প্রশ্নের সংক্ষিপ্ত, স্পষ্ট উত্তর বাংলায় দিন। "আজকে"/"today" বা কোনো
নির্দিষ্ট দিনের কথা বললে সেটাকে উপরের আজকের তারিখের সাপেক্ষে বুঝে, ডেটার Date কলামের
সাথে মিলিয়ে ফিল্টার করে উত্তর দিন। সংখ্যা/টাকার হিসাব থাকলে স্পষ্টভাবে দেখান। যদি
ডেটাতে উত্তর না থাকে, সেটা সরাসরি বলুন — অনুমান করে উত্তর বানাবেন না।
"""
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)
    return response.text.strip()


def answer_staff_query(question: str) -> str:
    """
    মূল ফাংশন — bot.py থেকে এটা কল হবে।

    ব্যবহার (bot.py-তে):
        import staff_ai_query
        answer = staff_ai_query.answer_staff_query(user_message_text)
        await update.message.reply_text(answer)
    """
    if not GEMINI_API_KEY:
        return "⚠️ AI query ফিচার এখনো সেটআপ হয়নি (GEMINI_API_KEY নেই)।"

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


# ---------- bot.py-তে যেভাবে যুক্ত করবেন (উদাহরণ হ্যান্ডলার) ----------
"""
bot.py-তে এই অংশটা যোগ করুন (roles.py-এর can_access() প্যাটার্ন অনুসরণ করে,
শুধু staff/owner-দের জন্য, patient-দের জন্য না):

    import staff_ai_query

    async def handle_staff_ai_query(update, context):
        user_id = update.effective_user.id
        if not roles.can_access(user_id, "staff_ai_query"):  # আপনার existing
                                                                # permission
                                                                # প্যাটার্ন
                                                                # অনুযায়ী
            return  # patient হলে কিছুই হবে না, নীরবে ignore

        question = update.message.text
        await update.message.reply_text("🤔 খুঁজছি...")
        answer = staff_ai_query.answer_staff_query(question)
        await update.message.reply_text(answer)

    # main()-এ handler যোগ (উদাহরণ — একটা নির্দিষ্ট মেনু বাটনের পর free-text
    # নেওয়ার জন্য ConversationHandler বা একটা আলাদা command/state লাগবে,
    # আপনার existing reg_conv প্যাটার্ন অনুসরণ করে বসাতে হবে)
"""
