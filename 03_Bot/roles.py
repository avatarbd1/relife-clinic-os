from enum import Enum


class Role(str, Enum):
    OWNER = "Owner"
    RECEPTIONIST = "Receptionist"
    THERAPIST = "Therapist"
    MANAGER = "Manager"
    DENTIST = "Dentist"
    DENTAL_ASSISTANT = "Dental_Assistant"
    AUDITOR = "Auditor"
    SYSTEM_ADMIN = "System Admin"


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
MENU_TODAY_SCHEDULE = "📋 আজকের শিডিউল"
MENU_PATIENT_MGMT = "👤 রোগী ব্যবস্থাপনা"
MENU_TREATMENT = "📝 ট্রিটমেন্ট"
MENU_AI_TOOLS = "🤖 AI টুলস"
MENU_BACK_MAIN = "🔙 মূল মেনু"
MENU_SETTINGS = "⚙️ সেটিংস"
MENU_ATTENDANCE = "🕐 হাজিরা"
MENU_TODAY_APPOINTMENTS = "📋 আজকের অ্যাপয়েন্টমেন্ট"
MENU_PATIENT_HISTORY = "📜 রোগীর ইতিহাস"
MENU_PATIENT_LIST = "📋 রোগীর তালিকা"
MENU_DAILY_REGISTER = "📋 আজকের রেজিস্টার"
MENU_STAFF_AI_QUERY = "🤖 AI প্রশ্ন করুন"
MENU_CASE_STUDY = "📚 কেস স্টাডি"
MENU_CLINICAL_AI = "🩺 ক্লিনিক্যাল অ্যাসিস্ট্যান্ট"
MENU_DELETE_ENTRY = "🗑️ আজকের এন্ট্রি মুছুন"
MENU_INVENTORY = "📦 ইনভেন্টরি"
MENU_SALARY = "💰 স্টাফ বেতন"
MENU_SALARY_HISTORY = "📜 বেতন হিস্টোরি"
MENU_MY_PAYMENTS = "🧾 আমার দেওয়া বেতন"
MENU_ADD_EXPENSE = "➕ খরচ যোগ করুন"  # legacy label; no role receives it
MENU_EXPENSE_TRACKER = "💸 ক্লিনিক খরচ হিসাব"
MENU_FINANCE = "💰 চলতি হিসাব"
MENU_CASH_HANDOVER = "💵 ক্যাশ হ্যান্ডওভার"
MENU_CASH_RECEIVE = "✅ হ্যান্ডওভার গ্রহণ"
MENU_CASH_MOVEMENTS = "🔄 ক্যাশ হ্যান্ডওভার হিস্ট্রি"
MENU_SMALL_EXPENSE_REQUEST = "➕ ছোট খরচের অনুরোধ"
MENU_EXPENSE_APPROVAL = "📋 খরচ অনুমোদন"
MENU_APPROVED_EXPENSES = "✅ অনুমোদিত খরচ পরিশোধ"
MENU_OWNER_CLINIC_EXPENSE = "🏥 বড় ক্লিনিক খরচ"
MENU_HOUSEHOLD_WITHDRAWAL = "🏠 Household Withdrawal"
MENU_CUSTODY_BALANCE = "⚖️ ক্যাশ ব্যালেন্স"
MENU_PHYSIO_FINANCE_DASHBOARD = "🩺 Physio Dashboard"
MENU_DENTAL_FINANCE_DASHBOARD = "🦷 Dental Dashboard"
MENU_COMBINED_BUSINESS_SUMMARY = "🏢 Combined Business Summary"

ROLE_MENU_ROWS: dict[Role, list[list[str]]] = {
    Role.OWNER: [
        [MENU_HOME],
        [MENU_PATIENT_MGMT],
        [MENU_APPOINTMENT, MENU_TODAY_SCHEDULE],
        [MENU_TREATMENT],
        [MENU_PAYMENT, MENU_REPORTS],
        [MENU_DELETE_ENTRY],
        [MENU_AI_TOOLS],
        [MENU_INVENTORY, MENU_FINANCE],
        [MENU_SETTINGS],
    ],
    Role.RECEPTIONIST: [
        [MENU_HOME],
        [MENU_PATIENT_MGMT],
        [MENU_APPOINTMENT, MENU_TODAY_SCHEDULE],
        [MENU_PAYMENT, MENU_REPORTS],
        [MENU_DELETE_ENTRY],
        [MENU_INVENTORY, MENU_FINANCE],
    ],
    Role.THERAPIST: [
        [MENU_HOME],
        [MENU_TODAY_SCHEDULE],
        [MENU_MY_PATIENTS],
        [MENU_TREATMENT_NOTE, MENU_TREATMENT_PLAN],
        [MENU_TREATMENT_HISTORY],
        [MENU_INVENTORY],
    ],
    Role.MANAGER: [
        [MENU_HOME],
        [MENU_PATIENT_MGMT],
        [MENU_APPOINTMENT, MENU_TODAY_SCHEDULE],
        [MENU_TREATMENT],
        [MENU_REPORTS],
        [MENU_DELETE_ENTRY],
        [MENU_INVENTORY, MENU_FINANCE],
    ],
}

ROLE_HIDDEN_MENU_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [
        MENU_ATTENDANCE, MENU_TODAY_APPOINTMENTS,
        MENU_PATIENT_REG, MENU_PATIENT_HISTORY, MENU_PATIENT_LIST,
        MENU_TREATMENT_NOTE, MENU_TREATMENT_PLAN, MENU_TREATMENT_HISTORY,
        MENU_DAILY_REGISTER, MENU_STAFF_AI_QUERY, MENU_CASE_STUDY, MENU_CLINICAL_AI,
        MENU_SALARY, MENU_SALARY_HISTORY, MENU_MY_PAYMENTS,
        MENU_OWNER_CLINIC_EXPENSE, MENU_HOUSEHOLD_WITHDRAWAL,
        MENU_EXPENSE_APPROVAL, MENU_EXPENSE_TRACKER,
        MENU_CASH_RECEIVE, MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
        MENU_PHYSIO_FINANCE_DASHBOARD, MENU_DENTAL_FINANCE_DASHBOARD,
        MENU_COMBINED_BUSINESS_SUMMARY,
    ],
    Role.RECEPTIONIST: [
        MENU_ATTENDANCE, MENU_TODAY_APPOINTMENTS,
        MENU_PATIENT_REG, MENU_PATIENT_LIST, MENU_DAILY_REGISTER,
        MENU_SMALL_EXPENSE_REQUEST, MENU_APPROVED_EXPENSES,
        MENU_EXPENSE_TRACKER, MENU_CASH_HANDOVER, MENU_CASH_MOVEMENTS,
        MENU_CUSTODY_BALANCE,
    ],
    Role.THERAPIST: [MENU_ATTENDANCE, MENU_CLINICAL_AI],
    Role.MANAGER: [
        MENU_ATTENDANCE, MENU_TODAY_APPOINTMENTS,
        MENU_PATIENT_REG, MENU_PATIENT_LIST, MENU_TREATMENT_HISTORY,
        MENU_DAILY_REGISTER, MENU_EXPENSE_TRACKER,
        MENU_CASH_RECEIVE, MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
    ],
}

ROLE_PATIENT_MGMT_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [MENU_PATIENT_REG, MENU_PATIENT_HISTORY, MENU_PATIENT_LIST],
    Role.RECEPTIONIST: [MENU_PATIENT_REG, MENU_PATIENT_LIST],
    Role.MANAGER: [MENU_PATIENT_REG, MENU_PATIENT_LIST],
}

ROLE_TREATMENT_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [MENU_TREATMENT_NOTE, MENU_TREATMENT_PLAN, MENU_TREATMENT_HISTORY],
    Role.MANAGER: [MENU_TREATMENT_HISTORY],
}

ROLE_AI_TOOLS_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [MENU_STAFF_AI_QUERY, MENU_CASE_STUDY, MENU_CLINICAL_AI],
    Role.THERAPIST: [MENU_CLINICAL_AI],
}

ROLE_FINANCE_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [
        MENU_PHYSIO_FINANCE_DASHBOARD, MENU_DENTAL_FINANCE_DASHBOARD,
        MENU_COMBINED_BUSINESS_SUMMARY,
        MENU_SALARY, MENU_SALARY_HISTORY, MENU_MY_PAYMENTS,
        MENU_OWNER_CLINIC_EXPENSE, MENU_HOUSEHOLD_WITHDRAWAL,
        MENU_EXPENSE_APPROVAL, MENU_EXPENSE_TRACKER,
        MENU_CASH_RECEIVE, MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
    ],
    Role.RECEPTIONIST: [
        MENU_SMALL_EXPENSE_REQUEST, MENU_APPROVED_EXPENSES,
        MENU_EXPENSE_TRACKER, MENU_CASH_HANDOVER,
        MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
    ],
    Role.MANAGER: [
        MENU_EXPENSE_TRACKER, MENU_CASH_RECEIVE,
        MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
    ],
}

ROLE_REPORTS_EXTRA_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [MENU_DAILY_REGISTER],
    Role.RECEPTIONIST: [MENU_DAILY_REGISTER],
    Role.MANAGER: [MENU_DAILY_REGISTER],
}


def get_menu_rows_for_role(role_str: str) -> list[list[str]]:
    try:
        role = Role(role_str.strip())
    except ValueError:
        return []
    return ROLE_MENU_ROWS.get(role, [])


def get_menu_for_role(role_str: str) -> list[str]:
    rows = get_menu_rows_for_role(role_str)
    flat = [item for row in rows for item in row]
    try:
        role = Role(role_str.strip())
    except ValueError:
        return flat
    flat += ROLE_HIDDEN_MENU_ITEMS.get(role, [])
    return flat


def _normalized_roles(role_values) -> list[Role]:
    """Return known roles once, in deterministic privilege/menu order."""
    if isinstance(role_values, str):
        role_values = [role_values]
    resolved = set()
    for value in role_values or []:
        try:
            resolved.add(Role(str(value).strip()))
        except ValueError:
            continue
    priority = [
        Role.OWNER,
        Role.MANAGER,
        Role.RECEPTIONIST,
        Role.THERAPIST,
        Role.DENTIST,
        Role.DENTAL_ASSISTANT,
        Role.AUDITOR,
        Role.SYSTEM_ADMIN,
    ]
    return [role for role in priority if role in resolved]


def get_menu_rows_for_roles(role_values) -> list[list[str]]:
    """Merge menus for explicit effective roles without duplicate buttons."""
    rows: list[list[str]] = []
    seen: set[str] = set()
    for role in _normalized_roles(role_values):
        for row in ROLE_MENU_ROWS.get(role, []):
            filtered = [item for item in row if item not in seen]
            if filtered:
                rows.append(filtered)
                seen.update(filtered)
    return rows


def get_menu_for_roles(role_values) -> list[str]:
    items = [item for row in get_menu_rows_for_roles(role_values) for item in row]
    seen = set(items)
    for role in _normalized_roles(role_values):
        for item in ROLE_HIDDEN_MENU_ITEMS.get(role, []):
            if item not in seen:
                items.append(item)
                seen.add(item)
    return items


def get_items_for_roles(items_map: dict[Role, list[str]], role_values) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for role in _normalized_roles(role_values):
        for item in items_map.get(role, []):
            if item not in seen:
                items.append(item)
                seen.add(item)
    return items


def can_any_access(role_values, menu_item: str) -> bool:
    return menu_item in get_menu_for_roles(role_values)


def can_access(role_str: str, menu_item: str) -> bool:
    """Legacy single-role adapter; production handlers use can_any_access."""
    return can_any_access([role_str], menu_item)


def is_therapist_owner_of_patient(therapist_name: str, patient_row: dict) -> bool:
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
    try:
        role = Role(role_str.strip())
    except ValueError:
        return []
    return ROLE_PATIENT_ACTIONS.get(role, [])
