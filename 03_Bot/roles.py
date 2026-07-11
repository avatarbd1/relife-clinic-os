STAFF = {
    111111111: {"name": "Malik Vai", "role": "owner"},
    222222222: {"name": "Receptionist Apa", "role": "receptionist"},
    333333333: {"name": "Therapist Bhai", "role": "therapist"},
    444444444: {"name": "Manager Apu", "role": "manager"},
}

ROLE_PERMISSIONS = {
    "owner": {
        "patients", "add_patient", "appointments", "add_appointment",
        "payments", "add_payment", "staff", "inventory", "reports",
        "therapy_notes", "settings",
    },
    "receptionist": {
        "patients", "add_patient", "appointments", "add_appointment",
        "payments", "add_payment", "reports_basic",
    },
    "therapist": {
        "my_sessions", "add_therapy_note", "my_patients",
    },
    "manager": {
        "appointments", "reports", "inventory",
    },
}


def get_staff_info(telegram_id: int):
    return STAFF.get(telegram_id)


def get_role(telegram_id: int):
    info = STAFF.get(telegram_id)
    return info["role"] if info else None


def has_permission(telegram_id: int, permission: str) -> bool:
    role = get_role(telegram_id)
    if not role:
        return False
    return permission in ROLE_PERMISSIONS.get(role, set())
