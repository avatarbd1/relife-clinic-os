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
from config import bd_now
import sheets
import roles
import calendar_helper

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
    TREAT_MACHINES,
    TREAT_UNUSED1,
    TREAT_UNUSED2,
    TREAT_UNUSED3,
    TREAT_UNUSED4,
    TREAT_UNUSED5,
    TREAT_UNUSED6,
    TREAT_UNUSED7,
) = range(19, 29)

PAY_METHODS = ["Cash", "bKash", "Nagad", "Card"]
THERAPIST_NAMES = ["Nipa", "Saiful"]

BN_WEEKDAYS = ["সোম", "মঙ্গল", "বুধ", "বৃহঃ", "শুক্র", "শনি", "রবি"]

_ALL_MENU_ITEMS = [
    roles.MENU_HOME,
    roles.MENU_PATIENT_REG,
    roles.MENU_APPOINTMENT,
    roles.MENU_MY_PATIENTS,
    roles.MENU_TREATMENT_NOTE,
    roles.MENU_TREATMENT_PLAN,
    roles.MENU_PAYMENT,
    roles.MENU_REPORTS,
    roles.MENU_SETTINGS,
    roles.MENU_ATTENDANCE,
    roles.MENU_TODAY_APPOINTMENTS,
    roles.MENU_PATIENT_HISTORY,
    roles.MENU_TREATMENT_HISTORY,
    roles.MENU_PATIENT_LIST,
    roles.MENU_DAILY_REGISTER,
]
_ALL_MENU_REGEX = "^(" + "|".join(re.escape(x) for x in _ALL_MENU_ITEMS) + ")$"

(
    TPLAN_SEARCH,
    TPLAN_SELECT,
    TPLAN_DIAGNOSIS,
    TPLAN_TOTAL,
    TPLAN_EXERCISE,
    TPLAN_ELECTRO,
    TPLAN_MANUAL,
    TPLAN_CONFIRM,
) = range(29, 37)

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
                row.append(InlineKeyboardButton(prefix + MACHINE_LIST[j], callback_data=f"trm_{j}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✅ সম্পন্ন — সেভ করো", callback_data="trdone_save")])
    buttons.append([InlineKeyboardButton("⬅️ আগের ধাপ", callback_data="trback_search")])
    buttons.append([InlineKeyboardButton("❌ বাতিল", callback_data="trcancel_")])
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


def _recent_patient_buttons(prefix: str, limit: int = 8) -> InlineKeyboardMarkup | None:
    """সার্চ/টাইপ না করে সরাসরি সাম্প্রতিক রোগী বাটনে বেছে নেওয়ার জন্য।
    prefix হবে সেই ফ্লো-র select callback prefix (যেমন 'treatsel_', 'tplansel_', 'paysel_', 'aptsel_')।
    কোনো রোগী না থাকলে None ফেরত দেয়।"""
    patients = sheets.get_recent_patients(limit)
    if not patients:
        return None
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
            callback_data=f"{prefix}{p.get('Patient_ID')}",
        )]
        for p in patients
    ]
    return InlineKeyboardMarkup(buttons)


def _patient_search_buttons(results, prefix: str, cancel_data: str) -> InlineKeyboardMarkup:
    """সার্চ-রেজাল্ট থেকে রোগী বাছাইয়ের বাটন বানায় (নাম বাটন + শেষে 🔙 বাতিল বাটন)।
    আগে apt/pay/treat/tplan/thist/hist প্রতিটাতে এই একই লুপ আলাদা আলাদা কপি-পেস্ট করা ছিল।"""
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name') or p.get('Name') or 'Unknown'} ({p.get('Patient_ID', '')})",
            callback_data=f"{prefix}{p.get('Patient_ID', '')}",
        )]
        for p in results
    ]
    buttons.append([InlineKeyboardButton("🔙 বাতিল করো", callback_data=cancel_data)])
    return InlineKeyboardMarkup(buttons)


async def _apt_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await apt_cancel(update, context)


async def _pay_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await pay_cancel(update, context)


async def _treat_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await treat_cancel(update, context)


async def _tplan_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await tplan_cancel(update, context)


async def _hist_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await hist_cancel(update, context)


async def _thist_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await thist_cancel(update, context)


def _date_multi_keyboard(selected: set) -> InlineKeyboardMarkup:
    """তারিখ মাল্টি-সিলেক্ট কীবোর্ড — একসাথে কয়েকদিনের অ্যাপয়েন্টমেন্ট বুক করার জন্য।
    ✅ চিহ্ন দিয়ে বোঝানো হয় কোন কোন দিন এখন পর্যন্ত বাছাই করা আছে।"""
    today = bd_now()
    buttons = []
    row = []
    for i in range(7):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        label = d.strftime("%d %b") + f" ({BN_WEEKDAYS[d.weekday()]})"
        if date_str in selected:
            label = "✅ " + label
        row.append(InlineKeyboardButton(label, callback_data=f"aptdatetoggle_{date_str}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    done_label = (
        f"➡️ পরের ধাপ ({len(selected)} দিন বাছাই করা হয়েছে)"
        if selected else "➡️ অন্তত ১টা দিন বাছাই করো"
    )
    buttons.append([InlineKeyboardButton(done_label, callback_data="aptdatedone")])
    buttons.append([InlineKeyboardButton("⬅️ আগের ধাপ", callback_data="aptback_search")])
    return InlineKeyboardMarkup(buttons)


def _date_keyboard() -> InlineKeyboardMarkup:
    today = bd_now()
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
    buttons.append([InlineKeyboardButton("⬅️ আগের ধাপ", callback_data="aptback_date")])
    return InlineKeyboardMarkup(buttons)


def _therapist_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"aptther_{name}")]
        for name in THERAPIST_NAMES
    ]
    buttons.append([InlineKeyboardButton("⬅️ আগের ধাপ", callback_data="aptback_time")])
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
    recent_kb = _recent_patient_buttons("aptsel_")
    if recent_kb:
        await update.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
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
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=_patient_search_buttons(results, "aptsel_", "aptsearchback"),
    )
    return APT_SELECT


async def apt_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """সার্চ-রেজাল্ট বাটন অথবা 'সাম্প্রতিক রোগী' বাটন — দুটো থেকেই আসতে পারে।"""
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("aptsel_", "", 1)
    results = context.user_data.get("apt_search_results", {})
    patient = results.get(patient_id) or sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text(
            "❌ রোগী পাওয়া যায়নি। আবার শুরু করতে /cancel দাও, তারপর 📅 অ্যাপয়েন্টমেন্ট বুকিং চাপো।"
        )
        return ConversationHandler.END
    context.user_data.pop("apt_search_results", None)
    context.user_data["new_appointment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
        "Department": patient.get("Department", ""),
    }
    context.user_data.pop("apt_dates", None)
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})"
    )
    await query.message.reply_text(
        "তারিখ বেছে নাও — একাধিক দিনও বাছাই করা যাবে (একাধিকবার চাপো), তারপর 'পরের ধাপ' চাপো:",
        reply_markup=_date_multi_keyboard(set()),
    )
    return APT_DATE


async def apt_back_to_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """তারিখ-নির্বাচনের ধাপ থেকে '⬅️ আগের ধাপ' চাপলে আবার রোগী খোঁজার ধাপে ফিরে যায়।"""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("apt_dates", None)
    context.user_data.pop("new_appointment", None)
    await query.edit_message_text("⬅️ রোগী খোঁজার ধাপে ফিরে যাওয়া হলো।")
    await query.message.reply_text("রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):")
    recent_kb = _recent_patient_buttons("aptsel_")
    if recent_kb:
        await query.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return APT_SEARCH


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
    context.user_data.pop("apt_dates", None)
    await update.message.reply_text(
        f"রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})\n\n"
        "তারিখ বেছে নাও — একাধিক দিনও বাছাই করা যাবে (একাধিকবার চাপো), তারপর 'পরের ধাপ' চাপো:",
        reply_markup=_date_multi_keyboard(set()),
    )
    return APT_DATE


async def apt_date_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """তারিখ বাটনে চাপলে সেটা বাছাই/বাতিল টগল হয় — 'পরের ধাপ' না চাপা পর্যন্ত একই স্ক্রিনে থাকে।"""
    query = update.callback_query
    date_str = query.data.replace("aptdatetoggle_", "", 1)
    selected = context.user_data.setdefault("apt_dates", set())
    if date_str in selected:
        selected.discard(date_str)
        await query.answer("বাদ দেওয়া হয়েছে")
    else:
        selected.add(date_str)
        await query.answer("যোগ করা হয়েছে")
    await query.edit_message_reply_markup(reply_markup=_date_multi_keyboard(selected))
    return APT_DATE


async def apt_date_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    selected = context.user_data.get("apt_dates", set())
    if not selected:
        await query.answer("অন্তত একটা তারিখ বাছাই করো।", show_alert=True)
        return APT_DATE
    await query.answer()
    dates = sorted(selected)
    context.user_data.setdefault("new_appointment", {})["Dates"] = dates
    context.user_data.pop("apt_dates", None)
    await query.edit_message_text(f"✅ তারিখ বাছাই করা হয়েছে: {', '.join(dates)}")
    await query.message.reply_text(
        "সময় বেছে নাও (অথবা টাইপ করো) — সবগুলো দিনের জন্য একই সময় প্রযোজ্য হবে:",
        reply_markup=_time_keyboard(),
    )
    return APT_TIME


async def apt_back_to_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """সময়-নির্বাচনের ধাপ থেকে '⬅️ আগের ধাপ' চাপলে আবার তারিখ-নির্বাচনের ধাপে ফিরে যায়।"""
    query = update.callback_query
    await query.answer()
    a = context.user_data.setdefault("new_appointment", {})
    prev_dates = set(a.get("Dates") or ([a["Date"]] if a.get("Date") else []))
    context.user_data["apt_dates"] = prev_dates
    await query.edit_message_text(
        "⬅️ তারিখ বেছে নাও — একাধিক দিনও বাছাই করা যাবে (একাধিকবার চাপো), তারপর 'পরের ধাপ' চাপো:",
        reply_markup=_date_multi_keyboard(prev_dates),
    )
    return APT_DATE


async def apt_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    dates = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    context.user_data.setdefault("new_appointment", {})["Dates"] = dates
    await update.message.reply_text(
        "সময় বেছে নাও (অথবা টাইপ করো) — সবগুলো দিনের জন্য একই সময় প্রযোজ্য হবে:",
        reply_markup=_time_keyboard(),
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


async def apt_back_to_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """থেরাপিস্ট-নির্বাচনের ধাপ থেকে '⬅️ আগের ধাপ' চাপলে আবার সময়-নির্বাচনের ধাপে ফিরে যায়।"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⬅️ সময় বেছে নাও (অথবা টাইপ করো) — সবগুলো দিনের জন্য একই সময় প্রযোজ্য হবে:",
        reply_markup=_time_keyboard(),
    )
    return APT_TIME


def _apt_summary_text(a: dict) -> str:
    dates = a.get("Dates") or ([a["Date"]] if a.get("Date") else [])
    date_line = ", ".join(dates) if len(dates) > 1 else (dates[0] if dates else "-")
    date_label = "তারিখসমূহ" if len(dates) > 1 else "তারিখ"
    return (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"রোগী: {a['Patient_Name']} ({a['Patient_ID']})\n"
        f"Department: {a.get('Department') or 'N/A'}\n"
        f"{date_label}: {date_line}\nসময়: {a['Time']}\n"
        f"থেরাপিস্ট: {a['Therapist']}\n\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )


async def apt_therapist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Therapist"] = update.message.text.strip()
    a = context.user_data["new_appointment"]
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(_apt_summary_text(a), reply_markup=confirm_keyboard)
    return APT_CONFIRM


async def apt_therapist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    therapist_name = query.data.replace("aptther_", "")
    context.user_data["new_appointment"]["Therapist"] = therapist_name
    a = context.user_data["new_appointment"]
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await query.edit_message_text(f"✅ থেরাপিস্ট নির্বাচন করা হয়েছে: {therapist_name}")
    await query.message.reply_text(_apt_summary_text(a), reply_markup=confirm_keyboard)
    return APT_CONFIRM


async def apt_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        a = context.user_data.get("new_appointment", {})
        dates = a.get("Dates") or ([a["Date"]] if a.get("Date") else [])
        ids = []
        for d in dates:
            row = dict(a)
            row["Date"] = d
            row.pop("Dates", None)
            appointment_id = sheets.add_appointment(row, created_by=staff.get("Full_Name", "Unknown"))
            ids.append(appointment_id)
        if len(ids) > 1:
            msg = f"✅ {len(ids)}টা অ্যাপয়েন্টমেন্ট বুক হয়েছে!\nAppointment IDs: {', '.join(ids)}"
        else:
            msg = f"✅ অ্যাপয়েন্টমেন্ট বুক হয়েছে! Appointment ID: {ids[0] if ids else '-'}"
        await update.message.reply_text(msg, reply_markup=_menu_keyboard(staff.get("Role", "")))
    else:
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    context.user_data.pop("new_appointment", None)
    context.user_data.pop("apt_dates", None)
    return ConversationHandler.END


async def apt_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("new_appointment", None)
    context.user_data.pop("apt_search_results", None)
    context.user_data.pop("apt_dates", None)
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
    date_str = bd_now().strftime("%Y-%m-%d")
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
    date_str = bd_now().strftime("%Y-%m-%d")
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
    date_str = bd_now().strftime("%Y-%m-%d")
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
            InlineKeyboardButton("✅ উপস্থিত", callback_data=f"aptstatus_{a.get('Appointment_ID')}_Completed_{a.get('Patient_ID')}"),
            InlineKeyboardButton("❌ আসেনি", callback_data=f"aptstatus_{a.get('Appointment_ID')}_NoShow_{a.get('Patient_ID')}"),
        ]])
        await update.message.reply_text(text, reply_markup=buttons)


async def apt_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_", 3)
    appointment_id = parts[1]
    status_code = parts[2]
    patient_id = parts[3] if len(parts) > 3 else ""
    status_map = {"Completed": "Completed", "NoShow": "No-show"}
    status = status_map.get(status_code, status_code)
    ok = sheets.update_appointment_status(appointment_id, status)
    if not ok:
        await query.edit_message_text("❌ আপডেট করা যায়নি।")
        return

    if status_code == "Completed" and patient_id:
        # Present চাপার পরপরই Patient Action Panel — Payment/Note এখন ১ ট্যাপ দূরে।
        patient = sheets.get_patient_by_id(patient_id)
        if patient:
            await query.edit_message_text(
                f"✅ {appointment_id} — উপস্থিত হয়েছে।\n\n" + _patient_card_text(patient),
                reply_markup=_patient_card_keyboard(patient_id),
            )
            return

    await query.edit_message_text(f"✅ {appointment_id} — স্ট্যাটাস: {status}")


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
    recent_kb = _recent_patient_buttons("paysel_")
    if recent_kb:
        await update.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
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
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=_patient_search_buttons(results, "paysel_", "paysearchback"),
    )
    return PAY_SELECT


async def pay_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("paysel_", "")
    results = context.user_data.get("pay_search_results", {})
    patient = results.get(patient_id) or sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text(
            "❌ তালিকার মেয়াদ শেষ। আবার শুরু করতে /cancel দাও, তারপর 📋 আজকের রেজিস্টার থেকে ➕ নতুন এন্ট্রি চাপো।"
        )
        return ConversationHandler.END
    context.user_data.setdefault("payment", {})["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["payment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data["payment"]["Department"] = patient.get("Department", "")
    context.user_data["payment"]["Sessions"] = 1
    context.user_data.pop("pay_search_results", None)

    await query.edit_message_text(
        _register_amount_prompt_text(patient.get("Full_Name", ""), patient.get("Patient_ID", ""), 1),
        reply_markup=_register_amount_keyboard(1),
    )
    return PAY_AMOUNT


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
    context.user_data["payment"]["Sessions"] = 1
    context.user_data.pop("pay_search_results", None)

    await update.message.reply_text(
        _register_amount_prompt_text(patient.get("Full_Name", ""), patient.get("Patient_ID", ""), 1),
        reply_markup=_register_amount_keyboard(1),
    )
    return PAY_AMOUNT


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
        reg_text, reg_kb = _register_view_text_and_keyboard()
        await update.message.reply_text(reg_text, reply_markup=reg_kb)
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


# ---------- ট্রিটমেন্ট নোট (দ্রুত দৈনিক ফ্লো — Active প্ল্যান থেকে অটো-ফিল) ----------

async def _treat_prepare_for_patient(patient: dict, context: ContextTypes.DEFAULT_TYPE):
    """
    রোগীর Active ট্রিটমেন্ট প্ল্যান খুঁজে বের করে।
    প্ল্যান না থাকলে (None, stop_text) রিটার্ন করে — কলার সাথে সাথে conversation END করবে।
    প্ল্যান থাকলে context.user_data["treatment"]/["treat_selected"] সাজিয়ে
    (selected_machines_set, summary_text) রিটার্ন করে — কলার তখন মেশিন-বাছাই কীবোর্ড দেখাবে।
    """
    patient_id = patient.get("Patient_ID", "")
    plan = sheets.get_active_plan_for_patient(patient_id)
    if plan is None:
        stop_text = (
            f"⚠️ {patient.get('Full_Name')} ({patient_id})-এর কোনো Active ট্রিটমেন্ট প্ল্যান নেই।\n\n"
            "আগে 🩺 ট্রিটমেন্ট প্ল্যান বাটনে গিয়ে একটা প্ল্যান বানাও, তারপর এখানে ফিরে এসো।"
        )
        return None, stop_text

    session_no = int(plan.get("Sessions_Done", 0) or 0) + 1
    context.user_data["treatment"] = {
        "Patient_ID": patient_id,
        "Patient_Name": patient.get("Full_Name", ""),
        "Plan_ID": plan.get("Plan_ID", ""),
        "Diagnosis": plan.get("Diagnosis", ""),
        "Treatment_Given": "",
        "Exercise": plan.get("Exercise_Plan", ""),
        "Electrotherapy": plan.get("Electrotherapy_Plan", ""),
        "Manual_Therapy": plan.get("Manual_Therapy_Plan", ""),
        "Session_No": session_no,
    }

    last_note = sheets.get_last_treatment_note_for_patient(patient_id)
    prev_machines = []
    if last_note:
        prev_machines = [m.strip() for m in str(last_note.get("Machines", "")).split(",") if m.strip()]
    selected = {idx for idx, name in enumerate(MACHINE_LIST) if name in prev_machines}
    context.user_data["treat_selected"] = selected

    total = plan.get("Total_Sessions", "N/A")
    summary = (
        f"📋 {patient.get('Full_Name')} ({patient_id}) — সেশন {session_no}/{total}\n\n"
        f"সমস্যা (Diagnosis): {plan.get('Diagnosis') or '-'}\n"
        f"এক্সারসাইজ: {plan.get('Exercise_Plan') or '-'}\n"
        f"ইলেক্ট্রোথেরাপি: {plan.get('Electrotherapy_Plan') or '-'}\n"
        f"ম্যানুয়াল থেরাপি: {plan.get('Manual_Therapy_Plan') or '-'}\n\n"
        "আজকের মেশিন/মোডালিটি বেছে নাও, তারপর সম্পন্ন চাপো:"
    )
    return selected, summary


async def treat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ট্রিটমেন্ট নোট এন্ট্রি শুরু — রোগী খোঁজা দিয়ে শুরু হয়।"""
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_TREATMENT_NOTE):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["treatment"] = {}
    context.user_data["treat_selected"] = set()
    await update.message.reply_text(
        "রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):",
        reply_markup=ReplyKeyboardRemove(),
    )
    recent_kb = _recent_patient_buttons("treatsel_")
    if recent_kb:
        await update.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return TREAT_SEARCH


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
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=_patient_search_buttons(results, "treatsel_", "treatsearchback"),
    )
    return TREAT_SELECT


async def treat_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("treatsel_", "")
    results = context.user_data.get("treat_search_results", {})
    patient = results.get(patient_id) or sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text(
            "❌ তালিকার মেয়াদ শেষ। আবার শুরু করতে /cancel দাও, তারপর 📝 ট্রিটমেন্ট নোট চাপো।"
        )
        return ConversationHandler.END
    context.user_data.pop("treat_search_results", None)

    selected, summary = await _treat_prepare_for_patient(patient, context)
    if selected is None:
        await query.edit_message_text(summary)
        return ConversationHandler.END

    await query.edit_message_text(summary, reply_markup=_machine_keyboard(selected))
    return TREAT_MACHINES


async def treat_back_to_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """মেশিন-নির্বাচনের ধাপ থেকে '⬅️ আগের ধাপ' চাপলে আবার রোগী খোঁজার ধাপে ফিরে যায়।"""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_selected", None)
    await query.edit_message_text("⬅️ রোগী খোঁজার ধাপে ফিরে যাওয়া হলো।")
    await query.message.reply_text("রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):")
    recent_kb = _recent_patient_buttons("treatsel_")
    if recent_kb:
        await query.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return TREAT_SEARCH


async def treat_machine_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.replace("trm_", ""))
    selected = context.user_data.get("treat_selected", set())
    if idx in selected:
        selected.discard(idx)
    else:
        selected.add(idx)
    context.user_data["treat_selected"] = selected
    await query.edit_message_reply_markup(reply_markup=_machine_keyboard(selected))
    return TREAT_MACHINES


async def treat_machine_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    t = context.user_data.get("treatment", {})
    selected = context.user_data.get("treat_selected", set())
    t["Machines"] = ", ".join(MACHINE_LIST[i] for i in sorted(selected))
    patient_id = t.get("Patient_ID", "")
    try:
        treatment_id = sheets.add_treatment_note(t, created_by=staff.get("Full_Name", "Unknown"))
        sheets.increment_plan_session(patient_id)
        await query.edit_message_text(
            f"✅ ট্রিটমেন্ট নোট সেভ হয়েছে! Treatment ID: {treatment_id}\n"
            f"সেশন: {t.get('Session_No', '?')}\n"
            f"মেশিন: {t['Machines'] or '(কিছু বাছাই করা হয়নি)'}"
        )
    except Exception as e:
        logger.exception("treat_machine_done ব্যর্থ হয়েছে")
        await query.edit_message_text(f"❌ সেভ করতে সমস্যা হয়েছে।\nError: {e}")
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_selected", None)
    await query.message.reply_text(
        "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(staff.get("Role", ""))
    )
    return ConversationHandler.END


async def treat_machine_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_selected", None)
    await query.edit_message_text("❌ বাতিল করা হয়েছে।")
    await query.message.reply_text(
        "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(staff.get("Role", ""))
    )
    return ConversationHandler.END


async def treat_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_selected", None)
    context.user_data.pop("treat_search_results", None)
    await update.effective_message.reply_text(
        "ট্রিটমেন্ট নোট এন্ট্রি বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END


# ---------- ট্রিটমেন্ট প্ল্যান (কোর্সের জন্য একবার লেখা হয়) ----------

async def tplan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_TREATMENT_PLAN):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["tplan"] = {}
    await update.message.reply_text(
        "রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):",
        reply_markup=ReplyKeyboardRemove(),
    )
    recent_kb = _recent_patient_buttons("tplansel_")
    if recent_kb:
        await update.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
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
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=_patient_search_buttons(results, "tplansel_", "tplansearchback"),
    )
    return TPLAN_SELECT


async def tplan_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("tplansel_", "")
    results = context.user_data.get("tplan_search_results", {})
    patient = results.get(patient_id) or sheets.get_patient_by_id(patient_id)
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

    warn = ""
    active = sheets.get_active_plan_for_patient(patient_id)
    if active:
        warn = (
            f"⚠️ খেয়াল করো — এই রোগীর ইতিমধ্যে একটা Active প্ল্যান আছে "
            f"({active.get('Plan_ID')}, {active.get('Sessions_Done')}/{active.get('Total_Sessions')} সেশন)। "
            "নতুন প্ল্যান বানালে সেটা আলাদা হিসেবে যোগ হবে।\n\n"
        )

    last_plan = sheets.get_last_plan_for_patient(patient_id)
    context.user_data["tplan_prev"] = last_plan or {}
    prev_diag = (last_plan or {}).get("Diagnosis", "")
    hint = f" (আগেরটা: {prev_diag} — একই রাখতে - দাও)" if prev_diag else ""

    await query.edit_message_text(
        f"{warn}✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient_id})"
    )
    await query.message.reply_text(
        f"সমস্যা/পর্যবেক্ষণ (Diagnosis) লেখো{hint}:",
        reply_markup=_skip_keyboard() if prev_diag else ReplyKeyboardRemove(),
    )
    return TPLAN_DIAGNOSIS


async def tplan_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    prev = context.user_data.get("tplan_prev", {})
    if text == "-" and prev.get("Diagnosis"):
        text = prev.get("Diagnosis", "")
    context.user_data["tplan"]["Diagnosis"] = text

    prev_total = prev.get("Total_Sessions", "")
    hint = f" (আগেরটা: {prev_total})" if prev_total else ""
    await update.message.reply_text(
        f"মোট কয়টা সেশনের প্ল্যান (যেমন: 5){hint}:",
        reply_markup=_number_keyboard([str(n) for n in range(1, 11)]),
    )
    return TPLAN_TOTAL


async def tplan_total(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        total = int(text)
        if total <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ শুধু একটা ধনাত্মক সংখ্যা লেখো (উদাহরণ: 5):")
        return TPLAN_TOTAL
    context.user_data["tplan"]["Total_Sessions"] = total

    prev = context.user_data.get("tplan_prev", {})
    prev_ex = prev.get("Exercise_Plan", "")
    hint = f" (আগেরটা: {prev_ex} — একই রাখতে - দাও)" if prev_ex else " (না থাকলে - দাও)"
    await update.message.reply_text(f"এক্সারসাইজ প্ল্যান লেখো{hint}:", reply_markup=_skip_keyboard())
    return TPLAN_EXERCISE


async def tplan_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    prev = context.user_data.get("tplan_prev", {})
    if text == "-":
        text = prev.get("Exercise_Plan", "") or ""
    context.user_data["tplan"]["Exercise_Plan"] = text

    prev_el = prev.get("Electrotherapy_Plan", "")
    hint = f" (আগেরটা: {prev_el} — একই রাখতে - দাও)" if prev_el else " (না থাকলে - দাও)"
    await update.message.reply_text(f"ইলেক্ট্রোথেরাপি প্ল্যান লেখো{hint}:", reply_markup=_skip_keyboard())
    return TPLAN_ELECTRO


async def tplan_electro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    prev = context.user_data.get("tplan_prev", {})
    if text == "-":
        text = prev.get("Electrotherapy_Plan", "") or ""
    context.user_data["tplan"]["Electrotherapy_Plan"] = text

    prev_man = prev.get("Manual_Therapy_Plan", "")
    hint = f" (আগেরটা: {prev_man} — একই রাখতে - দাও)" if prev_man else " (না থাকলে - দাও)"
    await update.message.reply_text(f"ম্যানুয়াল থেরাপি প্ল্যান লেখো{hint}:", reply_markup=_skip_keyboard())
    return TPLAN_MANUAL


async def tplan_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    prev = context.user_data.get("tplan_prev", {})
    if text == "-":
        text = prev.get("Manual_Therapy_Plan", "") or ""
    context.user_data["tplan"]["Manual_Therapy_Plan"] = text

    t = context.user_data["tplan"]
    summary = (
        "নিচের প্ল্যান ঠিক আছে কিনা চেক করো:\n\n"
        f"রোগী: {t['Patient_Name']} ({t['Patient_ID']})\n"
        f"সমস্যা: {t['Diagnosis']}\n"
        f"মোট সেশন: {t['Total_Sessions']}\n"
        f"এক্সারসাইজ: {t['Exercise_Plan'] or '-'}\n"
        f"ইলেক্ট্রোথেরাপি: {t['Electrotherapy_Plan'] or '-'}\n"
        f"ম্যানুয়াল থেরাপি: {t['Manual_Therapy_Plan'] or '-'}\n\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(summary, reply_markup=confirm_keyboard)
    return TPLAN_CONFIRM


async def tplan_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    t = context.user_data.get("tplan", {})

    if text not in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        context.user_data.pop("tplan", None)
        context.user_data.pop("tplan_prev", None)
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।", reply_markup=_menu_keyboard(staff.get("Role", ""))
        )
        return ConversationHandler.END

    try:
        plan_id = sheets.add_treatment_plan(t, created_by=staff.get("Full_Name", "Unknown"))
        await update.message.reply_text(
            f"✅ ট্রিটমেন্ট প্ল্যান সেভ হয়েছে! Plan ID: {plan_id}\n"
            "এখন থেকে 📝 ট্রিটমেন্ট নোট-এ এই রোগীর দৈনিক এন্ট্রি এই প্ল্যান থেকে অটো-ফিল হবে।",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    except Exception as e:
        logger.exception("tplan_confirm ব্যর্থ হয়েছে")
        await update.message.reply_text(
            f"❌ প্ল্যান সেভ করতে সমস্যা হয়েছে।\nError: {e}\n\n"
            "স্ক্রিনশট দিয়ে জানাও, ঠিক করে দেওয়া হবে।",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    context.user_data.pop("tplan", None)
    context.user_data.pop("tplan_prev", None)
    return ConversationHandler.END


async def tplan_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("tplan", None)
    context.user_data.pop("tplan_prev", None)
    context.user_data.pop("tplan_search_results", None)
    await update.effective_message.reply_text(
        "ট্রিটমেন্ট প্ল্যান বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END


def _register_amount_keyboard(sessions: int) -> InlineKeyboardMarkup:
    sess_label = "🔁 ২ সেশন হয়েছে" if sessions == 1 else "🔁 ১ সেশনে ফেরত যাও"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(sess_label, callback_data="regsesstoggle")],
        [
            InlineKeyboardButton("৳400", callback_data="regamt_400"),
            InlineKeyboardButton("✏️ অন্য পরিমাণ", callback_data="regamt_custom"),
        ],
    ])


def _register_amount_prompt_text(patient_name: str, patient_id: str, sessions: int) -> str:
    return (
        f"রোগী: {patient_name} ({patient_id})\n"
        f"সেশন: {sessions}  (ডিফল্ট ১, আজ ২টা সেশন হলে উপরের বাটনে চাপো)\n\n"
        "কত টাকা নেওয়া হলো?"
    )


def _register_view_text_and_keyboard():
    reg = sheets.get_daily_register()
    lines = [f"📋 আজকের রেজিস্টার ({reg['date']})", ""]
    if not reg["rows"]:
        lines.append("আজ এখনো কোনো এন্ট্রি হয়নি।")
    else:
        for r in reg["rows"]:
            lines.append(f"{r['Sl']}. {r['Patient_Name']} — সেশন: {r['Sessions']}")
        lines.append("")
        lines.append(f"👥 মোট রোগী: {reg['total_patients']}   🩺 মোট সেশন: {reg['total_sessions']}")
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("➕ নতুন এন্ট্রি", callback_data="regnew")]])
    return "\n".join(lines), keyboard


async def register_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    if not roles.can_access(staff.get("Role", ""), roles.MENU_DAILY_REGISTER):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    text, keyboard = _register_view_text_and_keyboard()
    await update.message.reply_text(text, reply_markup=keyboard)


async def reg_new_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    context.user_data["payment"] = {}
    await query.message.reply_text("রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):")
    recent_kb = _recent_patient_buttons("paysel_")
    if recent_kb:
        await query.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return PAY_SEARCH


async def reg_session_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    p = context.user_data.get("payment", {})
    sessions = 2 if p.get("Sessions", 1) == 1 else 1
    context.user_data.setdefault("payment", {})["Sessions"] = sessions
    await query.edit_message_text(
        _register_amount_prompt_text(p.get("Patient_Name", ""), p.get("Patient_ID", ""), sessions),
        reply_markup=_register_amount_keyboard(sessions),
    )
    return PAY_AMOUNT


async def reg_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.replace("regamt_", "")
    if choice == "custom":
        await query.edit_message_text("কত টাকা নেওয়া হলো লেখো (শুধু সংখ্যা):")
        return PAY_AMOUNT
    try:
        amount = float(choice)
    except ValueError:
        amount = 0.0
    context.user_data.setdefault("payment", {})["Amount"] = amount
    await query.edit_message_text(f"টাকা: {amount:.0f}")
    await query.message.reply_text(
        "Payment Method বেছে নাও:", reply_markup=_payment_method_keyboard()
    )
    return PAY_METHOD


async def reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    if not roles.can_access(staff.get("Role", ""), roles.MENU_REPORTS):
        return
    today_str = bd_now().strftime("%Y-%m-%d")
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
    results = results[:10]
    await update.message.reply_text(
        "কোন রোগীর ট্রিটমেন্ট হিস্টরি দেখতে চাও?",
        reply_markup=_patient_search_buttons(results, "thpsel_", "thistsearchback"),
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
        buttons.append([InlineKeyboardButton(f"🗓 {date_str} — {tid}", callback_data=f"thdate_{tid}")])
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
    patient_id = str(n.get("Patient_ID", "")).strip()
    context.user_data.pop("thist_notes", None)
    if patient_id:
        await query.edit_message_text("\n".join(lines), reply_markup=_patient_card_keyboard(patient_id))
    else:
        await query.edit_message_text("\n".join(lines))
    return ConversationHandler.END


async def thist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("thist_notes", None)
    await update.effective_message.reply_text("বাতিল করা হয়েছে।")
    return ConversationHandler.END


def _build_full_history_text(patient_id: str) -> str | None:
    """রোগীর সম্পূর্ণ ইতিহাস (প্রোফাইল + পেমেন্ট + অ্যাপয়েন্টমেন্ট + ট্রিটমেন্ট নোট) টেক্সট বানায়।
    আগে hist_select_callback() আর plist_action_hist() -এ এই একই কোড হুবহু দুইবার লেখা ছিল —
    এখন দুটোই এই একটামাত্র ফাংশন কল করে, তাই এক জায়গায় ফিক্স করলেই দুই জায়গায় কাজ করবে।"""
    patient = sheets.get_patient_by_id(patient_id)
    if patient is None:
        return None

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
    return full_text


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
    results = results[:10]
    await update.message.reply_text(
        "কোন রোগী দেখতে চাও?",
        reply_markup=_patient_search_buttons(results, "histsel_", "histsearchback"),
    )
    return "HIST_SEARCH"


async def hist_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("histsel_", "", 1)

    full_text = _build_full_history_text(patient_id)
    if full_text is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return ConversationHandler.END

    await query.edit_message_text(full_text, reply_markup=_patient_card_keyboard(patient_id))
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
    port = int(os.environ.get("PORT", 10000))

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
        [InlineKeyboardButton("📎 রিপোর্ট", callback_data=f"plistact_report_{patient_id}")],
        [InlineKeyboardButton("👁️ ফাইল দেখুন", callback_data=f"plistact_viewfiles_{patient_id}")],
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
    if not context.user_data.get("plist_patients"):
        # Action Panel অন্য ফ্লো (Present/History/Treatment History) থেকে এলে
        # plist_patients cache করা নাও থাকতে পারে — তখন এখানে বানিয়ে নেওয়া হয়,
        # যাতে "🔙 তালিকায় ফিরুন" কখনো খালি স্ক্রিন না দেখায়।
        patients = [
            p for p in sheets.get_all_patients()
            if str(p.get("Status", "")).strip() == "Active"
        ]
        patients.sort(key=lambda p: p.get("Full_Name", ""))
        context.user_data["plist_patients"] = {
            p.get("Patient_ID", "").strip(): p for p in patients
        }
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
        "Sessions": 1,
    }
    await query.edit_message_text(
        _register_amount_prompt_text(patient.get("Full_Name", ""), patient.get("Patient_ID", ""), 1),
        reply_markup=_register_amount_keyboard(1),
    )
    return PAY_AMOUNT


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
    context.user_data.pop("apt_dates", None)
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})"
    )
    await query.message.reply_text(
        "তারিখ বেছে নাও — একাধিক দিনও বাছাই করা যাবে (একাধিকবার চাপো), তারপর 'পরের ধাপ' চাপো:",
        reply_markup=_date_multi_keyboard(set()),
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

    selected, summary = await _treat_prepare_for_patient(patient, context)
    if selected is None:
        await query.edit_message_text(summary)
        return ConversationHandler.END

    await query.edit_message_text(summary, reply_markup=_machine_keyboard(selected))
    return TREAT_MACHINES


async def plist_action_hist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_hist_", "")

    full_text = _build_full_history_text(patient_id)
    if full_text is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return

    await query.edit_message_text(full_text, reply_markup=_patient_card_keyboard(patient_id))



REPORT_UPLOAD = "REPORT_UPLOAD"


async def plist_action_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_report_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["report_patient"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
    }
    await query.edit_message_text(
        f"📎 {patient.get('Full_Name')} ({patient_id})-এর জন্য রিপোর্ট (ছবি/ফাইল) পাঠাও।\n"
        "একাধিক ফাইল পাঠাতে চাইলে একটার পর একটা পাঠাতে থাকো। শেষ হলে /cancel দাও।"
    )
    return REPORT_UPLOAD


async def report_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import os
    import tempfile
    import drive as drive_module

    staff = context.user_data.get("staff", {})
    rp = context.user_data.get("report_patient")
    if not rp:
        await update.message.reply_text("❌ সমস্যা হয়েছে, আবার 📋 রোগীর তালিকা থেকে শুরু করো।")
        return ConversationHandler.END

    file_obj = None
    file_name = ""
    file_type = ""
    if update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
        file_name = f"{rp['Patient_ID']}_{file_obj.file_unique_id}.jpg"
        file_type = "Photo"
    elif update.message.document:
        doc = update.message.document
        file_obj = await doc.get_file()
        file_name = doc.file_name or f"{rp['Patient_ID']}_{doc.file_unique_id}"
        file_type = "Document"
    else:
        await update.message.reply_text("❌ শুধু ছবি বা ফাইল পাঠাও।")
        return REPORT_UPLOAD

    tmp_dir = tempfile.gettempdir()
    local_path = os.path.join(tmp_dir, file_name)
    await file_obj.download_to_drive(local_path)

    drive_link = ""
    try:
        _drive_id, drive_link = drive_module.upload_file_to_drive(local_path, file_name)
    except Exception:
        logger.exception("Drive আপলোড ব্যর্থ হয়েছে, শুধু Telegram-এ সংরক্ষিত থাকবে")

    try:
        report_id = sheets.add_report({
            "Patient_ID": rp["Patient_ID"],
            "Patient_Name": rp["Patient_Name"],
            "File_Telegram_ID": file_obj.file_id,
            "File_Name": file_name,
            "File_Type": file_type,
            "File_Drive_Link": drive_link,
        }, uploaded_by=staff.get("Full_Name", "Unknown"))
        note = "" if drive_link else "\n(⚠️ Drive ব্যাকআপ হয়নি, শুধু Telegram-এ সংরক্ষিত আছে)"
        await update.message.reply_text(
            f"✅ রিপোর্ট সেভ হয়েছে! Report ID: {report_id}{note}\n"
            "আরেকটা পাঠাতে চাইলে পাঠাও, নাহলে /cancel দাও।"
        )
    except Exception as e:
        logger.exception("report_receive শীটে সেভ করতে ব্যর্থ হয়েছে")
        await update.message.reply_text(f"❌ সেভ করতে সমস্যা হয়েছে।\nError: {e}")
    finally:
        try:
            os.remove(local_path)
        except OSError:
            pass
    return REPORT_UPLOAD


async def report_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("report_patient", None)
    await update.effective_message.reply_text(
        "রিপোর্ট আপলোড শেষ।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END



async def plist_action_viewfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_viewfiles_", "")
    staff = context.user_data.get("staff", {})
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return
    role = staff.get("Role", "").strip()
    allowed = role in ("Owner", "Manager") or (
        role == "Therapist" and roles.is_therapist_owner_of_patient(staff.get("Full_Name", ""), patient)
    )
    if not allowed:
        await query.edit_message_text("⛔ এই রোগীর ফাইল দেখার অনুমতি তোমার নেই।")
        return
    reports = sheets.get_reports_for_patient(patient_id)
    if not reports:
        await query.edit_message_text(f"📂 {patient.get('Full_Name')}-এর কোনো ফাইল এখনো আপলোড হয়নি।")
        return
    buttons = [
        [InlineKeyboardButton(
            f"{r.get('File_Type', 'ফাইল')} — {r.get('Upload_Date', '')}",
            callback_data=f"plistact_getfile_{r.get('Report_ID', '')}",
        )]
        for r in reversed(reports)
    ]
    buttons.append([InlineKeyboardButton("🔙 তালিকায় ফিরুন", callback_data="plistact_back")])
    await query.edit_message_text(
        f"📂 {patient.get('Full_Name')}-এর ফাইল ({len(reports)}টি) — দেখতে চাপো:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def plist_action_getfile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    report_id = query.data.replace("plistact_getfile_", "")
    staff = context.user_data.get("staff", {})
    record = sheets.get_report_by_id(report_id)
    if not record:
        await query.message.reply_text("❌ ফাইল পাওয়া যায়নি।")
        return
    patient = sheets.get_patient_by_id(record.get("Patient_ID", ""))
    role = staff.get("Role", "").strip()
    allowed = patient and (
        role in ("Owner", "Manager") or (
            role == "Therapist" and roles.is_therapist_owner_of_patient(staff.get("Full_Name", ""), patient)
        )
    )
    if not allowed:
        await query.message.reply_text("⛔ এই ফাইল দেখার অনুমতি তোমার নেই।")
        return
    caption = f"{record.get('File_Type', '')} — {record.get('Upload_Date', '')} ({record.get('Patient_Name', '')})"
    tg_id = record.get("File_Telegram_ID", "")
    sent = False
    if tg_id:
        try:
            if str(record.get("File_Type", "")).strip() == "Photo":
                await context.bot.send_photo(chat_id=query.message.chat_id, photo=tg_id, caption=caption)
            else:
                await context.bot.send_document(chat_id=query.message.chat_id, document=tg_id, caption=caption)
            sent = True
        except Exception:
            logger.exception("Telegram file_id দিয়ে পাঠাতে ব্যর্থ")
    if not sent:
        link = record.get("File_Drive_Link", "")
        if link:
            await query.message.reply_text(f"{caption}\nDrive লিংক: {link}")
        else:
            await query.message.reply_text("❌ ফাইলটা এখন খুলতে পারা যাচ্ছে না।")


async def date_report_menu(update, context):
    today = bd_now().date()
    await update.message.reply_text(
        "📅 তারিখ সিলেক্ট করুন:",
        reply_markup=calendar_helper.build_calendar(today.year, today.month)
    )

async def date_report_calendar_navigate(update, context):
    query = update.callback_query
    await query.answer()
    year, month = map(int, query.data.split("_", 1)[1].split("-"))
    await query.edit_message_reply_markup(reply_markup=calendar_helper.build_calendar(year, month))

async def date_report_day_selected(update, context):
    query = update.callback_query
    await query.answer()
    date_str = query.data.split("_", 1)[1]
    year, month, day = map(int, date_str.split("-"))

    patient_list = sheets.get_daily_patient_list(date_str)
    if patient_list:
        list_lines = "\n".join(
            f"{i+1}. {p['name']} — {p['session']} — {p['amount']:.0f} টাকা"
            for i, p in enumerate(patient_list)
        )
        text = f"📋 {date_str} — রোগীর তালিকা:\n{list_lines}"
    else:
        text = f"📋 {date_str} — এই তারিখে কোনো রোগীর এন্ট্রি পাওয়া যায়নি।"

    await query.edit_message_text(text, reply_markup=calendar_helper.build_calendar(year, month))


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
        MessageHandler(filters.Regex(f"^{roles.MENU_DAILY_REGISTER}$"), register_menu)
    )

    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_PATIENT_LIST}$"), patient_list_start)
    )
    app.add_handler(CallbackQueryHandler(patient_list_page_callback, pattern="^plistpage_"))
    app.add_handler(CallbackQueryHandler(patient_list_select_callback, pattern="^plistsel_"))
    app.add_handler(CallbackQueryHandler(patient_list_back_callback, pattern="^plistact_back$"))
    app.add_handler(CallbackQueryHandler(plist_action_viewfiles, pattern="^plistact_viewfiles_"))
    app.add_handler(CallbackQueryHandler(plist_action_getfile, pattern="^plistact_getfile_"))
    app.add_handler(CallbackQueryHandler(plist_action_hist, pattern="^plistact_hist_"))
    report_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(plist_action_report, pattern="^plistact_report_")],
        states={
            REPORT_UPLOAD: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, report_receive),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", report_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(report_conv)

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
            APT_SEARCH: [
                CallbackQueryHandler(apt_select_callback, pattern="^aptsel_"),
                CallbackQueryHandler(_apt_search_cancel, pattern="^aptsearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_search),
            ],
            APT_SELECT: [
                CallbackQueryHandler(apt_select_callback, pattern="^aptsel_"),
                CallbackQueryHandler(_apt_search_cancel, pattern="^aptsearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_select),
            ],
            APT_DATE: [
                CallbackQueryHandler(apt_date_toggle_callback, pattern="^aptdatetoggle_"),
                CallbackQueryHandler(apt_date_done_callback, pattern="^aptdatedone$"),
                CallbackQueryHandler(apt_back_to_search_callback, pattern="^aptback_search$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_date),
            ],
            APT_TIME: [
                CallbackQueryHandler(apt_time_callback, pattern="^apttime_"),
                CallbackQueryHandler(apt_back_to_date_callback, pattern="^aptback_date$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_time),
            ],
            APT_THERAPIST: [
                CallbackQueryHandler(apt_therapist_callback, pattern="^aptther_"),
                CallbackQueryHandler(apt_back_to_time_callback, pattern="^aptback_time$"),
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
            CallbackQueryHandler(reg_new_start, pattern="^regnew$"),
        ],
        states={
            PAY_SEARCH: [
                CallbackQueryHandler(pay_select_callback, pattern="^paysel_"),
                CallbackQueryHandler(_pay_search_cancel, pattern="^paysearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_search),
            ],
            PAY_SELECT: [
                CallbackQueryHandler(pay_select_callback, pattern="^paysel_"),
                CallbackQueryHandler(_pay_search_cancel, pattern="^paysearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_select),
            ],
            PAY_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_session)],
            PAY_AMOUNT: [
                CallbackQueryHandler(reg_amount_callback, pattern="^regamt_"),
                CallbackQueryHandler(reg_session_toggle, pattern="^regsesstoggle$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_amount),
            ],
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
                CallbackQueryHandler(treat_select_callback, pattern="^treatsel_"),
                CallbackQueryHandler(_treat_search_cancel, pattern="^treatsearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_search),
            ],
            TREAT_SELECT: [
                CallbackQueryHandler(treat_select_callback, pattern="^treatsel_"),
                CallbackQueryHandler(_treat_search_cancel, pattern="^treatsearchback$"),
            ],
            TREAT_MACHINES: [
                CallbackQueryHandler(treat_machine_toggle, pattern="^trm_"),
                CallbackQueryHandler(treat_machine_done, pattern="^trdone_"),
                CallbackQueryHandler(treat_back_to_search_callback, pattern="^trback_search$"),
                CallbackQueryHandler(treat_machine_cancel_callback, pattern="^trcancel_"),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", treat_cancel),
            CommandHandler("start", _restart_via_start),],
    )
    app.add_handler(treat_conv)

    tplan_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_TREATMENT_PLAN}$"), tplan_start),
        ],
        states={
            TPLAN_SEARCH: [
                CallbackQueryHandler(tplan_select_callback, pattern="^tplansel_"),
                CallbackQueryHandler(_tplan_search_cancel, pattern="^tplansearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_search),
            ],
            TPLAN_SELECT: [
                CallbackQueryHandler(tplan_select_callback, pattern="^tplansel_"),
                CallbackQueryHandler(_tplan_search_cancel, pattern="^tplansearchback$"),
            ],
            TPLAN_DIAGNOSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_diagnosis)],
            TPLAN_TOTAL: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_total)],
            TPLAN_EXERCISE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_exercise)],
            TPLAN_ELECTRO: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_electro)],
            TPLAN_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_manual)],
            TPLAN_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", tplan_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(tplan_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{roles.MENU_REPORTS}$"), reports_menu))
    app.add_handler(MessageHandler(filters.Regex(f"^{roles.MENU_DATE_REPORT}$"), date_report_menu))
    app.add_handler(CallbackQueryHandler(date_report_calendar_navigate, pattern="^calnav_"))
    app.add_handler(CallbackQueryHandler(date_report_day_selected, pattern="^calday_"))
    hist_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{roles.MENU_PATIENT_HISTORY}$"), hist_start)],
        states={
            "HIST_SEARCH": [
                CallbackQueryHandler(hist_select_callback, pattern="^histsel_"),
                CallbackQueryHandler(_hist_search_cancel, pattern="^histsearchback$"),
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
                CallbackQueryHandler(_thist_search_cancel, pattern="^thistsearchback$"),
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
