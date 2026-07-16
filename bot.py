"""
bot.py — Relife Clinic OS Telegram Bot (প্রথম ভার্সন)
"""

import logging
import os
import re
import threading
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
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
    PAY_TIME,
    PAY_CONFIRM,
) = range(13, 20)

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
) = range(20, 30)

PAY_METHODS = ["Cash", "bKash", "Nagad", "Card"]

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
    roles.MENU_TODAY_REGISTER,
]
_ALL_MENU_REGEX = "^(" + "|".join(re.escape(x) for x in _ALL_MENU_ITEMS) + ")$"


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


def _payment_method_keyboard() -> ReplyKeyboardMarkup:
    rows = [PAY_METHODS[i : i + 2] for i in range(0, len(PAY_METHODS), 2)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


# QUICK-BUTTON-HELPERS
def _skip_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["-"]], resize_keyboard=True, one_time_keyboard=True)


def _number_keyboard(nums, per_row: int = 5) -> ReplyKeyboardMarkup:
    rows = [nums[i : i + per_row] for i in range(0, len(nums), per_row)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


SESSION_TYPES = ["1", "1+1", "2", "2+1", "-"]


def _session_type_keyboard() -> ReplyKeyboardMarkup:
    rows = [SESSION_TYPES[i : i + 3] for i in range(0, len(SESSION_TYPES), 3)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def _session_count(session_type: str) -> int:
    """'1+1' স্টাইলের সেশন টেক্সট থেকে মোট সংখ্যা বের করে (প্যাকেজ সেশন গুনতে ব্যবহৃত)।
    উদাহরণ: '1+1' -> 2, '2' -> 2, '-' -> 0."""
    nums = re.findall(r"\d+", session_type or "")
    return sum(int(n) for n in nums)


def _time_keyboard_quick() -> ReplyKeyboardMarkup:
    now_str = datetime.now().strftime("%I:%M %p")
    return ReplyKeyboardMarkup(
        [[f"এখন ({now_str})"]], resize_keyboard=True, one_time_keyboard=True
    )


def _recent_patient_keyboard(limit: int = 10) -> InlineKeyboardMarkup:
    """সবচেয়ে নতুন রেজিস্ট্রেশন করা রোগীদের বাটন আকারে দেখায়।"""
    patients = sheets.get_recent_patients(limit)
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
            callback_data=f"plsel_{p.get('Patient_ID')}",
        )]
        for p in patients
    ]
    return InlineKeyboardMarkup(buttons)


def _patient_action_keyboard(role_str: str, patient_id: str, done: set | None = None) -> InlineKeyboardMarkup:
    """রোল অনুযায়ী কোন কোন অ্যাকশন এই স্টাফ করতে পারবে, তার বাটন বানায়।
    ইতিমধ্যে যেগুলো করা হয়ে গেছে (done) সেগুলো বাদ দিয়ে দেখায়।"""
    done = done or set()
    buttons = []
    for code in roles.get_patient_actions(role_str):
        if code in done:
            continue
        label = roles.PATIENT_ACTION_LABELS.get(code, code)
        buttons.append([InlineKeyboardButton(label, callback_data=f"plact_{code}_{patient_id}")])
    buttons.append([InlineKeyboardButton("✅ শেষ", callback_data=f"pldone_{patient_id}")])
    return InlineKeyboardMarkup(buttons)


async def _send_patient_action_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, patient_id: str):
    """রোগী বাছাই / উপস্থিত মার্ক করার পর, অথবা একটা কাজ (পেমেন্ট/অ্যাপয়েন্টমেন্ট/ট্রিটমেন্ট) শেষ হওয়ার পর
    বাকি প্রযোজ্য অ্যাকশন বাটন দেখায় — যাতে একই ভিজিটে একাধিক কাজ চেইন করে করা যায়।"""
    staff = context.user_data.get("staff", {})
    role = staff.get("Role", "")
    patient = sheets.get_patient_by_id(patient_id)
    name = patient.get("Full_Name", patient_id) if patient else patient_id
    done = context.user_data.get("pl_done", set())
    remaining = [c for c in roles.get_patient_actions(role) if c not in done]
    text = (
        f"👤 {name} ({patient_id})\n\nআর কী করতে চাও?"
        if remaining
        else f"👤 {name} ({patient_id}) — তোমার সব কাজ শেষ। ✅"
    )
    await update.effective_message.reply_text(
        text, reply_markup=_patient_action_keyboard(role, patient_id, done)
    )


async def _finish_patient_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action_code: str | None):
    """পেমেন্ট/অ্যাপয়েন্টমেন্ট/ট্রিটমেন্ট কনভারসেশন শেষ হওয়ার পর ডাকা হয়।
    'রোগী তালিকা' বা 'উপস্থিত' চেইন থেকে শুরু হলে বাকি অ্যাকশন বাটন দেখায়,
    না হলে সাধারণ রিপ্লাই-কীবোর্ড মেনু দেখায়।"""
    staff = context.user_data.get("staff", {})
    patient_id = context.user_data.get("pl_patient_id")
    if patient_id:
        if action_code:
            context.user_data.setdefault("pl_done", set()).add(action_code)
        await _send_patient_action_menu(update, context, patient_id)
    else:
        await update.effective_message.reply_text(
            "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(staff.get("Role", ""))
        )


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


# ---------- 👥 রোগী তালিকা (কুইক অ্যাকশন হাব) ----------

async def patient_list_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    patients = sheets.get_recent_patients(10)
    if not patients:
        await update.message.reply_text("এখনো কোনো রোগী রেজিস্ট্রেশন করা হয়নি।")
        return
    await update.message.reply_text(
        "👥 সাম্প্রতিক রোগীরা — নাম চাপো:",
        reply_markup=_recent_patient_keyboard(10),
    )


async def patient_list_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plsel_", "", 1)
    staff = context.user_data.get("staff") or {}
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return
    context.user_data["pl_patient_id"] = patient_id
    context.user_data["pl_done"] = set()
    role = staff.get("Role", "")
    await query.edit_message_text(
        f"✅ {patient.get('Full_Name')} ({patient_id})\n\nকী করতে চাও?",
        reply_markup=_patient_action_keyboard(role, patient_id, set()),
    )


async def patient_list_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'✅ শেষ' চাপলে চলমান রোগী-অ্যাকশন চেইন শেষ করে সাধারণ মেনুতে ফিরে যায়।"""
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    context.user_data.pop("pl_patient_id", None)
    context.user_data.pop("pl_done", None)
    await query.edit_message_text("✅ শেষ হয়েছে।")
    await query.message.reply_text(
        "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(staff.get("Role", ""))
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

async def apt_start_from_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'👥 রোগী তালিকা' বা 'আজকের অ্যাপয়েন্টমেন্ট' থেকে সরাসরি — রোগী আগে থেকেই বাছাই করা,
    তাই সার্চ ধাপ বাদ দিয়ে সরাসরি তারিখ জিজ্ঞাসা করে।"""
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plact_apt_", "", 1)
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_APPOINTMENT):
        await query.edit_message_text("⛔ এই কাজে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["new_appointment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
        "Department": patient.get("Department", ""),
    }
    context.user_data["pl_patient_id"] = patient_id
    await query.edit_message_text(
        f"📅 রোগী: {patient.get('Full_Name')} ({patient_id})\n\n"
        "তারিখ বেছে নাও (অথবা টাইপ করো, উদাহরণ: 2026-07-15):"
    )
    await query.message.reply_text("তারিখ বেছে নাও 👇", reply_markup=_date_keyboard())
    return APT_DATE


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
    await query.message.reply_text("থেরাপিস্ট / ডাক্তারের নাম লেখো:")
    return APT_THERAPIST


async def apt_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Time"] = update.message.text.strip()
    await update.message.reply_text("থেরাপিস্ট / ডাক্তারের নাম লেখো:")
    return APT_THERAPIST


async def apt_therapist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Therapist"] = update.message.text.strip()
    a = context.user_data["new_appointment"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"রোগী: {a['Patient_Name']} ({a['Patient_ID']})\n"
        f"Department: {a.get('Department') or 'N/A (রোগীর প্রোফাইলে নেই)'}\n"
        f"তারিখ: {a['Date']}\nসময়: {a['Time']}\n"
        f"থেরাপিস্ট: {a['Therapist']}\n\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(summary, reply_markup=confirm_keyboard)
    return APT_CONFIRM


async def apt_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    _chain = bool(context.user_data.get("pl_patient_id"))
    kb = ReplyKeyboardRemove() if _chain else _menu_keyboard(staff.get("Role", ""))
    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        appointment_id = sheets.add_appointment(
            context.user_data["new_appointment"],
            created_by=staff.get("Full_Name", "Unknown"),
        )
        await update.message.reply_text(
            f"✅ অ্যাপয়েন্টমেন্ট বুক হয়েছে! Appointment ID: {appointment_id}",
            reply_markup=kb,
        )
    else:
        await update.message.reply_text("❌ বাতিল করা হয়েছে।", reply_markup=kb)
    context.user_data.pop("new_appointment", None)
    await _finish_patient_action(update, context, "apt")
    return ConversationHandler.END


async def apt_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("new_appointment", None)
    context.user_data.pop("apt_search_results", None)
    _chain = bool(context.user_data.get("pl_patient_id"))
    if _chain:
        await update.effective_message.reply_text("❌ বাতিল করা হয়েছে।")
        await _finish_patient_action(update, context, None)
    else:
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
            f"Department: {a.get('Department') or 'N/A'} | থেরাপিস্ট: {a.get('Therapist')}"
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
    if not ok:
        await query.edit_message_text("❌ আপডেট করা যায়নি।")
        return
    await query.edit_message_text(f"✅ {appointment_id} — স্ট্যাটাস: {status}")

    # রোগী উপস্থিত হলে, একই ভিজিটে যা যা করা লাগে তার বাটন সাথে সাথে দেখিয়ে দাও
    if status_code == "Completed":
        appt = sheets.get_appointment_by_id(appointment_id)
        patient_id = (appt or {}).get("Patient_ID", "").strip()
        if patient_id:
            context.user_data["pl_patient_id"] = patient_id
            context.user_data["pl_done"] = set()
            await _send_patient_action_menu(update, context, patient_id)


# ---------- 📋 আজকের রেজিস্টার (খাতার মতো SL-নাম-সেশন-সময়-বিল) ----------

async def today_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    if not roles.can_access(staff.get("Role", ""), roles.MENU_TODAY_REGISTER):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    date_str = datetime.now().strftime("%Y-%m-%d")
    rows = sheets.get_payments_for_date(date_str)
    if not rows:
        await update.message.reply_text("আজ এখনো কোনো এন্ট্রি হয়নি।")
        return

    lines = [f"📋 আজকের রেজিস্টার — {date_str}", ""]
    lines.append("SL  নাম               সেশন   সময়            বিল")
    total = 0.0
    for r in rows:
        sl = str(r.get("SL", ""))
        name = str(r.get("Patient_Name", ""))[:16].ljust(16)
        session = str(r.get("Session_Type", "-") or "-")[:5].ljust(5)
        time_ = str(r.get("Time", "-") or "-")[:13].ljust(13)
        amount = float(r.get("Amount", 0) or 0)
        total += amount
        lines.append(f"{sl:<3} {name} {session} {time_} {amount:.0f}৳")
    lines.append("")
    lines.append(f"মোট বিল: {total:.0f}৳  |  মোট রোগী: {len(rows)}")

    await update.message.reply_text(
        "```\n" + "\n".join(lines) + "\n```",
        parse_mode="Markdown",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )


# ---------- পেমেন্ট / বিল এন্ট্রি ----------

async def pay_start_from_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'👥 রোগী তালিকা' বা 'আজকের অ্যাপয়েন্টমেন্ট' থেকে সরাসরি — সার্চ ছাড়াই পেমেন্ট শুরু।"""
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plact_pay_", "", 1)
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_PAYMENT):
        await query.edit_message_text("⛔ এই কাজে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["payment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
        "Department": patient.get("Department", ""),
    }
    context.user_data["pl_patient_id"] = patient_id
    total_bill = patient.get("Total_Bill", 0) or 0
    paid_amount = patient.get("Paid_Amount", 0) or 0
    due_amount = patient.get("Due_Amount", 0) or 0
    await query.edit_message_text(
        f"💳 রোগী: {patient.get('Full_Name')} ({patient_id})\n\n"
        f"মোট বিল: {total_bill}\nজমা হয়েছে: {paid_amount}\nবাকি: {due_amount}"
    )
    await query.message.reply_text(
        "আজ সেশন কী হলো বেছে নাও (1 / 1+1 / 2 ...):",
        reply_markup=_session_type_keyboard(),
    )
    return PAY_SESSION


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
        "আজ সেশন কী হলো বেছে নাও (1 / 1+1 / 2 ...):",
        reply_markup=_session_type_keyboard(),
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
        "আজ সেশন কী হলো বেছে নাও (1 / 1+1 / 2 ...):"
    )
    return PAY_SESSION


async def pay_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_type = update.message.text.strip()
    context.user_data["payment"]["Session_Type"] = session_type
    context.user_data["payment"]["Sessions"] = _session_count(session_type)
    await update.message.reply_text(
        "কত টাকা নেওয়া হলো লেখো (শুধু সংখ্যা):", reply_markup=ReplyKeyboardRemove()
    )
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
    await update.message.reply_text(
        "সময় লেখো (উদাহরণ: 6:30-7:30), অথবা নিচের বাটনে ট্যাপ করো:",
        reply_markup=_time_keyboard_quick(),
    )
    return PAY_TIME


async def pay_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("এখন"):
        text = datetime.now().strftime("%I:%M %p")
    context.user_data["payment"]["Time"] = text
    p = context.user_data["payment"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"রোগী: {p['Patient_Name']} ({p['Patient_ID']})\n"
        f"সেশন: {p.get('Session_Type', '-')}\nসময়: {p['Time']}\n"
        f"টাকা: {p['Amount']}\nMethod: {p['Payment_Method']}\n\n"
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
    _chain = bool(context.user_data.get("pl_patient_id"))
    kb = ReplyKeyboardRemove() if _chain else _menu_keyboard(staff.get("Role", ""))

    if text not in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        context.user_data.pop("payment", None)
        await update.message.reply_text("❌ বাতিল করা হয়েছে।", reply_markup=kb)
        await _finish_patient_action(update, context, None)
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
            "Time": p.get("Time", ""),
            "Session_Type": p.get("Session_Type", ""),
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

        await update.message.reply_text("\n".join(lines), reply_markup=kb)
    except Exception as e:
        logger.exception("pay_confirm ব্যর্থ হয়েছে")
        await update.message.reply_text(
            f"❌ পেমেন্ট সেভ করতে সমস্যা হয়েছে।\nError: {e}\n\n"
            "স্ক্রিনশট দিয়ে জানাও, ঠিক করে দেওয়া হবে।",
            reply_markup=kb,
        )
    context.user_data.pop("payment", None)
    await _finish_patient_action(update, context, "pay")
    return ConversationHandler.END


async def pay_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("payment", None)
    context.user_data.pop("pay_search_results", None)
    _chain = bool(context.user_data.get("pl_patient_id"))
    if _chain:
        await update.effective_message.reply_text("❌ বাতিল করা হয়েছে।")
        await _finish_patient_action(update, context, None)
    else:
        await update.effective_message.reply_text(
            "পেমেন্ট এন্ট্রি বাতিল করা হয়েছে।",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    return ConversationHandler.END


# ---------- ট্রিটমেন্ট নোট (Physio SOAP-স্টাইল) ----------

async def treat_start_from_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'👥 রোগী তালিকা' বা 'আজকের অ্যাপয়েন্টমেন্ট' থেকে সরাসরি — সার্চ ছাড়াই ট্রিটমেন্ট নোট শুরু।"""
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plact_treat_", "", 1)
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_TREATMENT_NOTE):
        await query.edit_message_text("⛔ এই কাজে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["treatment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
    }
    context.user_data["pl_patient_id"] = patient_id
    await query.edit_message_text(f"📝 রোগী: {patient.get('Full_Name')} ({patient_id})")
    await query.message.reply_text("আজকের সমস্যা/পর্যবেক্ষণ (Diagnosis) লেখো:")
    return TREAT_DIAGNOSIS


async def treat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ট্রিটমেন্ট নোট এন্ট্রি শুরু — রোগী খোঁজা দিয়ে শুরু হয়।"""
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_TREATMENT_NOTE):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["treatment"] = {}
    await update.message.reply_text(
        "রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):",
        reply_markup=ReplyKeyboardRemove(),
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
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
            callback_data=f"treatsel_{p.get('Patient_ID')}",
        )]
        for p in results
    ]
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return TREAT_SELECT


async def treat_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("treatsel_", "")
    results = context.user_data.get("treat_search_results", {})
    patient = results.get(patient_id)
    if not patient:
        await query.edit_message_text(
            "❌ তালিকার মেয়াদ শেষ। আবার শুরু করতে /cancel দাও, তারপর 📝 ট্রিটমেন্ট নোট চাপো।"
        )
        return ConversationHandler.END
    context.user_data.setdefault("treatment", {})["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["treatment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data.pop("treat_search_results", None)
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})"
    )
    await query.message.reply_text("আজকের সমস্যা/পর্যবেক্ষণ (Diagnosis) লেখো:")
    return TREAT_DIAGNOSIS


async def treat_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["treatment"]["Diagnosis"] = update.message.text.strip()
    await update.message.reply_text("আজ কী ট্রিটমেন্ট দেওয়া হলো লেখো:")
    return TREAT_GIVEN


async def treat_given(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["treatment"]["Treatment_Given"] = update.message.text.strip()
    await update.message.reply_text("এক্সারসাইজ প্ল্যান লেখো (না থাকলে - দাও):", reply_markup=_skip_keyboard())
    return TREAT_EXERCISE


async def treat_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["treatment"]["Exercise"] = "" if text == "-" else text
    await update.message.reply_text("ইলেক্ট্রোথেরাপি মোডালিটি লেখো (না থাকলে - দাও):", reply_markup=_skip_keyboard())
    return TREAT_ELECTRO


async def treat_electro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["treatment"]["Electrotherapy"] = "" if text == "-" else text
    await update.message.reply_text("ম্যানুয়াল থেরাপি টেকনিক লেখো (না থাকলে - দাও):", reply_markup=_skip_keyboard())
    return TREAT_MANUAL


async def treat_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["treatment"]["Manual_Therapy"] = "" if text == "-" else text
    await update.message.reply_text(
        "সেশন নম্বর লেখো (যেমন: 5):",
        reply_markup=_number_keyboard([str(n) for n in range(1, 11)]),
    )
    return TREAT_SESSION


async def treat_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["treatment"]["Session_No"] = update.message.text.strip()
    await update.message.reply_text(
        "পরবর্তী ভিজিটের তারিখ লেখো (YYYY-MM-DD, না থাকলে - দাও):"
    )
    return TREAT_NEXTVISIT


async def treat_nextvisit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["treatment"]["Next_Visit"] = "" if text == "-" else text
    t = context.user_data["treatment"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"রোগী: {t['Patient_Name']} ({t['Patient_ID']})\n"
        f"সমস্যা: {t['Diagnosis']}\n"
        f"ট্রিটমেন্ট: {t['Treatment_Given']}\n"
        f"এক্সারসাইজ: {t['Exercise'] or '-'}\n"
        f"ইলেক্ট্রোথেরাপি: {t['Electrotherapy'] or '-'}\n"
        f"ম্যানুয়াল থেরাপি: {t['Manual_Therapy'] or '-'}\n"
        f"সেশন নম্বর: {t['Session_No']}\n"
        f"পরবর্তী ভিজিট: {t['Next_Visit'] or '-'}\n\n"
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
    _chain = bool(context.user_data.get("pl_patient_id"))
    kb = ReplyKeyboardRemove() if _chain else _menu_keyboard(staff.get("Role", ""))

    if text not in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        context.user_data.pop("treatment", None)
        await update.message.reply_text("❌ বাতিল করা হয়েছে।", reply_markup=kb)
        await _finish_patient_action(update, context, None)
        return ConversationHandler.END

    try:
        treatment_id = sheets.add_treatment_note(t, created_by=staff.get("Full_Name", "Unknown"))
        next_visit = t.get("Next_Visit", "")
        if next_visit:
            sheets.update_next_visit(t.get("Patient_ID", ""), next_visit)
        await update.message.reply_text(
            f"✅ ট্রিটমেন্ট নোট সেভ হয়েছে! Treatment ID: {treatment_id}",
            reply_markup=kb,
        )
    except Exception as e:
        logger.exception("treat_confirm ব্যর্থ হয়েছে")
        await update.message.reply_text(
            f"❌ নোট সেভ করতে সমস্যা হয়েছে।\nError: {e}\n\n"
            "স্ক্রিনশট দিয়ে জানাও, ঠিক করে দেওয়া হবে।",
            reply_markup=kb,
        )
    context.user_data.pop("treatment", None)
    await _finish_patient_action(update, context, "treat")
    return ConversationHandler.END


async def treat_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_search_results", None)
    _chain = bool(context.user_data.get("pl_patient_id"))
    if _chain:
        await update.effective_message.reply_text("❌ বাতিল করা হয়েছে।")
        await _finish_patient_action(update, context, None)
    else:
        await update.effective_message.reply_text(
            "ট্রিটমেন্ট নোট এন্ট্রি বাতিল করা হয়েছে।",
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


def _build_patient_history_text(patient_id: str) -> str | None:
    """একটা রোগীর প্রোফাইল/পেমেন্ট/অ্যাপয়েন্টমেন্ট/ট্রিটমেন্ট ইতিহাস টেক্সট আকারে বানায়।
    hist_select_callback এবং 'রোগী তালিকা' → 📜 ইতিহাস দুই জায়গাতেই ব্যবহার হয়।"""
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


async def hist_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("histsel_", "", 1)
    full_text = _build_patient_history_text(patient_id)
    if full_text is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    await query.edit_message_text(full_text)
    return ConversationHandler.END


async def patient_list_hist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'👥 রোগী তালিকা' বা 'আজকের অ্যাপয়েন্টমেন্ট' চেইন থেকে সরাসরি ইতিহাস দেখায়,
    তারপর বাকি প্রযোজ্য অ্যাকশন বাটন দেখায়।"""
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plact_hist_", "", 1)
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    if not roles.can_access(staff.get("Role", ""), roles.MENU_PATIENT_HISTORY):
        await query.edit_message_text("⛔ এই কাজে তোমার অনুমতি নেই।")
        return
    full_text = _build_patient_history_text(patient_id)
    if full_text is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return
    await query.edit_message_text(full_text)
    context.user_data["pl_patient_id"] = patient_id
    context.user_data.setdefault("pl_done", set()).add("hist")
    await _send_patient_action_menu(update, context, patient_id)


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
        MessageHandler(filters.Regex(f"^{roles.MENU_PATIENT_LIST}$"), patient_list_start)
    )
    app.add_handler(CallbackQueryHandler(patient_list_select_callback, pattern="^plsel_"))
    app.add_handler(CallbackQueryHandler(patient_list_done_callback, pattern="^pldone_"))
    app.add_handler(CallbackQueryHandler(patient_list_hist_callback, pattern="^plact_hist_"))
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_TODAY_APPOINTMENTS}$"), today_appointments)
    )
    app.add_handler(CallbackQueryHandler(apt_status_callback, pattern="^aptstatus_"))
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_TODAY_REGISTER}$"), today_register)
    )

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
            CallbackQueryHandler(apt_start_from_list, pattern="^plact_apt_"),
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
            APT_THERAPIST: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_therapist)],
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
            CallbackQueryHandler(pay_start_from_list, pattern="^plact_pay_"),
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
            PAY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_time)],
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
            CallbackQueryHandler(treat_start_from_list, pattern="^plact_treat_"),
        ],
        states={
            TREAT_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_search)],
            TREAT_SELECT: [CallbackQueryHandler(treat_select_callback, pattern="^treatsel_")],
            TREAT_DIAGNOSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_diagnosis)],
            TREAT_GIVEN: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_given)],
            TREAT_EXERCISE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_exercise)],
            TREAT_ELECTRO: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_electro)],
            TREAT_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_manual)],
            TREAT_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_session)],
            TREAT_NEXTVISIT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_nextvisit)],
            TREAT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", treat_cancel),
            CommandHandler("start", _restart_via_start),],
    )
    app.add_handler(treat_conv)

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

    app.add_handler(MessageHandler(filters.Regex(f"^{roles.MENU_HOME}$"), go_home))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), unknown_menu))
    logger.info("Relife Clinic OS Bot চালু হচ্ছে...")
    _start_health_server()

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    app.run_polling()


if __name__ == "__main__":
    main()
