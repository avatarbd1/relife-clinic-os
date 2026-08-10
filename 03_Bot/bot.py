import os
import base64
import time
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
from datetime import datetime, timedelta, time as dt_time, timezone
from telegram import (
    Update,
    KeyboardButton,
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
    TypeHandler,
    ApplicationHandlerStop,
    filters,
)

import config
from config import bd_now
import sheets
from attendance_location import validate_location
from observability import capture_exception, init_sentry
import roles
import calendar_helper
import staff_ai_query
import case_study_ai
import photo_extract
import text_extract
import intent_router
import ai_helper
import assessment_defs
import clinical_ai
import async_runtime
import tenant_runtime
from learning import learning_engine

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
_tenant_resolver = None


async def _bind_update_tenant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resolve and bind a clinic before any business handler can touch Sheets."""
    if not config.MULTITENANT_ENABLED:
        return
    if update.effective_user is None:
        raise ApplicationHandlerStop

    try:
        tenant = await async_runtime.run_role_lookup(
            _tenant_resolver.resolve, update.effective_user.id
        )
    except Exception as error:
        capture_exception(error)
        if update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ ক্লিনিক পরিচয় যাচাই করা যাচ্ছে না। একটু পরে আবার চেষ্টা করুন।"
            )
        raise ApplicationHandlerStop

    if tenant is None:
        if update.effective_message:
            await update.effective_message.reply_text(
                "❌ আপনার Telegram ID কোনো সক্রিয় ক্লিনিকের সঙ্গে যুক্ত নেই।"
            )
        raise ApplicationHandlerStop

    previous = context.user_data.get("_clinic_id")
    if previous and previous != tenant.clinic_id:
        context.user_data.clear()
    context.user_data["_clinic_id"] = tenant.clinic_id
    context.user_data["_sheet_id"] = tenant.sheet_id
    tenant_runtime.bind_tenant(tenant)

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

REG_PHOTO_CHOICE, REG_PHOTO_WAIT, REG_PHOTO_CONFIRM = range(90, 93)

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
    TREAT_CONFIRM_PLAN,
    TREAT_EDIT_EXERCISE,
    TREAT_EDIT_ELECTRO,
    TREAT_EDIT_MANUAL,
    TREAT_AI_QUESTION,
    TREAT_PATIENT_COMMENT,
    TREAT_PROGRESS_SCORE,
) = range(19, 29)

PAY_METHODS = ["Cash", "bKash", "Nagad", "Card"]
THERAPIST_NAMES_FALLBACK = ["Nipa", "Saiful"]

BN_WEEKDAYS = ["সোম", "মঙ্গল", "বুধ", "বৃহঃ", "শুক্র", "শনি", "রবি"]

PATIENT_LOOKUP_PROMPT = (
    "🔎 রোগী শনাক্ত করতে নাম, ফোন নম্বর অথবা Patient ID লিখুন:"
)
STATUS_DOCUMENT_ANALYSIS = "🖼️ ছবি/রিপোর্টের তথ্য বিশ্লেষণ করছি…"
STATUS_CLINICAL_ANALYSIS = (
    "🧠 ক্লিনিক্যাল তথ্য ও প্রাসঙ্গিক ম্যানুয়াল বিশ্লেষণ করছি…"
)
STATUS_BUSINESS_ANALYSIS = (
    "📊 ক্লিনিকের তথ্য বিশ্লেষণ করে উত্তর প্রস্তুত করছি…"
)

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
    roles.MENU_PATIENT_MGMT,
    roles.MENU_TREATMENT,
    roles.MENU_AI_TOOLS,
    roles.MENU_BACK_MAIN,
    roles.MENU_STAFF_AI_QUERY,
    roles.MENU_CASE_STUDY,
    roles.MENU_CLINICAL_AI,
    roles.MENU_INVENTORY,
    roles.MENU_SALARY,
    roles.MENU_SALARY_HISTORY,
    roles.MENU_MY_PAYMENTS,
    roles.MENU_ADD_EXPENSE,
    roles.MENU_EXPENSE_TRACKER,
    roles.MENU_FINANCE,
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

(STAFFAI_QUESTION,) = range(37, 38)
(CASESTUDY_INPUT,) = range(38, 39)
(CASESTUDY_LESSON,) = range(39, 40)
(CASESTUDY_SEARCH, CASESTUDY_EXTRA) = range(40, 42)
(CASESTUDY_QUESTION,) = range(42, 43)  # আর ব্যবহার হয় না (patch22 revert) — future reuse-এর জন্য number সংরক্ষিত
(REG_FIELDS,) = range(43, 44)  # রেজিস্ট্রেশনে missing fields একসাথে জিজ্ঞাসার state (patch38)
(CLINICALAI_QUESTION,) = range(44, 45)  # AI Clinical Assistant state (patch40)
(SALARY_SELECT_STAFF, SALARY_ENTER_AMOUNT, SALARY_NOTE, SALARY_CONFIRM) = range(45, 49)  # Staff Salary System
(COST_CATEGORY, COST_AMOUNT, COST_NOTE, COST_CONFIRM) = range(49, 53)  # Daily Cost Tracker
(PAYDEL_LIST, PAYDEL_CONFIRM) = range(300, 302)  # আজকের এন্ট্রি মুছার ফ্লো
(INV_UPDATE,) = range(310, 311)  # ইনভেন্টরি স্টক আপডেট ফ্লো

TPLAN_CATEGORY, TPLAN_TESTS = range(200, 202)

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


def _treat_confirm_keyboard(patient_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("✅ গতকালের মতোই", callback_data=f"trsame_{patient_id}")],
        [InlineKeyboardButton("✏️ এডিট করবো", callback_data=f"tredit_{patient_id}")],
        [InlineKeyboardButton("⬅️ আগের ধাপ", callback_data="trback_search")],
    ]
    return InlineKeyboardMarkup(buttons)


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
    buttons.append([InlineKeyboardButton("⬅️ আগের ধাপ", callback_data="trback_confirm")])
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


async def _cancel_and_go_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """কনভারসেশনের মাঝখানে 🔙 মূল মেনু চাপলে চলমান কাজ বাতিল করে সরাসরি মূল মেনু দেখায়।"""
    context.user_data.clear()
    await back_to_main_menu(update, context)
    return ConversationHandler.END


def _menu_keyboard(role_str: str) -> ReplyKeyboardMarkup:
    rows = roles.get_menu_rows_for_role(role_str)
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _parse_date(date_str: str | None):
    text = str(date_str or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _extract_metric(note: dict | None, key: str) -> str:
    if not note:
        return ""
    direct = str(note.get(key, "") or "").strip()
    if direct:
        return direct
    blob = "\n".join(
        str(note.get(k, "") or "")
        for k in ("Remarks", "Note", "Notes", "Treatment_Given", "Assessment")
    )
    m = re.search(rf"{re.escape(key)}\s*[:=-]\s*([^|;\n]+)", blob, re.I)
    return m.group(1).strip() if m else ""


def _extract_numeric(value: str | None):
    m = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    return float(m.group(0)) if m else None


def _normalize_appt_status(status: str) -> str:
    value = str(status or "").strip().lower()
    if value in ("scheduled", "waiting", "pending"):
        return "Waiting"
    if value in ("in treatment", "intreatment", "ongoing"):
        return "In Treatment"
    if value in ("completed", "done"):
        return "Completed"
    if value in ("no-show", "noshow", "missed", "absent"):
        return "Missed Appointment"
    return status or "Waiting"


def _build_progress_percent(plan: dict | None, notes: list[dict]) -> int:
    if plan:
        total = _safe_int(plan.get("Total_Sessions", 0), 0)
        done = _safe_int(plan.get("Sessions_Done", 0), 0)
        if total > 0:
            return max(0, min(100, int((done / total) * 100)))
    return max(0, min(95, len(notes) * 12))


def _reassessment_due(plan: dict | None, notes: list[dict]) -> bool:
    today = bd_now().date()
    visit_due = False
    if plan:
        done = _safe_int(plan.get("Sessions_Done", 0), 0)
        visit_due = done > 0 and done % 7 == 0
    if notes:
        last_date = _parse_date(notes[-1].get("Date", ""))
        if last_date and (today - last_date).days >= 14:
            return True
    return visit_due


def _ai_summary_for_patient(plan: dict | None, notes: list[dict]) -> tuple[str, str]:
    reassess = _reassessment_due(plan, notes)
    if reassess:
        return (
            "⚠️ Reassessment required — 7 visits/14 days threshold reached.",
            "High",
        )

    if len(notes) >= 4:
        recent = notes[-4:]
        pain_values = [
            _extract_numeric(_extract_metric(n, "Pain"))
            for n in recent
            if _extract_numeric(_extract_metric(n, "Pain")) is not None
        ]
        if len(pain_values) >= 2:
            if pain_values[-1] < pain_values[0]:
                return ("Pain improving — continue current protocol.", "High")
            if pain_values[-1] >= pain_values[0]:
                return ("Possible plateau — review exercise progression.", "Medium")

    if notes:
        return ("Follow-up stable — continue protocol if no change reported.", "Medium")
    return ("New treatment cycle — monitor pain, ROM and function from visit 1.", "Medium")


def _patient_last_visit(notes: list[dict], patient: dict) -> str:
    if notes:
        return str(notes[-1].get("Date", "") or "-")
    return str(patient.get("Registration_Date", "") or "-")


def _therapist_today_queue(staff: dict) -> list[dict]:
    therapist_name = str(staff.get("Full_Name", "")).strip()
    today_str = bd_now().strftime("%Y-%m-%d")
    appointments = sheets.get_appointments_for_date(today_str)
    items = []
    for appt in sorted(appointments, key=lambda a: str(a.get("Time", ""))):
        appt_therapist = str(appt.get("Therapist", "")).strip()
        patient_id = str(appt.get("Patient_ID", "")).strip()
        patient = sheets.get_patient_by_id(patient_id) or {"Patient_ID": patient_id, "Full_Name": appt.get("Patient_Name", "")}
        patient_therapist = str(patient.get("Therapist", "")).strip()
        notes = sheets.get_treatment_notes_for_patient(patient_id)
        plan = sheets.get_active_plan_for_patient(patient_id) or sheets.get_last_plan_for_patient(patient_id)
        last_note = notes[-1] if notes else {}
        status = _normalize_appt_status(appt.get("Status", "Scheduled"))
        items.append({
            "appointment_id": str(appt.get("Appointment_ID", "")).strip(),
            "patient_id": patient_id,
            "name": patient.get("Full_Name", appt.get("Patient_Name", "Unknown")),
            "age": patient.get("Age", "-"),
            "diagnosis": patient.get("Diagnosis") or (plan or {}).get("Diagnosis", "-"),
            "visit_no": len(notes) + (0 if status == "Completed" else 1),
            "last_visit": _patient_last_visit(notes, patient),
            "pain": _extract_metric(last_note, "Pain") or "-",
            "progress": _build_progress_percent(plan, notes),
            "status": status,
            "time": str(appt.get("Time", "")).strip(),
            "reassessment_due": _reassessment_due(plan, notes),
        })
    return items


def _pt_dashboard_text(staff: dict) -> str:
    queue = _therapist_today_queue(staff)
    waiting = sum(1 for item in queue if item["status"] == "Waiting")
    in_treatment = sum(1 for item in queue if item["status"] == "In Treatment")
    completed = sum(1 for item in queue if item["status"] == "Completed")
    missed = sum(1 for item in queue if item["status"] == "Missed Appointment")
    reassessment = sum(1 for item in queue if item["reassessment_due"])

    lines = [
        f"🧑‍⚕️ {staff.get('Full_Name', '')} — Physiotherapist Dashboard",
        "",
        f"আজকের রোগী: {len(queue)}",
        f"Waiting: {waiting}",
        f"In Treatment: {in_treatment}",
        f"Completed: {completed}",
        f"Reassessment Due: {reassessment}",
        f"Missed Appointment: {missed}",
        "",
        "Patient Queue",
        "--------------------",
    ]

    if not queue:
        lines.append("আজ তোমার কোনো queue নেই। নতুন appointment এলে এখানেই দেখাবে।")
        return "\n".join(lines)

    for idx, item in enumerate(queue[:12], start=1):
        due = " | Reassessment Due" if item["reassessment_due"] else ""
        lines.extend([
            f"{idx}. {item['name']}",
            f"{item['diagnosis']}",
            f"Visit {item['visit_no']} | Pain {item['pain']} | Progress {item['progress']}%",
            f"{item['time']} | {item['status']}{due}",
            "",
        ])

    if len(queue) > 12:
        lines.append(f"... আরও {len(queue) - 12} জন আছে")
    return "\n".join(lines).strip()


def _pt_dashboard_keyboard(staff: dict) -> InlineKeyboardMarkup:
    buttons = []
    seen_history_patient_ids = set()
    for item in _therapist_today_queue(staff)[:12]:
        if item["status"] in ("Completed", "Missed Appointment"):
            if item["patient_id"] in seen_history_patient_ids:
                continue
            seen_history_patient_ids.add(item["patient_id"])
            buttons.append([
                InlineKeyboardButton(
                    f"📜 {item['name']} — History",
                    callback_data=f"ptdashhist_{item['patient_id']}",
                )
            ])
        else:
            buttons.append([
                InlineKeyboardButton(
                    f"▶️ Receive {item['name']}",
                    callback_data=f"ptrecv_{item['appointment_id']}_{item['patient_id']}",
                )
            ])
    buttons.append([InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="ptdash_refresh")])
    return InlineKeyboardMarkup(buttons)


def _pt_workspace_keyboard(patient_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Today's Session Done", callback_data="ptwdone")],
        [
            InlineKeyboardButton("＋ Edit", callback_data="ptwedit"),
            InlineKeyboardButton("📜 History", callback_data=f"ptwhist_{patient_id}"),
        ],
        [InlineKeyboardButton("🔄 Back to Dashboard", callback_data="ptwbackdash")],
    ])


def _pt_workspace_text(patient: dict, plan: dict, notes: list[dict], treatment: dict) -> str:
    last_note = notes[-1] if notes else {}
    ai_summary, confidence = _ai_summary_for_patient(plan, notes)
    last_assessment_parts = [
        f"Pain: {_extract_metric(last_note, 'Pain') or '-'}",
        f"ROM: {_extract_metric(last_note, 'ROM') or '-'}",
        f"MMT: {_extract_metric(last_note, 'MMT') or '-'}",
    ]
    return (
        "🟢 ACTIVE TREATMENT\n\n"
        f"{patient.get('Full_Name', '')} ({patient.get('Patient_ID', '')})\n"
        f"Age: {patient.get('Age', '-') } | Diagnosis: {treatment.get('Diagnosis') or '-'}\n"
        f"Visit Number: {treatment.get('Session_No', '-') } | Protocol Day: {treatment.get('Protocol_Day', '-') }\n"
        f"Last Visit: {_patient_last_visit(notes, patient)}\n\n"
        "Patient Summary\n"
        f"• Stage: {'Follow-up' if notes else 'New'}\n"
        f"• Red Flags: {patient.get('Red_Flags', '-') or '-'}\n"
        f"• Contraindication: {patient.get('Contraindication', '-') or '-'}\n"
        f"• MRI/Xray Summary: {patient.get('MRI_Xray_Summary', '-') or '-'}\n"
        f"• Last Assessment: {', '.join(last_assessment_parts)}\n\n"
        "Today's Treatment\n"
        f"✔ Electrotherapy: {treatment.get('Electrotherapy') or '-'}\n"
        f"✔ Manual Therapy: {treatment.get('Manual_Therapy') or '-'}\n"
        f"✔ Exercise: {treatment.get('Exercise') or '-'}\n"
        f"✔ Home Exercise: {treatment.get('Home_E…61684 tokens truncated…       REG_PHOTO_WAIT: [MessageHandler(filters.PHOTO, reg_photo_receive)],
            REG_PHOTO_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_photo_confirm)],
            REG_FIELDS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_fields)],
            REG_PHONE_DUP: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_phone_dup_confirm)],
            REG_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_note)],
            REG_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
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
                CallbackQueryHandler(apt_time_toggle_callback, pattern="^apttimetoggle_"),
                CallbackQueryHandler(apt_time_done_callback, pattern="^apttimedone$"),
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
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
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
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),CommandHandler("cancel", pay_cancel),
            CommandHandler("start", _restart_via_start),],
    )
    app.add_handler(pay_conv)

    paydel_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_DELETE_ENTRY}$"), paydel_start),
        ],
        states={
            PAYDEL_LIST: [
                CallbackQueryHandler(paydel_select_callback, pattern="^paydelsel_"),
                CallbackQueryHandler(paydel_cancel_callback, pattern="^paydelcancel$"),
            ],
            PAYDEL_CONFIRM: [
                CallbackQueryHandler(paydel_confirm_callback, pattern="^paydelconfirm_yes$"),
                CallbackQueryHandler(paydel_cancel_callback, pattern="^paydelcancel$"),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", pay_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(paydel_conv)

    inv_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_INVENTORY}$"), inventory_menu),
        ],
        states={
            INV_UPDATE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), inventory_update)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", inventory_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(inv_conv)

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
            TREAT_CONFIRM_PLAN: [
                CallbackQueryHandler(treat_confirm_same_callback, pattern="^trsame_"),
                CallbackQueryHandler(treat_confirm_edit_callback, pattern="^tredit_"),
                CallbackQueryHandler(treat_back_to_search_callback, pattern="^trback_search$"),
            ],
            TREAT_EDIT_EXERCISE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_edit_exercise),
            ],
            TREAT_EDIT_ELECTRO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_edit_electro),
            ],
            TREAT_EDIT_MANUAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_edit_manual),
            ],
            TREAT_MACHINES: [
                CallbackQueryHandler(treat_machine_toggle, pattern="^trm_"),
                CallbackQueryHandler(treat_machine_done, pattern="^trdone_"),
                CallbackQueryHandler(treat_back_to_confirm_callback, pattern="^trback_confirm$"),
                CallbackQueryHandler(treat_machine_cancel_callback, pattern="^trcancel_"),
            ],
            TREAT_PATIENT_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_patient_comment_receive),
            ],
            TREAT_PROGRESS_SCORE: [
                CallbackQueryHandler(treat_progress_score_callback, pattern="^trpain_"),
                CallbackQueryHandler(treat_progress_score_callback, pattern="^trpainskip$"),
            ],
            TREAT_AI_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_ai_question_receive),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
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
            TPLAN_CATEGORY: [
                CallbackQueryHandler(tplan_category_callback, pattern="^tpcat_"),
            ],
            TPLAN_TESTS: [
                CallbackQueryHandler(atest_callback, pattern="^atest_"),
                CallbackQueryHandler(atest_info_callback, pattern="^ainfo_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), atest_text_receive),
            ],
            TPLAN_DIAGNOSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_diagnosis)],
            TPLAN_TOTAL: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_total)],
            TPLAN_EXERCISE: [
                CallbackQueryHandler(tplan_ai_suggest_callback, pattern="^tplan_ai_suggest$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_exercise),
            ],
            TPLAN_ELECTRO: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_electro)],
            TPLAN_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_manual)],
            TPLAN_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_confirm)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", tplan_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(tplan_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{roles.MENU_REPORTS}$"), reports_menu))
    app.add_handler(CallbackQueryHandler(rpt_totals_callback, pattern="^rpt_totals$"))
    app.add_handler(CallbackQueryHandler(rpt_lastmonth_callback, pattern="^rpt_lastmonth$"))
    app.add_handler(CallbackQueryHandler(rpt_todayregister_callback, pattern="^rpt_todayregister$"))
    app.add_handler(CallbackQueryHandler(rpt_daterep_callback, pattern="^rpt_daterep$"))
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
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
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
    # thist_date_callback আগে শুধু thist_conv-এর THIST_DATE state-এর ভিতরেই ধরা যেত।
    # তারিখ সিলেক্ট করার পর conversation END হয়ে যায়, ফলে "🔙 ফিরুন" দিয়ে ফিরে এসে
    # আরেকটা তারিখ চাপলে কোনো handler সেটা ধরত না। গ্লোবালি রেজিস্টার করে ফিক্স (patch30)।
    app.add_handler(CallbackQueryHandler(thist_date_callback, pattern="^thdate_"))
    app.add_handler(CallbackQueryHandler(thist_nav_callback, pattern="^thnav_"))
    app.add_handler(CallbackQueryHandler(thist_back_to_dates_callback, pattern="^thistback_"))
    app.add_handler(CallbackQueryHandler(thist_progress_callback, pattern="^thistprog_"))

    staffai_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_STAFF_AI_QUERY}$"), staffai_start)
        ],
        states={
            STAFFAI_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), staffai_receive)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", staffai_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(staffai_conv)

    clinicalai_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_CLINICAL_AI}$"), clinicalai_start)
        ],
        states={
            CLINICALAI_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), clinicalai_receive)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", clinicalai_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(clinicalai_conv)

    casestudy_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_CASE_STUDY}$"), casestudy_start)
        ],
        states={
            CASESTUDY_SEARCH: [
                CallbackQueryHandler(casestudy_select_callback, pattern="^cssel_"),
                CallbackQueryHandler(casestudy_search_cancel_callback, pattern="^cssearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), casestudy_search_receive),
            ],
            CASESTUDY_EXTRA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), casestudy_extra_receive)
            ],
            CASESTUDY_LESSON: [
                CallbackQueryHandler(casestudy_lesson_callback, pattern="^cslesson_next$")
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", casestudy_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(casestudy_conv)

    app.add_handler(MessageHandler(filters.Regex(f"^{roles.MENU_HOME}$"), go_home))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), unknown_menu))

    async def _global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.exception("Unhandled error", exc_info=context.error)
        capture_exception(context.error)
        try:
            if isinstance(update, Update) and update.effective_message:
                await update.effective_message.reply_text(
                    "⚠️ সাময়িক সমস্যা হয়েছে (সম্ভবত Google Sheets সাময়িক ব্যস্ত)। "
                    "কয়েক সেকেন্ড পর আবার চেষ্টা করো।"
                )
        except Exception:
            logger.exception("error handler নিজেই ব্যর্থ হয়েছে")

    app.add_error_handler(_global_error_handler)

    logger.info("Relife Clinic OS Bot চালু হচ্ছে...")
    try:
        _start_health_server()
    except Exception as error:
        capture_exception(error)
        raise

    app.run_polling()


if __name__ == "__main__":
    main()

