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
import department_access
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
    "🏠 হাজিরা",
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
    roles.MENU_CASH_HANDOVER,
    roles.MENU_CASH_RECEIVE,
    roles.MENU_CASH_MOVEMENTS,
    roles.MENU_SMALL_EXPENSE_REQUEST,
    roles.MENU_EXPENSE_APPROVAL,
    roles.MENU_APPROVED_EXPENSES,
    roles.MENU_OWNER_CLINIC_EXPENSE,
    roles.MENU_HOUSEHOLD_WITHDRAWAL,
    roles.MENU_CUSTODY_BALANCE,
    roles.MENU_PHYSIO_FINANCE_DASHBOARD,
    roles.MENU_DENTAL_FINANCE_DASHBOARD,
    roles.MENU_COMBINED_BUSINESS_SUMMARY,
    roles.MENU_FINANCE,
]
_ALL_MENU_REGEX = "^(" + "|".join(re.escape(x) for x in _ALL_MENU_ITEMS) + ")$"
_ATTENDANCE_MENU_LABELS = (roles.MENU_ATTENDANCE, "🏠 হাজিরা")
_ATTENDANCE_MENU_REGEX = "^(?:" + "|".join(
    re.escape(label) for label in _ATTENDANCE_MENU_LABELS
) + ")$"

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
(CASH_AMOUNT, CASH_NOTE, CASH_CONFIRM) = range(53, 56)  # Cash handover workflow
(COST_DEPARTMENT, CASH_DEPARTMENT) = range(56, 58)
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


def _effective_role_strings(staff_or_role) -> list[str]:
    if isinstance(staff_or_role, str):
        return [staff_or_role]
    staff = staff_or_role or {}
    assignments = staff.get("_Department_Role_Assignments", ())
    role_values = [assignment.role.value for assignment in assignments]
    if role_values or config.DEPARTMENT_ENFORCEMENT_ENABLED:
        return role_values
    legacy_role = str(staff.get("Role", "")).strip()
    return [legacy_role] if legacy_role else []


def _staff_can_access_menu(staff: dict, menu_item: str) -> bool:
    return roles.can_any_access(_effective_role_strings(staff), menu_item)


def _menu_keyboard(staff_or_role) -> ReplyKeyboardMarkup:
    rows = roles.get_menu_rows_for_roles(
        _effective_role_strings(staff_or_role)
    )
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
    mappings = (
        sheets.get_staff_department_access(staff.get("Staff_ID", ""))
        if config.DEPARTMENT_ENFORCEMENT_ENABLED else []
    )
    items = []
    for appt in sorted(appointments, key=lambda a: str(a.get("Time", ""))):
        appt_therapist = str(appt.get("Therapist", "")).strip()
        patient_id = str(appt.get("Patient_ID", "")).strip()
        patient = sheets.get_patient_by_id_for_staff(
            patient_id, staff, mappings
        )
        if patient is None:
            if config.DEPARTMENT_ENFORCEMENT_ENABLED:
                continue
            patient = {
                "Patient_ID": patient_id,
                "Full_Name": appt.get("Patient_Name", ""),
            }
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
        f"✔ Home Exercise: {treatment.get('Home_Exercise') or '-'}\n"
        f"✔ Machines: {treatment.get('Machines') or '-'}\n\n"
        "AI Summary\n"
        f"{ai_summary}\n"
        f"Confidence: {confidence}\n\n"
        "Nothing changed হলে শুধু 'Today's Session Done' চাপলেই হবে।"
    )


def _load_patient_workspace(patient_id: str) -> tuple[dict | None, dict, list[dict]]:
    """Load related patient rows together so one thread hop serves the screen."""
    patient = sheets.get_patient_by_id(patient_id)
    plan = (
        sheets.get_active_plan_for_patient(patient_id)
        or sheets.get_last_plan_for_patient(patient_id)
        or {}
    )
    notes = sheets.get_treatment_notes_for_patient(patient_id)
    return patient, plan, notes


def _parse_pt_edit_message(text: str) -> dict:
    raw = str(text or "").strip()
    if not raw:
        return {}
    updates = {}
    mapping = {
        "pain": "Pain",
        "rom": "ROM",
        "mmt": "MMT",
        "specialtest": "Special_Test",
        "electro": "Electrotherapy",
        "electrotherapy": "Electrotherapy",
        "electrosetting": "Electro_Setting",
        "manual": "Manual_Therapy",
        "manualtherapy": "Manual_Therapy",
        "exercise": "Exercise",
        "homeexercise": "Home_Exercise",
        "home": "Home_Exercise",
        "machine": "Machines",
        "machines": "Machines",
        "note": "Clinical_Note",
        "clinicalnote": "Clinical_Note",
    }
    for chunk in re.split(r"[\n;]+", raw):
        if ":" not in chunk:
            continue
        key, value = chunk.split(":", 1)
        norm = re.sub(r"[^a-z]", "", key.lower())
        target = mapping.get(norm)
        if target and value.strip():
            updates[target] = value.strip()
    if not updates:
        updates["Clinical_Note"] = raw
    return updates


async def pt_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    if not _staff_can_access_menu(staff, roles.MENU_MY_PATIENTS):
        await update.effective_message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    await update.effective_message.reply_text(
        await async_runtime.run_sheets_read(_pt_dashboard_text, staff),
        reply_markup=_pt_dashboard_keyboard(staff),
    )


async def pt_dashboard_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None:
        await query.edit_message_text("❌ স্টাফ প্রোফাইল পাওয়া যায়নি। /start দাও।")
        return
    await query.edit_message_text(
        await async_runtime.run_sheets_read(_pt_dashboard_text, staff),
        reply_markup=_pt_dashboard_keyboard(staff),
    )


async def pt_dashboard_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("ptdashhist_", "", 1)
    if not await _patient_by_id_for_request(update, context, patient_id):
        await query.edit_message_text("⛔ এই রোগী দেখার অনুমতি নেই।")
        return
    history = await async_runtime.run_sheets_read(
        _build_full_history_text, patient_id
    ) or "কোনো history পাওয়া যায়নি।"
    await query.message.reply_text(history, reply_markup=_therapist_patient_action_keyboard(patient_id))


async def pt_dashboard_receive_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, appointment_id, patient_id = query.data.split("_", 2)
    patient = await _patient_by_id_for_request(update, context, patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    plan = await async_runtime.run_sheets_read(
        sheets.get_active_plan_for_patient, patient_id
    )
    if plan is None:
        await query.edit_message_text(
            f"⚠️ {patient.get('Full_Name')} ({patient_id})-এর কোনো Active protocol নেই। আগে ট্রিটমেন্ট প্ল্যান তৈরি করো।"
        )
        return ConversationHandler.END

    notes = await async_runtime.run_sheets_read(
        sheets.get_treatment_notes_for_patient, patient_id
    )
    last_note = notes[-1] if notes else {}
    session_no = _safe_int(plan.get("Sessions_Done", 0), 0) + 1
    treatment = {
        "Patient_ID": patient_id,
        "Patient_Name": patient.get("Full_Name", ""),
        "Plan_ID": plan.get("Plan_ID", ""),
        "Diagnosis": plan.get("Diagnosis", patient.get("Diagnosis", "")),
        "Exercise": plan.get("Exercise_Plan", ""),
        "Electrotherapy": plan.get("Electrotherapy_Plan", ""),
        "Manual_Therapy": plan.get("Manual_Therapy_Plan", ""),
        "Home_Exercise": _extract_metric(last_note, "Home_Exercise"),
        "Machines": str(last_note.get("Machines", "") or "").strip(),
        "Pain": _extract_metric(last_note, "Pain"),
        "ROM": _extract_metric(last_note, "ROM"),
        "MMT": _extract_metric(last_note, "MMT"),
        "Special_Test": _extract_metric(last_note, "Special_Test"),
        "Clinical_Note": _extract_metric(last_note, "Clinical_Note") or str(last_note.get("Remarks", "") or "").strip(),
        "Session_No": session_no,
        "Protocol_Day": session_no,
    }
    if not treatment["Machines"]:
        treatment["Machines"] = ", ".join(
            x for x in [treatment.get("Electrotherapy"), treatment.get("Manual_Therapy"), treatment.get("Exercise")] if x
        )

    context.user_data["pt_treatment"] = treatment
    context.user_data["pt_patient_id"] = patient_id
    context.user_data["pt_appointment_id"] = appointment_id
    if appointment_id:
        await async_runtime.run_sheets_write(
            sheets.update_appointment_status, appointment_id, "In Treatment"
        )

    await query.edit_message_text(
        _pt_workspace_text(patient, plan, notes, treatment),
        reply_markup=_pt_workspace_keyboard(patient_id),
    )
    return "PT_DASH_WORKSPACE"


async def pt_dashboard_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    treatment = context.user_data.get("pt_treatment")
    patient_id = context.user_data.get("pt_patient_id", "")
    if not treatment or not patient_id:
        await query.edit_message_text("❌ Session context পাওয়া যায়নি। আবার dashboard থেকে শুরু করো।")
        return ConversationHandler.END
    staff, patient = await _authorized_patient_action(
        update,
        context,
        patient_id,
        department_access.AccessAction.CLINICAL_WRITE,
        roles.MENU_TREATMENT_NOTE,
    )
    if staff is None or patient is None:
        await query.edit_message_text(
            "⛔ এই রোগীর clinical session save করার বর্তমান অনুমতি নেই।"
        )
        return ConversationHandler.END

    _, plan, notes = await async_runtime.run_sheets_read(
        _load_patient_workspace, patient_id
    )
    patient = patient or {"Full_Name": treatment.get("Patient_Name", "")}
    ai_summary, _ = _ai_summary_for_patient(plan, notes)

    treatment.setdefault("Machines", ", ".join(
        x for x in [treatment.get("Electrotherapy"), treatment.get("Manual_Therapy"), treatment.get("Exercise")] if x
    ))
    treatment["Treatment_Given"] = "; ".join([
        part for part in [
            f"Electrotherapy: {treatment.get('Electrotherapy')}" if treatment.get("Electrotherapy") else "",
            f"Manual: {treatment.get('Manual_Therapy')}" if treatment.get("Manual_Therapy") else "",
            f"Exercise: {treatment.get('Exercise')}" if treatment.get("Exercise") else "",
            f"Machines: {treatment.get('Machines')}" if treatment.get("Machines") else "",
        ] if part
    ]) or "Same treatment protocol continued."
    treatment["SOAP_Subjective"] = f"Pain: {treatment.get('Pain') or 'same as previous visit'}"
    treatment["SOAP_Objective"] = ", ".join([
        f"ROM: {treatment.get('ROM') or '-'}",
        f"MMT: {treatment.get('MMT') or '-'}",
        f"Special Test: {treatment.get('Special_Test') or '-'}",
    ])
    treatment["SOAP_Assessment"] = ai_summary
    treatment["SOAP_Plan"] = ", ".join(
        x for x in [treatment.get("Electrotherapy"), treatment.get("Manual_Therapy"), treatment.get("Exercise"), treatment.get("Home_Exercise")] if x
    )
    remarks = [
        f"Pain: {treatment.get('Pain')}" if treatment.get("Pain") else "",
        f"ROM: {treatment.get('ROM')}" if treatment.get("ROM") else "",
        f"MMT: {treatment.get('MMT')}" if treatment.get("MMT") else "",
        f"Special_Test: {treatment.get('Special_Test')}" if treatment.get("Special_Test") else "",
        f"Home_Exercise: {treatment.get('Home_Exercise')}" if treatment.get("Home_Exercise") else "",
        f"Clinical_Note: {treatment.get('Clinical_Note')}" if treatment.get("Clinical_Note") else "",
        f"AI: {ai_summary}",
    ]
    treatment["Remarks"] = " | ".join(x for x in remarks if x)

    try:
        treatment_id = await async_runtime.run_sheets_write(
            sheets.add_treatment_note,
            treatment,
            created_by=staff.get("Full_Name", "Unknown"),
        )
        await async_runtime.run_sheets_write(sheets.increment_plan_session, patient_id)
        appointment_id = context.user_data.get("pt_appointment_id", "")
        if appointment_id:
            mappings = await _patient_department_mappings(staff)
            appointment = await async_runtime.run_sheets_read(
                sheets.get_appointment_by_id_for_staff,
                appointment_id,
                staff,
                mappings,
                department_access.AccessAction.WRITE,
            )
            if appointment is not None:
                await async_runtime.run_sheets_write(
                    sheets.update_appointment_status_for_staff,
                    appointment_id,
                    "Completed",
                    staff,
                    mappings,
                )
        await query.edit_message_text(
            f"✅ Session Completed\n\n"
            f"রোগী: {patient.get('Full_Name', treatment.get('Patient_Name', ''))} ({patient_id})\n"
            f"Visit: {treatment.get('Session_No', '-')} | Protocol Day: {treatment.get('Protocol_Day', '-')}\n"
            f"Treatment ID: {treatment_id}\n"
            "Dashboard updated — next patient ready."
        )
    except Exception:
        logger.exception("pt_dashboard_done_callback ব্যর্থ হয়েছে")
        await query.edit_message_text(
            "❌ Session সেভ করা যায়নি। আবার চেষ্টা করো; একই সমস্যা হলে Admin-কে জানাও।"
        )
        return ConversationHandler.END

    context.user_data.pop("pt_treatment", None)
    context.user_data.pop("pt_patient_id", None)
    context.user_data.pop("pt_appointment_id", None)
    await query.message.reply_text(
        await async_runtime.run_sheets_read(_pt_dashboard_text, staff),
        reply_markup=_pt_dashboard_keyboard(staff),
    )
    return ConversationHandler.END


async def pt_dashboard_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    treatment = context.user_data.get("pt_treatment", {})
    prompt = (
        "✏️ Edit Mode\n\n"
        "যা বদলেছে শুধু সেটাই পাঠাও। কিছুই mandatory না।\n\n"
        "Example:\n"
        "Pain: 4/10\nROM: improved\nMMT: 4/5\nExercise: progressed core\nMachines: Hot Pack, TENS\nNote: tolerated well\n\n"
        f"Current Pain: {treatment.get('Pain') or '-'} | ROM: {treatment.get('ROM') or '-'} | MMT: {treatment.get('MMT') or '-'} | Machines: {treatment.get('Machines') or '-'}"
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Workspace", callback_data="ptwback")]])
    await query.edit_message_text(prompt, reply_markup=markup)
    return "PT_DASH_EDIT"


async def pt_dashboard_edit_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    treatment = context.user_data.get("pt_treatment")
    patient_id = context.user_data.get("pt_patient_id", "")
    if not treatment or not patient_id:
        await update.message.reply_text("❌ Edit session মেয়াদ শেষ হয়েছে। আবার dashboard থেকে শুরু করো।")
        return ConversationHandler.END

    treatment.update(_parse_pt_edit_message(update.message.text))
    patient, plan, notes = await async_runtime.run_sheets_read(
        _load_patient_workspace, patient_id
    )
    patient = patient or {"Patient_ID": patient_id, "Full_Name": treatment.get("Patient_Name", "")}
    await update.message.reply_text(
        _pt_workspace_text(patient, plan, notes, treatment),
        reply_markup=_pt_workspace_keyboard(patient_id),
    )
    return "PT_DASH_WORKSPACE"


async def pt_dashboard_edit_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    treatment = context.user_data.get("pt_treatment")
    patient_id = context.user_data.get("pt_patient_id", "")
    if not treatment or not patient_id:
        await query.edit_message_text("❌ Session মেয়াদ শেষ হয়েছে।")
        return ConversationHandler.END
    patient, plan, notes = await async_runtime.run_sheets_read(
        _load_patient_workspace, patient_id
    )
    patient = patient or {"Patient_ID": patient_id, "Full_Name": treatment.get("Patient_Name", "")}
    await query.edit_message_text(
        _pt_workspace_text(patient, plan, notes, treatment),
        reply_markup=_pt_workspace_keyboard(patient_id),
    )
    return "PT_DASH_WORKSPACE"


async def pt_dashboard_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None:
        await query.edit_message_text("❌ স্টাফ প্রোফাইল পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data.pop("pt_treatment", None)
    context.user_data.pop("pt_patient_id", None)
    context.user_data.pop("pt_appointment_id", None)
    await query.edit_message_text(
        await async_runtime.run_sheets_read(_pt_dashboard_text, staff),
        reply_markup=_pt_dashboard_keyboard(staff),
    )
    return ConversationHandler.END


async def pt_workspace_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("ptwhist_", "", 1)
    if not await _patient_by_id_for_request(update, context, patient_id):
        await query.edit_message_text("⛔ এই রোগী দেখার অনুমতি নেই।")
        return ConversationHandler.END
    history = await async_runtime.run_sheets_read(
        _build_full_history_text, patient_id
    ) or "কোনো history পাওয়া যায়নি।"
    await query.message.reply_text(history)
    return "PT_DASH_WORKSPACE"


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
    try:
        names = sheets.get_active_therapist_names()
    except Exception:
        logger.exception("get_active_therapist_names ব্যর্থ হয়েছে, fallback ব্যবহার হচ্ছে")
        names = []
    if not names:
        names = THERAPIST_NAMES_FALLBACK
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"aptther_{name}")]
        for name in names
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
    try:
        staff = await async_runtime.run_role_lookup(
            sheets.get_staff_by_telegram_id,
            telegram_id,
        )
    except _asyncio_p314.TimeoutError:
        await update.effective_message.reply_text(
            "⚠️ স্টাফ অনুমতি যাচাই করতে সময় লাগছে। একটু পরে আবার চেষ্টা করো।"
        )
        return None
    if staff is None:
        await update.effective_message.reply_text(
            "❌ তোমাকে সিস্টেমে স্টাফ হিসেবে খুঁজে পাওয়া যায়নি।\n"
            f"তোমার Telegram ID: {telegram_id}\n"
            "এই ID-টা ক্লিনিক ম্যানেজারকে দাও, তিনি 08_Staff শীটে যোগ করে দেবেন।"
        )
        return None

    staff = dict(staff)
    if config.DEPARTMENT_ENFORCEMENT_ENABLED:
        mappings = await async_runtime.run_sheets_read(
            sheets.get_staff_department_access, staff.get("Staff_ID", "")
        )
        assignments = department_access.effective_assignments(staff, mappings)
        if not assignments:
            await update.effective_message.reply_text(
                "⛔ তোমার সক্রিয় Department + Role assignment পাওয়া যায়নি। "
                "Owner-কে Staff_Department_Access ঠিক করতে বলো।"
            )
            return None
        staff["_Department_Mappings"] = mappings
        staff["_Department_Role_Assignments"] = assignments

    context.user_data["staff"] = staff
    return staff


async def _patient_department_mappings(staff: dict) -> list[dict]:
    if not config.DEPARTMENT_ENFORCEMENT_ENABLED:
        return []
    cached = staff.get("_Department_Mappings")
    if cached is not None:
        return cached
    return await async_runtime.run_sheets_read(
        sheets.get_staff_department_access, staff.get("Staff_ID", "")
    )


async def _visible_patients_for_request(update, context, patients):
    if not config.DEPARTMENT_ENFORCEMENT_ENABLED:
        return patients
    staff = await _require_staff(update, context)
    if staff is None:
        return []
    mappings = await _patient_department_mappings(staff)
    return await async_runtime.run_sheets_read(
        sheets.filter_patients_for_staff, patients, staff, mappings
    )


async def _search_patients_for_request(update, context, query_text: str):
    if not config.DEPARTMENT_ENFORCEMENT_ENABLED:
        return await async_runtime.run_sheets_read(
            sheets.search_patients, query_text
        )
    staff = await _require_staff(update, context)
    if staff is None:
        return []
    mappings = await _patient_department_mappings(staff)
    return await async_runtime.run_sheets_read(
        sheets.search_patients_for_staff, query_text, staff, mappings
    )


async def _patient_by_id_for_request(update, context, patient_id: str):
    """Re-authorize direct/stale Patient IDs using the current staff record."""
    if not config.DEPARTMENT_ENFORCEMENT_ENABLED:
        return await async_runtime.run_sheets_read(
            sheets.get_patient_by_id, patient_id
        )
    staff = await _require_staff(update, context)
    if staff is None:
        return None
    mappings = await _patient_department_mappings(staff)
    return await async_runtime.run_sheets_read(
        sheets.get_patient_by_id_for_staff, patient_id, staff, mappings
    )


async def _authorized_patient_action(
    update,
    context,
    patient_id: str,
    action: department_access.AccessAction,
    menu_item: str | None = None,
):
    """Reload staff and patient, then authorize the requested action live."""
    staff = await _require_staff(update, context)
    if staff is None:
        return None, None
    if menu_item and not _staff_can_access_menu(staff, menu_item):
        return staff, None
    mappings = await _patient_department_mappings(staff)
    patient = await async_runtime.run_sheets_read(
        sheets.get_patient_by_id_for_staff, patient_id, staff, mappings
    )
    if patient is None:
        return staff, None
    decision = department_access.authorize_record(
        staff,
        patient,
        action,
        mappings,
        assigned_or_cross_cover=True,
    )
    return (staff, patient) if decision.allowed else (staff, None)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    context.user_data["staff"] = staff
    role = staff.get("Role", "")
    name = staff.get("Full_Name", "")
    staff_id = staff.get("Staff_ID", "")

    await update.message.reply_text(f"স্বাগতম, {name}! ({role})")

    if staff_id and not learning_engine.has_seen_quiz_today(staff_id):
        quiz = learning_engine.get_next_quiz(staff_id)
        context.user_data["pending_quiz"] = quiz
        buttons = [
            [InlineKeyboardButton(opt, callback_data=f"lquiz:{i}")]
            for i, opt in enumerate(quiz["options"])
        ]
        await update.message.reply_text(
            f"🧠 আজকের প্রশ্ন:\n\n{quiz['question']}",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    await _send_daily_tip_and_menu(update.message, context, staff)


async def _send_daily_tip_and_menu(message, context: ContextTypes.DEFAULT_TYPE, staff: dict):
    role = staff.get("Role", "")
    name = staff.get("Full_Name", "")
    staff_id = staff.get("Staff_ID", "")

    if not staff_id:
        await message.reply_text(
            "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(staff)
        )
        return

    if learning_engine.has_seen_tip_today(staff_id):
        tip = learning_engine.get_todays_tip(staff_id, role)
    else:
        tip = learning_engine.get_next_tip(staff_id, role)
        learning_engine.record_tip_shown(staff_id, name, role, tip)

    await message.reply_text(
        f"💡 আজকের টিপ ({tip['category']}):\n{tip['text']}\n\nনিচের মেনু থেকে বেছে নাও 👇",
        reply_markup=_menu_keyboard(staff),
    )


async def learning_quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    quiz = context.user_data.pop("pending_quiz", None)
    staff = await _require_staff(update, context)
    if quiz is None or staff is None:
        return
    selected_index = int(query.data.split(":")[1])
    role = staff.get("Role", "")
    name = staff.get("Full_Name", "")
    staff_id = staff.get("Staff_ID", "")

    correct = learning_engine.record_quiz_answer(staff_id, name, role, quiz, selected_index)
    mark = "✅ সঠিক!" if correct else "❌ ভুল।"
    chosen = quiz["options"][selected_index]
    await query.edit_message_text(
        f"🧠 {quiz['question']}\n\nতোমার উত্তর: {chosen}\n{mark}\n\n📖 ব্যাখ্যা: {quiz['explanation']}"
    )
    await _send_daily_tip_and_menu(query.message, context, staff)


async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    role = staff.get("Role", "")
    name = staff.get("Full_Name", "")
    await update.message.reply_text(
        f"স্বাগতম, {name}! ({role})\nনিচের মেনু থেকে বেছে নাও 👇",
        reply_markup=_menu_keyboard(staff),
    )


async def my_patients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await pt_dashboard(update, context)


# ---------- রোগী রেজিস্ট্রেশন ----------

async def reg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_PATIENT_REG):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["new_patient"] = {}
    context.user_data.pop("new_patient_dup_checked", None)
    context.user_data.pop("new_patient_missing", None)
    choice_kb = ReplyKeyboardMarkup(
        [["📷 Photo/Report দিয়ে", "✍️ নিজে লিখব"]],
        resize_keyboard=True, one_time_keyboard=True,
    )
    await update.message.reply_text(
        "নতুন রোগী রেজিস্ট্রেশন — কীভাবে শুরু করবে?", reply_markup=choice_kb
    )
    return REG_PHOTO_CHOICE


_REG_REQUIRED_ORDER = ["Full_Name", "Phone", "Address", "Age"]
_REG_FIELD_LABELS = {"Full_Name": "নাম", "Phone": "ফোন", "Address": "ঠিকানা", "Age": "বয়স"}


def _reg_missing_fields(p: dict) -> list:
    return [k for k in _REG_REQUIRED_ORDER if not str(p.get(k, "")).strip()]


async def _reg_ask_fields_or_continue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    p = context.user_data.setdefault("new_patient", {})
    missing = _reg_missing_fields(p)
    if missing:
        context.user_data["new_patient_missing"] = missing
        labels = [_REG_FIELD_LABELS[k] for k in missing]
        if len(labels) == 1:
            prompt = f"{labels[0]} লেখো:"
        else:
            prompt = (
                "রোগীর তথ্য এক লাইনে স্বাভাবিক ভাষায় লেখো, ক্রম/কমা বাধ্যতামূলক না — "
                "AI বাকিটা বুঝে নেবে। উদাহরণ: রহিম, বয়স ৩২, 01712345678, মিরপুর ঢাকা\n\n"
                f"লাগবে: {', '.join(labels)}"
            )
        await update.message.reply_text(prompt, reply_markup=ReplyKeyboardRemove())
        return REG_FIELDS
    return await _reg_check_duplicate_then_note(update, context)


async def _reg_check_duplicate_then_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    p = context.user_data.setdefault("new_patient", {})
    phone = str(p.get("Phone", "")).strip()
    if phone and not context.user_data.get("new_patient_dup_checked"):
        context.user_data["new_patient_dup_checked"] = True
        existing = await async_runtime.run_sheets_read(
            sheets.find_patient_by_phone, phone
        )
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
    await update.message.reply_text(
        "সমস্যা/অন্য কিছু থাকলে এক লাইনে লেখো (না থাকলে - দাও):",
        reply_markup=_skip_keyboard(),
    )
    return REG_NOTE


async def reg_photo_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("📷"):
        await update.message.reply_text(
            "রোগীর report/prescription/x-ray-এর ছবিটা পাঠাও:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return REG_PHOTO_WAIT
    return await _reg_ask_fields_or_continue(update, context)


async def reg_photo_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    tg_file = await photo.get_file()
    image_bytes = bytes(await tg_file.download_as_bytearray())
    await update.message.reply_text(STATUS_DOCUMENT_ANALYSIS)
    debug_error = None
    try:
        extracted = await async_runtime.run_ai(
            photo_extract.extract_from_photo,
            image_bytes,
        )
    except Exception as e:
        logger.exception("photo_extract failed")
        extracted = None
        debug_error = f"{type(e).__name__}: {e}"

    field_map = {
        "full_name": "Full_Name",
        "age": "Age",
        "phone": "Phone",
        "address": "Address",
        "gender": "Gender",
    }
    p = context.user_data.setdefault("new_patient", {})
    found_lines = []
    if extracted:
        for src_key, dst_key in field_map.items():
            val = extracted.get(src_key)
            if val:
                p[dst_key] = str(val).strip()
                found_lines.append(f"{dst_key}: {p[dst_key]}")

    if not found_lines:
        debug_line = f"\n\n🔧 Debug: {debug_error}" if debug_error else ""
        await update.message.reply_text(
            f"⚠️ ছবি থেকে তথ্য পড়া যায়নি। নিজে লিখতে হবে।{debug_line}"
        )
        return await _reg_ask_fields_or_continue(update, context)

    summary = "📋 ছবি থেকে এই তথ্য পাওয়া গেছে:\n\n" + "\n".join(found_lines)
    summary += "\n\nঠিক আছে?"
    confirm_kb = ReplyKeyboardMarkup(
        [["হ্যাঁ, ঠিক আছে", "না, নিজে লিখব"]],
        resize_keyboard=True, one_time_keyboard=True,
    )
    await update.message.reply_text(summary, reply_markup=confirm_kb)
    return REG_PHOTO_CONFIRM


_AFFIRMATIVE_WORDS = {
    "হ্যাঁ", "হ্যা", "হুম", "হু", "হবে", "ঠিক", "ঠিক আছে",
    "yes", "ha", "haa", "hu", "hum", "hocche", "thik", "thik ache", "ok", "okay", "sure",
}
_NEGATIVE_WORDS = {
    "না", "না,", "no", "na", "nah", "nije likhbo", "নিজে লিখব",
}


def _is_affirmative(text: str) -> bool:
    norm = text.strip().lower().rstrip(".!,।")
    if norm.startswith("হ্যাঁ") or norm.startswith("হ্যা"):
        return True
    return norm in _AFFIRMATIVE_WORDS


def _is_negative(text: str) -> bool:
    norm = text.strip().lower().rstrip(".!,।")
    if norm.startswith("না"):
        return True
    return norm in _NEGATIVE_WORDS


async def reg_photo_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if _is_affirmative(text):
        return await _reg_ask_fields_or_continue(update, context)
    if _is_negative(text):
        context.user_data["new_patient"] = {}
        context.user_data.pop("new_patient_dup_checked", None)
        context.user_data.pop("new_patient_missing", None)
        await update.message.reply_text("ঠিক আছে, নতুন করে লেখো।")
        return await _reg_ask_fields_or_continue(update, context)
    confirm_kb = ReplyKeyboardMarkup(
        [["হ্যাঁ, ঠিক আছে", "না, নিজে লিখব"]],
        resize_keyboard=True, one_time_keyboard=True,
    )
    await update.message.reply_text(
        "বুঝতে পারিনি 🙏 নিচের বাটনে ট্যাপ করো (\"হ্যাঁ, ঠিক আছে\" বা \"না, নিজে লিখব\"):",
        reply_markup=confirm_kb,
    )
    return REG_PHOTO_CONFIRM


async def reg_fields(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    missing = context.user_data.get("new_patient_missing", [])
    raw_text = update.message.text.strip()
    p = context.user_data.setdefault("new_patient", {})

    # প্রথমে AI দিয়ে ফ্রি-টেক্সট থেকে ফিল্ড বের করার চেষ্টা — কমা/নির্দিষ্ট ক্রম লাগবে না।
    # AI ব্যর্থ হলে (key নেই / নেটওয়ার্ক সমস্যা / parse fail) নিচে পুরনো কমা-পদ্ধতিতে ফলব্যাক হয়।
    ai_filled = False
    if len(missing) > 1:
        try:
            extracted = await async_runtime.run_ai(
                text_extract.extract_patient_fields,
                raw_text,
            )
        except Exception as e:
            logger.warning(f"text_extract ব্যর্থ হয়েছে, comma-split এ ফলব্যাক: {e}")
            extracted = None
        if extracted:
            field_map = {"full_name": "Full_Name", "phone": "Phone", "address": "Address", "age": "Age"}
            for src_key, dst_key in field_map.items():
                val = extracted.get(src_key)
                if val and dst_key in missing:
                    p[dst_key] = str(val).strip()
                    ai_filled = True

    if ai_filled:
        still_missing = _reg_missing_fields(p)
        if not still_missing:
            context.user_data.pop("new_patient_missing", None)
            return await _reg_check_duplicate_then_note(update, context)
        context.user_data["new_patient_missing"] = still_missing
        labels = [_REG_FIELD_LABELS[k] for k in still_missing]
        if len(labels) == 1:
            prompt = f"⚠️ বাকি আছে — {labels[0]} লেখো:"
        else:
            prompt = f"⚠️ বাকি আছে: {', '.join(labels)} — এক লাইনে লেখো:"
        await update.message.reply_text(prompt)
        return REG_FIELDS

    # AI কিছু না পেলে বা ব্যর্থ হলে পুরনো কমা-ভিত্তিক পদ্ধতি (fallback, আগের মতোই কাজ করে)
    raw_parts = [x.strip() for x in raw_text.split(",")]
    parts = [x for x in raw_parts if x]

    if len(parts) >= len(missing):
        for key, val in zip(missing, parts):
            p[key] = val
        context.user_data.pop("new_patient_missing", None)
        return await _reg_check_duplicate_then_note(update, context)

    for key, val in zip(missing, parts):
        p[key] = val
    still_missing = missing[len(parts):]
    context.user_data["new_patient_missing"] = still_missing
    labels = [_REG_FIELD_LABELS[k] for k in still_missing]
    if len(labels) == 1:
        prompt = f"⚠️ বাকি আছে — {labels[0]} লেখো:"
    else:
        prompt = (
            f"⚠️ বাকি {len(still_missing)}টা তথ্য কমা (,) দিয়ে আলাদা করে এই ক্রমে লেখো:\n\n"
            f"{', '.join(labels)}"
        )
    await update.message.reply_text(prompt)
    return REG_FIELDS


async def reg_phone_dup_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        return await _reg_check_duplicate_then_note(update, context)
    context.user_data.pop("new_patient", None)
    context.user_data.pop("new_patient_dup_checked", None)
    context.user_data.pop("new_patient_missing", None)
    await update.message.reply_text(
        "❌ ডুপ্লিকেট এড়াতে রেজিস্ট্রেশন বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


async def reg_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text.strip()
    context.user_data["new_patient"]["Diagnosis"] = "" if note == "-" else note
    p = context.user_data["new_patient"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"নাম: {p['Full_Name']}\nফোন: {p['Phone']}\nঠিকানা: {p['Address']}\n"
        f"বয়স: {p.get('Age') or '-'}\n"
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
        patient_id = await async_runtime.run_sheets_write(
            sheets.add_patient,
            context.user_data["new_patient"],
            created_by=staff.get("Full_Name", "Unknown"),
        )
        try:
            await async_runtime.run_sheets_write(
                sheets.adjust_inventory_stock,
                "Patient Card", -1, "Auto-Registration",
                staff.get("Full_Name", "Unknown"),
                context.user_data["new_patient"].get("Department", ""),
            )
        except Exception as e:
            logger.warning(f"inventory auto-deduct (Patient Card) ব্যর্থ হয়েছে: {e}")
        await update.message.reply_text(
            f"✅ রোগী রেজিস্ট্রেশন সম্পন্ন! Patient ID: {patient_id}",
            reply_markup=_menu_keyboard(staff),
        )
        new_patient_row = await async_runtime.run_sheets_read(
            sheets.get_patient_by_id, patient_id
        )
        if new_patient_row:
            await update.message.reply_text(
                _patient_card_text(new_patient_row),
                reply_markup=_patient_card_keyboard(patient_id, context.user_data.get("staff", {})),
            )
    else:
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।",
            reply_markup=_menu_keyboard(staff),
        )
    context.user_data.pop("new_patient", None)
    context.user_data.pop("new_patient_dup_checked", None)
    context.user_data.pop("new_patient_missing", None)
    return ConversationHandler.END


async def reg_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("new_patient", None)
    context.user_data.pop("new_patient_dup_checked", None)
    context.user_data.pop("new_patient_missing", None)
    await update.message.reply_text(
        "রেজিস্ট্রেশন বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


# ---------- অ্যাপয়েন্টমেন্ট বুকিং ----------

async def apt_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_APPOINTMENT):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["new_appointment"] = {}
    await update.message.reply_text(
        PATIENT_LOOKUP_PROMPT,
        reply_markup=ReplyKeyboardRemove(),
    )
    recent_kb = await async_runtime.run_sheets_read(
        _recent_patient_buttons, "aptsel_"
    )
    if recent_kb:
        await update.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return APT_SEARCH


async def apt_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = await _search_patients_for_request(update, context, query)
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
    patient = await _patient_by_id_for_request(update, context, patient_id)
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
    await query.edit_message_text("⬅️ রোগী নির্বাচনের ধাপে ফিরে এসেছেন।")
    await query.message.reply_text(PATIENT_LOOKUP_PROMPT)
    recent_kb = await async_runtime.run_sheets_read(
        _recent_patient_buttons, "aptsel_"
    )
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


def _time_multi_keyboard(selected: list) -> InlineKeyboardMarkup:
    """সময় মাল্টি-সিলেক্ট কীবোর্ড — একই দিনে সর্বোচ্চ ২টা সেশন বুক করার জন্য
    (স্বাভাবিকভাবে ১টা সেশন হয়, মাঝেমধ্যে ২টা)। ✅ চিহ্ন দিয়ে বোঝানো হয় কোন কোন
    সময় এখন পর্যন্ত বাছাই করা আছে।"""
    slots = [
        "09:00 AM", "10:00 AM", "11:00 AM",
        "12:00 PM", "01:00 PM",
        "03:00 PM", "04:00 PM", "05:00 PM",
        "06:00 PM", "07:00 PM", "08:00 PM",
    ]
    buttons = []
    row = []
    for slot in slots:
        label = ("✅ " + slot) if slot in selected else slot
        row.append(InlineKeyboardButton(label, callback_data=f"apttimetoggle_{slot}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    done_label = (
        f"➡️ পরের ধাপ ({len(selected)}টা সময় বাছাই করা হয়েছে)"
        if selected else "➡️ অন্তত ১টা সময় বাছাই করো"
    )
    buttons.append([InlineKeyboardButton(done_label, callback_data="apttimedone")])
    buttons.append([InlineKeyboardButton("⬅️ আগের ধাপ", callback_data="aptback_date")])
    return InlineKeyboardMarkup(buttons)


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
        "সময় বেছে নাও — একই দিনে ২টা সেশন হলে দুইটাই বাছাই করো (সর্বোচ্চ ২টা), তারপর 'পরের ধাপ' চাপো:",
        reply_markup=_time_multi_keyboard([]),
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
        "সময় বেছে নাও — একই দিনে ২টা সেশন হলে দুইটাই বাছাই করো (সর্বোচ্চ ২টা), তারপর 'পরের ধাপ' চাপো:",
        reply_markup=_time_multi_keyboard([]),
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
        reply_markup=await async_runtime.run_sheets_read(_therapist_keyboard),
    )
    return APT_THERAPIST


async def apt_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    times = [p.strip() for p in raw.split(",") if p.strip()] or [raw]
    context.user_data.setdefault("new_appointment", {})["Times"] = times
    await update.message.reply_text(
        "থেরাপিস্ট বেছে নাও (অথবা টাইপ করো):",
        reply_markup=await async_runtime.run_sheets_read(_therapist_keyboard),
    )
    return APT_THERAPIST


async def apt_time_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    slot = query.data.replace("apttimetoggle_", "")
    selected = context.user_data.get("apt_times", [])
    if slot in selected:
        selected.remove(slot)
    else:
        if len(selected) >= 2:
            await query.answer("সর্বোচ্চ ২টা সময় বাছাই করা যাবে (দিনে বড়জোর ২টা সেশন হয়)।", show_alert=True)
            return APT_TIME
        selected.append(slot)
    context.user_data["apt_times"] = selected
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=_time_multi_keyboard(selected))
    return APT_TIME


async def apt_time_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    selected = context.user_data.get("apt_times", [])
    if not selected:
        await query.answer("অন্তত একটা সময় বাছাই করো।", show_alert=True)
        return APT_TIME
    await query.answer()
    context.user_data.setdefault("new_appointment", {})["Times"] = list(selected)
    context.user_data.pop("apt_times", None)
    await query.edit_message_text(f"✅ সময় বাছাই করা হয়েছে: {', '.join(selected)}")
    await query.message.reply_text(
        "থেরাপিস্ট বেছে নাও (অথবা টাইপ করো):",
        reply_markup=await async_runtime.run_sheets_read(_therapist_keyboard),
    )
    return APT_THERAPIST


async def apt_back_to_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """থেরাপিস্ট-নির্বাচনের ধাপ থেকে '⬅️ আগের ধাপ' চাপলে আবার সময়-নির্বাচনের ধাপে ফিরে যায়।"""
    query = update.callback_query
    await query.answer()
    a = context.user_data.setdefault("new_appointment", {})
    prev_times = list(a.get("Times") or ([a["Time"]] if a.get("Time") else []))
    context.user_data["apt_times"] = prev_times
    await query.edit_message_text(
        "⬅️ সময় বেছে নাও — একই দিনে ২টা সেশন হলে দুইটাই বাছাই করো (সর্বোচ্চ ২টা), তারপর 'পরের ধাপ' চাপো:",
        reply_markup=_time_multi_keyboard(prev_times),
    )
    return APT_TIME


def _apt_summary_text(a: dict) -> str:
    dates = a.get("Dates") or ([a["Date"]] if a.get("Date") else [])
    date_line = ", ".join(dates) if len(dates) > 1 else (dates[0] if dates else "-")
    date_label = "তারিখসমূহ" if len(dates) > 1 else "তারিখ"
    times = a.get("Times") or ([a["Time"]] if a.get("Time") else [])
    time_line = ", ".join(times) if len(times) > 1 else (times[0] if times else "-")
    time_label = "সময়সমূহ" if len(times) > 1 else "সময়"
    total = len(dates) * len(times) if dates and times else 0
    total_note = f"\nমোট অ্যাপয়েন্টমেন্ট হবে: {total}টা" if total > 1 else ""
    return (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"রোগী: {a['Patient_Name']} ({a['Patient_ID']})\n"
        f"Department: {a.get('Department') or 'N/A'}\n"
        f"{date_label}: {date_line}\n{time_label}: {time_line}{total_note}\n"
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
        times = a.get("Times") or ([a["Time"]] if a.get("Time") else [])
        ids = []
        for d in dates:
            for t in times:
                row = dict(a)
                row["Date"] = d
                row["Time"] = t
                row.pop("Dates", None)
                row.pop("Times", None)
                appointment_id = await async_runtime.run_sheets_write(
                    sheets.add_appointment,
                    row,
                    created_by=staff.get("Full_Name", "Unknown"),
                )
                ids.append(appointment_id)
        if len(ids) > 1:
            msg = f"✅ {len(ids)}টা অ্যাপয়েন্টমেন্ট বুক হয়েছে!\nAppointment IDs: {', '.join(ids)}"
        else:
            msg = f"✅ অ্যাপয়েন্টমেন্ট বুক হয়েছে! Appointment ID: {ids[0] if ids else '-'}"
        await update.message.reply_text(msg, reply_markup=_menu_keyboard(staff))
    else:
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।",
            reply_markup=_menu_keyboard(staff),
        )
    context.user_data.pop("new_appointment", None)
    context.user_data.pop("apt_dates", None)
    context.user_data.pop("apt_times", None)
    return ConversationHandler.END


async def apt_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("new_appointment", None)
    context.user_data.pop("apt_search_results", None)
    context.user_data.pop("apt_dates", None)
    context.user_data.pop("apt_times", None)
    await update.effective_message.reply_text(
        "অ্যাপয়েন্টমেন্ট বুকিং বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


async def search_patient(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args) if context.args else None
    if not query:
        await update.message.reply_text("ব্যবহার: /search <নাম বা ফোন নম্বর>")
        return
    results = await _search_patients_for_request(update, context, query)
    if not results:
        await update.message.reply_text("কোনো রোগী পাওয়া যায়নি।")
        return
    lines = [f"🔍 '{query}' এর ফলাফল ({len(results)} জন):\n"]
    for p in results[:15]:
        lines.append(f"• {p.get('Patient_ID')} — {p.get('Full_Name')} | {p.get('Phone')}")
    await update.message.reply_text("\n".join(lines))


# ---------- হাজিরা (স্টাফ) ----------

async def today_schedule_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📋 আজকের শিডিউল — হাজিরা ও আজকের অ্যাপয়েন্টমেন্ট একসাথে একটা সাবমেনুতে (patch36)।"""
    staff = await _require_staff(update, context)
    if staff is None:
        return
    buttons = []
    if _staff_can_access_menu(staff, roles.MENU_ATTENDANCE):
        buttons.append([InlineKeyboardButton("🕐 হাজিরা", callback_data="sched_att")])
    if _staff_can_access_menu(staff, roles.MENU_TODAY_APPOINTMENTS):
        buttons.append([InlineKeyboardButton("📋 আজকের অ্যাপয়েন্টমেন্ট", callback_data="sched_apt")])
    if not buttons:
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    await update.message.reply_text(
        "📋 আজকের শিডিউল — কোনটা দেখতে চাও?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def schedule_attendance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await attendance_menu(update, context)


async def schedule_appointments_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await today_appointments(update, context)


def _submenu_keyboard(labels: list[str]) -> ReplyKeyboardMarkup:
    rows = [[l] for l in labels] + [[roles.MENU_BACK_MAIN]]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


async def _generic_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE, items_map: dict, title: str):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    items = roles.get_items_for_roles(
        items_map, _effective_role_strings(staff)
    )
    if not items:
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    await update.message.reply_text(title, reply_markup=_submenu_keyboard(items))


async def patient_mgmt_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _generic_submenu(update, context, roles.ROLE_PATIENT_MGMT_ITEMS, "👤 রোগী ব্যবস্থাপনা — কী করতে চাও?")


async def treatment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _generic_submenu(update, context, roles.ROLE_TREATMENT_ITEMS, "📝 ট্রিটমেন্ট — কী করতে চাও?")


async def ai_tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _generic_submenu(update, context, roles.ROLE_AI_TOOLS_ITEMS, "🤖 AI টুলস — কী করতে চাও?")


def _finance_departments(staff: dict) -> frozenset[str]:
    return _report_departments(staff)


def _sheet_amount_value(value) -> float:
    """Normalize numeric or formatted Sheets money without crashing a handler."""
    text = str(value if value is not None else "").strip()
    normalized = text.replace("৳", "").replace(",", "").strip()
    try:
        return float(normalized or 0)
    except (TypeError, ValueError):
        logger.warning("Invalid money value returned by Google Sheets: %r", value)
        return 0.0


def _display_sheet_amount(value) -> str:
    """Format Sheets money safely, including formatted strings such as ৳5,000."""
    return f"{_sheet_amount_value(value):.0f}"


def _staff_has_finance_department(staff: dict, department: str) -> bool:
    target = department_access.normalize_department(department)
    if target not in {
        department_access.Department.PHYSIO,
        department_access.Department.DENTAL,
    }:
        return False
    for value in _finance_departments(staff):
        current = department_access.normalize_department(value)
        if current is department_access.Department.ALL or current is target:
            return True
    return False


def _finance_department_keyboard(prefix: str, staff: dict) -> InlineKeyboardMarkup:
    rows = []
    if _staff_has_finance_department(staff, config.DEPARTMENT_PHYSIO):
        rows.append([InlineKeyboardButton(
            "🩺 Physio", callback_data=f"{prefix}_Physio"
        )])
    if _staff_has_finance_department(staff, config.DEPARTMENT_DENTAL):
        rows.append([InlineKeyboardButton(
            "🦷 Dental", callback_data=f"{prefix}_Dental"
        )])
    return InlineKeyboardMarkup(rows)


async def finance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _generic_submenu(update, context, roles.ROLE_FINANCE_ITEMS, "💰 চলতি হিসাব — কী করতে চাও?")


async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    await update.message.reply_text("🏠 মূল মেনু", reply_markup=_menu_keyboard(staff))


async def attendance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    if not _staff_can_access_menu(staff, roles.MENU_ATTENDANCE):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    staff_id = staff.get("Staff_ID", "") or str(staff.get("Telegram_ID", ""))
    date_str = bd_now().strftime("%Y-%m-%d")
    record = await async_runtime.run_sheets_read(
        sheets.get_today_attendance, staff_id, date_str
    )

    buttons = []
    if not record:
        buttons.append([InlineKeyboardButton("✅ Check In", callback_data="att_checkin")])
        status_line = "🟡 এখনো Check In করোনি।"
    elif not record.get("Break_Out"):
        buttons.append([InlineKeyboardButton("☕ বিরতি শুরু", callback_data="att_breakout")])
        buttons.append([InlineKeyboardButton("🚪 Check Out", callback_data="att_checkout")])
        status_line = f"🟢 Check In: {record.get('Check_In')}"
    elif not record.get("Break_In"):
        buttons.append([InlineKeyboardButton("🔙 বিরতি শেষ", callback_data="att_breakin")])
        status_line = f"☕ Break Out: {record.get('Break_Out')}"
    elif not record.get("Check_Out"):
        buttons.append([InlineKeyboardButton("🚪 Check Out", callback_data="att_checkout")])
        status_line = f"🔙 Break In: {record.get('Break_In')}"
    else:
        await update.effective_message.reply_text(
            f"✅ আজকের হাজিরা সম্পন্ন।\n"
            f"Check In: {record.get('Check_In')}\nCheck Out: {record.get('Check_Out')}\n"
            f"মোট কাজের সময়: {record.get('Working_Hours')} ঘণ্টা"
        )
        return

    await update.effective_message.reply_text(status_line, reply_markup=InlineKeyboardMarkup(buttons))


async def attendance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None:
        await query.edit_message_text("❌ স্টাফ তথ্য পাওয়া যায়নি।")
        return
    staff_id = staff.get("Staff_ID", "") or str(staff.get("Telegram_ID", ""))
    date_str = bd_now().strftime("%Y-%m-%d")
    action = query.data

    if action == "att_checkin":
        existing = await async_runtime.run_sheets_read(
            sheets.get_today_attendance, staff_id, date_str
        )
        if existing:
            await query.edit_message_text(
                f"✅ আজকের Check In আগেই হয়েছে: {existing.get('Check_In', '')}"
            )
            return
        context.user_data["attendance_location_requested_at"] = bd_now().timestamp()
        location_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton("📍 বর্তমান লোকেশন পাঠান", request_location=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await query.edit_message_text("📍 Check In করতে বর্তমান লোকেশন পাঠান।")
        await query.message.reply_text(
            "নিচের বাটনে চাপ দিয়ে লোকেশন পাঠান। অনুরোধটি ২ মিনিট কার্যকর থাকবে।",
            reply_markup=location_keyboard,
        )
    elif action == "att_breakout":
        time_str = await async_runtime.run_sheets_write(
            sheets.attendance_break_out, staff_id, date_str
        )
        await query.edit_message_text(f"☕ Break শুরু: {time_str}" if time_str else "❌ আজকের রেকর্ড পাওয়া যায়নি।")
    elif action == "att_breakin":
        time_str = await async_runtime.run_sheets_write(
            sheets.attendance_break_in, staff_id, date_str
        )
        await query.edit_message_text(f"🔙 Break শেষ: {time_str}" if time_str else "❌ আজকের রেকর্ড পাওয়া যায়নি।")
    elif action == "att_checkout":
        result = await async_runtime.run_sheets_write(
            sheets.attendance_check_out, staff_id, date_str
        )
        if result:
            await query.edit_message_text(
                f"🚪 Check Out হয়েছে: {result['time']}\n"
                f"মোট কাজের সময়: {result['working_hours']} ঘণ্টা\n"
                f"ওভারটাইম: {result['overtime']} ঘণ্টা"
            )
        else:
            await query.edit_message_text("❌ আজকের রেকর্ড পাওয়া যায়নি।")


async def attendance_location_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requested_at = context.user_data.pop("attendance_location_requested_at", None)
    if not requested_at or bd_now().timestamp() - requested_at > 120:
        await update.message.reply_text(
            "⌛ লোকেশন অনুরোধের সময় শেষ হয়েছে। হাজিরা মেনু থেকে আবার Check In করুন।",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    staff = await _require_staff(update, context)
    if staff is None:
        return
    location = update.message.location
    tenant = tenant_runtime.current_tenant() if config.MULTITENANT_ENABLED else None
    result = validate_location(
        location.latitude,
        location.longitude,
        location.horizontal_accuracy,
        clinic_latitude=tenant.latitude if tenant else config.CLINIC_LATITUDE,
        clinic_longitude=tenant.longitude if tenant else config.CLINIC_LONGITUDE,
        radius_m=tenant.attendance_radius_m if tenant else config.ATTENDANCE_RADIUS_METERS,
        max_accuracy_m=(
            tenant.attendance_max_accuracy_m
            if tenant else config.ATTENDANCE_MAX_ACCURACY_METERS
        ),
    )
    if not result["allowed"]:
        messages = {
            "not_configured": "⚠️ Attendance location এখনো configure করা হয়নি। Owner-কে জানান।",
            "low_accuracy": "📡 লোকেশন যথেষ্ট নির্ভুল নয়। GPS চালু করে আবার চেষ্টা করুন।",
            "outside": (
                f"⛔ আপনি ক্লিনিকের অনুমোদিত এলাকার বাইরে আছেন "
                f"(প্রায় {result['distance_m']:.0f} মিটার দূরে)।"
            ),
            "invalid_location": "❌ সঠিক লোকেশন পাওয়া যায়নি। আবার চেষ্টা করুন।",
        }
        await update.message.reply_text(
            messages.get(result["reason"], "❌ লোকেশন যাচাই করা যায়নি।"),
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    accuracy = location.horizontal_accuracy
    audit_note = (
        f"Location verified | lat={location.latitude:.6f} | "
        f"lng={location.longitude:.6f} | distance_m={result['distance_m']:.1f} | "
        f"accuracy_m={accuracy if accuracy is not None else 'unknown'}"
    )
    time_str = await async_runtime.run_sheets_write(
        sheets.attendance_check_in, staff, location_note=audit_note
    )
    await update.message.reply_text(
        f"✅ Check In হয়েছে: {time_str}\n📍 লোকেশন যাচাই হয়েছে।",
        reply_markup=_menu_keyboard(staff),
    )


# ---------- আজকের অ্যাপয়েন্টমেন্ট (রোগীর ভিজিট হাজিরা) ----------

async def today_appointments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    if not _staff_can_access_menu(staff, roles.MENU_TODAY_APPOINTMENTS):
        await update.effective_message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    mappings = await _patient_department_mappings(staff)
    date_str = bd_now().strftime("%Y-%m-%d")
    all_appts = await async_runtime.run_sheets_read(
        sheets.get_appointments_for_date_for_staff,
        date_str,
        staff,
        mappings,
    )
    appts = [
        a for a in all_appts
        if str(a.get("Status", "")).strip() == "Scheduled"
    ]
    if not appts:
        await update.effective_message.reply_text("আজ কোনো পেন্ডিং অ্যাপয়েন্টমেন্ট নেই।")
        return
    for a in appts:
        text = (
            f"🕐 {a.get('Time')} — {a.get('Patient_Name')} ({a.get('Patient_ID')})\n"
            f"Department: {a.get('Department')} | থেরাপিস্ট: {a.get('Therapist')}"
        )
        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "✅ উপস্থিত",
                callback_data=f"aptstatus_{a.get('Appointment_ID')}_Completed",
            ),
            InlineKeyboardButton(
                "❌ আসেনি",
                callback_data=f"aptstatus_{a.get('Appointment_ID')}_NoShow",
            ),
        ]])
        await update.effective_message.reply_text(text, reply_markup=buttons)


async def apt_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_", 3)
    if len(parts) < 3:
        await query.edit_message_text("❌ অবৈধ অ্যাপয়েন্টমেন্ট অনুরোধ।")
        return
    appointment_id, status_code = parts[1], parts[2]
    status_map = {"Completed": "Completed", "NoShow": "No-show"}
    status = status_map.get(status_code)
    if status is None:
        await query.edit_message_text("❌ অবৈধ অ্যাপয়েন্টমেন্ট স্ট্যাটাস।")
        return

    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(
        staff, roles.MENU_TODAY_APPOINTMENTS
    ):
        await query.message.reply_text("⛔ এই অ্যাপয়েন্টমেন্ট বদলানোর অনুমতি তোমার নেই।")
        return
    mappings = await _patient_department_mappings(staff)
    appointment = await async_runtime.run_sheets_read(
        sheets.get_appointment_by_id_for_staff,
        appointment_id,
        staff,
        mappings,
        department_access.AccessAction.WRITE,
    )
    if appointment is None:
        await query.edit_message_text(
            "⛔ অ্যাপয়েন্টমেন্ট পাওয়া যায়নি অথবা বর্তমান অনুমতি নেই।"
        )
        return

    ok = await async_runtime.run_sheets_write(
        sheets.update_appointment_status_for_staff,
        appointment_id,
        status,
        staff,
        mappings,
    )
    if not ok:
        await query.edit_message_text(
            "⛔ বর্তমান অনুমতি আবার যাচাই করে স্ট্যাটাস আপডেট করা যায়নি।"
        )
        return

    patient_id = str(appointment.get("Patient_ID", "")).strip()
    if status_code == "Completed" and patient_id:
        patient = await _patient_by_id_for_request(update, context, patient_id)
        if patient:
            await query.edit_message_text(
                f"✅ {appointment_id} — উপস্থিত হয়েছে।\n\n" + _patient_card_text(patient),
                reply_markup=_patient_card_keyboard(
                    patient_id,
                    staff,
                    back_callback_data=f"apttodayback_{appointment_id}",
                    back_label="🔙 অ্যাপয়েন্টমেন্ট তালিকায় ফিরুন",
                ),
            )
            return
    await query.edit_message_text(f"✅ {appointment_id} — স্ট্যাটাস: {status}")


async def apt_today_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reload and reauthorize an appointment before rebuilding its action card."""
    query = update.callback_query
    await query.answer()
    appointment_id = query.data.replace("apttodayback_", "", 1)
    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(
        staff, roles.MENU_TODAY_APPOINTMENTS
    ):
        await query.message.reply_text("⛔ এই অ্যাপয়েন্টমেন্ট দেখার অনুমতি তোমার নেই।")
        return
    mappings = await _patient_department_mappings(staff)
    a = await async_runtime.run_sheets_read(
        sheets.get_appointment_by_id_for_staff,
        appointment_id,
        staff,
        mappings,
        department_access.AccessAction.READ,
    )
    if not a:
        await query.edit_message_text(
            "⛔ অ্যাপয়েন্টমেন্ট পাওয়া যায়নি অথবা বর্তমান অনুমতি নেই।"
        )
        return
    text = (
        f"🕐 {a.get('Time')} — {a.get('Patient_Name')} ({a.get('Patient_ID')})\n"
        f"Department: {a.get('Department')} | থেরাপিস্ট: {a.get('Therapist')}"
    )
    buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ উপস্থিত",
            callback_data=f"aptstatus_{a.get('Appointment_ID')}_Completed",
        ),
        InlineKeyboardButton(
            "❌ আসেনি",
            callback_data=f"aptstatus_{a.get('Appointment_ID')}_NoShow",
        ),
    ]])
    await query.edit_message_text(text, reply_markup=buttons)


async def pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_PAYMENT):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["payment"] = {}
    await update.message.reply_text(
        PATIENT_LOOKUP_PROMPT,
        reply_markup=ReplyKeyboardRemove(),
    )
    recent_kb = await async_runtime.run_sheets_read(
        _recent_patient_buttons, "paysel_"
    )
    if recent_kb:
        await update.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return PAY_SEARCH


async def pay_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()

    ai_data = await async_runtime.run_ai(ai_helper.parse_register_entry, query)
    if ai_data:
        ai_results = await _search_patients_for_request(
            update, context, ai_data["name"]
        )
        if len(ai_results) == 1:
            patient = ai_results[0]
            context.user_data.setdefault("payment", {})
            context.user_data["payment"]["Patient_ID"] = patient.get("Patient_ID", "")
            context.user_data["payment"]["Patient_Name"] = patient.get("Full_Name", "")
            context.user_data["payment"]["Department"] = patient.get("Department", "")
            context.user_data["payment"]["Sessions"] = ai_data["sessions"]
            context.user_data["payment"]["Amount"] = ai_data["amount"]
            await update.message.reply_text(
                f"🤖 AI বুঝেছে: {patient.get('Full_Name','')} ({patient.get('Patient_ID','')}) — "
                f"সেশন {ai_data['sessions']}, টাকা {ai_data['amount']:.0f}\n\n"
                "Payment Method বেছে নাও:",
                reply_markup=_payment_method_keyboard(),
            )
            return PAY_METHOD
        elif len(ai_results) > 1:
            context.user_data["pay_search_results"] = {
                p.get("Patient_ID", "").strip(): p for p in ai_results[:10]
            }
            context.user_data["_ai_prefill"] = {
                "amount": ai_data["amount"], "sessions": ai_data["sessions"]
            }
            await update.message.reply_text(
                f"🤖 '{ai_data['name']}' নামে একাধিক মিল পাওয়া গেছে — সঠিক রোগী বেছে নাও:",
                reply_markup=_patient_search_buttons(ai_results[:10], "paysel_", "paysearchback"),
            )
            return PAY_SELECT

    results = await _search_patients_for_request(update, context, query)
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
    patient = await _patient_by_id_for_request(update, context, patient_id)
    if not patient:
        await query.edit_message_text(
            "❌ তালিকার মেয়াদ শেষ। আবার শুরু করতে /cancel দাও, তারপর 📋 আজকের রেজিস্টার থেকে ➕ নতুন এন্ট্রি চাপো।"
        )
        return ConversationHandler.END
    context.user_data.setdefault("payment", {})["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["payment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data["payment"]["Department"] = patient.get("Department", "")
    context.user_data.pop("pay_search_results", None)

    ai_prefill = context.user_data.pop("_ai_prefill", None)
    if ai_prefill:
        context.user_data["payment"]["Sessions"] = ai_prefill["sessions"]
        context.user_data["payment"]["Amount"] = ai_prefill["amount"]
        await query.edit_message_text(
            f"🤖 রোগী: {patient.get('Full_Name','')} ({patient.get('Patient_ID','')}) — "
            f"সেশন {ai_prefill['sessions']}, টাকা {ai_prefill['amount']:.0f}"
        )
        await query.message.reply_text(
            "Payment Method বেছে নাও:", reply_markup=_payment_method_keyboard()
        )
        return PAY_METHOD

    context.user_data["payment"]["Sessions"] = 1
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
    p = context.user_data.get("payment", {})
    staff = context.user_data.get("staff", {})

    if text not in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        context.user_data.pop("payment", None)
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।", reply_markup=_menu_keyboard(staff)
        )
        return ConversationHandler.END

    patient_id = p.get("Patient_ID", "")
    staff, patient = await _authorized_patient_action(
        update, context, patient_id,
        department_access.AccessAction.WRITE,
        roles.MENU_PAYMENT,
    )
    if not patient:
        context.user_data.pop("payment", None)
        await update.message.reply_text(
            "⛔ বর্তমান Department/Role অনুযায়ী এই পেমেন্ট সেভ করার অনুমতি নেই।",
            reply_markup=_menu_keyboard(staff or {}),
        )
        return ConversationHandler.END
    # Never trust stale cached patient identity/department at the final write.
    p["Patient_Name"] = patient.get("Full_Name", "")
    p["Department"] = patient.get("Department", "")
    amount = p.get("Amount", 0)
    sessions = p.get("Sessions", 0)

    try:
        bill_status, receipt_no = await async_runtime.run_sheets_write(
            sheets.record_payment_transaction,
            patient_id,
            amount,
            sessions,
            {
                "Patient_ID": patient_id,
                "Patient_Name": p.get("Patient_Name", ""),
                "Department": p.get("Department", ""),
                "Amount": amount,
                "Discount": 0,
                "Due": "",
                "Payment_Method": p.get("Payment_Method", "") if amount > 0 else "N/A",
                "Received_By": staff.get("Full_Name", "Unknown"),
                "Remarks": f"Sessions: {sessions}" if sessions is not None else "",
            },
            idempotency_key=str(update.update_id),
        )

        if amount > 0:
            lines = [
                f"✅ পেমেন্ট সেভ হয়েছে! Receipt No: {receipt_no}",
                f"রোগী: {p.get('Patient_Name')} ({patient_id})",
                f"জমা নেওয়া হলো: {amount} ({p.get('Payment_Method')})",
            ]
            if bill_status:
                lines.append(f"মোট জমা: {bill_status['paid_amount']} | বাকি: {bill_status['due_amount']}")
        else:
            lines = [
                f"✅ সেভ হয়েছে (কোনো টাকা নেওয়া হয়নি — শুধু সেশন এন্ট্রি) — Entry No: {receipt_no}",
                f"রোগী: {p.get('Patient_Name')} ({patient_id})",
                f"সেশন: {sessions}" if sessions else "",
            ]

        await update.message.reply_text(
            "\n".join(lines), reply_markup=_menu_keyboard(staff)
        )
        reg_text, reg_kb = await async_runtime.run_sheets_read(
            _register_view_text_and_keyboard, _report_departments(staff)
        )
        await update.message.reply_text(reg_text, reply_markup=reg_kb)
    except Exception as e:
        logger.exception("pay_confirm ব্যর্থ হয়েছে")
        await update.message.reply_text(
            f"❌ পেমেন্ট সেভ করতে সমস্যা হয়েছে।\nError: {e}\n\n"
            "স্ক্রিনশট দিয়ে জানাও, ঠিক করে দেওয়া হবে।",
            reply_markup=_menu_keyboard(staff),
        )
    context.user_data.pop("payment", None)
    return ConversationHandler.END


async def pay_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("payment", None)
    context.user_data.pop("pay_search_results", None)
    await update.effective_message.reply_text(
        "পেমেন্ট এন্ট্রি বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


# ---------- আজকের এন্ট্রি মুছুন (ভুল টাকা/সেশন সংখ্যা ঠিক করার জন্য) ----------

def _paydel_list_keyboard(entries: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for e in entries:
        amount = e.get("Amount", 0)
        remarks = str(e.get("Remarks", ""))
        label_bits = [str(e.get("Patient_Name", ""))]
        if _safe_int(amount, 0) > 0:
            label_bits.append(f"৳{amount}")
        m = re.search(r"Sessions:\s*(\d+)", remarks)
        if m:
            label_bits.append(f"{m.group(1)} সেশন")
        label = f"{e.get('Receipt_No', '')} — " + " | ".join(label_bits)
        buttons.append([InlineKeyboardButton(label, callback_data=f"paydelsel_{e.get('Receipt_No', '')}")])
    buttons.append([InlineKeyboardButton("❌ বাতিল", callback_data="paydelcancel")])
    return InlineKeyboardMarkup(buttons)


async def paydel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_DELETE_ENTRY):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END

    staff_name = staff.get("Full_Name", "")
    entries = await async_runtime.run_sheets_read(
        sheets.get_today_payments_by_staff, staff_name
    )
    if not entries:
        await update.message.reply_text(
            "আজকে তোমার নামে কোনো এন্ট্রি নেই।",
            reply_markup=_menu_keyboard(staff),
        )
        return ConversationHandler.END

    context.user_data["paydel_entries"] = {str(e.get("Receipt_No", "")): e for e in entries}
    await update.message.reply_text(
        "আজকে তোমার করা এন্ট্রিগুলোর মধ্যে কোনটা মুছবে? বেছে নাও:\n"
        "(শুধু আজকের এন্ট্রি এখানে দেখানো হয়।)",
        reply_markup=_paydel_list_keyboard(entries),
    )
    return PAYDEL_LIST


async def paydel_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    receipt_no = query.data.replace("paydelsel_", "", 1)
    entries = context.user_data.get("paydel_entries", {})
    entry = entries.get(receipt_no)
    if entry is None:
        await query.edit_message_text("❌ এন্ট্রিটা আর পাওয়া যাচ্ছে না। আবার শুরু করো।")
        return ConversationHandler.END

    context.user_data["paydel_selected"] = receipt_no
    amount = entry.get("Amount", 0)
    remarks = str(entry.get("Remarks", ""))
    m = re.search(r"Sessions:\s*(\d+)", remarks)
    sessions_line = f"সেশন: {m.group(1)}\n" if m else ""
    text = (
        "নিচের এন্ট্রিটা মুছে ফেলা হবে — এটা ঠিক আছে?\n\n"
        f"রোগী: {entry.get('Patient_Name', '')} ({entry.get('Patient_ID', '')})\n"
        f"টাকা: {amount}\n"
        f"{sessions_line}"
        f"Entry No: {receipt_no}\n\n"
        "⚠️ মুছলে রোগীর হিসাব ও সেশন সংখ্যা থেকেও এটা বাদ যাবে। এটা ফেরানো যাবে না।"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ হ্যাঁ, মুছে দাও", callback_data="paydelconfirm_yes")],
        [InlineKeyboardButton("❌ না, বাতিল করো", callback_data="paydelcancel")],
    ])
    await query.edit_message_text(text, reply_markup=keyboard)
    return PAYDEL_CONFIRM


async def paydel_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    receipt_no = context.user_data.get("paydel_selected")

    if not receipt_no:
        await query.edit_message_text("❌ কিছু একটা ভুল হয়েছে। আবার শুরু করো।")
        return ConversationHandler.END

    try:
        deleted = await async_runtime.run_sheets_write(
            sheets.delete_payment,
            receipt_no,
            deleted_by=staff.get("Full_Name", "Unknown"),
        )
    except Exception as e:
        logger.exception("delete_payment ব্যর্থ হয়েছে")
        await query.edit_message_text(
            f"❌ মুছতে সমস্যা হয়েছে।\nError: {e}\nস্ক্রিনশট দিয়ে জানাও।"
        )
        context.user_data.pop("paydel_entries", None)
        context.user_data.pop("paydel_selected", None)
        return ConversationHandler.END

    if deleted is None:
        await query.edit_message_text("❌ এন্ট্রিটা খুঁজে পাওয়া যায়নি (হয়তো আগেই মোছা হয়েছে)।")
    else:
        await query.edit_message_text(f"✅ এন্ট্রি (Entry No: {receipt_no}) মুছে ফেলা হয়েছে।")

    context.user_data.pop("paydel_entries", None)
    context.user_data.pop("paydel_selected", None)
    await query.message.reply_text(
        "🏠 মূল মেনু", reply_markup=_menu_keyboard(staff)
    )
    return ConversationHandler.END


async def paydel_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    context.user_data.pop("paydel_entries", None)
    context.user_data.pop("paydel_selected", None)
    await query.edit_message_text("বাতিল করা হয়েছে — কিছুই মোছা হয়নি।")
    await query.message.reply_text(
        "🏠 মূল মেনু", reply_markup=_menu_keyboard(staff)
    )
    return ConversationHandler.END


# ---------- ট্রিটমেন্ট নোট (দ্রুত দৈনিক ফ্লো — Active প্ল্যান থেকে অটো-ফিল) ----------

async def _treat_prepare_for_patient(patient: dict, context: ContextTypes.DEFAULT_TYPE):
    """
    রোগীর Active ট্রিটমেন্ট প্ল্যান খুঁজে বের করে।
    প্ল্যান না থাকলে (None, stop_text) রিটার্ন করে — কলার সাথে সাথে conversation END করবে।
    প্ল্যান থাকলে context.user_data["treatment"]/["treat_selected"] সাজিয়ে
    (selected_machines_set, summary_text) রিটার্ন করে — কলার তখন মেশিন-বাছাই কীবোর্ড দেখাবে।

    Exercise/Manual_Therapy আগে সর্বশেষ ট্রিটমেন্ট নোট থেকে নেওয়া হয় (থেরাপিস্ট গতকাল যা
    এডিট করেছিল সেটাই), শুধু কোনো নোট না থাকলে (session 1) মূল প্ল্যানের মান ফলব্যাক
    হিসেবে ব্যবহৃত হয়। Electrotherapy আর আলাদা করে টাইপ করানো হয় না — এটা এখন সম্পূর্ণভাবে
    নিচের মেশিন-চেকলিস্ট (TENS/Ultrasound/SWD/IFT ইত্যাদি) দিয়ে ক্যাপচার হয়।
    """
    patient_id = patient.get("Patient_ID", "")
    plan = await async_runtime.run_sheets_read(
        sheets.get_active_plan_for_patient, patient_id
    )
    if plan is None:
        stop_text = (
            f"⚠️ {patient.get('Full_Name')} ({patient_id})-এর কোনো Active ট্রিটমেন্ট প্ল্যান নেই।\n\n"
            "আগে 🩺 ট্রিটমেন্ট প্ল্যান বাটনে গিয়ে একটা প্ল্যান বানাও, তারপর এখানে ফিরে এসো।"
        )
        return None, stop_text

    session_no = int(plan.get("Sessions_Done", 0) or 0) + 1

    last_note = await async_runtime.run_sheets_read(
        sheets.get_last_treatment_note_for_patient, patient_id
    )

    exercise = plan.get("Exercise_Plan", "")
    manual = plan.get("Manual_Therapy_Plan", "")
    if last_note:
        exercise = last_note.get("Exercise", "") or exercise
        manual = last_note.get("Manual_Therapy", "") or manual

    context.user_data["treatment"] = {
        "Patient_ID": patient_id,
        "Patient_Name": patient.get("Full_Name", ""),
        "Plan_ID": plan.get("Plan_ID", ""),
        "Diagnosis": plan.get("Diagnosis", ""),
        "Treatment_Given": "",
        "Exercise": exercise,
        "Electrotherapy": "",
        "Manual_Therapy": manual,
        "Session_No": session_no,
    }

    prev_machines = []
    if last_note:
        prev_machines = [m.strip() for m in str(last_note.get("Machines", "")).split(",") if m.strip()]
    selected = {idx for idx, name in enumerate(MACHINE_LIST) if name in prev_machines}
    context.user_data["treat_selected"] = selected

    total = plan.get("Total_Sessions", "N/A")
    summary = (
        f"📋 {patient.get('Full_Name')} ({patient_id}) — সেশন {session_no}/{total}\n\n"
        f"সমস্যা (Diagnosis): {plan.get('Diagnosis') or '-'}\n"
        f"এক্সারসাইজ: {exercise or '-'}\n"
        f"ম্যানুয়াল থেরাপি: {manual or '-'}\n\n"
        "আজকের এক্সারসাইজ/ম্যানুয়াল থেরাপি কি গতকালের মতোই থাকবে, নাকি এডিট করবে?"
    )
    return selected, summary


async def treat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ট্রিটমেন্ট নোট এন্ট্রি শুরু — রোগী খোঁজা দিয়ে শুরু হয়।"""
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_TREATMENT_NOTE):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["treatment"] = {}
    context.user_data["treat_selected"] = set()
    await update.message.reply_text(
        PATIENT_LOOKUP_PROMPT,
        reply_markup=ReplyKeyboardRemove(),
    )
    recent_kb = await async_runtime.run_sheets_read(
        _recent_patient_buttons, "treatsel_"
    )
    if recent_kb:
        await update.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return TREAT_SEARCH


async def treat_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = await _search_patients_for_request(update, context, query)
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
    patient = await _patient_by_id_for_request(update, context, patient_id)
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

    await query.edit_message_text(summary, reply_markup=_treat_confirm_keyboard(patient_id))
    return TREAT_CONFIRM_PLAN


async def treat_confirm_same_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'✅ গতকালের মতোই' চাপলে Exercise/Electrotherapy/Manual Therapy এবং Machines —
    সবকিছুই গতকালের মতো রেখে যাবে, তারপর রোগীর আজকের মন্তব্য জিজ্ঞেস করবে।"""
    query = update.callback_query
    await query.answer()
    t = context.user_data.get("treatment", {})
    selected = context.user_data.get("treat_selected", set())
    return await _treat_ask_patient_comment(query.edit_message_text, context, t, selected)


async def treat_confirm_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'✏️ এডিট করবো' চাপলে Exercise → Electrotherapy → Manual Therapy একে একে জিজ্ঞেস করা হবে।
    রিপ্লাইয়ে '-' দিলে আগের (প্ল্যানের) মানটাই থেকে যাবে।"""
    query = update.callback_query
    await query.answer()
    t = context.user_data.get("treatment", {})
    prev_ex = t.get("Exercise", "")
    hint = f" (আগেরটা: {prev_ex} — একই রাখতে - দাও)" if prev_ex else " (না থাকলে - দাও)"
    await query.edit_message_text(f"✏️ আজকের এক্সারসাইজ লেখো{hint}:")
    return TREAT_EDIT_EXERCISE


async def treat_edit_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    t = context.user_data.get("treatment", {})
    if text != "-":
        t["Exercise"] = text
    context.user_data["treatment"] = t

    prev_man = t.get("Manual_Therapy", "")
    hint = f" (আগেরটা: {prev_man} — একই রাখতে - দাও)" if prev_man else " (না থাকলে - দাও)"
    await update.message.reply_text(f"✏️ আজকের ম্যানুয়াল থেরাপি লেখো{hint}:")
    return TREAT_EDIT_MANUAL

async def treat_edit_electro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    t = context.user_data.get("treatment", {})
    if text != "-":
        t["Electrotherapy"] = text
    context.user_data["treatment"] = t

    prev_man = t.get("Manual_Therapy", "")
    hint = f" (আগেরটা: {prev_man} — একই রাখতে - দাও)" if prev_man else " (না থাকলে - দাও)"
    await update.message.reply_text(f"✏️ আজকের ম্যানুয়াল থেরাপি লেখো{hint}:")
    return TREAT_EDIT_MANUAL


async def treat_edit_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    t = context.user_data.get("treatment", {})
    if text != "-":
        t["Manual_Therapy"] = text
    context.user_data["treatment"] = t

    selected = context.user_data.get("treat_selected", set())
    summary = (
        f"📋 {t.get('Patient_Name')} ({t.get('Patient_ID')}) — সেশন {t.get('Session_No', '?')}\n\n"
        f"এক্সারসাইজ: {t.get('Exercise') or '-'}\n"
        f"ম্যানুয়াল থেরাপি: {t.get('Manual_Therapy') or '-'}\n\n"
        "আজকের মেশিন/মোডালিটি বেছে নাও, তারপর সম্পন্ন চাপো:"
    )
    await update.message.reply_text(summary, reply_markup=_machine_keyboard(selected))
    return TREAT_MACHINES

async def treat_back_to_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """মেশিন-নির্বাচনের ধাপ থেকে '⬅️ আগের ধাপ' চাপলে আবার রোগী খোঁজার ধাপে ফিরে যায়।"""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_selected", None)
    await query.edit_message_text("⬅️ রোগী নির্বাচনের ধাপে ফিরে এসেছেন।")
    await query.message.reply_text(PATIENT_LOOKUP_PROMPT)
    recent_kb = await async_runtime.run_sheets_read(
        _recent_patient_buttons, "treatsel_"
    )
    if recent_kb:
        await query.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return TREAT_SEARCH


async def treat_back_to_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """মেশিন-নির্বাচনের ধাপ থেকে '⬅️ আগের ধাপ' চাপলে ঠিক আগের ধাপে (গতকালের মতোই/এডিট করবো)
    ফিরে যায় — এতক্ষণ যা এক্সারসাইজ/ম্যানুয়াল থেরাপি এডিট বা মেশিন বাছাই করা হয়েছে সব অক্ষত থাকে
    (patch3: আগে এই বাটন ভুল করে একদম শুরুর 'রোগী খোঁজা' ধাপে নিয়ে যেত)।"""
    query = update.callback_query
    await query.answer()
    t = context.user_data.get("treatment", {})
    patient_id = t.get("Patient_ID", "")
    plan = await async_runtime.run_sheets_read(
        sheets.get_active_plan_for_patient, patient_id
    )
    total = plan.get("Total_Sessions", "N/A") if plan else "N/A"
    summary = (
        f"📋 {t.get('Patient_Name')} ({patient_id}) — সেশন {t.get('Session_No', '?')}/{total}\n\n"
        f"সমস্যা (Diagnosis): {t.get('Diagnosis') or '-'}\n"
        f"এক্সারসাইজ: {t.get('Exercise') or '-'}\n"
        f"ম্যানুয়াল থেরাপি: {t.get('Manual_Therapy') or '-'}\n\n"
        "আজকের এক্সারসাইজ/ম্যানুয়াল থেরাপি কি গতকালের মতোই থাকবে, নাকি এডিট করবে?"
    )
    await query.edit_message_text(summary, reply_markup=_treat_confirm_keyboard(patient_id))
    return TREAT_CONFIRM_PLAN


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


async def _treat_ask_patient_comment(reply_func, context: ContextTypes.DEFAULT_TYPE, t: dict, selected: set):
    """Machines বসিয়ে, সেভের আগে থেরাপিস্টকে রোগীর আজকের মন্তব্য জিজ্ঞেস করে (TREAT_PATIENT_COMMENT state)।"""
    t["Machines"] = ", ".join(MACHINE_LIST[i] for i in sorted(selected))
    context.user_data["treatment"] = t
    context.user_data["treat_selected"] = selected
    await reply_func(
        "🗣️ আজকে রোগী কী বললো/মন্তব্য করলো? (ব্যথা কেমন লাগছে, ঘুম কেমন হয়েছে, অন্য কোনো সমস্যা ইত্যাদি — "
        "যা যা বলেছে সব লিখো)\n\nকিছু না বললে - দাও:"
    )
    return TREAT_PATIENT_COMMENT


def _treat_progress_status(patient_id: str) -> tuple:
    """(due, mandatory, days_since) রিটার্ন করে — শেষবার কবে Pain Score নেওয়া হয়েছিল
    তার উপর ভিত্তি করে আজ progress check জিজ্ঞাসা করা উচিত কিনা ঠিক করে।
    ৩ দিনের কম হলে জিজ্ঞাসা করা হয় না, ৩-৬ দিন হলে ঐচ্ছিক (স্কিপ করা যাবে),
    ৭+ দিন (বা কখনো রেকর্ড না থাকলে) বাধ্যতামূলক (patch: progress tracker)।"""
    notes = sheets.get_treatment_notes_for_patient(patient_id)
    scored = [n for n in notes if str(n.get("Pain", "")).strip() != ""]
    if not scored:
        return True, False, None
    scored.sort(key=lambda n: str(n.get("Date", "")))
    last_date = _parse_date(scored[-1].get("Date", ""))
    if last_date is None:
        return True, False, None
    days_since = (bd_now().date() - last_date).days
    if days_since < 3:
        return False, False, days_since
    return True, days_since >= 7, days_since


def _pain_score_keyboard(mandatory: bool) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i in range(11):
        row.append(InlineKeyboardButton(str(i), callback_data=f"trpain_{i}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if not mandatory:
        rows.append([InlineKeyboardButton("⏭️ এখন স্কিপ করো", callback_data="trpainskip")])
    return InlineKeyboardMarkup(rows)


async def treat_patient_comment_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """রোগীর মন্তব্য নিয়ে Remarks-এ বসায়, তারপর প্রয়োজনে Pain Score জিজ্ঞেস করে,
    তারপর AI Missing-Info চেক করে সেভ করে।"""
    text = update.message.text.strip()
    t = context.user_data.get("treatment", {})
    selected = context.user_data.get("treat_selected", set())
    if text != "-":
        t["Remarks"] = f"[রোগীর মন্তব্য] {text}"
    context.user_data["treatment"] = t

    due, mandatory, _days_since = await async_runtime.run_sheets_read(
        _treat_progress_status, t.get("Patient_ID", "")
    )
    if due:
        note = "📈 আজ রোগীর ব্যথা ০-১০ স্কেলে কত? (০ = ব্যথা নেই, ১০ = সর্বোচ্চ ব্যথা)\n\n" + (
            "⚠️ শেষ ৭+ দিন কোনো Pain Score রেকর্ড হয়নি — এবার স্কিপ করা যাবে না।"
            if mandatory else "প্রতি কয়েকদিনে একবার এটা জিজ্ঞেস করা হয় — চাইলে স্কিপও করা যাবে।"
        )
        await update.message.reply_text(note, reply_markup=_pain_score_keyboard(mandatory))
        return TREAT_PROGRESS_SCORE

    return await _treat_save_note(update, update.message.reply_text, update.message.reply_text, context, t, selected)


async def treat_progress_score_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pain Score বাটন বা স্কিপ বাটনের রেসপন্স নিয়ে t['Pain']-এ বসায়, তারপর সেভ করে।"""
    query = update.callback_query
    await query.answer()
    t = context.user_data.get("treatment", {})
    selected = context.user_data.get("treat_selected", set())
    if query.data != "trpainskip":
        score = query.data.replace("trpain_", "", 1)
        t["Pain"] = score
        context.user_data["treatment"] = t
        await query.edit_message_text(f"✅ Pain Score রেকর্ড হয়েছে: {score}/10")
    else:
        await query.edit_message_text("⏭️ Pain Score স্কিপ করা হলো।")
    return await _treat_save_note(update, query.message.reply_text, query.message.reply_text, context, t, selected)


async def _treat_save_note(update, reply_func, menu_reply, context: ContextTypes.DEFAULT_TYPE, t: dict, selected: set):
    """রোগীর মন্তব্য বিবেচনায় নিয়ে, সত্যিই কিছু মিসিং থাকলে AI ১টা প্রশ্ন করে (TREAT_AI_QUESTION state-এ যায়,
    আগের মন্তব্যে যা বলা হয়ে গেছে তা নিয়ে duplicate প্রশ্ন করে না), নাহলে সরাসরি সেভ করে দেয়।"""
    try:
        question = await async_runtime.run_ai(
            case_study_ai.check_treatment_missing_info,
            t,
        )
    except Exception:
        logger.exception("check_treatment_missing_info ব্যর্থ হয়েছে — প্রশ্ন ছাড়াই এগোনো হচ্ছে")
        question = ""

    if question:
        context.user_data["treat_ai_question"] = question
        await reply_func(
            f"⚠️ {question}\n\n(উত্তর টাইপ করো — না জানলে 'জানি না' লিখো)"
        )
        return TREAT_AI_QUESTION

    return await _treat_do_save(update, reply_func, menu_reply, context, t, selected)


async def treat_ai_question_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Treatment সেভ হওয়ার আগে AI-এর Red Flag প্রশ্নের উত্তর নেয়, Remarks-এ যোগ করে, তারপর সেভ করে।"""
    text = update.message.text.strip()
    t = context.user_data.get("treatment", {})
    selected = context.user_data.get("treat_selected", set())
    question = context.user_data.pop("treat_ai_question", "")
    if text not in ("না", "না।", "no", "No", "N/A", "n/a", "জানি না"):
        note = f"[AI প্রশ্ন] {question}\n[উত্তর] {text}"
        prev_remarks = t.get("Remarks", "")
        t["Remarks"] = (prev_remarks + "\n" + note).strip() if prev_remarks else note
    return await _treat_do_save(update, update.message.reply_text, update.message.reply_text, context, t, selected)


def _apply_inventory_auto_deduct(
    machines_str: str, staff_name: str, department: str
):
    """ট্রিটমেন্ট নোট সেভ হওয়ার পর প্রাসঙ্গিক inventory item গুলো auto-deduct করে। কোনো
    item পাওয়া না গেলে বা Sheets-এ সমস্যা হলেও এই ফাংশন exception raise করে না — inventory
    ট্র্যাকিং ব্যর্থ হলেও মূল ট্রিটমেন্ট ফ্লো কখনো আটকাবে না।"""
    try:
        sheets.adjust_inventory_stock("Hand Gloves", -1, "Auto-Session", staff_name, department)
    except Exception as e:
        logger.warning(f"inventory auto-deduct (Hand Gloves) ব্যর্থ হয়েছে: {e}")
    try:
        sheets.adjust_inventory_stock("Tissue", -1, "Auto-Session", staff_name, department)
    except Exception as e:
        logger.warning(f"inventory auto-deduct (Tissue) ব্যর্থ হয়েছে: {e}")

    machines = [m.strip().lower() for m in (machines_str or "").split(",") if m.strip()]
    if "manual therapy" in machines:
        try:
            sheets.adjust_inventory_stock("Olive Oil", -33, "Auto-Session", staff_name, department)
        except Exception as e:
            logger.warning(f"inventory auto-deduct (Olive Oil) ব্যর্থ হয়েছে: {e}")
    if "dry needling" in machines:
        try:
            sheets.adjust_inventory_stock("Acupuncture Needle", -5, "Auto-Session", staff_name, department)
        except Exception as e:
            logger.warning(f"inventory auto-deduct (Acupuncture Needle) ব্যর্থ হয়েছে: {e}")
    if "wax bath" in machines:
        try:
            sheets.adjust_inventory_stock("Poly", -1, "Auto-Session", staff_name, department)
        except Exception as e:
            logger.warning(f"inventory auto-deduct (Poly) ব্যর্থ হয়েছে: {e}")
        try:
            sheets.adjust_inventory_stock("PP Wax", -0.05, "Auto-Session", staff_name, department)
        except Exception as e:
            logger.warning(f"inventory auto-deduct (PP Wax) ব্যর্থ হয়েছে: {e}")


def _inventory_list_text(departments) -> str:
    items = sheets.get_all_inventory(departments)
    lines = ["📦 বর্তমান স্টক:", ""]
    current_department = None
    for item in sorted(
        items,
        key=lambda row: (
            str(row.get("Department", "")),
            str(row.get("Item_Name", "")),
        ),
    ):
        department = str(item.get("Department", "")).strip()
        if department != current_department:
            current_department = department
            lines.extend([f"【{department}】"])
        name = str(item.get("Item_Name", "")).strip()
        if not name:
            continue
        stock = item.get("Current_Stock", "")
        unit = str(item.get("Unit", "")).strip()
        minimum_raw = item.get("Minimum_Stock", item.get("Minimum", ""))
        warning = ""
        try:
            if float(stock or 0) <= float(minimum_raw or 0) and float(minimum_raw or 0) > 0:
                warning = " ⚠️ কম আছে!"
        except (TypeError, ValueError):
            pass
        lines.append(f"• {name}: {stock} {unit}{warning}")
    if not items:
        lines.append("এই Department-এ এখনো কোনো inventory item নেই।")
    lines.extend([
        "",
        "একটি Department থাকলে: Hand Gloves -20",
        "Owner/একাধিক Department হলে: Physio: Hand Gloves -20",
    ])
    return "\n".join(lines)


async def inventory_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_INVENTORY):
        await update.effective_message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    departments = _report_departments(staff)
    await update.effective_message.reply_text(
        await async_runtime.run_sheets_read(_inventory_list_text, departments),
        reply_markup=ReplyKeyboardMarkup([[roles.MENU_BACK_MAIN]], resize_keyboard=True),
    )
    return INV_UPDATE


async def inventory_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(staff, roles.MENU_INVENTORY):
        return ConversationHandler.END
    departments = _report_departments(staff)
    text = update.message.text.strip()
    match = re.match(
        r"^(?:(Physio|Dental)\s*:\s*)?(.+?)\s*([+\-])\s*([\d.]+)\s*$",
        text,
        re.I,
    )
    if not match:
        await update.message.reply_text(
            "⚠️ যেমন লেখো: Hand Gloves -20 অথবা Physio: Hand Gloves -20"
        )
        return INV_UPDATE
    requested_department, item_name, sign, amount_str = match.groups()
    normalized = department_access.normalize_department(requested_department)
    if normalized:
        department = normalized.value
    elif len(departments) == 1:
        department = next(iter(departments))
    else:
        await update.message.reply_text(
            "⚠️ Department লিখুন: Physio: Item -20 অথবা Dental: Item +5"
        )
        return INV_UPDATE
    allowed = {
        department_access.Department.PHYSIO.value,
        department_access.Department.DENTAL.value,
    }
    expanded_scope = set()
    for value in departments:
        normalized_scope = department_access.normalize_department(value)
        if normalized_scope is department_access.Department.ALL:
            expanded_scope.update(allowed)
        elif normalized_scope:
            expanded_scope.add(normalized_scope.value)
    if department not in expanded_scope:
        await update.message.reply_text("⛔ এই Department-এর inventory বদলানোর অনুমতি নেই।")
        return INV_UPDATE
    amount = float(amount_str)
    change = amount if sign == "+" else -amount
    result = await async_runtime.run_sheets_write(
        sheets.adjust_inventory_stock,
        item_name.strip(),
        change,
        reason="Manual",
        staff=staff.get("Full_Name", "Unknown"),
        department=department,
    )
    if not result.get("ok"):
        await update.message.reply_text(f"❌ {result.get('error')}")
        return INV_UPDATE
    message = (
        f"✅ {department} / {item_name.strip()} আপডেট হয়েছে। "
        f"নতুন স্টক: {result['new_balance']}"
    )
    if result.get("low_stock"):
        message += "\n⚠️ স্টক Minimum লেভেলের নিচে/সমান নেমে গেছে।"
    await update.message.reply_text(message)
    await update.message.reply_text(
        await async_runtime.run_sheets_read(_inventory_list_text, departments)
    )
    return INV_UPDATE



async def inventory_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    await update.message.reply_text(
        "ইনভেন্টরি মেনু থেকে বের হওয়া হলো।", reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


async def _treat_do_save(update, result_reply, menu_reply, context: ContextTypes.DEFAULT_TYPE, t: dict, selected: set):
    """Reauthorize the live patient immediately before saving a clinical note."""
    patient_id = t.get("Patient_ID", "")
    staff, patient = await _authorized_patient_action(
        update, context, patient_id,
        department_access.AccessAction.CLINICAL_WRITE,
        roles.MENU_TREATMENT_NOTE,
    )
    if not patient:
        context.user_data.pop("treatment", None)
        context.user_data.pop("treat_selected", None)
        await result_reply(
            "⛔ বর্তমান Department/Role অনুযায়ী ট্রিটমেন্ট নোট সেভ করা যাবে না।"
        )
        return ConversationHandler.END
    t["Patient_ID"] = patient.get("Patient_ID", "")
    t["Patient_Name"] = patient.get("Full_Name", "")
    t["Department"] = patient.get("Department", "")
    t["Machines"] = ", ".join(MACHINE_LIST[i] for i in sorted(selected))
    patient_id = t["Patient_ID"]
    try:
        treatment_id = await async_runtime.run_sheets_write(
            sheets.add_treatment_note,
            t,
            created_by=staff.get("Full_Name", "Unknown"),
        )
        await async_runtime.run_sheets_write(sheets.increment_plan_session, patient_id)
        await async_runtime.run_sheets_write(
            _apply_inventory_auto_deduct,
            t["Machines"],
            staff.get("Full_Name", "Unknown"),
            t["Department"],
        )
        await result_reply(
            f"✅ ট্রিটমেন্ট নোট সেভ হয়েছে! Treatment ID: {treatment_id}\n"
            f"সেশন: {t.get('Session_No', '?')}\n"
            f"মেশিন: {t['Machines'] or '(কিছু বাছাই করা হয়নি)'}"
        )
    except Exception as e:
        logger.exception("_treat_do_save ব্যর্থ হয়েছে")
        await result_reply(f"❌ সেভ করতে সমস্যা হয়েছে।\nError: {e}")
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_selected", None)
    context.user_data.pop("treat_ai_question", None)
    await menu_reply(
        "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(staff)
    )
    return ConversationHandler.END


async def treat_machine_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    t = context.user_data.get("treatment", {})
    selected = context.user_data.get("treat_selected", set())
    return await _treat_ask_patient_comment(query.edit_message_text, context, t, selected)


async def treat_machine_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_selected", None)
    await query.edit_message_text("❌ বাতিল করা হয়েছে।")
    await query.message.reply_text(
        "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(staff)
    )
    return ConversationHandler.END


async def treat_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_selected", None)
    context.user_data.pop("treat_search_results", None)
    await update.effective_message.reply_text(
        "ট্রিটমেন্ট নোট এন্ট্রি বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


# ---------- ট্রিটমেন্ট প্ল্যান (কোর্সের জন্য একবার লেখা হয়) ----------

def _category_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(assessment_defs.ASSESSMENT_CATEGORIES[k]["label"], callback_data=f"tpcat_{k}")]
        for k in assessment_defs.CATEGORY_ORDER
    ]
    return InlineKeyboardMarkup(buttons)


async def _assessment_advance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """assessment queue থেকে পরের টেস্ট পাঠায়; queue শেষ হলে সেভ করে পুরনো Diagnosis ধাপে চলে যায়।"""
    send = update.message.reply_text if update.message else update.callback_query.message.reply_text
    queue = context.user_data.get("assessment_queue", [])

    if not queue:
        t = context.user_data.get("tplan", {})
        category = context.user_data.get("assessment_category", "")
        answers = context.user_data.get("assessment_answers", {})
        staff = context.user_data.get("staff", {})
        try:
            await async_runtime.run_sheets_write(
                sheets.add_assessment,
                t.get("Patient_ID", ""), category, answers,
                created_by=staff.get("Full_Name", "Unknown"),
            )
        except Exception:
            logger.exception("_assessment_advance: assessment সেভ করতে ব্যর্থ হয়েছে")
        context.user_data["tplan_assessment_snapshot"] = {"category": category, "answers": dict(answers)}
        context.user_data.pop("assessment_queue", None)
        context.user_data.pop("assessment_current", None)
        context.user_data.pop("assessment_answers", None)
        context.user_data.pop("assessment_category", None)

        prev = context.user_data.get("tplan_prev", {})
        prev_diag = prev.get("Diagnosis", "")
        hint = f" (আগেরটা: {prev_diag} — একই রাখতে - দাও)" if prev_diag else ""
        await send(
            f"✅ প্রাথমিক মূল্যায়ন সম্পন্ন হয়েছে।\n\nসমস্যা/পর্যবেক্ষণ (Diagnosis) লেখো{hint}:",
            reply_markup=_skip_keyboard() if prev_diag else ReplyKeyboardRemove(),
        )
        return TPLAN_DIAGNOSIS

    test = queue.pop(0)
    context.user_data["assessment_queue"] = queue
    context.user_data["assessment_current"] = test
    info_row = [InlineKeyboardButton("ℹ️ নরমাল রেঞ্জ/টেকনিক", callback_data=f"ainfo_{test['key']}")] if test.get("info") else None
    if test["type"] == "buttons":
        buttons = [
            [InlineKeyboardButton(opt, callback_data=f"atest_{test['key']}__{opt}")]
            for opt in test["options"]
        ]
        if info_row:
            buttons.append(info_row)
        await send(test["label"], reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await send(test["label"], reply_markup=ReplyKeyboardRemove())
        if info_row:
            await send("চাইলে নিচে থেকে দেখো:", reply_markup=InlineKeyboardMarkup([info_row]))
    return TPLAN_TESTS


async def tplan_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Chief Complaint ক্যাটাগরি বাছাই করলে সেই category-র টেস্ট-queue তৈরি করে assessment শুরু করে।"""
    query = update.callback_query
    await query.answer()
    key = query.data.replace("tpcat_", "", 1)
    category = assessment_defs.ASSESSMENT_CATEGORIES.get(key)
    if not category:
        return TPLAN_CATEGORY
    context.user_data["assessment_category"] = key
    context.user_data["assessment_queue"] = list(category["tests"])
    context.user_data["assessment_answers"] = {}
    await query.edit_message_text(
        f"✅ ক্যাটাগরি বাছাই হয়েছে: {category['label']}\n\nপ্রাথমিক মূল্যায়ন শুরু হচ্ছে..."
    )
    return await _assessment_advance(update, context)


async def atest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """assessment-এর বাটন-ভিত্তিক টেস্টের উত্তর রেকর্ড করে পরের টেস্টে যায়।"""
    query = update.callback_query
    await query.answer()
    payload = query.data.replace("atest_", "", 1)
    key, _, value = payload.partition("__")
    current = context.user_data.get("assessment_current")
    if not current or current.get("key") != key:
        return TPLAN_TESTS
    answers = context.user_data.setdefault("assessment_answers", {})
    answers[key] = value
    await query.edit_message_text(f"{current['label']}\n➡️ {value}")
    return await _assessment_advance(update, context)


async def atest_text_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """assessment-এর টেক্সট-ভিত্তিক টেস্টের উত্তর রেকর্ড করে পরের টেস্টে যায়।"""
    current = context.user_data.get("assessment_current")
    if not current or current.get("type") != "text":
        return TPLAN_TESTS
    answers = context.user_data.setdefault("assessment_answers", {})
    answers[current["key"]] = update.message.text.strip()
    return await _assessment_advance(update, context)


async def atest_info_callback(update, context):
    """টেস্টের ইনফো বাটনে চাপলে popup-এ তথ্য দেখায়, state/queue অপরিবর্তিত থাকে।"""
    query = update.callback_query
    key = query.data.replace("ainfo_", "", 1)
    info = assessment_defs.TEST_INFO_BY_KEY.get(key, "এই টেস্টের জন্য তথ্য পাওয়া যায়নি।")
    await query.answer(text=info, show_alert=True)


async def tplan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_TREATMENT_PLAN):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["tplan"] = {}
    await update.message.reply_text(
        PATIENT_LOOKUP_PROMPT,
        reply_markup=ReplyKeyboardRemove(),
    )
    recent_kb = await async_runtime.run_sheets_read(
        _recent_patient_buttons, "tplansel_"
    )
    if recent_kb:
        await update.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return TPLAN_SEARCH


async def tplan_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    results = await _search_patients_for_request(update, context, query)
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
    patient = await _patient_by_id_for_request(update, context, patient_id)
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
    active = await async_runtime.run_sheets_read(
        sheets.get_active_plan_for_patient, patient_id
    )
    if active:
        warn = (
            f"⚠️ খেয়াল করো — এই রোগীর ইতিমধ্যে একটা Active প্ল্যান আছে "
            f"({active.get('Plan_ID')}, {active.get('Sessions_Done')}/{active.get('Total_Sessions')} সেশন)। "
            "নতুন প্ল্যান বানালে সেটা আলাদা হিসেবে যোগ হবে।\n\n"
        )

    last_plan = await async_runtime.run_sheets_read(
        sheets.get_last_plan_for_patient, patient_id
    )
    context.user_data["tplan_prev"] = last_plan or {}
    await query.edit_message_text(
        f"{warn}✅ রোগী বাছাই হলো: {patient.get('Full_Name')} ({patient_id})"
    )
    await query.message.reply_text(
        "Chief Complaint অনুযায়ী ক্যাটাগরি বাছাই করো — এর ভিত্তিতে প্রাথমিক মূল্যায়ন (assessment) নেওয়া হবে:",
        reply_markup=_category_keyboard(),
    )
    return TPLAN_CATEGORY


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
    await update.message.reply_text(
        "চাইলে প্রথমে AI-এর সাজেশন দেখে নিতে পারো:",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🤖 AI সাজেশন দেখো", callback_data="tplan_ai_suggest")]]
        ),
    )
    return TPLAN_EXERCISE


def _build_tplan_case_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Diagnosis + assessment answers একত্র করে AI Clinical Assistant-কে দেওয়ার জন্য একটা
    সংক্ষিপ্ত case description বানায়।"""
    t = context.user_data.get("tplan", {})
    snap = context.user_data.get("tplan_assessment_snapshot", {})
    lines = [f"Diagnosis/Chief Complaint: {t.get('Diagnosis', '')}"]
    category = snap.get("category", "")
    if category:
        lines.append(f"Assessment Category: {category}")
    for k, v in snap.get("answers", {}).items():
        if v:
            lines.append(f"{k}: {v}")
    return "\n".join(lines)


async def tplan_ai_suggest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(STATUS_CLINICAL_ANALYSIS)
    case_text = _build_tplan_case_text(context)
    answer, matched_summary = await async_runtime.run_ai(
        clinical_ai.get_clinical_guidance,
        case_text,
    )
    prefix = f"📖 প্রাসঙ্গিক condition: {matched_summary}\n\n" if matched_summary else ""
    await query.message.reply_text(
        prefix + answer + "\n\n(এখান থেকে দরকারি অংশ copy করে Exercise/Electrotherapy/Manual Therapy "
        "ধাপে বসাতে পারো — এখন Exercise Plan লেখো।)"
    )


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
    cached = context.user_data.get("tplan", {})
    patient_id = str(cached.get("Patient_ID", "")).strip()

    staff, patient = await _authorized_patient_action(
        update,
        context,
        patient_id,
        department_access.AccessAction.CLINICAL_WRITE,
        roles.MENU_TREATMENT_PLAN,
    )
    if staff is None or patient is None:
        context.user_data.pop("tplan", None)
        await update.effective_message.reply_text(
            "⛔ এই রোগীর treatment plan save করার বর্তমান অনুমতি নেই।"
        )
        return ConversationHandler.END

    if text not in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        context.user_data.pop("tplan", None)
        context.user_data.pop("tplan_prev", None)
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।", reply_markup=_menu_keyboard(staff)
        )
        return ConversationHandler.END

    cached["Department"] = patient.get("Department", "")
    try:
        plan_id = await async_runtime.run_sheets_write(
            sheets.add_treatment_plan,
            cached,
            created_by=staff.get("Full_Name", "Unknown"),
        )
        await update.message.reply_text(
            f"✅ ট্রিটমেন্ট প্ল্যান সেভ হয়েছে! Plan ID: {plan_id}\n"
            "এখন থেকে 📝 ট্রিটমেন্ট নোট-এ এই রোগীর দৈনিক এন্ট্রি এই প্ল্যান থেকে অটো-ফিল হবে।",
            reply_markup=_menu_keyboard(staff),
        )
    except Exception:
        logger.exception("tplan_confirm ব্যর্থ হয়েছে")
        await update.message.reply_text(
            "❌ প্ল্যান সেভ করা যায়নি। আবার চেষ্টা করো; একই সমস্যা হলে Admin-কে জানাও।",
            reply_markup=_menu_keyboard(staff),
        )
    context.user_data.pop("tplan", None)
    context.user_data.pop("tplan_prev", None)
    context.user_data.pop("tplan_assessment_snapshot", None)
    return ConversationHandler.END


async def tplan_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("tplan", None)
    context.user_data.pop("tplan_prev", None)
    context.user_data.pop("tplan_search_results", None)
    await update.effective_message.reply_text(
        "ট্রিটমেন্ট প্ল্যান বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


def _register_amount_keyboard(sessions: int) -> InlineKeyboardMarkup:
    # চক্র: ১ → ২ → ০ (শুধু টাকা, সেশন নেই) → আবার ১
    if sessions == 1:
        sess_label = "🔁 ২ সেশন হয়েছে"
    elif sessions == 2:
        sess_label = "❌ সেশন হয়নি (শুধু টাকা)"
    else:
        sess_label = "🔁 ১ সেশনে ফেরত যাও"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(sess_label, callback_data="regsesstoggle")],
        [
            InlineKeyboardButton("৳400", callback_data="regamt_400"),
            InlineKeyboardButton("✏️ অন্য পরিমাণ", callback_data="regamt_custom"),
        ],
    ])


def _register_amount_prompt_text(patient_name: str, patient_id: str, sessions: int) -> str:
    sess_line = "সেশন: হয়নি (শুধু টাকা জমা)" if sessions == 0 else f"সেশন: {sessions}"
    return (
        f"রোগী: {patient_name} ({patient_id})\n"
        f"{sess_line}  (ডিফল্ট ১, টগল করতে উপরের বাটনে চাপো — ১→২→সেশন নেই)\n\n"
        "কত টাকা নেওয়া হলো?"
    )


def _register_view_text_and_keyboard(departments=()):
    reg = sheets.get_daily_register(departments=departments)
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
    staff = await _require_staff(update, context)
    if staff is None:
        return
    if not _staff_can_access_menu(staff, roles.MENU_DAILY_REGISTER):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    text, keyboard = await async_runtime.run_sheets_read(
        _register_view_text_and_keyboard, _report_departments(staff)
    )
    await update.message.reply_text(text, reply_markup=keyboard)


async def reg_new_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    context.user_data["payment"] = {}
    await query.message.reply_text(PATIENT_LOOKUP_PROMPT)
    recent_kb = await async_runtime.run_sheets_read(
        _recent_patient_buttons, "paysel_"
    )
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
    current = p.get("Sessions", 1)
    cycle = {1: 2, 2: 0, 0: 1}
    sessions = cycle.get(current, 1)
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


def _month_bounds(now):
    """(this_month_str, last_month_str) রিটার্ন করে — বছর পরিবর্তনসহ ঠিকমতো হ্যান্ডল করে।"""
    this_month_str = now.strftime("%Y-%m")
    if now.month == 1:
        last_month_dt = now.replace(year=now.year - 1, month=12, day=1)
    else:
        last_month_dt = now.replace(month=now.month - 1, day=1)
    last_month_str = last_month_dt.strftime("%Y-%m")
    return this_month_str, last_month_str


def _report_departments(staff: dict) -> frozenset[str]:
    """Return the current explicit report scope loaded by _require_staff."""
    assignments = staff.get("_Department_Role_Assignments", ())
    return frozenset(assignment.department.value for assignment in assignments)


def _reports_summary_keyboard(staff: dict) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("\U0001F465 মোট রোগী ও সর্বমোট আদায়", callback_data="rpt_totals")],
        [InlineKeyboardButton("\U0001F4B0 গত মাসের আদায়", callback_data="rpt_lastmonth")],
        [InlineKeyboardButton("\U0001F4C5 তারিখ ভিত্তিক রিপোর্ট", callback_data="rpt_daterep")],
    ]
    extras = roles.get_items_for_roles(
        roles.ROLE_REPORTS_EXTRA_ITEMS, _effective_role_strings(staff)
    )
    if roles.MENU_DAILY_REGISTER in extras:
        rows.append([InlineKeyboardButton("\U0001F4CB আজকের রেজিস্টার", callback_data="rpt_todayregister")])
    return InlineKeyboardMarkup(rows)


async def reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    if not _staff_can_access_menu(staff, roles.MENU_REPORTS):
        await update.effective_message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    departments = _report_departments(staff)
    now = bd_now()
    today_str = now.strftime("%Y-%m-%d")
    this_month_str, _ = _month_bounds(now)

    report_data = await async_runtime.run_sheets_read(
        sheets.get_scoped_report_records, departments
    )
    patients = report_data[config.SHEET_PATIENTS]
    payments = report_data[config.SHEET_PAYMENTS]
    today_new_patients = sum(
        1 for p in patients
        if str(p.get("Registration_Date", "")).strip() == today_str
    )
    this_month_patients = sum(
        1 for p in patients
        if str(p.get("Registration_Date", "")).strip().startswith(this_month_str)
    )
    today_payments = [
        p for p in payments if str(p.get("Date", "")).strip() == today_str
    ]
    today_collection = sum(_sheet_amount_value(p.get("Amount", 0) or 0) for p in today_payments)
    this_month_payments = [
        p for p in payments
        if str(p.get("Date", "")).strip().startswith(this_month_str)
    ]
    this_month_collection = sum(_sheet_amount_value(p.get("Amount", 0) or 0) for p in this_month_payments)

    lines = [
        "\U0001F4CA রিপোর্ট ও অ্যানালিটিক্স", "",
        f"\U0001F195 আজকের নতুন রোগী: {today_new_patients}",
        f"\U0001F4C8 এই মাসের ({this_month_str}) নতুন রোগী: {this_month_patients}",
        f"\U0001F4B0 আজকের আদায়: {today_collection:.0f} টাকা",
        f"\U0001F4B0 এই মাসের ({this_month_str}) আদায়: {this_month_collection:.0f} টাকা",
        "", "\U0001F447 আরও বিস্তারিত দেখতে নিচের বাটন চাপো:",
    ]
    await update.effective_message.reply_text(
        "\n".join(lines), reply_markup=_reports_summary_keyboard(staff)
    )
    await update.effective_message.reply_text(
        "মেনুতে ফিরতে নিচের কীবোর্ড ব্যবহার করো:",
        reply_markup=_menu_keyboard(staff),
    )


async def rpt_totals_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(staff, roles.MENU_REPORTS):
        await query.message.reply_text("⛔ এই রিপোর্ট দেখার অনুমতি তোমার নেই।")
        return
    report_data = await async_runtime.run_sheets_read(
        sheets.get_scoped_report_records, _report_departments(staff)
    )
    patients = report_data[config.SHEET_PATIENTS]
    payments = report_data[config.SHEET_PAYMENTS]
    total_collection = sum(_sheet_amount_value(p.get("Amount", 0) or 0) for p in payments)
    await query.message.reply_text(
        "\U0001F465 মোট রোগী ও সর্বমোট আদায়\n\n"
        f"\U0001F465 মোট রোগী (সর্বমোট): {len(patients)}\n"
        f"\U0001F4B0 সর্বমোট আদায়: {total_collection:.0f} টাকা"
    )


async def rpt_lastmonth_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(staff, roles.MENU_REPORTS):
        await query.message.reply_text("⛔ এই রিপোর্ট দেখার অনুমতি তোমার নেই।")
        return
    _, last_month_str = _month_bounds(bd_now())
    report_data = await async_runtime.run_sheets_read(
        sheets.get_scoped_report_records, _report_departments(staff)
    )
    payments = [
        p for p in report_data[config.SHEET_PAYMENTS]
        if str(p.get("Date", "")).strip().startswith(last_month_str)
    ]
    amount = sum(_sheet_amount_value(p.get("Amount", 0) or 0) for p in payments)
    await query.message.reply_text(
        f"\U0001F4B0 গত মাসের ({last_month_str}) আদায়: {amount:.0f} টাকা"
    )


async def rpt_daterep_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(staff, roles.MENU_REPORTS):
        await query.message.reply_text("⛔ এই রিপোর্ট দেখার অনুমতি তোমার নেই।")
        return
    today = bd_now().date()
    await query.message.reply_text(
        "\U0001F4C5 তারিখ সিলেক্ট করুন:",
        reply_markup=calendar_helper.build_calendar(today.year, today.month),
    )


async def rpt_todayregister_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    extras = roles.get_items_for_roles(
        roles.ROLE_REPORTS_EXTRA_ITEMS,
        _effective_role_strings(staff or {}),
    )
    if staff is None or roles.MENU_DAILY_REGISTER not in extras:
        await query.message.reply_text("⛔ আজকের রেজিস্টার দেখার অনুমতি তোমার নেই।")
        return
    text, keyboard = await async_runtime.run_sheets_read(
        _register_view_text_and_keyboard, _report_departments(staff)
    )
    await query.message.reply_text(text, reply_markup=keyboard)


async def _authorized_treatment_history_patient(update, context, patient_id: str):
    staff, patient = await _authorized_patient_action(
        update, context, patient_id,
        department_access.AccessAction.CLINICAL_READ,
        roles.MENU_TREATMENT_HISTORY,
    )
    return patient


async def thist_progress_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """রোগীর Pain Score ট্র্যাকিং — সময়ের সাথে ব্যথা কমছে না বাড়ছে তা লিস্ট + বার-চার্ট আকারে দেখায়।"""
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("thistprog_", "", 1)
    if not await _authorized_treatment_history_patient(
        update, context, patient_id
    ):
        await query.message.reply_text("⛔ এই ট্রিটমেন্ট হিস্ট্রি দেখার অনুমতি নেই।")
        return
    notes = await async_runtime.run_sheets_read(
        sheets.get_treatment_notes_for_patient, patient_id
    )
    scored = [n for n in notes if str(n.get("Pain", "")).strip() != ""]
    if not scored:
        await query.message.reply_text(
            "📈 এই রোগীর জন্য এখনো কোনো Pain Score রেকর্ড করা হয়নি।\n\n"
            "প্রতি ৩-৭ দিনে ট্রিটমেন্ট নোট সেভ করার সময় বট নিজে থেকেই Pain Score জিজ্ঞেস করবে।"
        )
        return
    scored.sort(key=lambda n: str(n.get("Date", "")))
    lines = [f"📈 {scored[0].get('Patient_Name', '')} ({patient_id}) — Pain Score ট্রেন্ড\n"]
    for n in scored:
        lines.append(f"{n.get('Date', '')}  {_pain_bar(n.get('Pain', ''))}  {n.get('Pain', '')}/10")
    try:
        diff = int(float(scored[0].get("Pain", ""))) - int(float(scored[-1].get("Pain", "")))
        if diff > 0:
            trend = f"✅ শুরু থেকে এখন পর্যন্ত ব্যথা {diff} পয়েন্ট কমেছে।"
        elif diff < 0:
            trend = f"⚠️ শুরু থেকে এখন পর্যন্ত ব্যথা {abs(diff)} পয়েন্ট বেড়েছে।"
        else:
            trend = "➖ শুরু থেকে এখন পর্যন্ত ব্যথার স্কোর একই আছে।"
        lines.append("\n" + trend)
    except (TypeError, ValueError):
        pass
    await query.message.reply_text("\n".join(lines))


async def thist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_TREATMENT_HISTORY):
        return ConversationHandler.END
    await update.effective_message.reply_text(PATIENT_LOOKUP_PROMPT)
    return "THIST_SEARCH"


async def thist_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    results = await _search_patients_for_request(update, context, query_text)
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
    if not await _patient_by_id_for_request(update, context, patient_id):
        await query.edit_message_text("⛔ এই রোগী দেখার অনুমতি নেই।")
        return ConversationHandler.END
    notes = await async_runtime.run_sheets_read(
        sheets.get_treatment_notes_for_patient, patient_id
    )
    if not notes:
        await query.edit_message_text("এই রোগীর কোনো ট্রিটমেন্ট নোট পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["thist_notes"] = {
        str(n.get("Treatment_ID", "")).strip(): n for n in notes
    }
    # সেশন ১→২→৩... নেভিগেশনের জন্য তারিখ অনুযায়ী বাড়ন্ত ক্রমে সাজানো (patch33)
    notes_asc = sorted(notes, key=lambda n: str(n.get("Date", "")))
    context.user_data["thist_notes_order"] = [
        str(n.get("Treatment_ID", "")).strip() for n in notes_asc
    ]
    notes_sorted = sorted(notes, key=lambda n: str(n.get("Date", "")), reverse=True)
    buttons = []
    for n in notes_sorted[:15]:
        tid = str(n.get("Treatment_ID", "")).strip()
        date_str = n.get("Date", "")
        buttons.append([InlineKeyboardButton(f"🗓 {date_str} — {tid}", callback_data=f"thdate_{tid}")])
    buttons.append([InlineKeyboardButton("📈 প্রোগ্রেস দেখো", callback_data=f"thistprog_{patient_id}")])
    await query.edit_message_text(
        "কোন তারিখের ট্রিটমেন্ট প্ল্যান দেখতে চাও?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return "THIST_DATE"

async def _thist_render_note(query, context: ContextTypes.DEFAULT_TYPE, tid: str):
    """একটা নির্দিষ্ট ট্রিটমেন্ট নোট দেখায়, সাথে সেশন ⬅️আগের/পরের➡️ নেভিগেশন বাটন (patch33)।"""
    notes_map = context.user_data.get("thist_notes", {})
    order = context.user_data.get("thist_notes_order", [])
    n = notes_map.get(tid)
    if not n:
        await query.edit_message_text("নোট পাওয়া যায়নি।")
        return
    idx = order.index(tid) if tid in order else -1
    lines = [
        f"📝 {n.get('Patient_Name', '')} ({n.get('Patient_ID', '')}) — {n.get('Date', '')}",
    ]
    if idx != -1:
        lines.append(f"সেশন {idx + 1}/{len(order)}")
    lines += [
        "",
        f"Diagnosis: {n.get('Diagnosis', '') or '-'}",
        f"Treatment Given: {n.get('Treatment_Given', '') or '-'}",
        f"Exercise: {n.get('Exercise', '') or '-'}",
        f"Electrotherapy: {n.get('Electrotherapy', '') or '-'}",
        f"Manual Therapy: {n.get('Manual_Therapy', '') or '-'}",
        f"Machines: {n.get('Machines', '') or '-'}",
    ]
    patient_id = str(n.get("Patient_ID", "")).strip()

    nav_row = []
    if idx > 0:
        nav_row.append(InlineKeyboardButton("⬅️ আগের সেশন", callback_data=f"thnav_{idx - 1}"))
    if idx != -1 and idx < len(order) - 1:
        nav_row.append(InlineKeyboardButton("পরের সেশন ➡️", callback_data=f"thnav_{idx + 1}"))

    buttons = [nav_row] if nav_row else []
    if patient_id:
        card_kb = _patient_card_keyboard(
            patient_id,
            context.user_data.get("staff", {}),
            back_callback_data=f"thistback_{patient_id}",
            back_label="🔙 তারিখের তালিকায় ফিরুন",
        )
        buttons += card_kb.inline_keyboard
        await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))
    else:
        markup = InlineKeyboardMarkup(buttons) if buttons else None
        await query.edit_message_text("\n".join(lines), reply_markup=markup)


async def thist_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tid = query.data.replace("thdate_", "", 1)
    note = context.user_data.get("thist_notes", {}).get(tid, {})
    if not await _authorized_treatment_history_patient(
        update, context, str(note.get("Patient_ID", "")).strip()
    ):
        await query.edit_message_text("⛔ এই ট্রিটমেন্ট হিস্ট্রি দেখার অনুমতি নেই।")
        return ConversationHandler.END
    await _thist_render_note(query, context, tid)
    return ConversationHandler.END


async def thist_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⬅️ আগের সেশন / পরের সেশন ➡️ বাটন হ্যান্ডেল করে (patch33)।"""
    query = update.callback_query
    order = context.user_data.get("thist_notes_order", [])
    idx = int(query.data.replace("thnav_", "", 1))
    if idx < 0 or idx >= len(order):
        await query.answer("আর কোনো সেশন নেই।", show_alert=True)
        return
    await query.answer()
    tid = order[idx]
    note = context.user_data.get("thist_notes", {}).get(tid, {})
    if not await _authorized_treatment_history_patient(
        update, context, str(note.get("Patient_ID", "")).strip()
    ):
        await query.edit_message_text("⛔ এই ট্রিটমেন্ট হিস্ট্রি দেখার অনুমতি নেই।")
        return
    await _thist_render_note(query, context, tid)


async def thist_back_to_dates_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Treatment History নোট কার্ড থেকে '🔙 তারিখের তালিকায় ফিরুন' চাপলে এই রোগীর
    তারিখ-ভিত্তিক ট্রিটমেন্ট নোট তালিকা আবার দেখায়।"""
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("thistback_", "", 1)
    if not await _authorized_treatment_history_patient(
        update, context, patient_id
    ):
        await query.edit_message_text("⛔ এই ট্রিটমেন্ট হিস্ট্রি দেখার অনুমতি নেই।")
        return
    notes = await async_runtime.run_sheets_read(
        sheets.get_treatment_notes_for_patient, patient_id
    )
    if not notes:
        await query.edit_message_text("এই রোগীর কোনো ট্রিটমেন্ট নোট পাওয়া যায়নি।")
        return
    context.user_data["thist_notes"] = {
        str(n.get("Treatment_ID", "")).strip(): n for n in notes
    }
    notes_asc = sorted(notes, key=lambda n: str(n.get("Date", "")))
    context.user_data["thist_notes_order"] = [
        str(n.get("Treatment_ID", "")).strip() for n in notes_asc
    ]
    notes_sorted = sorted(notes, key=lambda n: str(n.get("Date", "")), reverse=True)
    buttons = []
    for n in notes_sorted[:15]:
        tid = str(n.get("Treatment_ID", "")).strip()
        date_str = n.get("Date", "")
        buttons.append([InlineKeyboardButton(f"🗓 {date_str} — {tid}", callback_data=f"thdate_{tid}")])
    buttons.append([InlineKeyboardButton("📈 প্রোগ্রেস দেখো", callback_data=f"thistprog_{patient_id}")])
    await query.edit_message_text(
        "কোন তারিখের ট্রিটমেন্ট প্ল্যান দেখতে চাও?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

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
            amount = _sheet_amount_value(p.get("Amount", 0) or 0)
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
            note_text = t.get("Note", "") or t.get("Notes", "") or t.get("Treatment_Given", "") or t.get("Remarks", "")
            lines.append(f"  • {date_str}: {note_text}")
    else:
        lines.append("📝 কোনো ট্রিটমেন্ট নোট নেই।")

    full_text = "\n".join(lines)
    if len(full_text) > 4000:
        full_text = full_text[:3990] + "\n...(আরও আছে)"
    return full_text


async def hist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_PATIENT_HISTORY):
        return ConversationHandler.END
    await update.effective_message.reply_text(PATIENT_LOOKUP_PROMPT)
    return "HIST_SEARCH"


async def hist_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    results = await _search_patients_for_request(update, context, query_text)
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
    if not await _patient_by_id_for_request(update, context, patient_id):
        await query.edit_message_text("⛔ এই রোগী দেখার অনুমতি নেই।")
        return ConversationHandler.END

    full_text = await async_runtime.run_sheets_read(
        _build_full_history_text, patient_id
    )
    if full_text is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return ConversationHandler.END

    await query.edit_message_text(full_text, reply_markup=_patient_card_keyboard(patient_id))
    return ConversationHandler.END


async def hist_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    await update.effective_message.reply_text(
        "বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


async def unknown_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    text = (update.message.text or "").strip()
    allowed_items = roles.get_menu_for_roles(_effective_role_strings(staff))
    suggested = None
    if text:
        try:
            suggested = intent_router.classify_menu_intent(text, allowed_items)
        except Exception as e:
            logger.warning(f"intent_router ব্যর্থ হয়েছে: {e}")
            suggested = None

    if suggested:
        suggest_kb = ReplyKeyboardMarkup([[suggested]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            f"মনে হচ্ছে তুমি এটা করতে চাও 👇\nনিচের বাটনে ট্যাপ করো, অথবা মূল মেনুতে ফিরতে {roles.MENU_BACK_MAIN} চাপো।",
            reply_markup=suggest_kb,
        )
        return

    await update.message.reply_text(
        "এই সুবিধাটি এখনো সক্রিয় করা হয়নি।",
        reply_markup=_menu_keyboard(staff),
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


def _therapist_patient_action_keyboard(patient_id: str) -> InlineKeyboardMarkup:
    """থেরাপিস্ট ড্যাশবোর্ড থেকে History দেখার পর — পেমেন্ট বাদে বাকি অ্যাকশন বাটন।"""
    buttons = [
        [
            InlineKeyboardButton("📅 অ্যাপয়েন্টমেন্ট", callback_data=f"plistact_apt_{patient_id}"),
            InlineKeyboardButton("📝 ট্রিটমেন্ট নোট", callback_data=f"plistact_treat_{patient_id}"),
        ],
        [InlineKeyboardButton("📎 রিপোর্ট", callback_data=f"plistact_report_{patient_id}")],
        [InlineKeyboardButton("👁️ ফাইল দেখুন", callback_data=f"plistact_viewfiles_{patient_id}")],
        [InlineKeyboardButton("🔄 Dashboard-এ ফিরুন", callback_data="ptdash_refresh")],
    ]
    return InlineKeyboardMarkup(buttons)


def _patient_card_keyboard(
    patient_id: str,
    staff: dict | None = None,
    back_callback_data: str = "plistact_back",
    back_label: str = "🔙 তালিকায় ফিরুন",
) -> InlineKeyboardMarkup:
    """Build actions from current effective roles; handlers still reauthorize."""
    buttons = []
    top = []
    if staff and _staff_can_access_menu(staff, roles.MENU_PAYMENT):
        top.append(InlineKeyboardButton(
            "💰 পেমেন্ট নিন", callback_data=f"plistact_pay_{patient_id}"
        ))
    if staff and _staff_can_access_menu(staff, roles.MENU_APPOINTMENT):
        top.append(InlineKeyboardButton(
            "📅 অ্যাপয়েন্টমেন্ট", callback_data=f"plistact_apt_{patient_id}"
        ))
    if top:
        buttons.append(top)
    clinical = []
    if staff and _staff_can_access_menu(staff, roles.MENU_TREATMENT_NOTE):
        clinical.append(InlineKeyboardButton(
            "📝 ট্রিটমেন্ট নোট", callback_data=f"plistact_treat_{patient_id}"
        ))
    clinical.append(InlineKeyboardButton(
        "📜 সম্পূর্ণ ইতিহাস", callback_data=f"plistact_hist_{patient_id}"
    ))
    buttons.append(clinical)
    clinical_roles = {"Owner", "Manager", "Therapist", "Dentist"}
    if staff and clinical_roles.intersection(_effective_role_strings(staff)):
        buttons.append([InlineKeyboardButton(
            "📎 রিপোর্ট", callback_data=f"plistact_report_{patient_id}"
        )])
    buttons.append([InlineKeyboardButton(
        "👁️ ফাইল দেখুন", callback_data=f"plistact_viewfiles_{patient_id}"
    )])
    buttons.append([InlineKeyboardButton(back_label, callback_data=back_callback_data)])
    return InlineKeyboardMarkup(buttons)


async def patient_list_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_PATIENT_LIST):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    all_patients = await async_runtime.run_sheets_read(sheets.get_all_patients)
    all_patients = await _visible_patients_for_request(
        update, context, all_patients
    )
    patients = [
        p for p in all_patients
        if str(p.get("Status", "")).strip() == "Active"
    ]
    patients.sort(key=lambda p: p.get("Full_Name", ""))
    if not patients:
        await update.message.reply_text("কোনো সক্রিয় রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["plist_patients"] = {
        p.get("Patient_ID", "").strip(): p for p in patients
    }
    await _send_patient_list_page(update.message, context, page=0)
    return "PLIST_BROWSE"


async def patient_list_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """📋 রোগীর তালিকায় নাম/ফোন/আইডি টাইপ করলে এই হ্যান্ডলার ফিল্টার করা রেজাল্ট দেখায়
    (patch29) — আগে/পরের বাটনও কাজ করে, আবার সরাসরি টাইপ করেও খোঁজা যায়।"""
    query_text = update.message.text.strip()
    results = await _search_patients_for_request(update, context, query_text)
    results = [
        p for p in results
        if str(p.get("Status", "")).strip() == "Active"
    ]
    if not results:
        await update.message.reply_text(
            "❌ কোনো রোগী পাওয়া যায়নি। আবার নাম/ফোন/আইডি লেখো, অথবা নিচে স্ক্রল করো।"
        )
        return "PLIST_BROWSE"
    results.sort(key=lambda p: p.get("Full_Name", ""))
    context.user_data["plist_patients"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    await _send_patient_list_page(update.message, context, page=0)
    return "PLIST_BROWSE"


async def patient_list_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    await update.effective_message.reply_text(
        "❌ বাতিল করা হলো।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


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
    text = (
        f"📋 রোগীর তালিকা (পাতা {page + 1}) — রোগী নির্বাচন করুন, "
        "অথবা নাম/ফোন/আইডি লিখুন:"
    )
    markup = InlineKeyboardMarkup(buttons)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)


async def patient_list_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cached = list(context.user_data.get("plist_patients", {}).values())
    visible = await _visible_patients_for_request(update, context, cached)
    context.user_data["plist_patients"] = {
        p.get("Patient_ID", "").strip(): p for p in visible
    }
    page = int(query.data.replace("plistpage_", ""))
    await _send_patient_list_page(query.message, context, page=page, edit=True)


async def patient_list_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, patient_id, page = query.data.split("_", 2)
    patient = await _patient_by_id_for_request(
        update, context, patient_id
    )
    if not patient:
        await query.edit_message_text("❌ তালিকার মেয়াদ শেষ। আবার 📋 রোগীর তালিকা চাপো।")
        return
    context.user_data["plist_last_page"] = int(page)
    await query.edit_message_text(
        _patient_card_text(patient),
        reply_markup=_patient_card_keyboard(patient_id, context.user_data.get("staff", {})),
    )


async def patient_list_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not context.user_data.get("plist_patients"):
        # Action Panel অন্য ফ্লো (Present/History/Treatment History) থেকে এলে
        # plist_patients cache করা নাও থাকতে পারে — তখন এখানে বানিয়ে নেওয়া হয়,
        # যাতে "🔙 তালিকায় ফিরুন" কখনো খালি স্ক্রিন না দেখায়।
        all_patients = await async_runtime.run_sheets_read(sheets.get_all_patients)
        patients = [
            p for p in all_patients
            if str(p.get("Status", "")).strip() == "Active"
        ]
        patients.sort(key=lambda p: p.get("Full_Name", ""))
        context.user_data["plist_patients"] = {
            p.get("Patient_ID", "").strip(): p for p in patients
        }
    visible = await _visible_patients_for_request(
        update, context,
        list(context.user_data.get("plist_patients", {}).values()),
    )
    context.user_data["plist_patients"] = {
        p.get("Patient_ID", "").strip(): p for p in visible
    }
    page = context.user_data.get("plist_last_page", 0)
    await _send_patient_list_page(query.message, context, page=page, edit=True)


async def plist_action_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_pay_", "")
    staff, patient = await _authorized_patient_action(
        update, context, patient_id,
        department_access.AccessAction.WRITE,
        roles.MENU_PAYMENT,
    )
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
    staff, patient = await _authorized_patient_action(
        update, context, patient_id,
        department_access.AccessAction.WRITE,
        roles.MENU_APPOINTMENT,
    )
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
    staff, patient = await _authorized_patient_action(
        update, context, patient_id,
        department_access.AccessAction.CLINICAL_WRITE,
        roles.MENU_TREATMENT_NOTE,
    )
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END

    selected, summary = await _treat_prepare_for_patient(patient, context)
    if selected is None:
        await query.edit_message_text(summary)
        return ConversationHandler.END

    await query.edit_message_text(summary, reply_markup=_treat_confirm_keyboard(patient_id))
    return TREAT_CONFIRM_PLAN


async def plist_action_hist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_hist_", "")

    patient = await _patient_by_id_for_request(update, context, patient_id)
    if not patient:
        await query.edit_message_text("⛔ এই রোগী দেখার অনুমতি নেই।")
        return

    full_text = await async_runtime.run_sheets_read(
        _build_full_history_text, patient_id
    )
    if full_text is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return

    await query.edit_message_text(full_text, reply_markup=_patient_card_keyboard(patient_id))



REPORT_UPLOAD = "REPORT_UPLOAD"


async def plist_action_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_report_", "")
    staff, patient = await _authorized_patient_action(
        update, context, patient_id,
        department_access.AccessAction.CLINICAL_WRITE,
    )
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
    staff, patient = await _authorized_patient_action(
        update, context, rp.get("Patient_ID", ""),
        department_access.AccessAction.CLINICAL_WRITE,
    )
    if not patient:
        context.user_data.pop("report_patient", None)
        await update.message.reply_text("⛔ এই রোগীর রিপোর্টে প্রবেশাধিকার নেই।")
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
        report_id = await async_runtime.run_sheets_write(sheets.add_report, {
            "Patient_ID": patient.get("Patient_ID", ""),
            "Patient_Name": patient.get("Full_Name", ""),
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
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END



def _therapist_has_access_to_patient(therapist_name: str, patient: dict) -> bool:
    """
    Therapist-এর এই patient-এ অ্যাক্সেস আছে কিনা চেক করে।
    শুধু patient রেকর্ডের Therapist কলাম না দেখে, patient-এর
    appointment history-তেও এই therapist-এর নামে কোনো অ্যাপয়েন্টমেন্ট
    আছে কিনা দেখা হয়।
    """
    if roles.is_therapist_owner_of_patient(therapist_name, patient):
        return True
    patient_id = str(patient.get("Patient_ID", "")).strip()
    if not patient_id:
        return False
    therapist_name = therapist_name.strip()
    appts = sheets.get_appointments_for_patient(patient_id)
    return any(
        str(a.get("Therapist", "")).strip() == therapist_name
        for a in appts
    )


async def _staff_can_view_patient_files(staff: dict, patient: dict) -> bool:
    """Clinical reports are shared with every therapist plus Owner/Manager."""
    role = str(staff.get("Role", "")).strip()
    return role in ("Owner", "Manager", "Therapist")


_REPORT_FILES_PER_PAGE = 8


def _report_files_page(
    reports: list[dict], patient_id: str, page: int
) -> tuple[InlineKeyboardMarkup, int, int]:
    total_pages = max(1, (len(reports) + _REPORT_FILES_PER_PAGE - 1) // _REPORT_FILES_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    newest_first = list(reversed(reports))
    start = page * _REPORT_FILES_PER_PAGE
    chunk = newest_first[start:start + _REPORT_FILES_PER_PAGE]
    buttons = [
        [InlineKeyboardButton(
            f"{r.get('File_Type', 'ফাইল')} — {r.get('Upload_Date', '')}",
            callback_data=f"plistact_getfile_{r.get('Report_ID', '')}",
        )]
        for r in chunk
    ]
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(
            "⬅️ আগের", callback_data=f"plistfiles_{patient_id}_{page - 1}"
        ))
    if page + 1 < total_pages:
        navigation.append(InlineKeyboardButton(
            "পরের ➡️", callback_data=f"plistfiles_{patient_id}_{page + 1}"
        ))
    if navigation:
        buttons.append(navigation)
    buttons.append([InlineKeyboardButton("🔙 তালিকায় ফিরুন", callback_data="plistact_back")])
    return InlineKeyboardMarkup(buttons), page, total_pages


async def plist_action_viewfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_viewfiles_", "")
    staff = await _require_staff(update, context)
    if staff is None:
        return
    patient = await _patient_by_id_for_request(update, context, patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return
    allowed = await _staff_can_view_patient_files(staff, patient)
    if not allowed:
        await query.edit_message_text("⛔ এই রোগীর ফাইল দেখার অনুমতি তোমার নেই।")
        return
    reports = await async_runtime.run_sheets_read(
        sheets.get_reports_for_patient, patient_id
    )
    if not reports:
        await query.edit_message_text(f"📂 {patient.get('Full_Name')}-এর কোনো ফাইল এখনো আপলোড হয়নি।")
        return
    context.user_data.setdefault("plist_reports", {})[patient_id] = reports
    markup, page, total_pages = _report_files_page(reports, patient_id, 0)
    await query.edit_message_text(
        f"📂 {patient.get('Full_Name')}-এর ফাইল ({len(reports)}টি) — "
        f"পাতা {page + 1}/{total_pages}",
        reply_markup=markup,
    )


async def plist_report_files_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    payload = query.data.replace("plistfiles_", "", 1)
    patient_id, page_text = payload.rsplit("_", 1)
    page = int(page_text)
    staff = await _require_staff(update, context)
    if staff is None:
        return
    patient = await _patient_by_id_for_request(update, context, patient_id)
    if not patient or not await _staff_can_view_patient_files(staff, patient):
        await query.edit_message_text("⛔ এই রোগীর ফাইল দেখার অনুমতি তোমার নেই।")
        return
    reports = context.user_data.get("plist_reports", {}).get(patient_id)
    if reports is None:
        reports = await async_runtime.run_sheets_read(
            sheets.get_reports_for_patient, patient_id
        )
        context.user_data.setdefault("plist_reports", {})[patient_id] = reports
    if not reports:
        await query.edit_message_text("📂 কোনো ফাইল পাওয়া যায়নি।")
        return
    markup, page, total_pages = _report_files_page(reports, patient_id, page)
    patient_name = reports[-1].get("Patient_Name", patient_id)
    await query.edit_message_text(
        f"📂 {patient_name}-এর ফাইল ({len(reports)}টি) — পাতা {page + 1}/{total_pages}",
        reply_markup=markup,
    )


async def plist_action_getfile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    report_id = query.data.replace("plistact_getfile_", "")
    staff = await _require_staff(update, context)
    if staff is None:
        return
    record = await async_runtime.run_sheets_read(
        sheets.get_report_by_id, report_id
    )
    if not record:
        await query.message.reply_text("❌ ফাইল পাওয়া যায়নি।")
        return
    patient = await _patient_by_id_for_request(
        update, context, record.get("Patient_ID", "")
    )
    allowed = patient and await _staff_can_view_patient_files(staff, patient)
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
    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(staff, roles.MENU_REPORTS):
        await update.effective_message.reply_text("⛔ এই রিপোর্ট দেখার অনুমতি তোমার নেই।")
        return
    today = bd_now().date()
    await update.effective_message.reply_text(
        "📅 তারিখ সিলেক্ট করুন:",
        reply_markup=calendar_helper.build_calendar(today.year, today.month)
    )


async def date_report_calendar_navigate(update, context):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(staff, roles.MENU_REPORTS):
        await query.message.reply_text("⛔ এই রিপোর্ট দেখার অনুমতি তোমার নেই।")
        return
    year, month = map(int, query.data.split("_", 1)[1].split("-"))
    await query.edit_message_reply_markup(
        reply_markup=calendar_helper.build_calendar(year, month)
    )


async def date_report_day_selected(update, context):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(staff, roles.MENU_REPORTS):
        await query.message.reply_text("⛔ এই রিপোর্ট দেখার অনুমতি তোমার নেই।")
        return
    date_str = query.data.split("_", 1)[1]
    year, month, day = map(int, date_str.split("-"))
    patient_list = await async_runtime.run_sheets_read(
        sheets.get_daily_patient_list, date_str, _report_departments(staff)
    )
    if patient_list:
        list_lines = "\n".join(
            f"{i+1}. {p['name']} — {p['session']} — {p['amount']:.0f} টাকা"
            for i, p in enumerate(patient_list)
        )
        text = f"📋 {date_str} — রোগীর তালিকা:\n{list_lines}"
    else:
        text = f"📋 {date_str} — এই তারিখে কোনো রোগীর এন্ট্রি পাওয়া যায়নি।"
    await query.edit_message_text(
        text, reply_markup=calendar_helper.build_calendar(year, month)
    )


async def staffai_start(update, context):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_STAFF_AI_QUERY):
        return ConversationHandler.END
    await update.message.reply_text(
        "🤖 ক্লিনিক সম্পর্কে কী জানতে চান? সাধারণ ভাষায় লিখুন।\n\n"
        "উদাহরণ:\n"
        "• আজকে মোট কত টাকা জমা হয়েছে?\n"
        "• আজকে ফিজিও থেকে কত টাকা এসেছে?\n"
        "• এই মাসে মোট খরচ কত হয়েছে?\n"
        "• আজকে কতজন নতুন রোগী রেজিস্ট্রেশন করেছেন?\n"
        "• আজকে কতজন স্টাফ দেরিতে এসেছেন?\n\n"
        "বাতিল করতে /cancel লেখো।"
    )
    return STAFFAI_QUESTION


async def staffai_receive(update, context):
    staff = context.user_data.get("staff", {})
    question = update.message.text.strip()
    await update.message.reply_text(STATUS_BUSINESS_ANALYSIS)

    bot_api = context.bot
    chat_id = update.effective_chat.id
    role = staff.get("Role", "")

    async def deliver(answer):
        await bot_api.send_message(
            chat_id,
            answer,
            reply_markup=_menu_keyboard(staff),
        )

    async def deliver_error(reason):
        message = (
            "⏱️ তথ্য বিশ্লেষণের সময়সীমা শেষ হয়েছে। আবার চেষ্টা করুন।"
            if reason == "timeout"
            else "⚠️ এই মুহূর্তে তথ্য বিশ্লেষণ সম্পন্ন করা যায়নি। আবার চেষ্টা করুন।"
        )
        await bot_api.send_message(chat_id, message, reply_markup=_menu_keyboard(staff))

    context.application.create_task(async_runtime.run_ai_background(
        staff_ai_query.answer_staff_query,
        question,
        role=role,
        on_success=deliver,
        on_error=deliver_error,
    ))
    return ConversationHandler.END


async def staffai_cancel(update, context):
    staff = context.user_data.get("staff", {})
    await update.message.reply_text(
        "\u274c বাতিল করা হলো।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


async def clinicalai_start(update, context):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_CLINICAL_AI):
        return ConversationHandler.END
    await update.message.reply_text(
        "\U0001FA7A রোগীর presentation লেখো (উপসর্গ, history, যা যা দেখেছো/জেনেছো)।\n"
        "বাতিল করতে /cancel লেখো।"
    )
    return CLINICALAI_QUESTION


async def clinicalai_receive(update, context):
    staff = context.user_data.get("staff", {})
    case_text = update.message.text.strip()
    await update.message.reply_text(STATUS_CLINICAL_ANALYSIS)

    bot_api = context.bot
    chat_id = update.effective_chat.id
    role = staff.get("Role", "")

    async def deliver(result):
        answer, matched_summary = result
        prefix = f"📖 প্রাসঙ্গিক condition: {matched_summary}\n\n" if matched_summary else ""
        await bot_api.send_message(
            chat_id,
            prefix + answer,
            reply_markup=_menu_keyboard(staff),
        )

    async def deliver_error(reason):
        message = (
            "⏱️ ক্লিনিক্যাল বিশ্লেষণের সময়সীমা শেষ হয়েছে। আবার চেষ্টা করুন।"
            if reason == "timeout"
            else "⚠️ এই মুহূর্তে ক্লিনিক্যাল বিশ্লেষণ সম্পন্ন করা যায়নি। আবার চেষ্টা করুন।"
        )
        await bot_api.send_message(chat_id, message, reply_markup=_menu_keyboard(staff))

    context.application.create_task(async_runtime.run_ai_background(
        clinical_ai.get_clinical_guidance,
        case_text,
        on_success=deliver,
        on_error=deliver_error,
    ))
    return ConversationHandler.END


async def clinicalai_cancel(update, context):
    staff = context.user_data.get("staff", {})
    await update.message.reply_text(
        "\u274c বাতিল করা হলো।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


def _build_case_study_context(patient_id: str) -> str | None:
    """রোগীর Chief Complaint + Assessment + সাম্প্রতিক Treatment Note + Report লিস্ট
    একত্র করে Case Study AI-কে দেওয়ার জন্য একটা সংক্ষিপ্ত context বানায়।"""
    patient = sheets.get_patient_by_id(patient_id)
    if patient is None:
        return None

    name = patient.get("Full_Name") or patient.get("Name") or "Unknown"
    lines = [f"রোগী: {name} ({patient_id})"]

    problem = patient.get("Note") or patient.get("Notes") or patient.get("Problem", "")
    if problem:
        lines.append(f"প্রাথমিক সমস্যা/নোট: {problem}")

    assessments = sheets.get_assessments_for_patient(patient_id)
    if assessments:
        latest = assessments[0]
        category = latest.get("Category", "")
        test_data = latest.get("Test_Data", {}) or {}
        chief_complaint = test_data.get("ChiefComplaint", "")
        lines.append(f"\nAssessment Category: {category}")
        if chief_complaint:
            lines.append(f"Chief Complaint: {chief_complaint}")
        for k, v in test_data.items():
            if k == "ChiefComplaint" or not v:
                continue
            lines.append(f"  {k}: {v}")
    else:
        lines.append("\nকোনো Assessment রেকর্ড নেই।")

    treatment_notes = sheets.get_treatment_notes_for_patient(patient_id)
    if treatment_notes:
        lines.append("\nসাম্প্রতিক ট্রিটমেন্ট নোট:")
        for t in treatment_notes[-3:]:
            date_str = t.get("Date", "")
            note_text = t.get("Note", "") or t.get("Notes", "") or t.get("Treatment_Given", "") or t.get("Remarks", "")
            pain = str(t.get("Pain", "")).strip()
            pain_note = f" [Pain Score: {pain}/10]" if pain else ""
            if note_text or pain_note:
                lines.append(f"  • {date_str}: {note_text}{pain_note}")

    scored_notes = [t for t in treatment_notes if str(t.get("Pain", "")).strip() != ""]
    if len(scored_notes) >= 2:
        scored_notes_sorted = sorted(scored_notes, key=lambda t: str(t.get("Date", "")))
        first_n, last_n = scored_notes_sorted[0], scored_notes_sorted[-1]
        lines.append(
            f"\nPain Score Trend: {first_n.get('Pain', '')}/10 ({first_n.get('Date', '')}) "
            f"→ {last_n.get('Pain', '')}/10 ({last_n.get('Date', '')})"
        )

    reports = sheets.get_reports_for_patient(patient_id)
    if reports:
        lines.append("\nআপলোড করা রিপোর্ট/ফাইল:")
        for r in reports[-5:]:
            fname = r.get("File_Name", "")
            ftype = r.get("File_Type", "")
            if fname:
                lines.append(f"  • {fname} ({ftype})")

    full_text = "\n".join(lines)
    if len(full_text) > 3000:
        full_text = full_text[:2990] + "\n...(আরও আছে)"
    return full_text


def _cslesson_next_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("➡️ পরবর্তী Lesson", callback_data="cslesson_next")]]
    )


async def casestudy_start(update, context):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_CASE_STUDY):
        return ConversationHandler.END
    await update.message.reply_text(
        "\U0001F4DA কোন রোগীর কেস পড়াবে? নাম, ফোন নম্বর, অথবা Patient ID লেখো।\n"
        "বাতিল করতে /cancel লেখো।"
    )
    return CASESTUDY_SEARCH


async def casestudy_search_receive(update, context):
    query_text = update.message.text.strip()
    results = await _search_patients_for_request(update, context, query_text)
    if not results:
        await update.message.reply_text("কোনো রোগী পাওয়া যায়নি। আবার চেষ্টা করো, অথবা /cancel দাও।")
        return CASESTUDY_SEARCH
    results = results[:10]
    await update.message.reply_text(
        "কোন রোগীর কেস পড়াবে?",
        reply_markup=_patient_search_buttons(results, "cssel_", "cssearchback"),
    )
    return CASESTUDY_SEARCH


async def casestudy_select_callback(update, context):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("cssel_", "", 1)
    patient = await _patient_by_id_for_request(update, context, patient_id)
    if not patient:
        await query.edit_message_text("⛔ এই রোগী দেখার অনুমতি নেই।")
        return ConversationHandler.END

    case_context = await async_runtime.run_sheets_read(
        _build_case_study_context, patient_id
    )
    if case_context is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return ConversationHandler.END

    context.user_data["cs_case_context"] = case_context
    context.user_data["cs_patient_id"] = patient_id
    context.user_data["cs_patient_name"] = patient.get("Full_Name") or patient.get("Name") or ""
    context.user_data["cs_session_id"] = f"CS-{patient_id}-{int(time.time())}"
    await query.edit_message_text(
        "\u2705 রোগীর ডেটা লোড হয়েছে।\n"
        "কেসের বাড়তি কোনো তথ্য/অবজারভেশন থাকলে লেখো — X-ray/MRI রিপোর্টের লেখা/ফাইন্ডিংস থাকলে এখানেই টাইপ করে দাও (ছবি থেকে AI film ঠিকমতো পড়তে না পারলে টাইপ করে দেওয়াই সবচেয়ে নির্ভরযোগ্য), না থাকলে শুধু 'না' লিখো।"
    )
    return CASESTUDY_EXTRA


async def casestudy_search_cancel_callback(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("\u274c বাতিল করা হলো।")
    return ConversationHandler.END


def _extract_drive_file_id(drive_link: str) -> str:
    """Google Drive webViewLink থেকে raw file ID বের করে (যেমন
    https://drive.google.com/file/d/XXXX/view -> XXXX)।"""
    if not drive_link:
        return ""
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", drive_link)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", drive_link)
    if m:
        return m.group(1)
    return ""


async def _download_report_images(context, patient_id: str, limit: int = 4) -> list:
    """রোগীর সাম্প্রতিক ছবি-রিপোর্ট (X-ray/MRI ইত্যাদি) ডাউনলোড করে।
    আগে Google Drive থেকে চেষ্টা করে (স্থায়ী, প্রোডাকশনে reliable), Drive লিংক না থাকলে
    বা ফেইল করলে Telegram file_id দিয়ে ফলব্যাক করে। সর্বোচ্চ `limit` টা ছবি নেয়
    (ফ্রি ভিশন মডেলের রেট-লিমিট বাঁচাতে)।"""
    reports = await async_runtime.run_sheets_read(
        sheets.get_reports_for_patient, patient_id
    )
    image_reports = [r for r in reports if str(r.get("File_Type", "")).lower() in ("photo", "image") or str(r.get("File_Type", "")).lower().startswith("image")]
    image_reports = image_reports[-limit:]
    out = []
    for r in image_reports:
        img_bytes = None

        drive_link = r.get("File_Drive_Link", "")
        drive_file_id = _extract_drive_file_id(drive_link)
        if drive_file_id:
            img_bytes = drive_module.download_file_from_drive(drive_file_id)

        if img_bytes is None:
            file_id = r.get("File_Telegram_ID", "")
            if file_id:
                try:
                    file_obj = await context.bot.get_file(file_id)
                    file_bytes = await file_obj.download_as_bytearray()
                    img_bytes = bytes(file_bytes)
                except Exception:
                    img_bytes = None

        if img_bytes is None:
            continue

        b64 = base64.b64encode(img_bytes).decode("utf-8")
        out.append({
            "base64": b64,
            "mime_type": r.get("File_Type") or "image/jpeg",
            "file_name": r.get("File_Name", ""),
        })
    return out


async def casestudy_extra_receive(update, context):
    text = update.message.text.strip()
    case_context = context.user_data.get("cs_case_context", "")
    extra = "" if text in ("না", "না।", "no", "No", "No.") else text
    case_text = case_context + (f"\n\nবাড়তি তথ্য: {extra}" if extra else "")

    patient_id = context.user_data.get("cs_patient_id", "")
    images = await _download_report_images(context, patient_id, limit=4)
    if images:
        await update.message.reply_text("\U0001F50D রিপোর্টের ছবি দেখছি...")
        vision_notes = await async_runtime.run_ai(
            case_study_ai.analyze_report_images,
            images,
        )
        if vision_notes:
            case_text += f"\n\nরিপোর্ট ছবি বিশ্লেষণ (AI Vision):\n{vision_notes}"

    context.user_data["cs_case_text"] = case_text
    context.user_data["cs_lesson"] = 1
    await update.message.reply_text(
        "🧠 কেসের তথ্য বিশ্লেষণ করে Lesson 1 প্রস্তুত করছি…"
    )
    answer = await async_runtime.run_ai(
        case_study_ai.answer_case_lesson,
        case_text,
        1,
    )
    staff = context.user_data.get("staff", {})
    try:
        await async_runtime.run_sheets_write(
            sheets.add_case_study_lesson,
            context.user_data.get("cs_session_id", ""),
            context.user_data.get("cs_patient_id", ""),
            context.user_data.get("cs_patient_name", ""),
            1,
            case_study_ai.LESSON_TITLES[0],
            answer,
            staff.get("Full_Name") or staff.get("Name") or str(staff.get("Staff_ID", "")),
        )
    except Exception:
        pass
    await update.message.reply_text(answer, reply_markup=_cslesson_next_keyboard())
    return CASESTUDY_LESSON


async def casestudy_lesson_callback(update, context):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    case_text = context.user_data.get("cs_case_text", "")
    lesson = context.user_data.get("cs_lesson", 1)

    lesson += 1
    await query.message.reply_text(
        f"🧠 কেসের অগ্রগতি বিশ্লেষণ করে Lesson {lesson} প্রস্তুত করছি…"
    )
    answer = await async_runtime.run_ai(
        case_study_ai.answer_case_lesson,
        case_text,
        lesson,
    )
    context.user_data["cs_lesson"] = lesson
    try:
        await async_runtime.run_sheets_write(
            sheets.add_case_study_lesson,
            context.user_data.get("cs_session_id", ""),
            context.user_data.get("cs_patient_id", ""),
            context.user_data.get("cs_patient_name", ""),
            lesson,
            case_study_ai.LESSON_TITLES[lesson - 1],
            answer,
            staff.get("Full_Name") or staff.get("Name") or str(staff.get("Staff_ID", "")),
        )
    except Exception:
        pass

    if lesson >= len(case_study_ai.LESSON_TITLES):
        await query.message.reply_text(
            answer,
            reply_markup=_menu_keyboard(staff),
        )
        return ConversationHandler.END

    await query.message.reply_text(answer, reply_markup=_cslesson_next_keyboard())
    return CASESTUDY_LESSON




async def casestudy_cancel(update, context):
    staff = context.user_data.get("staff", {})
    await update.message.reply_text(
        "\u274c বাতিল করা হলো।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


async def salary_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_SALARY):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    staff_rows = await async_runtime.run_sheets_read(sheets.get_all_staff)
    all_staff = [s for s in staff_rows if s.get("Staff_ID")]
    if not all_staff:
        await update.message.reply_text("❌ কোনো স্টাফ পাওয়া যায়নি।")
        return ConversationHandler.END
    buttons = []
    for s in all_staff:
        name = s.get("Full_Name", "")
        role = s.get("Role", "")
        sid = s.get("Staff_ID")
        label = f"{name} ({role})"
        buttons.append([InlineKeyboardButton(label, callback_data=f"salsel_{sid}")])
    await update.message.reply_text("কোন স্টাফের বেতন দেবে?", reply_markup=InlineKeyboardMarkup(buttons))
    return SALARY_SELECT_STAFF


async def salary_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff_id = query.data.replace("salsel_", "", 1)
    month = bd_now().strftime("%Y-%m")
    summary = await async_runtime.run_sheets_read(
        sheets.get_salary_summary, staff_id, month
    )
    if not summary:
        await query.edit_message_text("❌ স্টাফ পাওয়া যায়নি।")
        return ConversationHandler.END

    name = summary["Full_Name"]
    monthly_salary = summary["Monthly_Salary"]
    paid = summary["Paid"]
    due = summary["Due"]

    if monthly_salary <= 0:
        await query.edit_message_text(
            f"⚠️ {name}-এর জন্য 08_Staff শীটে Salary সেট করা নেই। আগে সেটা ঠিক করো।"
        )
        return ConversationHandler.END
    if due <= 0:
        await query.edit_message_text(
            f"✅ {name}-এর এই মাসের ({month}) বেতন সম্পূর্ণ পরিশোধ হয়েছে।\n"
            f"বেতন: ৳{monthly_salary:.0f} | পরিশোধিত: ৳{paid:.0f}"
        )
        return ConversationHandler.END

    context.user_data["salary"] = {
        "Staff_ID": staff_id,
        "Full_Name": name,
        "Telegram_ID": summary["Telegram_ID"],
        "Month": month,
        "Monthly_Salary": monthly_salary,
        "Paid": paid,
        "Due": due,
    }
    await query.edit_message_text(
        f"👤 {name} — {month}\n"
        f"মোট বেতন: ৳{monthly_salary:.0f}\n"
        f"পরিশোধিত: ৳{paid:.0f}\n"
        f"বাকি: ৳{due:.0f}\n\n"
        "কত টাকা দিচ্ছো লেখো:"
    )
    return SALARY_ENTER_AMOUNT


async def salary_amount_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    s = context.user_data.get("salary", {})
    due = s.get("Due", 0)
    try:
        amount = float(text)
    except ValueError:
        await update.message.reply_text("❌ শুধু সংখ্যা লেখো (যেমন: 5000):")
        return SALARY_ENTER_AMOUNT
    if amount <= 0:
        await update.message.reply_text("❌ Amount অবশ্যই ০-এর বেশি হতে হবে:")
        return SALARY_ENTER_AMOUNT
    if amount > due:
        await update.message.reply_text(
            f"❌ বাকি আছে ৳{due:.0f}, কিন্তু তুমি ৳{amount:.0f} দিতে চাইছো। "
            "আবার লেখো (বাকির বেশি দেওয়া যাবে না):"
        )
        return SALARY_ENTER_AMOUNT
    s["Amount"] = amount
    context.user_data["salary"] = s
    await update.message.reply_text("কোনো নোট থাকলে লেখো, না থাকলে '-' দাও:")
    return SALARY_NOTE


async def salary_note_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    s = context.user_data.get("salary", {})
    s["Note"] = "" if text == "-" else text
    context.user_data["salary"] = s
    name = s.get("Full_Name", "")
    month = s.get("Month", "")
    amount = s.get("Amount", 0)
    note = s.get("Note") or "-"
    summary = (
        f"👤 {name} — {month}\n"
        f"পরিশোধ: ৳{amount:.0f}\n"
        f"নোট: {note}\n\n"
        "নিশ্চিত করো:"
    )
    confirm_keyboard = ReplyKeyboardMarkup([["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(summary, reply_markup=confirm_keyboard)
    return SALARY_CONFIRM


async def salary_confirm_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    cached = context.user_data.get("salary", {})

    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(staff, roles.MENU_SALARY):
        context.user_data.pop("salary", None)
        await update.effective_message.reply_text(
            "⛔ বেতন দেওয়ার বর্তমান অনুমতি নেই।"
        )
        return ConversationHandler.END

    if text not in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        context.user_data.pop("salary", None)
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।", reply_markup=_menu_keyboard(staff)
        )
        return ConversationHandler.END

    required = ("Staff_ID", "Month", "Amount")
    if any(not cached.get(key) for key in required):
        context.user_data.pop("salary", None)
        await update.message.reply_text(
            "⚠️ বেতনের অনুরোধটি পুরোনো বা অসম্পূর্ণ। নতুন করে শুরু করো।",
            reply_markup=_menu_keyboard(staff),
        )
        return ConversationHandler.END

    paid_by_name = (
        staff.get("Full_Name")
        or staff.get("Name")
        or str(staff.get("Staff_ID", ""))
    )
    amount = _sheet_amount_value(cached.get("Amount", 0))
    try:
        result = await async_runtime.run_sheets_write(
            sheets.add_salary_payment_checked,
            cached["Staff_ID"],
            cached["Month"],
            amount,
            paid_by=paid_by_name,
            note=cached.get("Note", ""),
        )
        if not result.get("ok"):
            due = _sheet_amount_value(result.get("due", 0))
            context.user_data.pop("salary", None)
            await update.message.reply_text(
                f"⚠️ বেতনের বর্তমান বাকি পরিবর্তিত হয়েছে (এখন ৳{due:.0f})। "
                "নতুন করে বেতন মেনু থেকে শুরু করো।",
                reply_markup=_menu_keyboard(staff),
            )
            return ConversationHandler.END

        payment_id = result["payment_id"]
        remaining_due = _sheet_amount_value(result.get("remaining_due", 0))
        await update.message.reply_text(
            f"✅ বেতন কিস্তি সেভ হয়েছে! Payment ID: {payment_id}\n"
            f"এই মাসের বাকি: ৳{remaining_due:.0f}",
            reply_markup=_menu_keyboard(staff),
        )

        staff_telegram_id = cached.get("Telegram_ID")
        if staff_telegram_id:
            try:
                await context.bot.send_message(
                    chat_id=int(staff_telegram_id),
                    text=(
                        "💰 আপনার বেতনের কিস্তি প্রদান করা হয়েছে।\n"
                        f"এই কিস্তি: ৳{amount:.0f}\n"
                        f"এই মাসের বাকি: ৳{remaining_due:.0f}\n"
                        "ধন্যবাদ।"
                    ),
                )
            except Exception:
                logger.exception(
                    "salary_confirm_receive: staff notification failed"
                )
    except Exception:
        logger.exception("salary_confirm_receive failed")
        await update.message.reply_text(
            "❌ বেতন সেভ করা যায়নি। আবার চেষ্টা করো; একই সমস্যা হলে Admin-কে জানাও।",
            reply_markup=_menu_keyboard(staff),
        )
    context.user_data.pop("salary", None)
    return ConversationHandler.END


async def salary_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("salary", None)
    await update.message.reply_text("❌ বাতিল করা হলো।", reply_markup=_menu_keyboard(staff))
    return ConversationHandler.END


async def send_break_reminder(context: ContextTypes.DEFAULT_TYPE):
    """প্রতিদিন দুপুর ১টায় (Bangladesh time) চলে — যারা Check-In করেছে কিন্তু এখনো
    Break নেয়নি এবং Check-Out করেনি, তাদের বিরতি নেওয়ার reminder পাঠায়।"""
    date_str = bd_now().strftime("%Y-%m-%d")
    if config.MULTITENANT_ENABLED:
        try:
            tenants = await async_runtime.run_role_lookup(
                _tenant_resolver.list_active_tenants
            )
        except Exception as error:
            capture_exception(error)
            logger.exception("send_break_reminder: tenant list failed")
            return
        for tenant in tenants:
            tenant_runtime.bind_tenant(tenant)
            await _send_break_reminder_for_bound_tenant(context, date_str)
        return
    await _send_break_reminder_for_bound_tenant(context, date_str)


async def _send_break_reminder_for_bound_tenant(context, date_str: str):
    try:
        pending = await async_runtime.run_sheets_read(
            sheets.get_staff_needing_break_reminder, date_str
        )
    except Exception:
        logger.exception("send_break_reminder: pending স্টাফ লিস্ট আনতে ব্যর্থ হয়েছে")
        return
    for staff in pending:
        telegram_id = staff.get("Telegram_ID", "")
        if not telegram_id:
            continue
        try:
            await context.bot.send_message(
                chat_id=int(telegram_id),
                text=(
                    "⏰ আপনি এখনো বিরতি শুরু করেননি।\n"
                    "বিরতিতে গেলে '☕ বিরতি শুরু' চাপুন।"
                ),
            )
        except Exception:
            logger.exception(f"send_break_reminder: {telegram_id}-কে মেসেজ পাঠাতে ব্যর্থ হয়েছে")


async def salhist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    if not _staff_can_access_menu(staff, roles.MENU_SALARY_HISTORY):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    staff_rows = await async_runtime.run_sheets_read(sheets.get_all_staff)
    all_staff = [s for s in staff_rows if s.get("Staff_ID")]
    if not all_staff:
        await update.message.reply_text("❌ কোনো স্টাফ পাওয়া যায়নি।")
        return
    buttons = []
    for s in all_staff:
        name = s.get("Full_Name", "")
        role = s.get("Role", "")
        sid = s.get("Staff_ID")
        buttons.append([InlineKeyboardButton(f"{name} ({role})", callback_data=f"salhist_{sid}")])
    await update.message.reply_text(
        "কোন স্টাফের বেতন হিস্টোরি দেখবে?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def salhist_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff_id = query.data.replace("salhist_", "", 1)
    month = bd_now().strftime("%Y-%m")
    summary, history = await _asyncio_p314.gather(
        async_runtime.run_sheets_read(sheets.get_salary_summary, staff_id, month),
        async_runtime.run_sheets_read(
            sheets.get_staff_salary_history, staff_id, limit=15
        ),
    )

    name = summary.get("Full_Name", "") if summary else staff_id
    lines = [f"📜 {name} — বেতন হিস্টোরি\n"]

    if summary:
        lines.append(
            f"এই মাস ({month}): বেতন ৳{summary.get('Monthly_Salary', 0):.0f} | "
            f"পরিশোধিত ৳{summary.get('Paid', 0):.0f} | বাকি ৳{summary.get('Due', 0):.0f}\n"
        )

    if not history:
        lines.append("কোনো কিস্তির রেকর্ড পাওয়া যায়নি।")
    else:
        for r in history:
            lines.append(
                f"• {r.get('Date', '')} | ৳{r.get('Amount', 0)} | "
                f"মাস: {r.get('Month', '')} | দিয়েছেন: {r.get('Paid_By', '')}"
            )

    await query.edit_message_text("\n".join(lines))


async def mypayments_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    if not _staff_can_access_menu(staff, roles.MENU_MY_PAYMENTS):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    my_name = staff.get("Full_Name") or staff.get("Name") or str(staff.get("Staff_ID", ""))
    rows = await async_runtime.run_sheets_read(
        sheets.get_payments_made_by, my_name, limit=30
    )
    if not rows:
        await update.message.reply_text("🧾 তুমি এখনো কাউকে বেতন দাওনি।")
        return
    lines = [f"🧾 তুমি ({my_name}) যা দিয়েছো —\n"]
    total = 0.0
    for r in rows:
        amt = _sheet_amount_value(r.get("Amount", 0) or 0)
        total += amt
        lines.append(
            f"• {r.get('Date', '')} | {r.get('Staff_Full_Name', '')} | ৳{amt:.0f} | মাস: {r.get('Month', '')}"
        )
    lines.append(f"\nসর্বমোট: ৳{total:.0f}")
    await update.message.reply_text("\n".join(lines))


async def cash_handover_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, roles.MENU_CASH_HANDOVER):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["cash_handover"] = {}
    await update.message.reply_text(
        "কোন বিভাগের Reception cash হ্যান্ডওভার করবে?",
        reply_markup=_finance_department_keyboard("cashdept", staff),
    )
    return CASH_DEPARTMENT


async def cash_department_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    department = query.data.replace("cashdept_", "", 1)
    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(staff, roles.MENU_CASH_HANDOVER):
        return ConversationHandler.END
    if not _staff_has_finance_department(staff, department):
        await query.edit_message_text("⛔ এই Department-এর cash access নেই।")
        return ConversationHandler.END
    if department not in (config.DEPARTMENT_PHYSIO, config.DEPARTMENT_DENTAL):
        await query.edit_message_text("❌ বিভাগ সঠিক নয়।")
        return ConversationHandler.END
    context.user_data["cash_handover"] = {"Department": department}
    await query.edit_message_text(
        f"{department} Reception থেকে Home Treasury-তে কত টাকা হ্যান্ডওভার করবে?\n"
        "শুধু টাকার পরিমাণ লেখো (যেমন: 5000):"
    )
    return CASH_AMOUNT


async def cash_amount_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ শুধু সংখ্যা লেখো (যেমন: 5000):")
        return CASH_AMOUNT
    if amount <= 0:
        await update.message.reply_text("❌ Amount অবশ্যই ০-এর বেশি হতে হবে:")
        return CASH_AMOUNT
    handover = context.user_data.get("cash_handover", {})
    handover["Amount"] = amount
    context.user_data["cash_handover"] = handover
    await update.message.reply_text("কোনো নোট থাকলে লেখো, না থাকলে '-' দাও:")
    return CASH_NOTE


async def cash_note_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    handover = context.user_data.get("cash_handover", {})
    note = update.message.text.strip()
    handover["Note"] = "" if note == "-" else note
    context.user_data["cash_handover"] = handover
    await update.message.reply_text(
        "💵 ক্যাশ হ্যান্ডওভার\n"
        f"Department: {handover.get('Department', '')}\n"
        "From: Reception\n"
        "To: Home Treasury\n"
        f"Amount: ৳{handover.get('Amount', 0):.0f}\n"
        f"Note: {handover.get('Note') or '-'}\n\n"
        "হ্যান্ডওভার request পাঠাবে?",
        reply_markup=ReplyKeyboardMarkup(
            [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return CASH_CONFIRM


async def cash_confirm_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None or not _staff_can_access_menu(staff, roles.MENU_CASH_HANDOVER):
        return ConversationHandler.END
    handover = context.user_data.get("cash_handover", {})
    text = update.message.text.strip().lower()
    if not _staff_has_finance_department(
        staff, handover.get("Department", "")
    ):
        context.user_data.pop("cash_handover", None)
        await update.message.reply_text("⛔ এই Department-এর cash handover অনুমতি নেই।")
        return ConversationHandler.END
    if text not in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        context.user_data.pop("cash_handover", None)
        await update.message.reply_text(
            "❌ হ্যান্ডওভার বাতিল করা হয়েছে।",
            reply_markup=_menu_keyboard(staff),
        )
        return ConversationHandler.END

    moved_by = (
        staff.get("Full_Name")
        or staff.get("Name")
        or str(staff.get("Staff_ID", ""))
    )
    try:
        movement_id = await async_runtime.run_sheets_write(
            sheets.add_cash_movement,
            config.CASH_CUSTODIAN_RECEPTION,
            config.CASH_CUSTODIAN_HOME_TREASURY,
            handover.get("Amount", 0),
            moved_by,
            handover.get("Note", ""),
            handover.get("Department", ""),
        )
        await update.message.reply_text(
            f"✅ হ্যান্ডওভার request পাঠানো হয়েছে। ID: {movement_id}\n"
            "Owner/Manager গ্রহণ নিশ্চিত করলে এটি সম্পন্ন হবে।",
            reply_markup=_menu_keyboard(staff),
        )
        try:
            recipients = await async_runtime.run_sheets_read(sheets.get_all_staff)
            markup = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✅ গ্রহণ",
                        callback_data=f"cashact_accept_{movement_id}",
                    ),
                    InlineKeyboardButton(
                        "❌ প্রত্যাখ্যান",
                        callback_data=f"cashact_reject_{movement_id}",
                    ),
                ]
            ])
            for recipient in recipients:
                if str(recipient.get("Role", "")).strip() not in ("Owner", "Manager"):
                    continue
                telegram_id = recipient.get("Telegram_ID")
                if not telegram_id:
                    continue
                try:
                    await context.bot.send_message(
                        chat_id=int(telegram_id),
                        text=(
                            f"💵 নতুন cash handover request: {movement_id}\n"
                            f"Reception → Home Treasury\n"
                            f"পরিমাণ: ৳{handover.get('Amount', 0):.0f}\n"
                            f"দিয়েছেন: {moved_by}\n"
                            f"নোট: {handover.get('Note') or '-'}"
                        ),
                        reply_markup=markup,
                    )
                except Exception:
                    logger.exception(
                        "cash_confirm_receive: receiver notification failed"
                    )
        except Exception:
            logger.exception("cash_confirm_receive: receiver list failed")
    except Exception as error:
        logger.exception("cash_confirm_receive failed")
        await update.message.reply_text(
            f"❌ হ্যান্ডওভার save করা যায়নি।\nError: {error}",
            reply_markup=_menu_keyboard(staff),
        )
    context.user_data.pop("cash_handover", None)
    return ConversationHandler.END


async def cash_handover_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("cash_handover", None)
    await update.effective_message.reply_text(
        "❌ হ্যান্ডওভার বাতিল করা হলো।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


def _cash_pending_keyboard(rows: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for row in rows[:20]:
        movement_id = str(row.get("Movement_ID", "")).strip()
        buttons.append([
            InlineKeyboardButton(
                f"✅ {movement_id} গ্রহণ",
                callback_data=f"cashact_accept_{movement_id}",
            ),
            InlineKeyboardButton(
                "❌ প্রত্যাখ্যান",
                callback_data=f"cashact_reject_{movement_id}",
            ),
        ])
    return InlineKeyboardMarkup(buttons)


async def cash_receive_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    if not _staff_can_access_menu(staff, roles.MENU_CASH_RECEIVE):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    rows = await async_runtime.run_sheets_read(sheets.get_pending_cash_movements, _finance_departments(staff))
    if not rows:
        await update.message.reply_text("✅ কোনো pending cash handover নেই।")
        return
    lines = ["💵 Pending cash handover:\n"]
    for row in rows[:20]:
        lines.append(
            f"• {row.get('Movement_ID', '')} | ৳{_display_sheet_amount(row.get('Amount', 0))} "
            f"| {row.get('Moved_By', '')} | {row.get('Timestamp', '')}"
        )
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=_cash_pending_keyboard(rows),
    )


async def cash_finalize_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None:
        await query.edit_message_text("❌ স্টাফ তথ্য পাওয়া যায়নি।")
        return
    if not _staff_can_access_menu(staff, roles.MENU_CASH_RECEIVE):
        await query.edit_message_text("⛔ এই কাজের অনুমতি তোমার নেই।")
        return

    payload = query.data.replace("cashact_", "", 1)
    action, movement_id = payload.split("_", 1)
    decision = "Accepted" if action == "accept" else "Rejected"
    confirmed_by = (
        staff.get("Full_Name")
        or staff.get("Name")
        or str(staff.get("Staff_ID", ""))
    )
    result = await async_runtime.run_sheets_write(
        sheets.finalize_cash_movement,
        movement_id,
        confirmed_by,
        decision,
        _finance_departments(staff),
    )
    if result.get("ok"):
        label = "গ্রহণ করা হয়েছে" if decision == "Accepted" else "প্রত্যাখ্যান করা হয়েছে"
        await query.edit_message_text(
            f"{'✅' if decision == 'Accepted' else '❌'} {movement_id} {label}।\n"
            f"নিশ্চিত করেছেন: {confirmed_by}"
        )
        return
    if result.get("reason") == "already_finalized":
        await query.edit_message_text(
            f"ℹ️ {movement_id} আগেই {result.get('status', 'finalized')} হয়েছে।"
        )
        return
    await query.edit_message_text(f"❌ {movement_id} পাওয়া যায়নি।")


async def cash_movements_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    if not _staff_can_access_menu(staff, roles.MENU_CASH_MOVEMENTS):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    today = bd_now().strftime("%Y-%m-%d")
    rows = await async_runtime.run_sheets_read(
        sheets.get_cash_movements_for_date, today, _finance_departments(staff)
    )
    if not rows:
        await update.message.reply_text("🔄 আজ কোনো cash movement নেই।")
        return
    lines = [f"🔄 আজকের cash movement — {today}\n"]
    for row in rows[:30]:
        lines.append(
            f"• {row.get('Movement_ID', '')} | "
            f"{row.get('From_Custodian', '')} → {row.get('To_Custodian', '')} | "
            f"৳{_display_sheet_amount(row.get('Amount', 0))} | "
            f"{row.get('Status', 'Pending')}"
        )
    await update.message.reply_text("\n".join(lines))


async def _expense_form_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    mode: str,
    menu_item: str,
):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(staff, menu_item):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["cost"] = {"Mode": mode}
    await update.message.reply_text(
        "খরচ কোন বিভাগের?",
        reply_markup=_finance_department_keyboard("costdept", staff),
    )
    return COST_DEPARTMENT


async def _send_expense_category_prompt(message):
    buttons = [
        [InlineKeyboardButton(cat, callback_data=f"costcat_{cat}")]
        for cat in sheets.EXPENSE_CATEGORIES
    ]
    await message.reply_text(
        "খরচের ক্যাটাগরি বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def cost_department_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    department = query.data.replace("costdept_", "", 1)
    staff = await _require_staff(update, context)
    if staff is None or not _staff_has_finance_department(staff, department):
        await query.edit_message_text("⛔ এই Department-এর finance access নেই।")
        return ConversationHandler.END
    if department not in (config.DEPARTMENT_PHYSIO, config.DEPARTMENT_DENTAL):
        await query.edit_message_text("❌ বিভাগ সঠিক নয়।")
        return ConversationHandler.END
    expense = context.user_data.get("cost", {})
    expense["Department"] = department
    context.user_data["cost"] = expense
    await query.edit_message_text(f"বিভাগ: {department}")
    if expense.get("Mode") == "household":
        await query.message.reply_text(
            "🏠 Home Treasury থেকে household-এর জন্য কত টাকা নিচ্ছেন?"
        )
        return COST_AMOUNT
    await _send_expense_category_prompt(query.message)
    return COST_CATEGORY


async def small_expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await _expense_form_start(
        update,
        context,
        mode="reception_request",
        menu_item=roles.MENU_SMALL_EXPENSE_REQUEST,
    )


async def owner_clinic_expense_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    return await _expense_form_start(
        update,
        context,
        mode="owner_clinic",
        menu_item=roles.MENU_OWNER_CLINIC_EXPENSE,
    )


async def household_withdrawal_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not _staff_can_access_menu(
        staff, roles.MENU_HOUSEHOLD_WITHDRAWAL
    ):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    context.user_data["cost"] = {
        "Mode": "household",
        "Category": "Household Withdrawal",
    }
    await update.message.reply_text(
        "এই withdrawal কোন বিভাগের business source থেকে?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🩺 Physio", callback_data="costdept_Physio")],
            [InlineKeyboardButton("🦷 Dental", callback_data="costdept_Dental")],
        ]),
    )
    return COST_DEPARTMENT


async def cost_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.replace("costcat_", "", 1)
    expense = context.user_data.get("cost", {})
    expense["Category"] = category
    context.user_data["cost"] = expense
    await query.edit_message_text(
        f"ক্যাটাগরি: {category}\n\nকত টাকা খরচ হবে লেখো:"
    )
    return COST_AMOUNT


async def cost_amount_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expense = context.user_data.get("cost", {})
    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ শুধু সংখ্যা লেখো (যেমন: 500):")
        return COST_AMOUNT
    if amount <= 0:
        await update.message.reply_text("❌ Amount অবশ্যই ০-এর বেশি হতে হবে:")
        return COST_AMOUNT
    expense["Amount"] = amount
    context.user_data["cost"] = expense
    await update.message.reply_text("কোনো নোট থাকলে লেখো, না থাকলে '-' দাও:")
    return COST_NOTE


async def cost_note_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    expense = context.user_data.get("cost", {})
    note = update.message.text.strip()
    expense["Note"] = "" if note == "-" else note
    context.user_data["cost"] = expense
    mode = expense.get("Mode", "")
    action = (
        "Owner-এর অনুমোদনের জন্য request পাঠাবে?"
        if mode == "reception_request"
        else "এই লেনদেন Paid হিসেবে save করবে?"
    )
    await update.message.reply_text(
        f"ক্যাটাগরি: {expense.get('Category', '')}\n"
        f"পরিমাণ: ৳{expense.get('Amount', 0):.0f}\n"
        f"নোট: {expense.get('Note') or '-'}\n\n"
        f"{action}",
        reply_markup=ReplyKeyboardMarkup(
            [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return COST_CONFIRM


async def _notify_expense_approvers(
    context: ContextTypes.DEFAULT_TYPE,
    expense_id: str,
    expense: dict,
    requested_by: str,
):
    recipients = await async_runtime.run_sheets_read(sheets.get_all_staff)
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "✅ অনুমোদন", callback_data=f"expact_approve_{expense_id}"
        ),
        InlineKeyboardButton(
            "❌ বাতিল", callback_data=f"expact_reject_{expense_id}"
        ),
    ]])
    for recipient in recipients:
        if str(recipient.get("Role", "")).strip() != "Owner":
            continue
        telegram_id = recipient.get("Telegram_ID")
        if not telegram_id:
            continue
        try:
            await context.bot.send_message(
                chat_id=int(telegram_id),
                text=(
                    f"💸 ছোট খরচের request: {expense_id}\n"
                    f"ক্যাটাগরি: {expense.get('Category', '')}\n"
                    f"পরিমাণ: ৳{expense.get('Amount', 0):.0f}\n"
                    f"Request করেছেন: {requested_by}\n"
                    f"নোট: {expense.get('Note') or '-'}"
                ),
                reply_markup=markup,
            )
        except Exception:
            logger.exception("expense approval notification failed")


async def cost_confirm_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    expense = context.user_data.get("cost", {})
    if not _staff_has_finance_department(
        staff, expense.get("Department", "")
    ):
        context.user_data.pop("cost", None)
        await update.message.reply_text("⛔ এই Department-এর expense save অনুমতি নেই।")
        return ConversationHandler.END
    answer = update.message.text.strip().lower()
    if answer not in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        context.user_data.pop("cost", None)
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।",
            reply_markup=_menu_keyboard(staff),
        )
        return ConversationHandler.END

    actor = (
        staff.get("Full_Name")
        or staff.get("Name")
        or str(staff.get("Staff_ID", ""))
    )
    mode = expense.get("Mode", "")
    try:
        if mode == "reception_request":
            if not _staff_can_access_menu(
                staff, roles.MENU_SMALL_EXPENSE_REQUEST
            ):
                raise PermissionError("Reception expense permission denied")
            expense_id = await async_runtime.run_sheets_write(
                sheets.create_expense_request,
                expense.get("Category", ""),
                expense.get("Amount", 0),
                actor,
                expense.get("Note", ""),
                expense.get("Department", ""),
            )
            await update.message.reply_text(
                f"✅ খরচের request পাঠানো হয়েছে। ID: {expense_id}\n"
                "Owner অনুমোদন করলে টাকা দেওয়ার button চালু হবে।",
                reply_markup=_menu_keyboard(staff),
            )
            try:
                await _notify_expense_approvers(
                    context, expense_id, expense, actor
                )
            except Exception:
                logger.exception("expense approver list failed")
        else:
            if mode == "owner_clinic":
                menu_item = roles.MENU_OWNER_CLINIC_EXPENSE
                expense_type = config.EXPENSE_TYPE_CLINIC
            elif mode == "household":
                menu_item = roles.MENU_HOUSEHOLD_WITHDRAWAL
                expense_type = config.EXPENSE_TYPE_HOUSEHOLD
            else:
                raise ValueError("Unknown expense workflow mode")
            if not _staff_can_access_menu(staff, menu_item):
                raise PermissionError("Owner expense permission denied")
            expense_id = await async_runtime.run_sheets_write(
                sheets.add_expense,
                expense.get("Category", ""),
                expense.get("Amount", 0),
                actor,
                note=expense.get("Note", ""),
                expense_type=expense_type,
                paid_from=config.CASH_CUSTODIAN_HOME_TREASURY,
                status="Paid",
                approved_by=actor,
                paid_by=actor,
                department=expense.get("Department", ""),
            )
            label = (
                "Household Withdrawal"
                if expense_type == config.EXPENSE_TYPE_HOUSEHOLD
                else "বড় clinic expense"
            )
            await update.message.reply_text(
                f"✅ {label} Paid হিসেবে save হয়েছে। ID: {expense_id}",
                reply_markup=_menu_keyboard(staff),
            )
    except Exception as error:
        logger.exception("expense workflow save failed")
        await update.message.reply_text(
            f"❌ Save করা যায়নি।\nError: {error}",
            reply_markup=_menu_keyboard(staff),
        )
    context.user_data.pop("cost", None)
    return ConversationHandler.END


async def cost_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("cost", None)
    await update.effective_message.reply_text(
        "❌ বাতিল করা হলো।",
        reply_markup=_menu_keyboard(staff),
    )
    return ConversationHandler.END


def _expense_approval_keyboard(rows: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for row in rows[:20]:
        expense_id = str(row.get("Expense_ID", "")).strip()
        buttons.append([
            InlineKeyboardButton(
                f"✅ {expense_id} অনুমোদন",
                callback_data=f"expact_approve_{expense_id}",
            ),
            InlineKeyboardButton(
                "❌ বাতিল",
                callback_data=f"expact_reject_{expense_id}",
            ),
        ])
    return InlineKeyboardMarkup(buttons)


async def expense_approval_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    if not _staff_can_access_menu(staff, roles.MENU_EXPENSE_APPROVAL):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    rows = await async_runtime.run_sheets_read(
        sheets.get_expense_requests, "Pending Approval", _finance_departments(staff)
    )
    if not rows:
        await update.message.reply_text("✅ কোনো pending খরচের request নেই।")
        return
    lines = ["📋 Pending ছোট খরচের request:\n"]
    for row in rows[:20]:
        lines.append(
            f"• {row.get('Expense_ID', '')} | {row.get('Category', '')} | "
            f"৳{_sheet_amount_value(row.get('Amount', 0) or 0):.0f} | "
            f"{row.get('Requested_By', '')}"
        )
    await update.message.reply_text(
        "\n".join(lines), reply_markup=_expense_approval_keyboard(rows)
    )


async def expense_approval_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None:
        await query.edit_message_text("❌ স্টাফ তথ্য পাওয়া যায়নি।")
        return
    if not _staff_can_access_menu(staff, roles.MENU_EXPENSE_APPROVAL):
        await query.edit_message_text("⛔ এই কাজের অনুমতি তোমার নেই।")
        return
    payload = query.data.replace("expact_", "", 1)
    action, expense_id = payload.split("_", 1)
    decision = "Approved" if action == "approve" else "Rejected"
    actor = (
        staff.get("Full_Name")
        or staff.get("Name")
        or str(staff.get("Staff_ID", ""))
    )
    result = await async_runtime.run_sheets_write(
        sheets.finalize_expense_request, expense_id, actor, decision,
        _finance_departments(staff)
    )
    if result.get("ok"):
        message = (
            "✅ অনুমোদন হয়েছে। Receptionist এখন টাকা দিতে পারবে।"
            if decision == "Approved"
            else "❌ খরচের request বাতিল হয়েছে।"
        )
        await query.edit_message_text(f"{expense_id}: {message}")
    elif result.get("reason") == "invalid_status":
        await query.edit_message_text(
            f"ℹ️ {expense_id} আগেই {result.get('status', 'finalized')} হয়েছে।"
        )
    else:
        await query.edit_message_text(f"❌ {expense_id} পাওয়া যায়নি।")


async def approved_expenses_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    if not _staff_can_access_menu(
        staff, roles.MENU_APPROVED_EXPENSES
    ):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    rows = await async_runtime.run_sheets_read(
        sheets.get_expense_requests, "Approved", _finance_departments(staff)
    )
    if not rows:
        await update.message.reply_text("✅ টাকা দেওয়ার মতো approved খরচ নেই।")
        return
    buttons = []
    lines = ["✅ Approved—টাকা দেওয়ার অপেক্ষায়:\n"]
    for row in rows[:20]:
        expense_id = str(row.get("Expense_ID", "")).strip()
        lines.append(
            f"• {expense_id} | {row.get('Category', '')} | "
            f"৳{_sheet_amount_value(row.get('Amount', 0) or 0):.0f}"
        )
        buttons.append([InlineKeyboardButton(
            f"💵 {expense_id} টাকা দেওয়া হয়েছে",
            callback_data=f"exppaid_{expense_id}",
        )])
    await update.message.reply_text(
        "\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons)
    )


async def expense_paid_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()
    staff = await _require_staff(update, context)
    if staff is None:
        await query.edit_message_text("❌ স্টাফ তথ্য পাওয়া যায়নি।")
        return
    if not _staff_can_access_menu(
        staff, roles.MENU_APPROVED_EXPENSES
    ):
        await query.edit_message_text("⛔ এই কাজের অনুমতি তোমার নেই।")
        return
    expense_id = query.data.replace("exppaid_", "", 1)
    actor = (
        staff.get("Full_Name")
        or staff.get("Name")
        or str(staff.get("Staff_ID", ""))
    )
    result = await async_runtime.run_sheets_write(
        sheets.mark_expense_paid, expense_id, actor, _finance_departments(staff)
    )
    if result.get("ok"):
        await query.edit_message_text(
            f"✅ {expense_id} Paid হয়েছে। Reception cash থেকে টাকা কমেছে।"
        )
    elif result.get("reason") == "invalid_status":
        await query.edit_message_text(
            f"ℹ️ {expense_id} এখন {result.get('status', 'finalized')} অবস্থায় আছে।"
        )
    else:
        await query.edit_message_text(f"❌ {expense_id} পাওয়া যায়নি।")


_FINANCIAL_REPORT_MENUS = {
    "expense": roles.MENU_EXPENSE_TRACKER,
    "cash": roles.MENU_CUSTODY_BALANCE,
}


def _financial_report_date_range(shortcut: str, today=None) -> tuple[str, str]:
    today = today or bd_now().date()
    if shortcut == "today":
        start = today
    elif shortcut == "yesterday":
        start = today - timedelta(days=1)
        today = start
    elif shortcut == "week":
        start = today - timedelta(days=(today.weekday() + 1) % 7)
    elif shortcut == "month":
        start = today.replace(day=1)
    else:
        raise ValueError("Unknown financial report shortcut")
    return start.isoformat(), today.isoformat()


def _financial_report_keyboard(report: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("আজ", callback_data=f"finrange_{report}_today"),
            InlineKeyboardButton("গতকাল", callback_data=f"finrange_{report}_yesterday"),
        ],
        [
            InlineKeyboardButton("এই সপ্তাহ", callback_data=f"finrange_{report}_week"),
            InlineKeyboardButton("এই মাস", callback_data=f"finrange_{report}_month"),
        ],
        [InlineKeyboardButton("কাস্টম তারিখ", callback_data=f"finrange_{report}_custom")],
    ])


async def _authorized_financial_report_staff(update, context, report: str):
    staff = await _require_staff(update, context)
    menu_item = _FINANCIAL_REPORT_MENUS.get(report)
    if staff is None or menu_item is None:
        return None
    if not _staff_can_access_menu(staff, menu_item):
        await update.effective_message.reply_text("⛔ এই রিপোর্ট দেখার অনুমতি তোমার নেই।")
        return None
    return staff


async def _financial_report_start(update, context, report: str):
    if await _authorized_financial_report_staff(update, context, report) is None:
        return
    await update.effective_message.reply_text(
        "📅 রিপোর্টের সময় বেছে নিন:",
        reply_markup=_financial_report_keyboard(report),
    )


def _expense_report_text(rows, start_date: str, end_date: str, role_str: str) -> str:
    owner = role_str.strip() == roles.Role.OWNER.value
    visible_rows = rows if owner else [
        row for row in rows
        if str(row.get("Paid_From", "")).strip()
        != config.CASH_CUSTODIAN_HOME_TREASURY
    ]
    paid_clinic = sum(
        _sheet_amount_value(row.get("Amount", 0) or 0)
        for row in visible_rows
        if row.get("Type") == config.EXPENSE_TYPE_CLINIC
        and row.get("Status") in ("Paid", "Legacy Paid")
    )
    household = sum(
        _sheet_amount_value(row.get("Amount", 0) or 0)
        for row in visible_rows
        if row.get("Type") == config.EXPENSE_TYPE_HOUSEHOLD
        and row.get("Status") in ("Paid", "Legacy Paid")
    )
    label = start_date if start_date == end_date else f"{start_date} — {end_date}"
    lines = [f"💸 খরচ হিসাব — {label}\n"]
    if not visible_rows:
        lines.append("এই সময়ে কোনো খরচের record নেই।")
    for row in visible_rows:
        lines.append(
            f"• {row.get('Expense_ID', '')} | {row.get('Category', '')} | "
            f"৳{_sheet_amount_value(row.get('Amount', 0) or 0):.0f} | "
            f"{row.get('Status', '')} | {row.get('Paid_From', '')}"
        )
    lines.append(f"\nPaid clinic expense: ৳{paid_clinic:.0f}")
    if owner:
        lines.append(f"Household Withdrawal: ৳{household:.0f}")
    return "\n".join(lines)


async def costtracker_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _financial_report_start(update, context, "expense")


def _cash_custody_summary_text(summary: dict, role_str: str) -> str:
    text = (
        f"⚖️ Cash reconciliation — {summary['Date']}\n\n"
        f"Reception\n"
        f"Cash collection: ৳{summary['Cash_Collected']:.0f}\n"
        f"Paid ছোট খরচ: ৳{summary['Reception_Expense']:.0f}\n"
        f"Accepted handover: ৳{summary['Reception_Handover']:.0f}\n"
        f"নির্বাচিত সময়ের net balance: ৳{summary['Reception_Balance']:.0f}"
    )
    if role_str.strip() == roles.Role.OWNER.value:
        text += (
            f"\n\nHome Treasury\n"
            f"Accepted receipt: ৳{summary['Home_Received']:.0f}\n"
            f"বড় clinic expense: ৳{summary['Home_Clinic_Expense']:.0f}\n"
            f"Household Withdrawal: ৳{summary['Household_Withdrawal']:.0f}\n"
            f"Transfer out: ৳{summary['Home_Transfer_Out']:.0f}\n"
            f"নির্বাচিত সময়ের net balance: ৳{summary['Home_Balance']:.0f}"
        )
    return (
        text
        + "\n\nℹ️ এটি নির্বাচিত সময়ের movement balance; আগের opening cash এতে নেই।"
    )


async def custody_balance_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    await _financial_report_start(update, context, "cash")


async def _show_financial_report(update, context, report, start_date, end_date):
    staff = await _authorized_financial_report_staff(update, context, report)
    if staff is None:
        return
    if report == "cash":
        summary = await async_runtime.run_sheets_read(
            sheets.get_cash_custody_summary, start_date, end_date,
            _finance_departments(staff)
        )
        text = _cash_custody_summary_text(summary, staff.get("Role", ""))
    else:
        rows = await async_runtime.run_sheets_read(
            sheets.get_expenses_for_date, start_date, end_date,
            _finance_departments(staff)
        )
        text = _expense_report_text(
            rows, start_date, end_date, staff.get("Role", "")
        )
    await update.effective_message.reply_text(text)


async def financial_report_range_callback(update, context):
    query = update.callback_query
    await query.answer()
    _, report, shortcut = query.data.split("_", 2)
    if await _authorized_financial_report_staff(update, context, report) is None:
        return
    if shortcut == "custom":
        context.user_data["financial_report_range"] = {"report": report}
        today = bd_now().date()
        await query.message.reply_text(
            "📅 শুরুর তারিখ বেছে নিন:",
            reply_markup=calendar_helper.build_calendar(
                today.year, today.month, "finstart"
            ),
        )
        return
    start_date, end_date = _financial_report_date_range(shortcut)
    await _show_financial_report(update, context, report, start_date, end_date)


async def financial_report_calendar_navigate(update, context):
    query = update.callback_query
    await query.answer()
    prefix, value = query.data.split("nav_", 1)
    year, month = map(int, value.split("-"))
    await query.edit_message_reply_markup(
        reply_markup=calendar_helper.build_calendar(year, month, prefix)
    )


async def financial_report_start_day_callback(update, context):
    query = update.callback_query
    await query.answer()
    state = context.user_data.get("financial_report_range", {})
    report = state.get("report", "")
    if await _authorized_financial_report_staff(update, context, report) is None:
        return
    start_date = query.data.split("_", 1)[1]
    state["start_date"] = start_date
    context.user_data["financial_report_range"] = state
    selected = datetime.strptime(start_date, "%Y-%m-%d").date()
    await query.message.reply_text(
        "📅 শেষের তারিখ বেছে নিন:",
        reply_markup=calendar_helper.build_calendar(
            selected.year, selected.month, "finend"
        ),
    )


async def financial_report_end_day_callback(update, context):
    query = update.callback_query
    await query.answer()
    state = context.user_data.get("financial_report_range", {})
    report = state.get("report", "")
    start_date = state.get("start_date", "")
    if await _authorized_financial_report_staff(update, context, report) is None:
        return
    end_date = query.data.split("_", 1)[1]
    if not start_date or end_date < start_date:
        await query.message.reply_text(
            "⚠️ শেষের তারিখ শুরুর তারিখের আগে হতে পারবে না।"
        )
        return
    context.user_data.pop("financial_report_range", None)
    await _show_financial_report(update, context, report, start_date, end_date)


def _owner_finance_view_text(data: dict, view: str) -> str:
    date_str = data["Date"]
    if view in {config.DEPARTMENT_PHYSIO, config.DEPARTMENT_DENTAL}:
        summary = data[view]
        icon = "🩺" if view == config.DEPARTMENT_PHYSIO else "🦷"
        title = f"{icon} {view} Dashboard"
        comparison = ""
        warning = ""
    else:
        summary = data["Combined"]
        title = "🏢 Combined Business Summary"
        physio = data[config.DEPARTMENT_PHYSIO]
        dental = data[config.DEPARTMENT_DENTAL]
        comparison = (
            "\nDepartment totals\n"
            f"🩺 Physio: collection ৳{physio['Month_Collection']:.0f}, "
            f"net ৳{physio['Month_Net_Before_Salary']:.0f}\n"
            f"🦷 Dental: collection ৳{dental['Month_Collection']:.0f}, "
            f"net ৳{dental['Month_Net_Before_Salary']:.0f}\n"
        )
        unclassified = summary["Unclassified_Rows"]
        warning = (
            "\n\n⚠️ Unclassified (totals থেকে বাদ): "
            f"Payment {unclassified['Payments']}, Expense {unclassified['Expenses']}, "
            f"Cash Movement {unclassified['Cash_Movements']}"
        )
    opening = summary["Opening"]
    closing = summary["Closing"]
    return (
        f"{title} — {date_str}\n\n"
        f"আজকের collection: ৳{summary['Today_Collection']:.0f}\n"
        f"এই মাসের collection: ৳{summary['Month_Collection']:.0f}\n"
        f"এই মাসের clinic expense: ৳{summary['Month_Clinic_Expense']:.0f}\n"
        f"এই মাসের net (salary-এর আগে): ৳{summary['Month_Net_Before_Salary']:.0f}\n"
        f"Household Withdrawal: ৳{summary['Month_Household_Withdrawal']:.0f}\n"
        f"{comparison}\n"
        "Opening → Closing custody\n"
        f"Reception: ৳{opening['Reception']:.0f} → ৳{closing['Reception']:.0f}\n"
        f"Home Treasury: ৳{opening['Home Treasury']:.0f} → ৳{closing['Home Treasury']:.0f}\n"
        f"Digital/Bank: ৳{opening['Digital/Bank']:.0f} → ৳{closing['Digital/Bank']:.0f}"
        f"{warning}"
    )


async def owner_financial_dashboard_start(
    update: Update, context: ContextTypes.DEFAULT_TYPE, view: str
):
    staff = await _require_staff(update, context)
    if staff is None:
        return
    menu_item = {
        config.DEPARTMENT_PHYSIO: roles.MENU_PHYSIO_FINANCE_DASHBOARD,
        config.DEPARTMENT_DENTAL: roles.MENU_DENTAL_FINANCE_DASHBOARD,
        "Combined": roles.MENU_COMBINED_BUSINESS_SUMMARY,
    }[view]
    if not _staff_can_access_menu(staff, menu_item):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    today = bd_now().strftime("%Y-%m-%d")
    data = await async_runtime.run_sheets_read(
        sheets.get_owner_financial_dashboard, today
    )
    await update.message.reply_text(_owner_finance_view_text(data, view))


async def physio_finance_dashboard_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await owner_financial_dashboard_start(update, context, config.DEPARTMENT_PHYSIO)


async def dental_finance_dashboard_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await owner_financial_dashboard_start(update, context, config.DEPARTMENT_DENTAL)


async def combined_business_summary_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await owner_financial_dashboard_start(update, context, "Combined")


def main():
    global _tenant_resolver
    init_sentry()
    # Do not enable concurrent_updates: ConversationHandler needs ordered updates.
    app = Application.builder().token(config.BOT_TOKEN).build()
    if config.MULTITENANT_ENABLED:
        _tenant_resolver = tenant_runtime.MasterTenantResolver(
            sheets._get_client(),
            config.MASTER_SHEET_ID,
            cache_ttl=float(os.getenv("TENANT_LOOKUP_CACHE_TTL", "30")),
        )
        app.add_handler(TypeHandler(Update, _bind_update_tenant), group=-100)
    app.job_queue.run_daily(
        send_break_reminder,
        time=dt_time(hour=13, minute=0, tzinfo=timezone(timedelta(hours=6))),
    )

    salary_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_SALARY}$"), salary_start)
        ],
        states={
            SALARY_SELECT_STAFF: [
                CallbackQueryHandler(salary_select_callback, pattern="^salsel_")
            ],
            SALARY_ENTER_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), salary_amount_receive)
            ],
            SALARY_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), salary_note_receive)
            ],
            SALARY_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), salary_confirm_receive)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", salary_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(salary_conv)
    app.add_handler(MessageHandler(filters.Regex(f"^{roles.MENU_SALARY_HISTORY}$"), salhist_start))
    app.add_handler(CallbackQueryHandler(salhist_select_callback, pattern="^salhist_"))
    app.add_handler(MessageHandler(filters.Regex(f"^{roles.MENU_MY_PAYMENTS}$"), mypayments_start))

    cash_handover_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(f"^{roles.MENU_CASH_HANDOVER}$"),
                cash_handover_start,
            )
        ],
        states={
            CASH_DEPARTMENT: [
                CallbackQueryHandler(cash_department_callback, pattern="^cashdept_")
            ],
            CASH_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX),
                    cash_amount_receive,
                )
            ],
            CASH_NOTE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX),
                    cash_note_receive,
                )
            ],
            CASH_CONFIRM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX),
                    cash_confirm_receive,
                )
            ],
        },
        fallbacks=[
            MessageHandler(
                filters.Regex(f"^{roles.MENU_BACK_MAIN}$"),
                _cancel_and_go_home,
            ),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", cash_handover_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(cash_handover_conv)
    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_CASH_RECEIVE}$"),
            cash_receive_start,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_CASH_MOVEMENTS}$"),
            cash_movements_start,
        )
    )
    app.add_handler(
        CallbackQueryHandler(cash_finalize_callback, pattern="^cashact_")
    )

    cost_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(f"^{roles.MENU_SMALL_EXPENSE_REQUEST}$"),
                small_expense_start,
            ),
            MessageHandler(
                filters.Regex(f"^{roles.MENU_OWNER_CLINIC_EXPENSE}$"),
                owner_clinic_expense_start,
            ),
            MessageHandler(
                filters.Regex(f"^{roles.MENU_HOUSEHOLD_WITHDRAWAL}$"),
                household_withdrawal_start,
            ),
        ],
        states={
            COST_DEPARTMENT: [
                CallbackQueryHandler(cost_department_callback, pattern="^costdept_")
            ],
            COST_CATEGORY: [
                CallbackQueryHandler(cost_category_callback, pattern="^costcat_")
            ],
            COST_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), cost_amount_receive)
            ],
            COST_NOTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), cost_note_receive)
            ],
            COST_CONFIRM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), cost_confirm_receive)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", cost_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(cost_conv)
    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_EXPENSE_APPROVAL}$"),
            expense_approval_start,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_APPROVED_EXPENSES}$"),
            approved_expenses_start,
        )
    )
    app.add_handler(
        CallbackQueryHandler(expense_approval_callback, pattern="^expact_")
    )
    app.add_handler(
        CallbackQueryHandler(expense_paid_callback, pattern="^exppaid_")
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_EXPENSE_TRACKER}$"),
            costtracker_start,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_CUSTODY_BALANCE}$"),
            custody_balance_start,
        )
    )
    app.add_handler(CallbackQueryHandler(
        financial_report_range_callback, pattern="^finrange_(expense|cash)_"
    ))
    app.add_handler(CallbackQueryHandler(
        financial_report_calendar_navigate, pattern="^fin(start|end)nav_"
    ))
    app.add_handler(CallbackQueryHandler(
        financial_report_start_day_callback, pattern="^finstartday_"
    ))
    app.add_handler(CallbackQueryHandler(
        financial_report_end_day_callback, pattern="^finendday_"
    ))
    app.add_handler(MessageHandler(
        filters.Regex(f"^{roles.MENU_PHYSIO_FINANCE_DASHBOARD}$"),
        physio_finance_dashboard_start,
    ))
    app.add_handler(MessageHandler(
        filters.Regex(f"^{roles.MENU_DENTAL_FINANCE_DASHBOARD}$"),
        dental_finance_dashboard_start,
    ))
    app.add_handler(MessageHandler(
        filters.Regex(f"^{roles.MENU_COMBINED_BUSINESS_SUMMARY}$"),
        combined_business_summary_start,
    ))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(learning_quiz_answer_callback, pattern="^lquiz:"))
    app.add_handler(CommandHandler("search", search_patient))
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_MY_PATIENTS}$"), my_patients)
    )
    app.add_handler(
        MessageHandler(filters.Regex(_ATTENDANCE_MENU_REGEX), attendance_menu)
    )
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_TODAY_SCHEDULE}$"), today_schedule_menu)
    )
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_PATIENT_MGMT}$"), patient_mgmt_menu)
    )
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_TREATMENT}$"), treatment_menu)
    )
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_AI_TOOLS}$"), ai_tools_menu)
    )
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_FINANCE}$"), finance_menu)
    )
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), back_to_main_menu)
    )
    app.add_handler(CallbackQueryHandler(schedule_attendance_callback, pattern="^sched_att$"))
    app.add_handler(CallbackQueryHandler(schedule_appointments_callback, pattern="^sched_apt$"))
    # Attendance is outside ConversationHandler. Running only these callbacks as
    # non-blocking tasks lets different clinics check in concurrently while all
    # stateful conversation updates remain sequential.
    app.add_handler(
        CallbackQueryHandler(attendance_callback, pattern="^att_", block=False)
    )
    app.add_handler(
        MessageHandler(filters.LOCATION, attendance_location_receive, block=False)
    )
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_TODAY_APPOINTMENTS}$"), today_appointments)
    )
    app.add_handler(CallbackQueryHandler(apt_status_callback, pattern="^aptstatus_"))
    app.add_handler(CallbackQueryHandler(apt_today_back_callback, pattern="^apttodayback_"))
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_DAILY_REGISTER}$"), register_menu)
    )

    plist_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_PATIENT_LIST}$"), patient_list_start)
        ],
        states={
            "PLIST_BROWSE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), patient_list_search),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", patient_list_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(plist_conv)
    app.add_handler(CallbackQueryHandler(patient_list_page_callback, pattern="^plistpage_"))
    app.add_handler(CallbackQueryHandler(patient_list_select_callback, pattern="^plistsel_"))
    app.add_handler(CallbackQueryHandler(patient_list_back_callback, pattern="^plistact_back$"))
    app.add_handler(CallbackQueryHandler(plist_action_viewfiles, pattern="^plistact_viewfiles_"))
    app.add_handler(CallbackQueryHandler(plist_report_files_page_callback, pattern="^plistfiles_"))
    app.add_handler(CallbackQueryHandler(plist_action_getfile, pattern="^plistact_getfile_"))
    app.add_handler(CallbackQueryHandler(plist_action_hist, pattern="^plistact_hist_"))
    app.add_handler(CallbackQueryHandler(pt_dashboard_refresh_callback, pattern="^ptdash_refresh$"))
    app.add_handler(CallbackQueryHandler(pt_dashboard_history_callback, pattern="^ptdashhist_"))
    ptdash_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(pt_dashboard_receive_callback, pattern="^ptrecv_")],
        states={
            "PT_DASH_WORKSPACE": [
                CallbackQueryHandler(pt_dashboard_done_callback, pattern="^ptwdone$"),
                CallbackQueryHandler(pt_dashboard_edit_callback, pattern="^ptwedit$"),
                CallbackQueryHandler(pt_workspace_history_callback, pattern="^ptwhist_"),
                CallbackQueryHandler(pt_dashboard_back_callback, pattern="^ptwbackdash$"),
            ],
            "PT_DASH_EDIT": [
                CallbackQueryHandler(pt_dashboard_edit_back_callback, pattern="^ptwback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pt_dashboard_edit_message),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(f"^{roles.MENU_BACK_MAIN}$"), _cancel_and_go_home),
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", treat_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(ptdash_conv)
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
            REG_PHOTO_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_photo_choice)],
            REG_PHOTO_WAIT: [MessageHandler(filters.PHOTO, reg_photo_receive)],
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
                    "⚠️ কাজটি সম্পন্ন হয়নি—এটি সব সময় Google Sheets busy বোঝায় না। "
                    "একবার আবার চেষ্টা করো; একই button-এ আবার হলে Admin-কে জানাও।"
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
