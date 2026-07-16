from enum import Enum


class Role(str, Enum):
    OWNER = "Owner"
    RECEPTIONIST = "Receptionist"
    THERAPIST = "Therapist"
    MANAGER = "Manager"


MENU_HOME = "🏠 হোম"
MENU_PATIENT_REG = "👤 রোগী রেজিস্ট্রেশন"
MENU_APPOINTMENT = "📅 অ্যাপয়েন্টমেন্ট বুকিং"
MENU_MY_PATIENTS = "🧑‍⚕️ আমার রোগী / সেশন"
MENU_TREATMENT_NOTE = "📝 ট্রিটমেন্ট নোট"
MENU_TREATMENT_PLAN = "🩺 ট্রিটমেন্ট প্ল্যান"
MENU_PAYMENT = "💳 পেমেন্ট তথ্য"
MENU_REPORTS = "📊 রিপোর্ট ও অ্যানালিটিক্স"
MENU_SETTINGS = "⚙️ সেটিংস"
MENU_ATTENDANCE = "🕐 হাজিরা"
MENU_TODAY_APPOINTMENTS = "📋 আজকের অ্যাপয়েন্টমেন্ট"
MENU_PATIENT_HISTORY = "📜 রোগীর ইতিহাস"
MENU_TREATMENT_HISTORY = "📅 ট্রিটমেন্ট হিস্টরি"
MENU_PATIENT_LIST = "📋 রোগীর তালিকা"
MENU_DAILY_REGISTER = "📋 আজকের রেজিস্টার"

ROLE_MENU_ROWS: dict[Role, list[list[str]]] = {
    Role.OWNER: [
        [MENU_HOME],
        [MENU_PATIENT_REG, MENU_PATIENT_HISTORY],
        [MENU_PATIENT_LIST],
        [MENU_APPOINTMENT, MENU_TODAY_APPOINTMENTS],
        [MENU_ATTENDANCE, MENU_TREATMENT_NOTE],
        [MENU_TREATMENT_PLAN, MENU_TREATMENT_HISTORY],
        [MENU_DAILY_REGISTER, MENU_REPORTS],
        [MENU_SETTINGS],
    ],
    Role.RECEPTIONIST: [
        [MENU_HOME],
        [MENU_PATIENT_REG],
        [MENU_PATIENT_LIST],
        [MENU_APPOINTMENT, MENU_TODAY_APPOINTMENTS],
        [MENU_ATTENDANCE],
        [MENU_DAILY_REGISTER, MENU_REPORTS],
    ],
    Role.THERAPIST: [
        [MENU_HOME],
        [MENU_ATTENDANCE],
        [MENU_MY_PATIENTS],
        [MENU_TREATMENT_NOTE],
        [MENU_TREATMENT_PLAN, MENU_TREATMENT_HISTORY],
    ],
    Role.MANAGER: [
        [MENU_HOME],
        [MENU_PATIENT_REG],
        [MENU_PATIENT_LIST],
        [MENU_APPOINTMENT, MENU_TODAY_APPOINTMENTS],
        [MENU_ATTENDANCE],
        [MENU_REPORTS],
    ],
}


def get_menu_rows_for_role(role_str: str) -> list[list[str]]:
    try:
        role = Role(role_str.strip())
    except ValueError:
        return []
    return ROLE_MENU_ROWS.get(role, [])


def get_menu_for_role(role_str: str) -> list[str]:
    rows = get_menu_rows_for_role(role_str)
    return [item for row in rows for item in row]


def can_access(role_str: str, menu_item: str) -> bool:
    return menu_item in get_menu_for_role(role_str)


def is_therapist_owner_of_patient(therapist_name: str, patient_row: dict) -> bool:
    return patient_row.get("Therapist", "").strip() == therapist_name.strip()
