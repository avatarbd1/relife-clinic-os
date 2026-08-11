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
bot.py тАФ Relife Clinic OS Telegram Bot (ржкрзНрж░ржержо ржнрж╛рж░рзНрж╕ржи)
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
                "тЪая╕П ржХрзНрж▓рж┐ржирж┐ржХ ржкрж░рж┐ржЪрзЯ ржпрж╛ржЪрж╛ржЗ ржХрж░рж╛ ржпрж╛ржЪрзНржЫрзЗ ржирж╛ред ржПржХржЯрзБ ржкрж░рзЗ ржЖржмрж╛рж░ ржЪрзЗрж╖рзНржЯрж╛ ржХрж░рзБржиред"
            )
        raise ApplicationHandlerStop

    if tenant is None:
        if update.effective_message:
            await update.effective_message.reply_text(
                "тЭМ ржЖржкржирж╛рж░ Telegram ID ржХрзЛржирзЛ рж╕ржХрзНрж░рж┐рзЯ ржХрзНрж▓рж┐ржирж┐ржХрзЗрж░ рж╕ржЩрзНржЧрзЗ ржпрзБржХрзНржд ржирзЗржЗред"
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

BN_WEEKDAYS = ["рж╕рзЛржо", "ржоржЩрзНржЧрж▓", "ржмрзБржз", "ржмрзГрж╣ржГ", "рж╢рзБржХрзНрж░", "рж╢ржирж┐", "рж░ржмрж┐"]

PATIENT_LOOKUP_PROMPT = (
    "ЁЯФО рж░рзЛржЧрзА рж╢ржирж╛ржХрзНржд ржХрж░рждрзЗ ржирж╛ржо, ржлрзЛржи ржиржорзНржмрж░ ржЕржержмрж╛ Patient ID рж▓рж┐ржЦрзБржи:"
)
STATUS_DOCUMENT_ANALYSIS = "ЁЯЦ╝я╕П ржЫржмрж┐/рж░рж┐ржкрзЛрж░рзНржЯрзЗрж░ рждржерзНржп ржмрж┐рж╢рзНрж▓рзЗрж╖ржг ржХрж░ржЫрж┐тАж"
STATUS_CLINICAL_ANALYSIS = (
    "ЁЯза ржХрзНрж▓рж┐ржирж┐ржХрзНржпрж╛рж▓ рждржерзНржп ржУ ржкрзНрж░рж╛рж╕ржЩрзНржЧрж┐ржХ ржорзНржпрж╛ржирзБржпрж╝рж╛рж▓ ржмрж┐рж╢рзНрж▓рзЗрж╖ржг ржХрж░ржЫрж┐тАж"
)
STATUS_BUSINESS_ANALYSIS = (
    "ЁЯУК ржХрзНрж▓рж┐ржирж┐ржХрзЗрж░ рждржерзНржп ржмрж┐рж╢рзНрж▓рзЗрж╖ржг ржХрж░рзЗ ржЙрждрзНрждрж░ ржкрзНрж░рж╕рзНрждрзБржд ржХрж░ржЫрж┐тАж"
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
    "ЁЯПа рж╣рж╛ржЬрж┐рж░рж╛",
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
_ATTENDANCE_MENU_LABELS = (roles.MENU_ATTENDANCE, "ЁЯПа рж╣рж╛ржЬрж┐рж░рж╛")
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
(CASESTUDY_QUESTION,) = range(42, 43)  # ржЖрж░ ржмрзНржпржмрж╣рж╛рж░ рж╣ржпрж╝ ржирж╛ (patch22 revert) тАФ future reuse-ржПрж░ ржЬржирзНржп number рж╕ржВрж░ржХрзНрж╖рж┐ржд
(REG_FIELDS,) = range(43, 44)  # рж░рзЗржЬрж┐рж╕рзНржЯрзНрж░рзЗрж╢ржирзЗ missing fields ржПржХрж╕рж╛ржерзЗ ржЬрж┐ржЬрзНржЮрж╛рж╕рж╛рж░ state (patch38)
(CLINICALAI_QUESTION,) = range(44, 45)  # AI Clinical Assistant state (patch40)
(SALARY_SELECT_STAFF, SALARY_ENTER_AMOUNT, SALARY_NOTE, SALARY_CONFIRM) = range(45, 49)  # Staff Salary System
(COST_CATEGORY, COST_AMOUNT, COST_NOTE, COST_CONFIRM) = range(49, 53)  # Daily Cost Tracker
(CASH_AMOUNT, CASH_NOTE, CASH_CONFIRM) = range(53, 56)  # Cash handover workflow
(COST_DEPARTMENT, CASH_DEPARTMENT) = range(56, 58)
(PAYDEL_LIST, PAYDEL_CONFIRM) = range(300, 302)  # ржЖржЬржХрзЗрж░ ржПржирзНржЯрзНрж░рж┐ ржорзБржЫрж╛рж░ ржлрзНрж▓рзЛ
(INV_UPDATE,) = range(310, 311)  # ржЗржиржнрзЗржирзНржЯрж░рж┐ рж╕рзНржЯржХ ржЖржкржбрзЗржЯ ржлрзНрж▓рзЛ

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
        [InlineKeyboardButton("тЬЕ ржЧрждржХрж╛рж▓рзЗрж░ ржорждрзЛржЗ", callback_data=f"trsame_{patient_id}")],
        [InlineKeyboardButton("тЬПя╕П ржПржбрж┐ржЯ ржХрж░ржмрзЛ", callback_data=f"tredit_{patient_id}")],
        [InlineKeyboardButton("тмЕя╕П ржЖржЧрзЗрж░ ржзрж╛ржк", callback_data="trback_search")],
    ]
    return InlineKeyboardMarkup(buttons)


def _machine_keyboard(selected: set) -> InlineKeyboardMarkup:
    buttons = []
    for i in range(0, len(MACHINE_LIST), 2):
        row = []
        for j in (i, i + 1):
            if j < len(MACHINE_LIST):
                prefix = "тЬЕ " if j in selected else "тмЬ "
                row.append(InlineKeyboardButton(prefix + MACHINE_LIST[j], callback_data=f"trm_{j}"))
        buttons.append(row)
    buttons.append([InlineKeyboardButton("тЬЕ рж╕ржорзНржкржирзНржи тАФ рж╕рзЗржн ржХрж░рзЛ", callback_data="trdone_save")])
    buttons.append([InlineKeyboardButton("тмЕя╕П ржЖржЧрзЗрж░ ржзрж╛ржк", callback_data="trback_confirm")])
    buttons.append([InlineKeyboardButton("тЭМ ржмрж╛рждрж┐рж▓", callback_data="trcancel_")])
    return InlineKeyboardMarkup(buttons)



async def _cancel_on_menu_press(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ржХржиржнрж╛рж░рж╕рзЗрж╢ржирзЗрж░ ржорж╛ржЭржЦрж╛ржирзЗ ржЕржирзНржп ржорзЗржирзБ ржмрж╛ржЯржи ржЪрж╛ржкрж▓рзЗ ржЪрж▓ржорж╛ржи ржХрж╛ржЬ ржмрж╛рждрж┐рж▓ ржХрж░рзЗ ржжрзЗржпрж╝,
    ржпрж╛рждрзЗ рж╕рзЗржЗ ржмрж╛ржЯржирзЗрж░ рж▓рзЗржЦрж╛ржЯрж╛ ржнрзБрж▓ ржХрж░рзЗ ржлрзЛржи ржиржорзНржмрж░/ржирж╛ржо рж╣рж┐рж╕рзЗржмрзЗ рж╕рзЗржн ржирж╛ рж╣ржпрж╝рзЗ ржпрж╛ржпрж╝ред"""
    context.user_data.clear()
    await update.message.reply_text(
        "тЭМ ржЖржЧрзЗрж░ ржХрж╛ржЬржЯрж┐ ржмрж╛рждрж┐рж▓ ржХрж░рж╛ рж╣рж▓рзЛред ржПржЦржи ржЖржмрж╛рж░ рж╕рзЗржЗ ржмрж╛ржЯржирзЗ ржЪрж╛ржк ржжрж╛ржУред"
    )
    return ConversationHandler.END


async def _cancel_and_go_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ржХржиржнрж╛рж░рж╕рзЗрж╢ржирзЗрж░ ржорж╛ржЭржЦрж╛ржирзЗ ЁЯФЩ ржорзВрж▓ ржорзЗржирзБ ржЪрж╛ржкрж▓рзЗ ржЪрж▓ржорж╛ржи ржХрж╛ржЬ ржмрж╛рждрж┐рж▓ ржХрж░рзЗ рж╕рж░рж╛рж╕рж░рж┐ ржорзВрж▓ ржорзЗржирзБ ржжрзЗржЦрж╛ржпрж╝ред"""
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
            "тЪая╕П Reassessment required тАФ 7 visits/14 days threshold reached.",
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
                return ("Pain improving тАФ continue current protocol.", "High")
            if pain_values[-1] >= pain_values[0]:
                return ("Possible plateau тАФ review exercise progression.", "Medium")

    if notes:
        return ("Follow-up stable тАФ continue protocol if no change reported.", "Medium")
    return ("New treatment cycle тАФ monitor pain, ROM and function from visit 1.", "Medium")


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
        patient_therapist = str(patient.get("Therapist", "")).stў▐xц┌$z{-ощ▄j╫ЭЎ╓ўVчBТ└╨в╥└╨вХЇ╘UDДЇCв┤╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬ХЎ╓WFЖЎBХ╥└╨вХЇ4ЇфdХ$╙в┤╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬ХЎ6ЎцfЧ&╥Х╥└╨в╥└╨вf╞╞&6╖3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇ$4╡Ї╘Фч╥B"Т┬Ў6ц6V┼ЎцEЎvїЎЖЎ╓RТ└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬Ў6ц6V┼ЎЎхЎ╓VчUў&W72Т─6Ў╓╓цDЖцF╞W"В&6ц6V┬"┬ХЎ6ц6V┬Т└╨в6Ў╓╓цDЖцF╞W"В'7F'B"┬ў&W7F'EўfЦў7F'BТ┼╥└╨вР╨вцFEЎЖцF╞W"ЗХЎ6ЎчbР╨а╨вЦFV┼Ў6Ўчb╥6ЎчfW'6FЦЎфЖцF╞W"А╨вVчG'ХўЎЦчG3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇDT─UDUЇTхE%Ч╥B"Т┬ЦFV┼ў7F'BТ└╨в╥└╨в7FFW3╫░╨вФDT┼Ї─Х5Cв░╨в6╞╞&6╡VW'ФЖцF╞W"ЗЦFV┼ў6V╞V7EЎ6╞╞&6▓┬GFW&у╥%чЦFV╟6V┼Є"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЗЦFV┼Ў6ц6V┼Ў6╞╞&6▓┬GFW&у╥%чЦFV╞6ц6V┬B"Т└╨в╥└╨вФDT┼Ї4ЇфdХ$╙в░╨в6╞╞&6╡VW'ФЖцF╞W"ЗЦFV┼Ў6ЎцfЧ&╒Ў6╞╞&6▓┬GFW&у╥%чЦFV╞6ЎцfЧ&╒ўЦW2B"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЗЦFV┼Ў6ц6V┼Ў6╞╞&6▓┬GFW&у╥%чЦFV╞6ц6V┬B"Т└╨в╥└╨в╥└╨вf╞╞&6╖3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇ$4╡Ї╘Фч╥B"Т┬Ў6ц6V┼ЎцEЎvїЎЖЎ╓RТ└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬Ў6ц6V┼ЎЎхЎ╓VчUў&W72Т└╨в6Ў╓╓цDЖцF╞W"В&6ц6V┬"┬ХЎ6ц6V┬Т└╨в6Ў╓╓цDЖцF╞W"В'7F'B"┬ў&W7F'EўfЦў7F'BТ└╨в╥└╨вР╨вцFEЎЖцF╞W"ЗЦFV┼Ў6ЎчbР╨а╨вЦчeЎ6Ўчb╥6ЎчfW'6FЦЎфЖцF╞W"А╨вVчG'ХўЎЦчG3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇФхdTхDї%Ч╥B"Т┬ЦчfVчFў'ХЎ╓VчRТ└╨в╥└╨в7FFW3╫░╨вФхeїUDDSв┤╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬ЦчfVчFў'ХўWFFRХ╥└╨в╥└╨вf╞╞&6╖3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇ$4╡Ї╘Фч╥B"Т┬Ў6ц6V┼ЎцEЎvїЎЖЎ╓RТ└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬Ў6ц6V┼ЎЎхЎ╓VчUў&W72Т└╨в6Ў╓╓цDЖцF╞W"В&6ц6V┬"┬ЦчfVчFў'ХЎ6ц6V┬Т└╨в6Ў╓╓цDЖцF╞W"В'7F'B"┬ў&W7F'EўfЦў7F'BТ└╨в╥└╨вР╨вцFEЎЖцF╞W"ЖЦчeЎ6ЎчbР╨а╨вG&VEЎ6Ўчb╥6ЎчfW'6FЦЎфЖцF╞W"А╨вVчG'ХўЎЦчG3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUїE$TD╘TхEЇфїDW╥B"Т┬G&VEў7F'BТ└╨в6╞╞&6╡VW'ФЖцF╞W"З╞Ч7EЎ7FЦЎхўG&VB┬GFW&у╥%ч╞Ч7F7EўG&VEЄ"Т└╨в╥└╨в7FFW3╫░╨вE$TEї4T$4Гв░╨в6╞╞&6╡VW'ФЖцF╞W"ЗG&VEў6V╞V7EЎ6╞╞&6▓┬GFW&у╥%чG&VG6V┼Є"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЕўG&VEў6V&6ЕЎ6ц6V┬┬GFW&у╥%чG&VG6V&6Ж&6▓B"Т└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G&VEў6V&6ВТ└╨в╥└╨вE$TEї4T─T5Cв░╨в6╞╞&6╡VW'ФЖцF╞W"ЗG&VEў6V╞V7EЎ6╞╞&6▓┬GFW&у╥%чG&VG6V┼Є"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЕўG&VEў6V&6ЕЎ6ц6V┬┬GFW&у╥%чG&VG6V&6Ж&6▓B"Т└╨в╥└╨вE$TEЇ4ЇфdХ$╒ї─ув░╨в6╞╞&6╡VW'ФЖцF╞W"ЗG&VEЎ6ЎцfЧ&╒ў6╓UЎ6╞╞&6▓┬GFW&у╥%чG'6╓UЄ"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЗG&VEЎ6ЎцfЧ&╒ЎVFЧEЎ6╞╞&6▓┬GFW&у╥%чG&VFЧEЄ"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЗG&VEЎ&6╡ўFїў6V&6ЕЎ6╞╞&6▓┬GFW&у╥%чG&&6╡ў6V&6ВB"Т└╨в╥└╨вE$TEЇTDХEЇUДU$4Х4Sв░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G&VEЎVFЧEЎWЖW&6Ч6RТ└╨в╥└╨вE$TEЇTDХEЇT─T5E$єв░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G&VEЎVFЧEЎV╞V7G&ЄТ└╨в╥└╨вE$TEЇTDХEЇ╘хT├в░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G&VEЎVFЧEЎ╓чV┬Т└╨в╥└╨вE$TEЇ╘4ДФфU3в░╨в6╞╞&6╡VW'ФЖцF╞W"ЗG&VEЎ╓6ЖЦцUўFЎvv╞R┬GFW&у╥%чG&╒Є"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЗG&VEЎ╓6ЖЦцUЎFЎцR┬GFW&у╥%чG&FЎцUЄ"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЗG&VEЎ&6╡ўFїЎ6ЎцfЧ&╒Ў6╞╞&6▓┬GFW&у╥%чG&&6╡Ў6ЎцfЧ&╥B"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЗG&VEЎ╓6ЖЦцUЎ6ц6V┼Ў6╞╞&6▓┬GFW&у╥%чG&6ц6V┼Є"Т└╨в╥└╨вE$TEїDФTхEЇ4Ї╘╘TхCв░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G&VEўFЦVчEЎ6Ў╓╓VчEў&V6VЧfRТ└╨в╥└╨вE$TEї$Їu$U55ї44ї$Sв░╨в6╞╞&6╡VW'ФЖцF╞W"ЗG&VEў&Ўw&W75ў66ў&UЎ6╞╞&6▓┬GFW&у╥%чG'ЦхЄ"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЗG&VEў&Ўw&W75ў66ў&UЎ6╞╞&6▓┬GFW&у╥%чG'Цч6╢ЧB"Т└╨в╥└╨вE$TEЇХїTU5DФЇув░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G&VEЎХўVW7FЦЎхў&V6VЧfRТ└╨в╥└╨в╥└╨вf╞╞&6╖3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇ$4╡Ї╘Фч╥B"Т┬Ў6ц6V┼ЎцEЎvїЎЖЎ╓RТ└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬Ў6ц6V┼ЎЎхЎ╓VчUў&W72Т└╨в6Ў╓╓цDЖцF╞W"В&6ц6V┬"┬G&VEЎ6ц6V┬Т└╨в6Ў╓╓цDЖцF╞W"В'7F'B"┬ў&W7F'EўfЦў7F'BТ┼╥└╨вР╨вцFEЎЖцF╞W"ЗG&VEЎ6ЎчbР╨а╨вG╞хЎ6Ўчb╥6ЎчfW'6FЦЎфЖцF╞W"А╨вVчG'ХўЎЦчG3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUїE$TD╘TхEї─ч╥B"Т┬G╞хў7F'BТ└╨в╥└╨в7FFW3╫░╨вE─хї4T$4Гв░╨в6╞╞&6╡VW'ФЖцF╞W"ЗG╞хў6V╞V7EЎ6╞╞&6▓┬GFW&у╥%чG╞ч6V┼Є"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЕўG╞хў6V&6ЕЎ6ц6V┬┬GFW&у╥%чG╞ч6V&6Ж&6▓B"Т└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G╞хў6V&6ВТ└╨в╥└╨вE─хї4T─T5Cв░╨в6╞╞&6╡VW'ФЖцF╞W"ЗG╞хў6V╞V7EЎ6╞╞&6▓┬GFW&у╥%чG╞ч6V┼Є"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЕўG╞хў6V&6ЕЎ6ц6V┬┬GFW&у╥%чG╞ч6V&6Ж&6▓B"Т└╨в╥└╨вE─хЇ4DTtї%Ув░╨в6╞╞&6╡VW'ФЖцF╞W"ЗG╞хЎ6FVvў'ХЎ6╞╞&6▓┬GFW&у╥%чG6EЄ"Т└╨в╥└╨вE─хїDU5E3в░╨в6╞╞&6╡VW'ФЖцF╞W"ЖFW7EЎ6╞╞&6▓┬GFW&у╥%цFW7EЄ"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЖFW7EЎЦцfїЎ6╞╞&6▓┬GFW&у╥%цЦцfїЄ"Т└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬FW7EўFWЗEў&V6VЧfRТ└╨в╥└╨вE─хЇDФtфї4Х3в┤╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G╞хЎFЦvцў6Ч2Х╥└╨вE─хїDїD├в┤╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G╞хўFўF┬Х╥└╨вE─хЇUДU$4Х4Sв░╨в6╞╞&6╡VW'ФЖцF╞W"ЗG╞хЎХў7VvvW7EЎ6╞╞&6▓┬GFW&у╥%чG╞хЎХў7VvvW7BB"Т└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G╞хЎWЖW&6Ч6RТ└╨в╥└╨вE─хЇT─T5E$єв┤╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G╞хЎV╞V7G&ЄХ╥└╨вE─хЇ╘хT├в┤╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G╞хЎ╓чV┬Х╥└╨вE─хЇ4ЇфdХ$╙в┤╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬G╞хЎ6ЎцfЧ&╥Х╥└╨в╥└╨вf╞╞&6╖3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇ$4╡Ї╘Фч╥B"Т┬Ў6ц6V┼ЎцEЎvїЎЖЎ╓RТ└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬Ў6ц6V┼ЎЎхЎ╓VчUў&W72Т└╨в6Ў╓╓цDЖцF╞W"В&6ц6V┬"┬G╞хЎ6ц6V┬Т└╨в6Ў╓╓цDЖцF╞W"В'7F'B"┬ў&W7F'EўfЦў7F'BТ└╨в╥└╨вР╨вцFEЎЖцF╞W"ЗG╞хЎ6ЎчbР╨а╨вцFEЎЖцF╞W"Д╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUї$Uї%E7╥B"Т┬&Wў'G5Ў╓VчRТР╨вцFEЎЖцF╞W"Д6╞╞&6╡VW'ФЖцF╞W"З'EўFўF╟5Ў6╞╞&6▓┬GFW&у╥%ч'EўFўF╟2B"ТР╨вцFEЎЖцF╞W"Д6╞╞&6╡VW'ФЖцF╞W"З'EЎ╞7F╓ЎчFЕЎ6╞╞&6▓┬GFW&у╥%ч'EЎ╞7F╓ЎчFВB"ТР╨вцFEЎЖцF╞W"Д6╞╞&6╡VW'ФЖцF╞W"З'EўFЎFЧ&VvЧ7FW%Ў6╞╞&6▓┬GFW&у╥%ч'EўFЎFЧ&VvЧ7FW"B"ТР╨вцFEЎЖцF╞W"Д6╞╞&6╡VW'ФЖцF╞W"З'EЎFFW&WЎ6╞╞&6▓┬GFW&у╥%ч'EЎFFW&WB"ТР╨вцFEЎЖцF╞W"Д╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇDDUї$Uї%G╥B"Т┬FFUў&Wў'EЎ╓VчRТР╨вцFEЎЖцF╞W"Д6╞╞&6╡VW'ФЖцF╞W"ЖFFUў&Wў'EЎ6╞VцF%ЎцfЦvFR┬GFW&у╥%ц6╞цeЄ"ТР╨вцFEЎЖцF╞W"Д6╞╞&6╡VW'ФЖцF╞W"ЖFFUў&Wў'EЎFХў6V╞V7FVB┬GFW&у╥%ц6╞FХЄ"ТР╨вЖЧ7EЎ6Ўчb╥6ЎчfW'6FЦЎфЖцF╞W"А╨вVчG'ХўЎЦчG3╒┤╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUїDФTхEЇДХ5Dї%Ч╥B"Т┬ЖЧ7Eў7F'BХ╥└╨в7FFW3╫░╨в$ДХ5Eї4T$4В#в░╨в6╞╞&6╡VW'ФЖцF╞W"ЖЖЧ7Eў6V╞V7EЎ6╞╞&6▓┬GFW&у╥%цЖЧ7G6V┼Є"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЕЎЖЧ7Eў6V&6ЕЎ6ц6V┬┬GFW&у╥%цЖЧ7G6V&6Ж&6▓B"Т└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬ЖЧ7Eў6V&6ВТ└╨в╥└╨в╥└╨вf╞╞&6╖3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇ$4╡Ї╘Фч╥B"Т┬Ў6ц6V┼ЎцEЎvїЎЖЎ╓RТ└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬Ў6ц6V┼ЎЎхЎ╓VчUў&W72Т─6Ў╓╓цDЖцF╞W"В&6ц6V┬"┬ЖЧ7EЎ6ц6V┬Т└╨в6Ў╓╓цDЖцF╞W"В'7F'B"┬ў&W7F'EўfЦў7F'BТ┼╥└╨вР╨вцFEЎЖцF╞W"ЖЖЧ7EЎ6ЎчbР╨а╨вFЖЧ7EЎ6Ўчb╥6ЎчfW'6FЦЎфЖцF╞W"А╨вVчG'ХўЎЦчG3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUїE$TD╘TхEЇДХ5Dї%Ч╥B"Т┬FЖЧ7Eў7F'BТ└╨в╥└╨в7FFW3╫░╨в%DДХ5Eї4T$4В#в░╨в6╞╞&6╡VW'ФЖцF╞W"ЗFЖЧ7EўFЦVчEЎ6╞╞&6▓┬GFW&у╥%чFЗ6V┼Є"Т└╨в6╞╞&6╡VW'ФЖцF╞W"ЕўFЖЧ7Eў6V&6ЕЎ6ц6V┬┬GFW&у╥%чFЖЧ7G6V&6Ж&6▓B"Т└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фB┬FЖЧ7Eў6V&6ВТ└╨в╥└╨в%DДХ5EЇDDR#в░╨в6╞╞&6╡VW'ФЖцF╞W"ЗFЖЧ7EЎFFUЎ6╞╞&6▓┬GFW&у╥%чFЖFFUЄ"Т└╨в╥└╨в╥└╨вf╞╞&6╖3╒┤6Ў╓╓цDЖцF╞W"В&6ц6V┬"┬FЖЧ7EЎ6ц6V┬Х╥└╨вР╨вцFEЎЖцF╞W"ЗFЖЧ7EЎ6ЎчbР╨в2FЖЧ7EЎFFUЎ6╞╞&6▓
hn
i~
xr
kn
x
j~
xFЖЧ7EЎ6Ўчb▐
h■
kDДХ5EЇDDR7FFR▐
h■
k
j▐
k■
jN
k
x~
hr
j~
k
kт
j■
x~
jN
Z@╨в2
jN
kю
k
k■
ib
kО
k■
k.
x~
i^
x▐
iЄ
i^
k
kю
k
jо
k6ЎчfW'6FЦЎтTфB
kЮ
j■
k╬
xr
j■
kю
j■
k┬┬
j╛
k.
xr/	∙IТ
j╛
k■
k
x
jВ"
jn
k■
j■
k╬
xr
j╛
k■
k
xr
h■
kО
xp╨в2
hn
k
x~
i^
i■
kт
jN
kю
k
k■
ib
iо
kю
jо
k.
xr
i^
x╛
jО
x▓ЖцF╞W"
kО
x~
i■
kт
j~
k
jB
jО
kю
ZB
i~
x▐
k.
x╛
j╬
kю
k.
kЄ
k
x~
i╬
k■
kО
x▐
i■
kю
k
i^
k
xr
j╛
k■
i^
x▐
kВЗF6Г3Ю
Z@╨вцFEЎЖцF╞W"Д6╞╞&6╡VW'ФЖцF╞W"ЗFЖЧ7EЎFFUЎ6╞╞&6▓┬GFW&у╥%чFЖFFUЄ"ТР╨вцFEЎЖцF╞W"Д6╞╞&6╡VW'ФЖцF╞W"ЗFЖЧ7EЎцeЎ6╞╞&6▓┬GFW&у╥%чFЖцeЄ"ТР╨вцFEЎЖцF╞W"Д6╞╞&6╡VW'ФЖцF╞W"ЗFЖЧ7EЎ&6╡ўFїЎFFW5Ў6╞╞&6▓┬GFW&у╥%чFЖЧ7F&6╡Є"ТР╨вцFEЎЖцF╞W"Д6╞╞&6╡VW'ФЖцF╞W"ЗFЖЧ7Eў&Ўw&W75Ў6╞╞&6▓┬GFW&у╥%чFЖЧ7G&ЎuЄ"ТР╨а╨в7FffХЎ6Ўчb╥6ЎчfW'6FЦЎфЖцF╞W"А╨вVчG'ХўЎЦчG3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUї5DdeЇХїTU%Ч╥B"Т┬7FffХў7F'BР╨в╥└╨в7FFW3╫░╨в5DddХїTU5DФЇув░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬7FffХў&V6VЧfRР╨в╥└╨в╥└╨вf╞╞&6╖3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇ$4╡Ї╘Фч╥B"Т┬Ў6ц6V┼ЎцEЎvїЎЖЎ╓RТ└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬Ў6ц6V┼ЎЎхЎ╓VчUў&W72Т└╨в6Ў╓╓цDЖцF╞W"В&6ц6V┬"┬7FffХЎ6ц6V┬Т└╨в6Ў╓╓цDЖцF╞W"В'7F'B"┬ў&W7F'EўfЦў7F'BТ└╨в╥└╨вР╨вцFEЎЖцF╞W"З7FffХЎ6ЎчbР╨а╨в6╞ЦцЦ6╞ХЎ6Ўчb╥6ЎчfW'6FЦЎфЖцF╞W"А╨вVчG'ХўЎЦчG3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇ4─ФфФ4┼ЇЧ╥B"Т┬6╞ЦцЦ6╞Хў7F'BР╨в╥└╨в7FFW3╫░╨в4─ФфФ4─ХїTU5DФЇув░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬6╞ЦцЦ6╞Хў&V6VЧfRР╨в╥└╨в╥└╨вf╞╞&6╖3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇ$4╡Ї╘Фч╥B"Т┬Ў6ц6V┼ЎцEЎvїЎЖЎ╓RТ└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬Ў6ц6V┼ЎЎхЎ╓VчUў&W72Т└╨в6Ў╓╓цDЖцF╞W"В&6ц6V┬"┬6╞ЦцЦ6╞ХЎ6ц6V┬Т└╨в6Ў╓╓цDЖцF╞W"В'7F'B"┬ў&W7F'EўfЦў7F'BТ└╨в╥└╨вР╨вцFEЎЖцF╞W"Ж6╞ЦцЦ6╞ХЎ6ЎчbР╨а╨в66W7GVGХЎ6Ўчb╥6ЎчfW'6FЦЎфЖцF╞W"А╨вVчG'ХўЎЦчG3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇ44Uї5ETEЧ╥B"Т┬66W7GVGХў7F'BР╨в╥└╨в7FFW3╫░╨в44U5ETEХї4T$4Гв░╨в6╞╞&6╡VW'ФЖцF╞W"Ж66W7GVGХў6V╞V7EЎ6╞╞&6▓┬GFW&у╥%ц776V┼Є"Т└╨в6╞╞&6╡VW'ФЖцF╞W"Ж66W7GVGХў6V&6ЕЎ6ц6V┼Ў6╞╞&6▓┬GFW&у╥%ц776V&6Ж&6▓B"Т└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬66W7GVGХў6V&6Еў&V6VЧfRТ└╨в╥└╨в44U5ETEХЇUЕE$в░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬66W7GVGХЎWЗG&ў&V6VЧfRР╨в╥└╨в44U5ETEХЇ─U54Їув░╨в6╞╞&6╡VW'ФЖцF╞W"Ж66W7GVGХЎ╞W76ЎхЎ6╞╞&6▓┬GFW&у╥%ц76╞W76ЎхЎцWЗBB"Р╨в╥└╨в╥└╨вf╞╞&6╖3╒░╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇ$4╡Ї╘Фч╥B"Т┬Ў6ц6V┼ЎцEЎvїЎЖЎ╓RТ└╨в╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬Ў6ц6V┼ЎЎхЎ╓VчUў&W72Т└╨в6Ў╓╓цDЖцF╞W"В&6ц6V┬"┬66W7GVGХЎ6ц6V┬Т└╨в6Ў╓╓цDЖцF╞W"В'7F'B"┬ў&W7F'EўfЦў7F'BТ└╨в╥└╨вР╨вцFEЎЖцF╞W"Ж66W7GVGХЎ6ЎчbР╨а╨вцFEЎЖцF╞W"Д╓W76vTЖцF╞W"ЖfЦ╟FW'2х&VvWВЖb%ч╖&Ў╞W2ф╘TхUЇДЇ╘W╥B"Т┬vїЎЖЎ╓RТР╨вцFEЎЖцF╞W"Д╓W76vTЖцF╞W"ЖfЦ╟FW'2хDUЕBbцfЦ╟FW'2ф4Ї╘╘фBbцfЦ╟FW'2х&VvWВЕЇ─┼Ї╘TхUї$TtUВТ┬Vц╢цўvхЎ╓VчRТР╨а╨в7Цц2FVbЎv╞Ў&┼ЎW'&ў%ЎЖцF╞W"ЗWFFSвЎ&жV7B┬6ЎчFWЗCв6ЎчFWЗEGЧW2фDTdT┼EїEХRУа╨в╞ЎvvW"цWЖ6WFЦЎтВ%VцЖцF╞VBW'&ў""┬WЖ5ЎЦцfє╓6ЎчFWЗBцW'&ў"Р╨в6GW&UЎWЖ6WFЦЎтЖ6ЎчFWЗBцW'&ў"Р╨вG'Уа╨вЦbЧ6Цч7Fц6RЗWFFR┬WFFRТцBWFFRцVffV7FЧfUЎ╓W76vSа╨вvЧBWFFRцVffV7FЧfUЎ╓W76vRч&W╟ХўFWЗBА╨в.)к√ИЄ
kО
kю
jю
j■
k╬
k■
iR
kО
jю
kО
x▐
j■
kт
kЮ
j■
k╬
x~
i╛
xrО
kО
jю
x▐
j▐
j╬
jBvЎЎv╞R6ЖVWG2
kО
kю
jю
j■
k╬
k■
iR
j╬
x▐
j■
kО
x▐
jBЮ
ZB ╨в.
i^
j■
k╬
x~
iR
kО
x~
i^
x~
jО
x▐
j
jо
k
hn
j╬
kю
k
iо
x~
k~
x▐
i■
kт
i^
k
x╛
ZB ╨вР╨вWЖ6WBWЖ6WFЦЎуа╨в╞ЎvvW"цWЖ6WFЦЎтВ&W'&ў"ЖцF╞W"
jО
k■
i╬
x~
hr
j╬
x▐
j■
k
x▐
jR
kЮ
j■
k╬
x~
i╛
xr"Р╨а╨вцFEЎW'&ў%ЎЖцF╞W"ЕЎv╞Ў&┼ЎW'&ў%ЎЖцF╞W"Р╨а╨в╞ЎvvW"цЦцfЄВ%&V╞ЦfR6╞ЦцЦ2ї2&ўB
iо
kю
k.
x
kЮ
iо
x▐
i╛
xrттт"Р╨вG'Уа╨вў7F'EЎЖV╟FЕў6W'fW"ВР╨вWЖ6WBWЖ6WFЦЎт2W'&ў#а╨в6GW&UЎWЖ6WFЦЎтЖW'&ў"Р╨в&Ч6P╨а╨вч'VхўЎ╞╞ЦцrВР╨а╨а╨жЦbїЎц╓UїЄ╙╥%їЎ╓ЦхїЄ#а╨в╓ЦтВР╨