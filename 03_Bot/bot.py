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
        "সমস্যা/বয়স/অন্য কিছু থাকলে এক লাইনে লেখো (না থাকলে - দাও):"
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
    await query.message.reply_text("আজ কয়টা সেশন হলো লেখো (না থাকলে 0):")
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

    # প্রোফাইল
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

    # সেশন/প্যাকেজ
    package = sheets.get_active_package_for_patient(patient_id)
    if package:
        total = package.get("Total_Sessions", "N/A")
        done = package.get("Sessions_Completed", "N/A")
        lines.append(f"🗓️ সেশন: {done} সম্পন্ন / {total} মোট")
        lines.append("")

    # পেমেন্ট হিস্টরি
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

    # অ্যাপয়েন্টমেন্ট হিস্টরি
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

    # ট্রিটমেন্ট নোট
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

    reg_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_PATIENT_REG}$"), reg_start)
        ],
        states={
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_name)],
            REG_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_phone)],
            REG_PHONE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_phone_confirm)],
            REG_PHONE_DUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_phone_dup_confirm)],
            REG_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_address)],
            REG_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_note)],
            REG_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, reg_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),CommandHandler("cancel", reg_cancel)],
    )
    app.add_handler(reg_conv)

    apt_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_APPOINTMENT}$"), apt_start)
        ],
        states={
            APT_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, apt_search)],
            APT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, apt_select)],
            APT_DATE: [
                CallbackQueryHandler(apt_date_callback, pattern="^aptdate_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, apt_date),
            ],
            APT_TIME: [
                CallbackQueryHandler(apt_time_callback, pattern="^apttime_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, apt_time),
            ],
            APT_THERAPIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, apt_therapist)],
            APT_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, apt_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),CommandHandler("cancel", apt_cancel)],
    )
    app.add_handler(apt_conv)

    pay_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_PAYMENT}$"), pay_start)
        ],
        states={
            PAY_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_search)],
            PAY_SELECT: [
                CallbackQueryHandler(pay_select_callback, pattern="^paysel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, pay_select),
            ],
            PAY_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_session)],
            PAY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_amount)],
            PAY_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_method)],
            PAY_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, pay_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),CommandHandler("cancel", pay_cancel)],
    )
    app.add_handler(pay_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{roles.MENU_REPORTS}$"), reports_menu))
    hist_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^{roles.MENU_PATIENT_HISTORY}$"), hist_start)],
        states={
            "HIST_SEARCH": [
                CallbackQueryHandler(hist_select_callback, pattern="^histsel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, hist_search),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),CommandHandler("cancel", hist_cancel)],
    )
    app.add_handler(hist_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{roles.MENU_HOME}$"), go_home))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_menu))
    logger.info("Relife Clinic OS Bot চালু হচ্ছে...")
    app.run_polling()


if __name__ == "__main__":
    main()
