from enum import Enum


class Role(str, Enum):
    OWNER = "Owner"
    RECEPTIONIST = "Receptionist"
    THERAPIST = "Therapist"
    MANAGER = "Manager"


# ---- মেনু আইটেমসমূহ ----
MENU_HOME = "🏠 হোম"
MENU_PATIENT_REG = "👤 রোগী রেজিস্ট্রেশন"
MENU_APPOINTMENT = "📅 অ্যাপয়েন্টমেন্ট বুকিং"
MENU_MY_PATIENTS = "🧑‍⚕️ আমার রোগী / সেশন"
MENU_TREATMENT_NOTE = "📝 ট্রিটমেন্ট নোট"
MENU_TREATMENT_PLAN = "📋 এসেসমেন্ট / ট্রিটমেন্ট প্ল্যান"
MENU_TREATMENT_HISTORY = "📜 ট্রিটমেন্ট হিস্ট্রি"
MENU_PAYMENT = "💳 পেমেন্ট তথ্য"
MENU_REPORTS = "📊 রিপোর্ট ও অ্যানালিটিক্স"
MENU_DATE_REPORT = "📅 তারিখ ভিত্তিক রিপোর্ট"
MENU_SETTINGS = "⚙️ সেটিংস"
MENU_ATTENDANCE = "🕐 হাজিরা"
MENU_TODAY_APPOINTMENTS = "📋 আজকের অ্যাপয়েন্টমেন্ট"
MENU_PATIENT_HISTORY = "📜 রোগীর ইতিহাস"
MENU_PATIENT_LIST = "📋 রোগীর তালিকা"
MENU_DAILY_REGISTER = "📋 আজকের রেজিস্টার"
MENU_STAFF_AI_QUERY = "🤖 AI প্রশ্ন করুন"
MENU_CASE_STUDY = "📚 কেস স্টাডি"

# ---- Role অনুযায়ী মেনু, row আকারে গ্রুপ করা (সম্পর্কিত আইটেম পাশাপাশি) ----

ROLE_MENU_ROWS: dict[Role, list[list[str]]] = {
    Role.OWNER: [
        [MENU_HOME],
        [MENU_PATIENT_REG, MENU_PATIENT_HISTORY],
        [MENU_PATIENT_LIST],
        [MENU_APPOINTMENT, MENU_TODAY_APPOINTMENTS],
        [MENU_ATTENDANCE, MENU_TREATMENT_NOTE],
        [MENU_TREATMENT_PLAN, MENU_TREATMENT_HISTORY],
        [MENU_PAYMENT, MENU_REPORTS],
        [MENU_DAILY_REGISTER],
        [MENU_STAFF_AI_QUERY],
        [MENU_CASE_STUDY],
        [MENU_SETTINGS],
    ],
    Role.RECEPTIONIST: [
        [MENU_HOME],
        [MENU_PATIENT_REG],
        [MENU_PATIENT_LIST],
        [MENU_APPOINTMENT, MENU_TODAY_APPOINTMENTS],
        [MENU_ATTENDANCE],
        [MENU_PAYMENT, MENU_REPORTS],
        [MENU_DAILY_REGISTER],
        [MENU_STAFF_AI_QUERY],
    ],
    Role.THERAPIST: [
        [MENU_HOME],
        [MENU_ATTENDANCE],
        [MENU_MY_PATIENTS],
        [MENU_TREATMENT_NOTE, MENU_TREATMENT_PLAN],
        [MENU_TREATMENT_HISTORY],
        [MENU_STAFF_AI_QUERY],
    ],
    Role.MANAGER: [
        [MENU_HOME],
        [MENU_PATIENT_REG],
        [MENU_PATIENT_LIST],
        [MENU_APPOINTMENT, MENU_TODAY_APPOINTMENTS],
        [MENU_ATTENDANCE],
        [MENU_TREATMENT_HISTORY],
        [MENU_REPORTS],
        [MENU_DAILY_REGISTER],
        [MENU_STAFF_AI_QUERY],
    ],
}


def get_menu_rows_for_role(role_str: str) -> list[list[str]]:
    """Role অনুযায়ী row-আকারে গ্রুপ করা মেনু ফেরত দেয়।"""
    try:
        role = Role(role_str.strip())
    except ValueError:
        return []
    return ROLE_MENU_ROWS.get(role, [])


def get_menu_for_role(role_str: str) -> list[str]:
    """পুরনো কোড যেখানে flat লিস্ট আশা করে, তাদের জন্য backward-compatible।"""
    rows = get_menu_rows_for_role(role_str)
    return [item for row in rows for item in row]


def can_access(role_str: str, menu_item: str) -> bool:
    """একটা নির্দিষ্ট মেনু আইটেমে এই role-এর অ্যাক্সেস আছে কিনা।"""
    return menu_item in get_menu_for_role(role_str)


def is_therapist_owner_of_patient(therapist_name: str, patient_row: dict) -> bool:
    """
    Therapist শুধু নিজের Assigned Patient দেখবে —
    02_Patients শীটের 'Therapist' কলামের সাথে মিলিয়ে চেক করা হয়।
    """
    return patient_row.get("Therapist", "").strip() == therapist_name.strip()


PATIENT_ACTION_LABELS: dict[str, str] = {
    "hist": "📜 ইতিহাস দেখো",
    "apt": "📅 অ্যাপয়েন্টমেন্ট দাও",
    "pay": "💳 পেমেন্ট নাও",
    "treat": "📝 ট্রিটমেন্ট নোট লেখো",
}

ROLE_PATIENT_ACTIONS: dict[Role, list[str]] = {
    Role.OWNER: ["hist", "apt", "pay", "treat"],
    Role.RECEPTIONIST: ["hist", "apt", "pay"],
    Role.THERAPIST: ["hist", "treat"],
    Role.MANAGER: ["hist", "apt", "pay"],
}


def get_patient_actions(role_str: str) -> list[str]:
    """Role অনুযায়ী রোগী-অ্যাকশন কোডের লিস্ট ফেরত দেয় (hist/apt/pay/treat)।"""
    try:
        role = Role(role_str.strip())
    except ValueError:
        return []
    return ROLE_PATIENT_ACTIONS.get(role, [])
