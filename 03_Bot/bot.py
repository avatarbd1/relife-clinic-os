import os
# GLOBAL-EVENTLOOP-PATCH-PY314
import asyncio as _asyncio_p314
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
_orig_gel = _asyncio_p314.get_event_loop
def _patched_gel():
    try:
        return _asyncio_p314.get_running_loop()
    except RuntimeError:
        pass
    try:
        return _orig_gel()
    except RuntimeError:
        _loop = _asyncio_p314.new_event_loop()
        _asyncio_p314.set_event_loop(_loop)
        return _loop
_asyncio_p314.get_event_loop = _patched_gel

"""
bot.py — Relife Clinic OS Telegram Bot (প্রথম ভার্সন)
"""

import logging
import re
from datetime import datetime, timedelta
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import config
import sheets
import roles

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

(
    REG_NAME,
    REG_PHONE,
    REG_PHONE_CONFIRM,
    REG_PHONE_DUP,
    REG_ADDRESS,
    REG_NOTE,
    REG_CONFIRM,
    APT_SEARCH,
    APT_SELECT,
    APT_DATE,
    APT_TIME,
    APT_THERAPIST,
    APT_CONFIRM,
) = range(13)

(
    PAY_SEARCH,
    PAY_SELECT,
    PAY_SESSION,
    PAY_AMOUNT,
    PAY_METHOD,
    PAY_CONFIRM,
) = range(13, 19)

(
    TREAT_SEARCH,
    TREAT_SELECT,
    TREAT_DIAGNOSIS,
    TREAT_GIVEN,
    TREAT_EXERCISE,
    TREAT_ELECTRO,
    TREAT_MANUAL,
    TREAT_SESSION,
    TREAT_NEXTVISIT,
    TREAT_CONFIRM,
    TREAT_REPEAT_CHOICE,
) = range(19, 30)

PAY_METHODS = ["Cash", "bKash", "Nagad", "Card"]
THERAPIST_NAMES = ["Nipa", "Saiful"]

BN_WEEKDAYS = ["সোম", "মঙ্গল", "বুধ", "বৃহঃ", "শুক্র", "শনি", "রবি"]

_ALL_MENU_ITEMS = [
    roles.MENU_HOME,
    roles.MENU_PATIENT_REG,
    roles.MENU_APPOINTMENT,
    roles.MENU_MY_PATIENTS,
    roles.MENU_TREATMENT_NOTE,
    roles.MENU_PAYMENT,
    roles.MENU_REPORTS,
    roles.MENU_SETTINGS,
    roles.MENU_ATTENDANCE,
    roles.MENU_TODAY_APPOINTMENTS,
    roles.MENU_PATIENT_HISTORY,
    roles.MENU_PATIENT_LIST,
]
_ALL_MENU_REGEX = "^(" + "|".join(re.escape(x) for x in _ALL_MENU_ITEMS) + ")$"

(
    TPLAN_SEARCH,
    TPLAN_SELECT,
    TPLAN_DIAGNOSIS,
    TPLAN_GIVEN,
    TPLAN_EXERCISE,
    TPLAN_ELECTRO,
    TPLAN_MANUAL,
    TPLAN_MACHINES,
) = range(30, 38)

MACHINE_LIST = [
    "Hot Pack", "Cold Pack",
    "TENS", "IFT",
    "Ultrasound", "SWD (Short Wave)",
    "Shockwave Therapy", "Laser Therapy",
    "Traction (Cervical)", "Traction (Lumbar)",
    "Exercise Therapy", "Manual Therapy",
    "ISTM (Myofascial Release)", "Dry Needling",
    "Wax Bath", "Cupping",
]

def _machine_keyboard(selected: set) -> InlineKeyboardMarkup:
    buttons = []
    for i in range(0, len(MACHINE_LIST), 2):
        row = []
        for j in (i, i + 1):
            if j < len(MACHINE_LIST):
                prefix = "✅ " if j in selected else "⬜ "
                row.append(InlineKeyboardButton(prefix + MACHINE_LIST[j], callback_data=f"tpm_{j}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✅ সম্পন্ন — সেভ করো", callback_data="tpdone_save")])
    buttons.append([InlineKeyboardButton("❌ বাতিল", callback_data="tpcancel_")])
    return InlineKeyboardMarkup(buttons)

def _recent_patient_keyboard(prefix: str, patients: list[dict]) -> InlineKeyboardMarkup:
    """সাম্প্রতিক রোগীর quick-pick inline buttons।"""
    buttons = [
        [
            InlineKeyboardButton(
                f"{p.get('Full_Name', 'Unknown')} ({p.get('Patient_ID', '')})",
                callback_data=f"{prefix}_{p.get('Patient_ID', '')}",
            )
        ]
        for p in patients
    ]
    buttons.append([
        InlineKeyboardButton(
            "🔎 নাম/ফোন/ID দিয়ে খুঁজি",
            callback_data=f"{prefix}_search",
        )
    ])
    return InlineKeyboardMarkup(buttons)

async def _cancel_on_menu_press(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    """কনভারসেশনের মাঝখানে অন্য মেনু বাটন চাপলে চলমান কাজ বাতিল করে দেয়,
    যাতে সেই বাটনের লেখাটা ভুল করে ফোন নম্বর/নাম হিসেবে সেভ না হয়ে যায়।"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ আগের কাজটি বাতিল করা হলো। এখন আবার সেই বাটনে চাপ দাও।"
    )
    return ConversationHandler.END

def _menu_keyboard(role_str: str) -> ReplyKeyboardMarkup:
    rows = roles.get_menu_rows_for_role(role_str)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def _date_keyboard() -> InlineKeyboardMarkup:
    today = datetime.now()
    buttons = []
    row = []
    for i in range(7):
        d = today + timedelta(days=i)
        label = d.strftime("%d %b") + f" ({BN_WEEKDAYS[d.weekday()]})"
        row.append(InlineKeyboardButton(label, callback_data=f"aptdate_{d.strftime('%Y-%m-%d')}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)

def _time_keyboard() -> InlineKeyboardMarkup:
    slots = [
        "09:00 AM", "10:00 AM", "11:00 AM",
        "12:00 PM", "01:00 PM",
        "03:00 PM", "04:00 PM", "05:00 PM",
        "06:00 PM", "07:00 PM", "08:00 PM",
    ]
    buttons = []
    row = []
    for s in slots:
        row.append(InlineKeyboardButton(s, callback_data=f"apttime_{s}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)

def _therapist_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"aptther_{name}")]
        for name in THERAPIST_NAMES
    ]
    return InlineKeyboardMarkup(buttons)

def _payment_method_keyboard() -> ReplyKeyboardMarkup:
    rows = [PAY_METHODS[i : i + 2] for i in range(0, len(PAY_METHODS), 2)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)

# QUICK-BUTTON-HELPERS
def _skip_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["-"]], resize_keyboard=True, one_time_keyboard=True)

def _number_keyboard(nums, per_row: int = 5) -> ReplyKeyboardMarkup:
    rows = [nums[i : i + per_row] for i in range(0, len(nums), per_row)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)

async def _require_staff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    staff = sheets.get_staff_by_telegram_id(telegram_id)
    if staff is None:
        await update.effective_message.reply_text(
            "❌ তোমাকে সিস্টেমে স্টাফ হিসেবে খুঁজে পাওয়া যায়নি।\n"
            f"তোমার Telegram ID: {telegram_id}\n"
            "এই ID-টা ক্লিনিক ম্যানেজারকে দাও, তিনি 08_Staff শীটে যোগ করে দেবেন।"
        )
        return None
    return staff

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    context.user_data["staff"] = staff
    role = staff.get("Role", "")
    name = staff.get("Full_Name", "")
    await update.message.reply_text(
        f"স্বাগতম, {name}! ({role})\nনিচের মেনু থেকে বেছে নাও 👇",
        reply_markup=_menu_keyboard(role),
    )

async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    role = staff.get("Role", "")
    name = staff.get("Full_Name", "")
    await update.message.reply_text(
        f"স্বাগতম, {name}! ({role})\nনিচের মেনু থেকে বেছে নাও 👇",
        reply_markup=_menu_keyboard(role),
    )

async def my_patients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    if not roles.can_access(staff.get("Role", ""), roles.MENU_MY_PATIENTS):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    patients = sheets.get_patients_for_therapist(staff.get("Full_Name", ""))
    if not patients:
        await update.message.reply_text("তোমার নামে এখনো কোনো assigned patient নেই।")
        return
    lines = ["🧑‍⚕️ তোমার Assigned Patients:\n"]
    for p in patients:
        lines.append(
            f"• {p.get('Patient_ID')} — {p.get('Full_Name')} "
            f"| {p.get('Diagnosis', 'N/A')} | পরবর্তী ভিজিট: {p.get('Next_Visit', 'N/A')}"
        )
    await update.message.reply_text("\n".join(lines))

# ---------- রোগী রেজিস্ট্রেশন ----------

async def reg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_PATIENT_REG):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["new_patient"] = {}
    await update.message.reply_text(
        "নতুন রোগীর পূর্ণ নাম লেখো:", reply_markup=ReplyKeyboardRemove()
    )
    return REG_NAME

async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_patient"]["Full_Name"] = update.message.text.strip()
    await update.message.reply_text("ফোন নম্বর লেখো:")
    return REG_PHONE

async def reg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data["_phone_pending"] = phone
    await update.message.reply_text("ফোন নম্বরটা আবার লেখো (নিশ্চিত করার জন্য):")
    return REG_PHONE_CONFIRM

async def reg_phone_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    typed_again = update.message.text.strip()
    pending = context.user_data.get("_phone_pending", "")
    if typed_again != pending:
        await update.message.reply_text(
            "⚠️ দুইবার লেখা নম্বর মেলেনি। আবার প্রথম থেকে ফোন নম্বর লেখো:"
        )
        return REG_PHONE

    phone = pending
    context.user_data["new_patient"]["Phone"] = phone
    existing = sheets.find_patient_by_phone(phone)
    if existing:
        dup_keyboard = ReplyKeyboardMarkup(
            [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            "⚠️ এই ফোন নম্বরে ইতিমধ্যে রোগী আছে:\n"
            f"নাম: {existing.get('Full_Name')}\n"
            f"Patient ID: {existing.get('Patient_ID')}\n\n"
            "তবুও কি নতুন করে রেজিস্ট্রেশন করবে?",
            reply_markup=dup_keyboard,
        )
        return REG_PHONE_DUP
    await update.message.reply_text("ঠিকানা লেখো:", reply_markup=ReplyKeyboardRemove())
    return REG_ADDRESS

async def reg_phone_dup_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        await update.message.reply_text("ঠিকানা লেখো:", reply_markup=ReplyKeyboardRemove())
        return REG_ADDRESS
    context.user_data.pop("new_patient", None)
    await update.message.reply_text(
        "❌ ডুপ্লিকেট এড়াতে রেজিস্ট্রেশন বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END

async def reg_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_patient"]["Address"] = update.message.text.strip()
    await update.message.reply_text(
        "সমস্যা/বয়স/অন্য কিছু থাকলে এক লাইনে লেখো (না থাকলে - দাও):",
        reply_markup=_skip_keyboard(),
    )
    return REG_NOTE

async def reg_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    context.user_data["new_patient"]["Diagnosis"] = "" if note == "-" else note
    p = context.user_data["new_patient"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"নাম: {p['Full_Name']}\nফোন: {p['Phone']}\nঠিকানা: {p['Address']}\n"
        f"নোট: {p['Diagnosis'] or '-'}\n\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(summary, reply_markup=confirm_keyboard)
    return REG_CONFIRM

async def reg_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        patient_id = sheets.add_patient(
            context.user_data["new_patient"],
            created_by=staff.get("Full_Name", "Unknown"),
        )
        await update.message.reply_text(
            f"✅ রোগী রেজিস্ট্রেশন সম্পন্ন! Patient ID: {patient_id}",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    else:
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    context.user_data.pop("new_patient", None)
    return ConversationHandler.END

async def reg_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("new_patient", None)
    await update.message.reply_text(
        "রেজিস্ট্রেশন বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END

# ---------- অ্যাপয়েন্টমেন্ট বুকিং ----------

async def apt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_APPOINTMENT):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["new_appointment"] = {}
    await update.message.reply_text(
        "রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return APT_SEARCH

async def apt_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = sheets.search_patients(query)
    if not results:
        await update.message.reply_text(
            "❌ কোনো রোগী পাওয়া যায়নি। আবার নাম/ফোন/আইডি লেখো, অথবা /cancel দাও।"
        )
        return APT_SEARCH

    results = results[:10]
    context.user_data["apt_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    lines = ["🔍 ফলাফল — সঠিক Patient ID লিখো:\n"]
    for p in results:
        lines.append(
            f"• {p.get('Patient_ID')} — {p.get('Full_Name')} | {p.get('Phone')}"
        )
    await update.message.reply_text("\n".join(lines))
    return APT_SELECT

async def apt_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    results = context.user_data.get("apt_search_results", {})
    patient = results.get(text)
    if not patient:
        await update.message.reply_text(
            "❌ তালিকা থেকে সঠিক Patient ID লেখো (উদাহরণ: PT0001), অথবা /cancel দাও।"
        )
        return APT_SELECT
    context.user_data["new_appointment"]["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["new_appointment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data["new_appointment"]["Department"] = patient.get("Department", "")
    context.user_data.pop("apt_search_results", None)
    await update.message.reply_text(
        f"রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})\n\n"
        "তারিখ বেছে নাও (অথবা টাইপ করো, উদাহরণ: 2026-07-15):",
        reply_markup=_date_keyboard(),
    )
    return APT_DATE

async def apt_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.replace("aptdate_", "")
    context.user_data.setdefault("new_appointment", {})["Date"] = date_str
    await query.edit_message_text(f"✅ তারিখ নির্বাচন করা হয়েছে: {date_str}")
    await query.message.reply_text(
        "সময় বেছে নাও (অথবা টাইপ করো):", reply_markup=_time_keyboard()
    )
    return APT_TIME

async def apt_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Date"] = update.message.text.strip()
    await update.message.reply_text(
        "সময় বেছে নাও (অথবা টাইপ করো):", reply_markup=_time_keyboard()
    )
    return APT_TIME

async def apt_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_str = query.data.replace("apttime_", "")
    context.user_data.setdefault("new_appointment", {})["Time"] = time_str
    await query.edit_message_text(f"✅ সময় নির্বাচন করা হয়েছে: {time_str}")
    await query.message.reply_text(
        "থেরাপিস্ট বেছে নাও (অথবা টাইপ করো):",
        reply_markup=_therapist_keyboard(),
    )
    return APT_THERAPIST

async def apt_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Time"] = update.message.text.strip()
    await update.message.reply_text(
        "থেরাপিস্ট বেছে নাও (অথবা টাইপ করো):",
        reply_markup=_therapist_keyboard(),
    )
    return APT_THERAPIST

async def apt_therapist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Therapist"] = update.message.text.strip()
    a = context.user_data["new_appointment"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"রোগী: {a['Patient_Name']} ({a['Patient_ID']})\n"
        f"Department: {a['Department']}\n"
        f"তারিখ: {a['Date']}\nসময়: {a['Time']}\n"
        f"থেরাপিস্ট: {a['Therapist']}\n\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(summary, reply_markup=confirm_keyboard)
    return APT_CONFIRM

async def apt_therapist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    therapist_name = query.data.replace("aptther_", "")
    context.user_data["new_appointment"]["Therapist"] = therapist_name
    a = context.user_data["new_appointment"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"রোগী: {a['Patient_Name']} ({a['Patient_ID']})\n"
        f"Department: {a['Department']}\n"
        f"তারিখ: {a['Date']}\nসময়: {a['Time']}\n"
        f"থেরাপিস্ট: {a['Therapist']}\n\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await query.edit_message_text(f"✅ থেরাপিস্ট নির্বাচন করা হয়েছে: {therapist_name}")
    await query.message.reply_text(summary, reply_markup=confirm_keyboard)
    return APT_CONFIRM

async def apt_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        appointment_id = sheets.add_appointment(
            context.user_data["new_appointment"],
            created_by=staff.get("Full_Name", "Unknown"),
        )
        await update.message.reply_text(
            f"✅ অ্যাপয়েন্টমেন্ট বুক হয়েছে! Appointment ID: {appointment_id}",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    else:
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    context.user_data.pop("new_appointment", None)
    return ConversationHandler.END

async def apt_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("new_appointment", None)
    context.user_data.pop("apt_search_results", None)
    await update.effective_message.reply_text(
        "অ্যাপয়েন্টমেন্ট বুকিং বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END

async def search_patient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else None
    if not query:
        await update.message.reply_text("ব্যবহার: /search <নাম বা ফোন নম্বর>")
        return
    results = sheets.search_patients(query)
    if not results:
        await update.message.reply_text("কোনো রোগী পাওয়া যায়নি।")
        return
    lines = [f"🔍 '{query}' এর ফলাফল ({len(results)} জন):\n"]
    for p in results[:15]:
        lines.append(f"• {p.get('Patient_ID')} — {p.get('Full_Name')} | {p.get('Phone')}")
    await update.message.reply_text("\n".join(lines))

# ---------- হাজিরা (স্টাফ) ----------

async def attendance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    if not roles.can_access(staff.get("Role", ""), roles.MENU_ATTENDANCE):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    staff_id = staff.get("Staff_ID", "") or str(staff.get("Telegram_ID", ""))
    date_str = datetime.now().strftime("%Y-%m-%d")
    record = sheets.get_today_attendance(staff_id, date_str)

    buttons = []
    if not record:
        buttons.append([InlineKeyboardButton("✅ Check In", callback_data="att_checkin")])
        status_line = "🟡 এখনো Check In করোনি।"
    elif not record.get("Break_Out"):
        buttons.append([InlineKeyboardButton("☕ Break Out", callback_data="att_breakout")])
        buttons.append([InlineKeyboardButton("🚪 Check Out", callback_data="att_checkout")])
        status_line = f"🟢 Check In: {record.get('Check_In')}"
    elif not record.get("Break_In"):
        buttons.append([InlineKeyboardButton("🔙 Break In", callback_data="att_breakin")])
        status_line = f"☕ Break Out: {record.get('Break_Out')}"
    elif not record.get("Check_Out"):
        buttons.append([InlineKeyboardButton("🚪 Check Out", callback_data="att_checkout")])
        status_line = f"🔙 Break In: {record.get('Break_In')}"
    else:
        await update.message.reply_text(
            f"✅ আজকের হাজিরা সম্পন্ন।\n"
            f"Check In: {record.get('Check_In')}\nCheck Out: {record.get('Check_Out')}\n"
            f"মোট কাজের সময়: {record.get('Working_Hours')} ঘণ্টা"
        )
        return

    await update.message.reply_text(status_line, reply_markup=InlineKeyboardMarkup(buttons))

async def attendance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff") or sheets.get_staff_by_telegram_id(update.effective_user.id)
    if staff is None:
        await query.edit_message_text("❌ স্টাফ তথ্য পাওয়া যায়নি।")
        return
    staff_id = staff.get("Staff_ID", "") or str(staff.get("Telegram_ID", ""))
    date_str = datetime.now().strftime("%Y-%m-%d")
    action = query.data

    if action == "att_checkin":
        time_str = sheets.attendance_check_in(staff)
        await query.edit_message_text(f"✅ Check In হয়েছে: {time_str}")
    elif action == "att_breakout":
        time_str = sheets.attendance_break_out(staff_id, date_str)
        await query.edit_message_text(f"☕ Break শুরু: {time_str}" if time_str else "❌ আজকের রেকর্ড পাওয়া যায়নি।")
    elif action == "att_breakin":
        time_str = sheets.attendance_break_in(staff_id, date_str)
        await query.edit_message_text(f"🔙 Break শেষ: {time_str}" if time_str else "❌ আজকের রেকর্ড পাওয়া যায়নি।")
    elif action == "att_checkout":
        result = sheets.attendance_check_out(staff_id, date_str)
        if result:
            await query.edit_message_text(
                f"🚪 Check Out হয়েছে: {result['time']}\n"
                f"মোট কাজের সময়: {result['working_hours']} ঘণ্টা\n"
                f"ওভারটাইম: {result['overtime']} ঘণ্টা"
            )
        else:
            await query.edit_message_text("❌ আজকের রেকর্ড পাওয়া যায়নি।")

# ---------- আজকের অ্যাপয়েন্টমেন্ট (রোগীর ভিজিট হাজিরা) ----------

async def today_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    if not roles.can_access(staff.get("Role", ""), roles.MENU_TODAY_APPOINTMENTS):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    date_str = datetime.now().strftime("%Y-%m-%d")
    appts = [
        a for a in sheets.get_appointments_for_date(date_str)
        if a.get("Status", "").strip() == "Scheduled"
    ]
    if not appts:
        await update.message.reply_text("আজ কোনো পেন্ডিং অ্যাপয়েন্টমেন্ট নেই।")
        return
    for a in appts:
        text = (
            f"🕐 {a.get('Time')} — {a.get('Patient_Name')} ({a.get('Patient_ID')})\n"
            f"Department: {a.get('Department')} | থেরাপিস্ট: {a.get('Therapist')}"
        )
        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ উপস্থিত", callback_data=f"aptstatus_{a.get('Appointment_ID')}_Completed"),
            InlineKeyboardButton("❌ আসেনি", callback_data=f"aptstatus_{a.get('Appointment_ID')}_NoShow"),
        ]])
        await update.message.reply_text(text, reply_markup=buttons)

async def apt_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, appointment_id, status_code = query.data.split("_", 2)
    status_map = {"Completed": "Completed", "NoShow": "No-show"}
    status = status_map.get(status_code, status_code)
    ok = sheets.update_appointment_status(appointment_id, status)
    if ok:
        await query.edit_message_text(f"✅ {appointment_id} — স্ট্যাটাস: {status}")
    else:
        await query.edit_message_text("❌ আপডেট করা যায়নি।")

# ---------- পেমেন্ট / বিল এন্ট্রি ----------

async def pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_PAYMENT):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["payment"] = {}
    await update.message.reply_text(
        "রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return PAY_SEARCH

async def pay_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = sheets.search_patients(query)
    if not results:
        await update.message.reply_text(
            "❌ কোনো রোগী পাওয়া যায়নি। আবার নাম/ফোন/আইডি লেখো, অথবা /cancel দাও।"
        )
        return PAY_SEARCH

    results = results[:10]
    context.user_data["pay_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
            callback_data=f"paysel_{p.get('Patient_ID')}",
        )]
        for p in results
    ]
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return PAY_SELECT

async def pay_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("paysel_", "")
    results = context.user_data.get("pay_search_results", {})
    patient = results.get(patient_id)
    if not patient:
        await query.edit_message_text(
            "❌ তালিকার মেয়াদ শেষ। আবার শুরু করতে /cancel দাও, তারপর 💳 পেমেন্ট তথ্য চাপো।"
        )
        return ConversationHandler.END
    context.user_data.setdefault("payment", {})["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["payment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data["payment"]["Department"] = patient.get("Department", "")
    context.user_data.pop("pay_search_results", None)

    total_bill = patient.get("Total_Bill", 0) or 0
    paid_amount = patient.get("Paid_Amount", 0) or 0
    due_amount = patient.get("Due_Amount", 0) or 0
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})\n\n"
        f"মোট বিল: {total_bill}\nজমা হয়েছে: {paid_amount}\nবাকি: {due_amount}"
    )
    await query.message.reply_text(
        "আজ কয়টা সেশন হলো লেখো (না থাকলে 0):",
        reply_markup=_number_keyboard([str(n) for n in range(0, 6)]),
    )
    return PAY_SESSION

async def pay_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    results = context.user_data.get("pay_search_results", {})
    patient = results.get(text)
    if not patient:
        await update.message.reply_text(
            "❌ উপরের তালিকা থেকে একটা বাটনে ট্যাপ করো, অথবা /cancel দাও।"
        )
        return PAY_SELECT
    context.user_data["payment"]["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["payment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data["payment"]["Department"] = patient.get("Department", "")
    context.user_data.pop("pay_search_results", None)

    total_bill = patient.get("Total_Bill", 0) or 0
    paid_amount = patient.get("Paid_Amount", 0) or 0
    due_amount = patient.get("Due_Amount", 0) or 0
    await update.message.reply_text(
        f"রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})\n\n"
        f"মোট বিল: {total_bill}\nজমা হয়েছে: {paid_amount}\nবাকি: {due_amount}\n\n"
        "আজ কয়টা সেশন হলো লেখো (না থাকলে 0):"
    )
    return PAY_SESSION

async def pay_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        sessions = int(text)
        if sessions < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ শুধু সংখ্যা লেখো (উদাহরণ: 1), অথবা 0 লেখো।")
        return PAY_SESSION
    context.user_data["payment"]["Sessions"] = sessions
    await update.message.reply_text("কত টাকা নেওয়া হলো লেখো (শুধু সংখ্যা):")
    return PAY_AMOUNT

async def pay_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(",", "")
    try:
        amount = float(text)
        if amount < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ শুধু সংখ্যা লেখো (উদাহরণ: 200), অথবা 0 লেখো।")
        return PAY_AMOUNT
    context.user_data["payment"]["Amount"] = amount
    await update.message.reply_text(
        "Payment Method বেছে নাও:", reply_markup=_payment_method_keyboard()
    )
    return PAY_METHOD

async def pay_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    method = update.message.text.strip()
    if method not in PAY_METHODS:
        await update.message.reply_text(
            "❌ তালিকা থেকে একটা Method বেছে নাও:", reply_markup=_payment_method_keyboard()
        )
        return PAY_METHOD
    context.user_data["payment"]["Payment_Method"] = method
    p = context.user_data["payment"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"রোগী: {p['Patient_Name']} ({p['Patient_ID']})\n"
        f"সেশন: {p['Sessions']}\nটাকা: {p['Amount']}\nMethod: {p['Payment_Method']}\n\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(summary, reply_markup=confirm_keyboard)
    return PAY_CONFIRM

async def pay_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    p = context.user_data.get("payment", {})

    if text not in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        context.user_data.pop("payment", None)
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।", reply_markup=_menu_keyboard(staff.get("Role", ""))
        )
        return ConversationHandler.END

    patient_id = p.get("Patient_ID", "")
    amount = p.get("Amount", 0)
    sessions = p.get("Sessions", 0)

    try:
        bill_status = sheets.update_patient_payment(patient_id, amount, discount=0)

        receipt_no = sheets.add_payment({
            "Patient_ID": patient_id,
            "Patient_Name": p.get("Patient_Name", ""),
            "Department": p.get("Department", ""),
            "Amount": amount,
            "Discount": 0,
            "Due": bill_status["due_amount"] if bill_status else "",
            "Payment_Method": p.get("Payment_Method", ""),
            "Received_By": staff.get("Full_Name", "Unknown"),
            "Remarks": f"Sessions: {sessions}" if sessions else "",
        })

        if sessions > 0:
            for _ in range(sessions):
                sheets.increment_package_session(patient_id)

        lines = [
            f"✅ পেমেন্ট সেভ হয়েছে! Receipt No: {receipt_no}",
            f"রোগী: {p.get('Patient_Name')} ({patient_id})",
            f"জমা নেওয়া হলো: {amount} ({p.get('Payment_Method')})",
        ]
        if bill_status:
            lines.append(f"মোট জমা: {bill_status['paid_amount']} | বাকি: {bill_status['due_amount']}")

        await update.message.reply_text(
            "\n".join(lines), reply_markup=_menu_keyboard(staff.get("Role", ""))
        )
    except Exception as e:
        logger.exception("pay_confirm ব্যর্থ হয়েছে")
        await update.message.reply_text(
            f"❌ পেমেন্ট সেভ করতে সমস্যা হয়েছে।\nError: {e}\n\n"
            "স্ক্রিনশট দিয়ে জানাও, ঠিক করে দেওয়া হবে।",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    context.user_data.pop("payment", None)
    return ConversationHandler.END

async def pay_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("payment", None)
    context.user_data.pop("pay_search_results", None)
    await update.effective_message.reply_text(
        "পেমেন্ট এন্ট্রি বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END

# ---------- ট্রিটমেন্ট নোট (Physio SOAP-স্টাইল) ----------

async def treat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Phase B: recent-patient quick-pick সহ ট্রিটমেন্ট নোট শুরু।"""
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_TREATMENT_NOTE):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END

    context.user_data["treatment"] = {}
    context.user_data.pop("treat_search_results", None)
    context.user_data.pop("treat_recent_map", None)
    context.user_data.pop("treatment_snapshot", None)
    context.user_data.pop("treatment_selected_machines", None)
    context.user_data.pop("treatment_edit_mode", None)

    therapist_name = staff.get("Full_Name") if staff.get("Role") == "Therapist" else None
    recent = sheets.get_recent_patients(limit=6, therapist_name=therapist_name)
    if recent:
        context.user_data["treat_recent_map"] = {
            p.get("Patient_ID", "").strip(): p for p in recent
        }
        await update.message.reply_text(
            "🧑‍⚕️ সাম্প্রতিক রোগী (ট্যাপ করো বা নিচে খুঁজো):",
            reply_markup=_recent_patient_keyboard("trecentsel", recent),
        )
        return TREAT_SELECT

    await update.message.reply_text(
        "রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return TREAT_SEARCH

async def treat_recent_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Phase B: recent-patient quick-pick inline button callback।"""
    query = update.callback_query
    await query.answer()

    if query.data == "trecentsel_search":
        await query.edit_message_text("রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো:")
        return TREAT_SEARCH

    patient_id = query.data.replace("trecentsel_", "")
    recent_map = context.user_data.get("treat_recent_map", {})
    patient = recent_map.get(patient_id) or sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি। আবার চেষ্টা করো।")
        return TREAT_SEARCH

    context.user_data["treatment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
    }
    context.user_data.pop("treat_recent_map", None)
    return await _treat_after_patient_selected(query, context, patient)

async def treat_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = sheets.search_patients(query)
    if not results:
        await update.message.reply_text(
            "❌ কোনো রোগী পাওয়া যায়নি। আবার নাম/ফোন/আইডি লেখো, অথবা /cancel দাও।"
        )
        return TREAT_SEARCH

    results = results[:10]
    context.user_data["treat_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    buttons = [
        [
            InlineKeyboardButton(
                f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
                callback_data=f"treatsel_{p.get('Patient_ID')}",
            )
        ]
        for p in results
    ]
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return TREAT_SELECT

async def treat_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Phase C: রোগী select হলে follow-up vs first-visit branch।"""
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("treatsel_", "")
    results = context.user_data.get("treat_search_results", {})
    patient = results.get(patient_id)
    if not patient:
        await query.edit_message_text(
            "❌ তালিকার মেয়াদ শেষ। আবার শুরু করতে /cancel দাও।"
        )
        return ConversationHandler.END

    context.user_data["treatment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
    }
    context.user_data.pop("treat_search_results", None)
    return await _treat_after_patient_selected(query, context, patient)

async def _treat_after_patient_selected(query_or_msg, context, patient: dict):
    """
    রোগী select হওয়ার পর follow-up branch দেখায়।
    query_or_msg হয় CallbackQuery অথবা message-like object।
    """
    pid = patient.get("Patient_ID", "")
    t = context.user_data.setdefault("treatment", {})
    t["Patient_ID"] = pid
    t["Patient_Name"] = patient.get("Full_Name", "")
    t["Session_No"] = str(sheets.get_next_session_no(pid))

    snapshot = sheets.get_last_treatment_snapshot(pid)
    selected: set[int] = set()
    if snapshot:
        prev_machines = [
            m.strip()
            for m in str(snapshot.get("Machines", "")).split(",")
            if m.strip()
        ]
        selected = {
            idx for idx, name in enumerate(MACHINE_LIST) if name in prev_machines
        }
        context.user_data["treatment_snapshot"] = snapshot
    else:
        context.user_data.pop("treatment_snapshot", None)
    context.user_data["treatment_selected_machines"] = selected
    context.user_data.pop("treatment_edit_mode", None)

    is_callback = hasattr(query_or_msg, "edit_message_text")

    async def _edit(text: str):
        if is_callback:
            await query_or_msg.edit_message_text(text)

    async def _reply(text: str, **kwargs):
        if is_callback:
            await query_or_msg.message.reply_text(text, **kwargs)
        else:
            await query_or_msg.reply_text(text, **kwargs)

    if snapshot:
        next_session = t.get("Session_No", "")
        summary_lines = [
            f"📜 আগের ভিজিটের সারাংশ ({snapshot.get('Date', 'N/A')}):",
            "",
            f"• সমস্যা: {snapshot.get('Diagnosis') or '-'}",
            f"• ট্রিটমেন্ট: {snapshot.get('Treatment_Given') or '-'}",
            f"• এক্সারসাইজ: {snapshot.get('Exercise') or '-'}",
            f"• ইলেক্ট্রো: {snapshot.get('Electrotherapy') or '-'}",
            f"• ম্যানুয়াল: {snapshot.get('Manual_Therapy') or '-'}",
            f"• মেশিন: {snapshot.get('Machines') or '-'}",
            "",
            f"📌 পরবর্তী Session #{next_session} (অটো)",
            "",
            "এই সেশনে কী করবে?",
        ]
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ গতকালের মতোই", callback_data="treat_repeat_yes")],
            [InlineKeyboardButton("✏️ পরিবর্তন করবো", callback_data="treat_repeat_edit")],
            [InlineKeyboardButton("🔎 অন্য রোগী", callback_data="treat_repeat_research")],
        ])
        await _edit(f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({pid})")
        await _reply("\n".join(summary_lines), reply_markup=keyboard)
        return TREAT_REPEAT_CHOICE

    await _edit(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({pid})\n(প্রথম ভিজিট)"
    )
    await _reply("আজকের সমস্যা/পর্যবেক্ষণ (Diagnosis) লেখো:")
    return TREAT_DIAGNOSIS

async def treat_repeat_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Phase C: "✅ গতকালের মতোই" / "✏️ পরিবর্তন করবো" / "🔎 অন্য রোগী" handle করে।
    """
    query = update.callback_query
    await query.answer()
    choice = query.data.replace("treat_repeat_", "")
    t = context.user_data.setdefault("treatment", {})
    snapshot = context.user_data.get("treatment_snapshot", {}) or {}
    selected = context.user_data.get("treatment_selected_machines", set())

    if choice == "research":
        context.user_data.pop("treatment", None)
        context.user_data.pop("treatment_snapshot", None)
        context.user_data.pop("treatment_selected_machines", None)
        context.user_data.pop("treatment_edit_mode", None)
        await query.edit_message_text("আবার রোগী খুঁজছো…")
        await query.message.reply_text(
            "রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return TREAT_SEARCH

    if choice == "yes":
        t["Diagnosis"] = snapshot.get("Diagnosis", "")
        t["Treatment_Given"] = snapshot.get("Treatment_Given", "")
        t["Exercise"] = snapshot.get("Exercise", "")
        t["Electrotherapy"] = snapshot.get("Electrotherapy", "")
        t["Manual_Therapy"] = snapshot.get("Manual_Therapy", "")
        t["Machines"] = ", ".join(MACHINE_LIST[i] for i in sorted(selected))
        t["_via_repeat"] = True
        await query.edit_message_text(
            f"✅ গতকালের মতোই reuse হয়েছে। Session #{t.get('Session_No', 'N/A')}"
        )
        summary = (
            "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
            f"রোগী: {t.get('Patient_Name', '')} ({t.get('Patient_ID', '')})\n"
            f"সমস্যা: {t.get('Diagnosis') or '-'}\n"
            f"ট্রিটমেন্ট: {t.get('Treatment_Given') or '-'}\n"
            f"এক্সারসাইজ: {t.get('Exercise') or '-'}\n"
            f"ইলেক্ট্রো: {t.get('Electrotherapy') or '-'}\n"
            f"ম্যানুয়াল: {t.get('Manual_Therapy') or '-'}\n"
            f"মেশিন: {t.get('Machines') or '-'}\n"
            f"সেশন নম্বর: {t.get('Session_No') or '-'}\n\n"
            "ঠিক থাকলে 'হ্যাঁ' লেখো।"
        )
        confirm_kb = ReplyKeyboardMarkup(
            [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
        )
        await query.message.reply_text(summary, reply_markup=confirm_kb)
        return TREAT_CONFIRM

    t["Diagnosis"] = snapshot.get("Diagnosis", "")
    t["Treatment_Given"] = snapshot.get("Treatment_Given", "")
    t["Exercise"] = snapshot.get("Exercise", "")
    t["Electrotherapy"] = snapshot.get("Electrotherapy", "")
    t["Manual_Therapy"] = snapshot.get("Manual_Therapy", "")
    t["Machines"] = ", ".join(MACHINE_LIST[i] for i in sorted(selected))
    context.user_data["treatment_edit_mode"] = True
    await query.edit_message_text(
        "✏️ আগের তথ্য লোড হয়েছে। নতুন Diagnosis লেখো (আগেরটা রাখতে '-' দাও):"
    )
    return TREAT_DIAGNOSIS

async def treat_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    edit_mode = bool(context.user_data.get("treatment_edit_mode"))
    if not (edit_mode and text == "-"):
        context.user_data["treatment"]["Diagnosis"] = text
    prompt = "আজ কী ট্রিটমেন্ট দেওয়া হলো লেখো"
    if edit_mode:
        prompt += " (আগেরটা রাখতে - দাও)"
    await update.message.reply_text(prompt + ":")
    return TREAT_GIVEN

async def treat_given(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    edit_mode = bool(context.user_data.get("treatment_edit_mode"))
    if not (edit_mode and text == "-"):
        context.user_data["treatment"]["Treatment_Given"] = text
    prompt = "এক্সারসাইজ প্ল্যান লেখো"
    if edit_mode:
        prompt += " (আগেরটা রাখতে - দাও)"
    else:
        prompt += " (না থাকলে - দাও)"
    await update.message.reply_text(prompt + ":", reply_markup=_skip_keyboard())
    return TREAT_EXERCISE

async def treat_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    edit_mode = bool(context.user_data.get("treatment_edit_mode"))
    if edit_mode:
        if text != "-":
            context.user_data["treatment"]["Exercise"] = text
    else:
        context.user_data["treatment"]["Exercise"] = "" if text == "-" else text
    prompt = "ইলেক্ট্রোথেরাপি মোডালিটি লেখো"
    if edit_mode:
        prompt += " (আগেরটা রাখতে - দাও)"
    else:
        prompt += " (না থাকলে - দাও)"
    await update.message.reply_text(prompt + ":", reply_markup=_skip_keyboard())
    return TREAT_ELECTRO

async def treat_electro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    edit_mode = bool(context.user_data.get("treatment_edit_mode"))
    if edit_mode:
        if text != "-":
            context.user_data["treatment"]["Electrotherapy"] = text
    else:
        context.user_data["treatment"]["Electrotherapy"] = "" if text == "-" else text
    prompt = "ম্যানুয়াল থেরাপি টেকনিক লেখো"
    if edit_mode:
        prompt += " (আগেরটা রাখতে - দাও)"
    else:
        prompt += " (না থাকলে - দাও)"
    await update.message.reply_text(prompt + ":", reply_markup=_skip_keyboard())
    return TREAT_MANUAL

async def treat_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    edit_mode = bool(context.user_data.get("treatment_edit_mode"))
    if edit_mode:
        if text != "-":
            context.user_data["treatment"]["Manual_Therapy"] = text
    else:
        context.user_data["treatment"]["Manual_Therapy"] = "" if text == "-" else text

    selected = context.user_data.get("treatment_selected_machines", set())
    await update.message.reply_text(
        "আজকের মেশিন/মোডালিটি বেছে নাও (✅ toggle), সব শেষে 'সম্পন্ন' চাপো:",
        reply_markup=_machine_keyboard(selected),
    )
    return TREAT_SESSION

async def treat_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Machine selection state-এ text এলে user-কে button use করতে বলে।"""
    await update.message.reply_text(
        "উপরে থাকা মেশিন বাটনগুলো ব্যবহার করো, তারপর 'সম্পন্ন' চাপো।"
    )
    return TREAT_SESSION

async def treat_machine_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.replace("tpm_", ""))
    selected = context.user_data.get("treatment_selected_machines", set())
    if idx in selected:
        selected.discard(idx)
    else:
        selected.add(idx)
    context.user_data["treatment_selected_machines"] = selected
    await query.edit_message_reply_markup(reply_markup=_machine_keyboard(selected))
    return TREAT_SESSION

async def treat_machine_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    t = context.user_data.setdefault("treatment", {})
    selected = context.user_data.get("treatment_selected_machines", set())
    t["Machines"] = ", ".join(MACHINE_LIST[i] for i in sorted(selected))
    if not str(t.get("Session_No", "")).strip():
        t["Session_No"] = str(sheets.get_next_session_no(t.get("Patient_ID", "")))
    await query.edit_message_text(
        f"✅ মেশিন নির্বাচন সম্পন্ন: {t.get('Machines') or '(কিছু বাছাই করা হয়নি)'}"
    )
    await query.message.reply_text(
        "পরবর্তী ভিজিটের তারিখ লেখো (YYYY-MM-DD, না থাকলে - দাও):",
        reply_markup=_skip_keyboard(),
    )
    return TREAT_NEXTVISIT

async def treat_machine_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_search_results", None)
    context.user_data.pop("treat_recent_map", None)
    context.user_data.pop("treatment_snapshot", None)
    context.user_data.pop("treatment_selected_machines", None)
    context.user_data.pop("treatment_edit_mode", None)
    await query.edit_message_text("❌ ট্রিটমেন্ট নোট এন্ট্রি বাতিল করা হয়েছে।")
    await query.message.reply_text(
        "ট্রিটমেন্ট নোট এন্ট্রি বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END

async def treat_nextvisit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["treatment"]["Next_Visit"] = "" if text == "-" else text
    t = context.user_data["treatment"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"রোগী: {t['Patient_Name']} ({t['Patient_ID']})\n"
        f"সমস্যা: {t.get('Diagnosis') or '-'}\n"
        f"ট্রিটমেন্ট: {t.get('Treatment_Given') or '-'}\n"
        f"এক্সারসাইজ: {t.get('Exercise') or '-'}\n"
        f"ইলেক্ট্রোথেরাপি: {t.get('Electrotherapy') or '-'}\n"
        f"ম্যানুয়াল থেরাপি: {t.get('Manual_Therapy') or '-'}\n"
        f"মেশিন: {t.get('Machines') or '-'}\n"
        f"সেশন নম্বর: {t.get('Session_No') or '-'}\n"
        f"পরবর্তী ভিজিট: {t.get('Next_Visit') or '-'}\n\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(summary, reply_markup=confirm_keyboard)
    return TREAT_CONFIRM

async def treat_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    t = context.user_data.get("treatment", {})

    if text not in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        context.user_data.pop("treatment", None)
        context.user_data.pop("treat_search_results", None)
        context.user_data.pop("treat_recent_map", None)
        context.user_data.pop("treatment_snapshot", None)
        context.user_data.pop("treatment_selected_machines", None)
        context.user_data.pop("treatment_edit_mode", None)
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।", reply_markup=_menu_keyboard(staff.get("Role", ""))
        )
        return ConversationHandler.END

    try:
        if not str(t.get("Session_No", "")).strip():
            t["Session_No"] = str(sheets.get_next_session_no(t.get("Patient_ID", "")))

        treatment_id = sheets.add_treatment_note(
            t, created_by=staff.get("Full_Name", "Unknown")
        )
        next_visit = t.get("Next_Visit", "")
        if next_visit:
            sheets.update_next_visit(t.get("Patient_ID", ""), next_visit)
        await update.message.reply_text(
            f"✅ ট্রিটমেন্ট নোট সেভ হয়েছে! Treatment ID: {treatment_id}",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    except Exception as e:
        logger.exception("treat_confirm ব্যর্থ হয়েছে")
        await update.message.reply_text(
            f"❌ নোট সেভ করতে সমস্যা হয়েছে।\nError: {e}\n\n"
            "স্ক্রিনশট দিয়ে জানাও, ঠিক করে দেওয়া হবে।",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )

    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_search_results", None)
    context.user_data.pop("treat_recent_map", None)
    context.user_data.pop("treatment_snapshot", None)
    context.user_data.pop("treatment_selected_machines", None)
    context.user_data.pop("treatment_edit_mode", None)
    return ConversationHandler.END

async def treat_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_search_results", None)
    context.user_data.pop("treat_recent_map", None)
    context.user_data.pop("treatment_snapshot", None)
    context.user_data.pop("treatment_selected_machines", None)
    context.user_data.pop("treatment_edit_mode", None)
    await update.effective_message.reply_text(
        "ট্রিটমেন্ট নোট এন্ট্রি বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END

# ---------- ট্রিটমেন্ট প্ল্যান (দ্রুত, বাটন-চালিত) ----------

async def tplan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_TREATMENT_PLAN):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["tplan"] = {}
    context.user_data["tplan_selected"] = set()
    await update.message.reply_text(
        "রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return TPLAN_SEARCH

async def tplan_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = sheets.search_patients(query)
    if not results:
        await update.message.reply_text(
            "❌ কোনো রোগী পাওয়া যায়নি। আবার নাম/ফোন/আইডি লেখো, অথবা /cancel দাও।"
        )
        return TPLAN_SEARCH
    results = results[:10]
    context.user_data["tplan_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
            callback_data=f"tplansel_{p.get('Patient_ID')}",
        )]
        for p in results
    ]
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return TPLAN_SELECT

async def tplan_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("tplansel_", "")
    results = context.user_data.get("tplan_search_results", {})
    patient = results.get(patient_id)
    if not patient:
        await query.edit_message_text(
            "❌ তালিকার মেয়াদ শেষ। আবার শুরু করতে /cancel দাও, তারপর 🩺 ট্রিটমেন্ট প্ল্যান চাপো।"
        )
        return ConversationHandler.END
    context.user_data.pop("tplan_search_results", None)
    context.user_data["tplan"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
    }

    last = sheets.get_last_treatment_note_for_patient(patient_id)
    if last:
        t = context.user_data["tplan"]
        t["Diagnosis"] = last.get("Diagnosis", "")
        t["Treatment_Given"] = last.get("Treatment_Given", "")
        t["Exercise"] = last.get("Exercise", "")
        t["Electrotherapy"] = last.get("Electrotherapy", "")
        t["Manual_Therapy"] = last.get("Manual_Therapy", "")
        prev_machines = [m.strip() for m in str(last.get("Machines", "")).split(",") if m.strip()]
        selected = {idx for idx, name in enumerate(MACHINE_LIST) if name in prev_machines}
        context.user_data["tplan_selected"] = selected
        await query.edit_message_text(
            f"✅ {patient.get('Full_Name')} ({patient_id}) — আগের ভিজিট থেকে অটো-ক্যারি-ওভার হয়েছে।"
        )
        await query.message.reply_text(
            "আজকের মেশিন/মোডালিটি বেছে নাও, তারপর সম্পন্ন চাপো:",
            reply_markup=_machine_keyboard(selected),
        )
        return TPLAN_MACHINES

    context.user_data["tplan_selected"] = set()
    await query.edit_message_text(
        f"📝 নতুন রোগী: {patient.get('Full_Name')} ({patient_id}) — প্রথম অ্যাসেসমেন্ট"
    )
    await query.message.reply_text("আজকের সমস্যা/পর্যবেক্ষণ (Diagnosis) লেখো:")
    return TPLAN_DIAGNOSIS

async def tplan_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tplan"]["Diagnosis"] = update.message.text.strip()
    await update.message.reply_text("কী ট্রিটমেন্ট প্ল্যান করা হচ্ছে লেখো:")
    return TPLAN_GIVEN

async def tplan_given(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tplan"]["Treatment_Given"] = update.message.text.strip()
    await update.message.reply_text("এক্সারসাইজ প্ল্যান লেখো (না থাকলে - দাও):", reply_markup=_skip_keyboard())
    return TPLAN_EXERCISE

async def tplan_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["tplan"]["Exercise"] = "" if text == "-" else text
    await update.message.reply_text("ইলেক্ট্রোথেরাপি নোট লেখো (না থাকলে - দাও):", reply_markup=_skip_keyboard())
    return TPLAN_ELECTRO

async def tplan_electro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["tplan"]["Electrotherapy"] = "" if text == "-" else text
    await update.message.reply_text("ম্যানুয়াল থেরাপি নোট লেখো (না থাকলে - দাও):", reply_markup=_skip_keyboard())
    return TPLAN_MANUAL

async def tplan_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["tplan"]["Manual_Therapy"] = "" if text == "-" else text
    selected = context.user_data.get("tplan_selected", set())
    await update.message.reply_text(
        "আজকের মেশিন/মোডালিটি বেছে নাও, তারপর সম্পন্ন চাপো:",
        reply_markup=_machine_keyboard(selected),
    )
    return TPLAN_MACHINES

async def tplan_machine_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.replace("tpm_", ""))
    selected = context.user_data.get("tplan_selected", set())
    if idx in selected:
        selected.discard(idx)
    else:
        selected.add(idx)
    context.user_data["tplan_selected"] = selected
    await query.edit_message_reply_markup(reply_markup=_machine_keyboard(selected))
    return TPLAN_MACHINES

async def tplan_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    t = context.user_data.get("tplan", {})
    selected = context.user_data.get("tplan_selected", set())
    t["Machines"] = ", ".join(MACHINE_LIST[i] for i in sorted(selected))
    try:
        treatment_id = sheets.add_treatment_note(t, created_by=staff.get("Full_Name", "Unknown"))
        await query.edit_message_text(
            f"✅ ট্রিটমেন্ট প্ল্যান সেভ হয়েছে! ID: {treatment_id}\n"
            f"মেশিন: {t['Machines'] or '(কিছু বাছাই করা হয়নি)'}"
        )
    except Exception as e:
        logger.exception("tplan_done ব্যর্থ হয়েছে")
        await query.edit_message_text(f"❌ সেভ করতে সমস্যা হয়েছে।\nError: {e}")
    context.user_data.pop("tplan", None)
    context.user_data.pop("tplan_selected", None)
    await query.message.reply_text(
        "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(staff.get("Role", ""))
    )
    return ConversationHandler.END

async def tplan_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    context.user_data.pop("tplan", None)
    context.user_data.pop("tplan_selected", None)
    await query.edit_message_text("❌ বাতিল করা হয়েছে।")
    await query.message.reply_text(
        "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(staff.get("Role", ""))
    )
    return ConversationHandler.END

async def tplan_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("tplan", None)
    context.user_data.pop("tplan_selected", None)
    context.user_data.pop("tplan_search_results", None)
    await update.effective_message.reply_text(
        "ট্রিটমেন্ট প্ল্যান বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END

async def reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    if not roles.can_access(staff.get("Role", ""), roles.MENU_REPORTS):
        return
    today_str = datetime.now().strftime("%Y-%m-%d")
    patients = sheets.get_all_patients()
    total_patients = len(patients)
    today_appointments = sheets.get_appointments_for_date(today_str)
    payments = sheets.get_all_payments()
    today_payments = [p for p in payments if str(p.get("Date", "")) == today_str]
    today_collection = sum(float(p.get("Amount", 0) or 0) for p in today_payments)
    total_collection = sum(float(p.get("Amount", 0) or 0) for p in payments)
    lines = [
        "\U0001F4CA রিপোর্ট ও অ্যানালিটিক্স",
        "",
        f"\U0001F465 মোট রোগী: {total_patients}",
        f"\U0001F4CB আজকের অ্যাপয়েন্টমেন্ট: {len(today_appointments)}",
        f"\U0001F4B0 আজকের আয়: {today_collection:.0f} টাকা",
        f"\U0001F4B0 সর্বমোট আয়: {total_collection:.0f} টাকা",
    ]
    await update.effective_message.reply_text(
        "\n".join(lines),
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )

# ---------- ট্রিটমেন্ট হিস্ট্রি (তারিখ-ভিত্তিক ভিউয়ার) ----------

async def thist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_TREATMENT_HISTORY):
        return ConversationHandler.END
    await update.effective_message.reply_text("রোগীর নাম, ফোন নম্বর, অথবা Patient ID লেখো (খুঁজতে):")
    return "THIST_SEARCH"

async def thist_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    results = sheets.search_patients(query_text)
    if not results:
        await update.message.reply_text("কোনো রোগী পাওয়া যায়নি। আবার চেষ্টা করো, অথবা /cancel দাও।")
        return "THIST_SEARCH"
    buttons = []
    for p in results[:10]:
        pid = p.get("Patient_ID", "")
        name = p.get("Full_Name") or p.get("Name") or "Unknown"
        buttons.append([InlineKeyboardButton(f"{name} ({pid})", callback_data=f"thpsel_{pid}")])
    await update.message.reply_text(
        "কোন রোগীর ট্রিটমেন্ট হিস্টরি দেখতে চাও?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return "THIST_SEARCH"

async def thist_patient_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("thpsel_", "", 1)
    notes = sheets.get_treatment_notes_for_patient(patient_id)
    if not notes:
        await query.edit_message_text("এই রোগীর কোনো ট্রিটমেন্ট নোট পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["thist_notes"] = {
        str(n.get("Treatment_ID", "")).strip(): n for n in notes
    }
    notes_sorted = sorted(notes, key=lambda n: str(n.get("Date", "")), reverse=True)
    buttons = []
    for n in notes_sorted[:15]:
        tid = str(n.get("Treatment_ID", "")).strip()
        date_str = n.get("Date", "")
        buttons.append([InlineKeyboardButton(f"🗓 {date_str}", callback_data=f"thdate_{tid}")])
    await query.edit_message_text(
        "কোন তারিখের ট্রিটমেন্ট প্ল্যান দেখতে চাও?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return "THIST_DATE"

async def thist_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = query.data.replace("thdate_", "", 1)
    notes_map = context.user_data.get("thist_notes", {})
    n = notes_map.get(tid)
    if not n:
        await query.edit_message_text("নোট পাওয়া যায়নি।")
        return ConversationHandler.END
    lines = [
        f"📝 {n.get('Patient_Name', '')} ({n.get('Patient_ID', '')}) — {n.get('Date', '')}",
        "",
        f"Diagnosis: {n.get('Diagnosis', '') or '-'}",
        f"Treatment Given: {n.get('Treatment_Given', '') or '-'}",
        f"Exercise: {n.get('Exercise', '') or '-'}",
        f"Electrotherapy: {n.get('Electrotherapy', '') or '-'}",
        f"Manual Therapy: {n.get('Manual_Therapy', '') or '-'}",
        f"Machines: {n.get('Machines', '') or '-'}",
    ]
    await query.edit_message_text("\n".join(lines))
    context.user_data.pop("thist_notes", None)
    return ConversationHandler.END

async def thist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("thist_notes", None)
    await update.effective_message.reply_text("বাতিল করা হয়েছে।")
    return ConversationHandler.END

async def hist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_PATIENT_HISTORY):
        return ConversationHandler.END
    await update.effective_message.reply_text("রোগীর নাম, ফোন নম্বর, অথবা Patient ID লেখো (খুঁজতে):")
    return "HIST_SEARCH"

async def hist_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    results = sheets.search_patients(query_text)
    if not results:
        await update.message.reply_text("কোনো রোগী পাওয়া যায়নি। আবার চেষ্টা করো, অথবা /cancel দাও।")
        return "HIST_SEARCH"
    buttons = []
    for p in results[:10]:
        pid = p.get("Patient_ID", "")
        name = p.get("Full_Name") or p.get("Name") or "Unknown"
        buttons.append([InlineKeyboardButton(f"{name} ({pid})", callback_data=f"histsel_{pid}")])
    await update.message.reply_text(
        "কোন রোগী দেখতে চাও?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return "HIST_SEARCH"

async def hist_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("histsel_", "", 1)

    patient = sheets.get_patient_by_id(patient_id)
    if patient is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return ConversationHandler.END

    name = patient.get("Full_Name") or patient.get("Name") or "Unknown"
    lines = [f"📜 {name} ({patient_id})-এর ইতিহাস", ""]

    lines.append("👤 প্রোফাইল:")
    lines.append(f"  ফোন: {patient.get('Phone', 'N/A')}")
    lines.append(f"  ঠিকানা: {patient.get('Address', 'N/A')}")
    note = patient.get("Note") or patient.get("Notes") or patient.get("Problem", "")
    if note:
        lines.append(f"  নোট: {note}")
    therapist = patient.get("Therapist", "")
    if therapist:
        lines.append(f"  থেরাপিস্ট: {therapist}")
    lines.append("")

    package = sheets.get_active_package_for_patient(patient_id)
    if package:
        total = package.get("Total_Sessions", "N/A")
        done = package.get("Sessions_Completed", "N/A")
        lines.append(f"🗓️ সেশন: {done} সম্পন্ন / {total} মোট")
        lines.append("")

    payments = sheets.get_payments_for_patient(patient_id)
    if payments:
        lines.append("💳 পেমেন্ট হিস্টরি:")
        total_paid = 0.0
        last_due = 0.0
        for p in payments:
            date_str = p.get("Date", "")
            amount = float(p.get("Amount", 0) or 0)
            due = float(p.get("Due", 0) or 0)
            method = p.get("Payment_Method", "")
            total_paid += amount
            last_due = due
            lines.append(f"  • {date_str}: {amount:.0f} টাকা ({method})")
        lines.append("")
        lines.append(f"💰 সর্বমোট জমা: {total_paid:.0f} টাকা")
        lines.append(f"⏳ সর্বশেষ বাকি: {last_due:.0f} টাকা")
    else:
        lines.append("💳 কোনো পেমেন্ট রেকর্ড নেই।")
    lines.append("")

    appointments = sheets.get_appointments_for_patient(patient_id)
    if appointments:
        lines.append("📅 অ্যাপয়েন্টমেন্ট হিস্টরি:")
        for a in appointments[-10:]:
            date_str = a.get("Date", "")
            status = a.get("Status", "")
            lines.append(f"  • {date_str}: {status}")
    else:
        lines.append("📅 কোনো অ্যাপয়েন্টমেন্ট রেকর্ড নেই।")
    lines.append("")

    treatment_notes = sheets.get_treatment_notes_for_patient(patient_id)
    if treatment_notes:
        lines.append("📝 ট্রিটমেন্ট নোট:")
        for t in treatment_notes[-5:]:
            date_str = t.get("Date", "")
            note_text = t.get("Note", "") or t.get("Notes", "")
            lines.append(f"  • {date_str}: {note_text}")
    else:
        lines.append("📝 কোনো ট্রিটমেন্ট নোট নেই।")

    full_text = "\n".join(lines)
    if len(full_text) > 4000:
        full_text = full_text[:3990] + "\n...(আরও আছে)"

    await query.edit_message_text(full_text)
    return ConversationHandler.END

async def hist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    await update.effective_message.reply_text(
        "বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END

async def unknown_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    await update.message.reply_text(
        "এই ফিচারটা এখনো তৈরি হচ্ছে 🚧",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )

async def _restart_via_start(update, context):
    # /start chaple je conversation theke ber kore mul menute firiye ane
    context.user_data.clear()
    await start(update, context)
    return ConversationHandler.END

def _start_health_server():
    """Render/cloud hosting-er jonno choto HTTP health-check server (UptimeRobot ping korbe)."""
    port = int(os.environ.get("PORT", 10001))

    class _HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot is running")

        def do_HEAD(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()

        def log_message(self, format, *args):
            pass  # health-check log noise বন্ধ রাখা

    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Health server chalu hoyeche port {port}-e")

def _patient_card_text(patient: dict) -> str:
    name = patient.get("Full_Name", "")
    pid = patient.get("Patient_ID", "")
    phone = patient.get("Phone", "")
    dept = patient.get("Department", "")
    therapist = patient.get("Therapist", "")
    total_bill = patient.get("Total_Bill", 0) or 0
    paid = patient.get("Paid_Amount", 0) or 0
    due = patient.get("Due_Amount", 0) or 0
    return (
        f"👤 {name} ({pid})\n"
        f"📞 {phone}\n"
        f"🏥 বিভাগ: {dept}\n"
        f"🧑‍⚕️ থেরাপিস্ট: {therapist or '—'}\n\n"
        f"💰 মোট বিল: {total_bill}\n"
        f"✅ জমা হয়েছে: {paid}\n"
        f"⏳ বাকি: {due}"
    )

def _patient_card_keyboard(patient_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("💰 পেমেন্ট নিন", callback_data=f"plistact_pay_{patient_id}"),
            InlineKeyboardButton("📅 অ্যাপয়েন্টমেন্ট", callback_data=f"plistact_apt_{patient_id}"),
        ],
        [
            InlineKeyboardButton("📝 ট্রিটমেন্ট নোট", callback_data=f"plistact_treat_{patient_id}"),
            InlineKeyboardButton("📜 সম্পূর্ণ ইতিহাস", callback_data=f"plistact_hist_{patient_id}"),
        ],
        [InlineKeyboardButton("🔙 তালিকায় ফিরুন", callback_data="plistact_back")],
    ]
    return InlineKeyboardMarkup(buttons)

async def patient_list_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    if not roles.can_access(staff.get("Role", ""), roles.MENU_PATIENT_LIST):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    patients = [
        p for p in sheets.get_all_patients()
        if str(p.get("Status", "")).strip() == "Active"
    ]
    patients.sort(key=lambda p: p.get("Full_Name", ""))
    if not patients:
        await update.message.reply_text("কোনো সক্রিয় রোগী পাওয়া যায়নি।")
        return
    context.user_data["plist_patients"] = {
        p.get("Patient_ID", "").strip(): p for p in patients
    }
    await _send_patient_list_page(update.message, context, page=0)

async def _send_patient_list_page(message, context: ContextTypes.DEFAULT_TYPE, page: int, edit: bool = False):
    patients = list(context.user_data.get("plist_patients", {}).values())
    per_page = 8
    start = page * per_page
    chunk = patients[start:start + per_page]
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
            callback_data=f"plistsel_{p.get('Patient_ID')}_{page}",
        )]
        for p in chunk
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ আগের", callback_data=f"plistpage_{page - 1}"))
    if start + per_page < len(patients):
        nav.append(InlineKeyboardButton("পরের ➡️", callback_data=f"plistpage_{page + 1}"))
    if nav:
        buttons.append(nav)
    text = f"📋 রোগীর তালিকা (পাতা {page + 1}) — নাম চাপো:"
    markup = InlineKeyboardMarkup(buttons)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)

async def patient_list_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.replace("plistpage_", ""))
    await _send_patient_list_page(query.message, context, page=page, edit=True)

async def patient_list_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, patient_id, page = query.data.split("_", 2)
    patients = context.user_data.get("plist_patients", {})
    patient = patients.get(patient_id)
    if not patient:
        await query.edit_message_text("❌ তালিকার মেয়াদ শেষ। আবার 📋 রোগীর তালিকা চাপো।")
        return
    context.user_data["plist_last_page"] = int(page)
    await query.edit_message_text(
        _patient_card_text(patient),
        reply_markup=_patient_card_keyboard(patient_id),
    )

async def patient_list_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = context.user_data.get("plist_last_page", 0)
    await _send_patient_list_page(query.message, context, page=page, edit=True)

async def plist_action_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_pay_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["payment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
        "Department": patient.get("Department", ""),
    }
    total_bill = patient.get("Total_Bill", 0) or 0
    paid_amount = patient.get("Paid_Amount", 0) or 0
    due_amount = patient.get("Due_Amount", 0) or 0
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})\n\n"
        f"মোট বিল: {total_bill}\nজমা হয়েছে: {paid_amount}\nবাকি: {due_amount}"
    )
    await query.message.reply_text(
        "আজ কয়টা সেশন হলো লেখো (না থাকলে 0):",
        reply_markup=_number_keyboard([str(n) for n in range(0, 6)]),
    )
    return PAY_SESSION

async def plist_action_apt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_apt_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["new_appointment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
        "Department": patient.get("Department", ""),
    }
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})"
    )
    await query.message.reply_text(
        "তারিখ বেছে নাও (অথবা টাইপ করো, উদাহরণ: 2026-07-15):",
        reply_markup=_date_keyboard(),
    )
    return APT_DATE

async def plist_action_treat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_treat_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END

    context.user_data["treatment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
    }
    context.user_data.pop("treat_search_results", None)
    context.user_data.pop("treat_recent_map", None)
    context.user_data.pop("treatment_snapshot", None)
    context.user_data.pop("treatment_selected_machines", None)
    context.user_data.pop("treatment_edit_mode", None)
    return await _treat_after_patient_selected(query, context, patient)
async def plist_action_hist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_hist_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if patient is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return

    name = patient.get("Full_Name") or patient.get("Name") or "Unknown"
    lines = [f"📜 {name} ({patient_id})-এর ইতিহাস", ""]
    lines.append("👤 প্রোফাইল:")
    lines.append(f"  ফোন: {patient.get('Phone', 'N/A')}")
    lines.append(f"  ঠিকানা: {patient.get('Address', 'N/A')}")
    note = patient.get("Note") or patient.get("Notes") or patient.get("Problem", "")
    if note:
        lines.append(f"  নোট: {note}")
    therapist = patient.get("Therapist", "")
    if therapist:
        lines.append(f"  থেরাপিস্ট: {therapist}")
    lines.append("")

    package = sheets.get_active_package_for_patient(patient_id)
    if package:
        total = package.get("Total_Sessions", "N/A")
        done = package.get("Sessions_Completed", "N/A")
        lines.append(f"🗓️ সেশন: {done} সম্পন্ন / {total} মোট")
        lines.append("")

    payments = sheets.get_payments_for_patient(patient_id)
    if payments:
        lines.append("💳 পেমেন্ট হিস্টরি:")
        total_paid = 0.0
        last_due = 0.0
        for p in payments:
            date_str = p.get("Date", "")
            amount = float(p.get("Amount", 0) or 0)
            due = float(p.get("Due", 0) or 0)
            method = p.get("Payment_Method", "")
            total_paid += amount
            last_due = due
            lines.append(f"  • {date_str}: {amount:.0f} টাকা ({method})")
        lines.append("")
        lines.append(f"💰 সর্বমোট জমা: {total_paid:.0f} টাকা")
        lines.append(f"⏳ সর্বশেষ বাকি: {last_due:.0f} টাকা")
    else:
        lines.append("💳 কোনো পেমেন্ট রেকর্ড নেই।")
    lines.append("")

    appointments = sheets.get_appointments_for_patient(patient_id)
    if appointments:
        lines.append("📅 অ্যাপয়েন্টমেন্ট হিস্টরি:")
        for a in appointments[-10:]:
            date_str = a.get("Date", "")
            status = a.get("Status", "")
            lines.append(f"  • {date_str}: {status}")
    else:
        lines.append("📅 কোনো অ্যাপয়েন্টমেন্ট রেকর্ড নেই।")
    lines.append("")

    treatment_notes = sheets.get_treatment_notes_for_patient(patient_id)
    if treatment_notes:
        lines.append("📝 ট্রিটমেন্ট নোট:")
        for t in treatment_notes[-5:]:
            date_str = t.get("Date", "")
            note_text = t.get("Note", "") or t.get("Notes", "")
            lines.append(f"  • {date_str}: {note_text}")
    else:
        lines.append("📝 কোনো ট্রিটমেন্ট নোট নেই।")

    full_text = "\n".join(lines)
    if len(full_text) > 4000:
        full_text = full_text[:3990] + "\n...(আরও আছে)"

    await query.edit_message_text(full_text)

def main():
    app = Application.builder().token(config.BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search_patient))
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_MY_PATIENTS}$"), my_patients)
    )
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_ATTENDANCE}$"), attendance_menu)
    )
    app.add_handler(CallbackQueryHandler(attendance_callback, pattern="^att_"))
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_TODAY_APPOINTMENTS}$"), today_appointments)
    )
    app.add_handler(CallbackQueryHandler(apt_status_callback, pattern="^aptstatus_"))

    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_PATIENT_LIST}$"), patient_list_start)
    )
    app.add_handler(CallbackQueryHandler(patient_list_page_callback, pattern="^plistpage_"))
    app.add_handler(CallbackQueryHandler(patient_list_select_callback, pattern="^plistsel_"))
    app.add_handler(CallbackQueryHandler(patient_list_back_callback, pattern="^plistact_back$"))
    app.add_handler(CallbackQueryHandler(plist_action_hist, pattern="^plistact_hist_"))

    reg_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_PATIENT_REG}$"), reg_start)
        ],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_name)],
            REG_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_phone)],
            REG_PHONE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_phone_confirm)],
            REG_PHONE_DUP: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_phone_dup_confirm)],
            REG_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_address)],
            REG_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_note)],
            REG_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),CommandHandler("cancel", reg_cancel),
            CommandHandler("start", _restart_via_start),],
    )
    app.add_handler(reg_conv)

    apt_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_APPOINTMENT}$"), apt_start),
            CallbackQueryHandler(plist_action_apt, pattern="^plistact_apt_"),
        ],
        states={
            APT_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_search)],
            APT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_select)],
            APT_DATE: [
                CallbackQueryHandler(apt_date_callback, pattern="^aptdate_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_date),
            ],
            APT_TIME: [
                CallbackQueryHandler(apt_time_callback, pattern="^apttime_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_time),
            ],
            APT_THERAPIST: [
                CallbackQueryHandler(apt_therapist_callback, pattern="^aptther_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_therapist),
            ],
            APT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),CommandHandler("cancel", apt_cancel),
            CommandHandler("start", _restart_via_start),],
    )
    app.add_handler(apt_conv)

    pay_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_PAYMENT}$"), pay_start),
            CallbackQueryHandler(plist_action_pay, pattern="^plistact_pay_"),
        ],
        states={
            PAY_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_search)],
            PAY_SELECT: [
                CallbackQueryHandler(pay_select_callback, pattern="^paysel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_select),
            ],
            PAY_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_session)],
            PAY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_amount)],
            PAY_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_method)],
            PAY_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),CommandHandler("cancel", pay_cancel),
            CommandHandler("start", _restart_via_start),],
    )
    app.add_handler(pay_conv)

    treat_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_TREATMENT_NOTE}$"), treat_start),
            CallbackQueryHandler(plist_action_treat, pattern="^plistact_treat_"),
        ],
        states={
            TREAT_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_search)
            ],
            TREAT_SELECT: [
                CallbackQueryHandler(treat_recent_callback, pattern="^trecentsel_"),
                CallbackQueryHandler(treat_select_callback, pattern="^treatsel_"),
            ],
            TREAT_REPEAT_CHOICE: [
                CallbackQueryHandler(treat_repeat_choice_callback, pattern="^treat_repeat_")
            ],
            TREAT_DIAGNOSIS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_diagnosis)
            ],
            TREAT_GIVEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_given)
            ],
            TREAT_EXERCISE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_exercise)
            ],
            TREAT_ELECTRO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_electro)
            ],
            TREAT_MANUAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_manual)
            ],
            TREAT_SESSION: [
                CallbackQueryHandler(treat_machine_toggle, pattern="^tpm_"),
                CallbackQueryHandler(treat_machine_done, pattern="^tpdone_save$"),
                CallbackQueryHandler(treat_machine_cancel_callback, pattern="^tpcancel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_session),
            ],
            TREAT_NEXTVISIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_nextvisit)
            ],
            TREAT_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_confirm)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", treat_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(treat_conv)

    tplan_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_TREATMENT_PLAN}$"), tplan_start),
        ],
        states={
            TPLAN_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_search)],
            TPLAN_SELECT: [CallbackQueryHandler(tplan_select_callback, pattern="^tplansel_")],
            TPLAN_DIAGNOSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_diagnosis)],
            TPLAN_GIVEN: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_given)],
            TPLAN_EXERCISE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_exercise)],
            TPLAN_ELECTRO: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_electro)],
            TPLAN_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_manual)],
            TPLAN_MACHINES: [
                CallbackQueryHandler(tplan_machine_toggle, pattern="^tpm_"),
                CallbackQueryHandler(tplan_done, pattern="^tpdone_"),
                CallbackQueryHandler(tplan_cancel_callback, pattern="^tpcancel_"),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", tplan_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(tplan_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{roles.MENU_REPORTS}$"), reports_menu))
    hist_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{roles.MENU_PATIENT_HISTORY}$"), hist_start)],
        states={
            "HIST_SEARCH": [
                CallbackQueryHandler(hist_select_callback, pattern="^histsel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), hist_search),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),CommandHandler("cancel", hist_cancel),
            CommandHandler("start", _restart_via_start),],
    )
    app.add_handler(hist_conv)

    thist_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_TREATMENT_HISTORY}$"), thist_start),
        ],
        states={
            "THIST_SEARCH": [
                CallbackQueryHandler(thist_patient_callback, pattern="^thpsel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, thist_search),
            ],
            "THIST_DATE": [
                CallbackQueryHandler(thist_date_callback, pattern="^thdate_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", thist_cancel)],
    )
    app.add_handler(thist_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{roles.MENU_HOME}$"), go_home))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), unknown_menu))
    logger.info("Relife Clinic OS Bot চালু হচ্ছে...")
    _start_health_server()

    app.run_polling()

if __name__ == "__main__":
    main()
