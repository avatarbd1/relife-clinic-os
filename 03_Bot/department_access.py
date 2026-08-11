"""Department and role authorization primitives for Relife Clinic OS.

This module is intentionally side-effect free.  PR-1 establishes the access
contract without enabling enforcement in existing production query paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class Department(str, Enum):
    PHYSIO = "Physio"
    DENTAL = "Dental"
    ALL = "All"


class Role(str, Enum):
    OWNER = "Owner"
    MANAGER = "Manager"
    RECEPTIONIST = "Receptionist"
    THERAPIST = "Therapist"
    DENTIST = "Dentist"
    DENTAL_ASSISTANT = "Dental_Assistant"
    AUDITOR = "Auditor"
    SYSTEM_ADMIN = "System Admin"


class AccessAction(str, Enum):
    READ = "read"
    WRITE = "write"
    CLINICAL_READ = "clinical_read"
    CLINICAL_WRITE = "clinical_write"
    FINANCIAL_READ = "financial_read"


class DenialReason(str, Enum):
    STAFF_MISSING = "staff_missing"
    ROLE_MISSING = "role_missing"
    ROLE_UNKNOWN = "role_unknown"
    DEPARTMENT_MISSING = "department_missing"
    DEPARTMENT_UNKNOWN = "department_unknown"
    STAFF_SCOPE_MISSING = "staff_scope_missing"
    DEPARTMENT_MISMATCH = "department_mismatch"
    ROLE_FORBIDDEN = "role_forbidden"
    ASSIGNMENT_REQUIRED = "assignment_required"
    AUTHOR_MISMATCH = "author_mismatch"


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str
    department: Department | None = None


def normalize_department(value: object) -> Department | None:
    text = str(value or "").strip().casefold()
    return {
        "physio": Department.PHYSIO,
        "dental": Department.DENTAL,
        "all": Department.ALL,
    }.get(text)


def normalize_role(value: object) -> Role | None:
    text = str(value or "").strip().replace("-", "_").replace(" ", "_").casefold()
    return {
        "owner": Role.OWNER,
        "manager": Role.MANAGER,
        "receptionist": Role.RECEPTIONIST,
        "therapist": Role.THERAPIST,
        "dentist": Role.DENTIST,
        "dental_assistant": Role.DENTAL_ASSISTANT,
        "auditor": Role.AUDITOR,
        "system_admin": Role.SYSTEM_ADMIN,
        "systemadmin": Role.SYSTEM_ADMIN,
    }.get(text)


def allowed_departments(
    staff: Mapping[str, object] | None,
    mappings: Iterable[Mapping[str, object]] = (),
) -> frozenset[Department]:
    """Resolve department access from explicit owner scope or mapping rows.

    Multi-department access is mapping-based.  Department_Access in 08_Staff is
    deliberately not parsed as a comma-separated authorization source.
    """
    if not staff:
        return frozenset()
    role = normalize_role(staff.get("Role"))
    primary = normalize_department(staff.get("Primary_Department"))
    if role is Role.OWNER and primary is Department.ALL:
        return frozenset({Department.ALL})

    staff_id = str(staff.get("Staff_ID", "")).strip()
    resolved: set[Department] = set()
    for row in mappings:
        if str(row.get("Staff_ID", "")).strip() != staff_id:
            continue
        if str(row.get("Status", "Active")).strip().casefold() != "active":
            continue
        department = normalize_department(row.get("Department"))
        if department in {Department.PHYSIO, Department.DENTAL}:
            resolved.add(department)

    if not resolved and primary in {Department.PHYSIO, Department.DENTAL}:
        resolved.add(primary)
    return frozenset(resolved)


def authorize_record(
    staff: Mapping[str, object] | None,
    record: Mapping[str, object],
    action: AccessAction,
    mappings: Iterable[Mapping[str, object]] = (),
    *,
    assigned_or_cross_cover: bool = False,
    author_id: object = None,
) -> AccessDecision:
    """Return a fail-closed department and role decision for one record."""
    if not staff:
        return AccessDecision(False, DenialReason.STAFF_MISSING.value)
    raw_role = str(staff.get("Role", "")).strip()
    if not raw_role:
        return AccessDecision(False, DenialReason.ROLE_MISSING.value)
    role = normalize_role(raw_role)
    if role is None:
        return AccessDecision(False, DenialReason.ROLE_UNKNOWN.value)

    raw_department = str(record.get("Department", "")).strip()
    if not raw_department:
        return AccessDecision(False, DenialReason.DEPARTMENT_MISSING.value)
    department = normalize_department(raw_department)
    if department not in {Department.PHYSIO, Department.DENTAL}:
        return AccessDecision(False, DenialReason.DEPARTMENT_UNKNOWN.value)

    scopes = allowed_departments(staff, mappings)
    if not scopes:
        return AccessDecision(False, DenialReason.STAFF_SCOPE_MISSING.value, department)
    if Department.ALL not in scopes and department not in scopes:
        return AccessDecision(False, DenialReason.DEPARTMENT_MISMATCH.value, department)

    clinical = action in {AccessAction.CLINICAL_READ, AccessAction.CLINICAL_WRITE}
    if clinical and role in {Role.SYSTEM_ADMIN, Role.AUDITOR}:
        return AccessDecision(False, DenialReason.ROLE_FORBIDDEN.value, department)

    if role is Role.AUDITOR and action is AccessAction.WRITE:
        return AccessDecision(False, DenialReason.ROLE_FORBIDDEN.value, department)

    if role is Role.THERAPIST:
        if department is not Department.PHYSIO:
            return AccessDecision(False, DenialReason.DEPARTMENT_MISMATCH.value, department)
        if action is AccessAction.FINANCIAL_READ:
            return AccessDecision(False, DenialReason.ROLE_FORBIDDEN.value, department)
    if role is Role.DENTIST:
        if department is not Department.DENTAL:
            return AccessDecision(False, DenialReason.DEPARTMENT_MISMATCH.value, department)
        if action is AccessAction.FINANCIAL_READ:
            return AccessDecision(False, DenialReason.ROLE_FORBIDDEN.value, department)
    clinical_scope = str(staff.get("Clinical_Write_Scope", "")).strip().casefold()
    manager_therapist_scope = clinical_scope == "assigned_or_today_cross_cover"
    assistant_support_scope = clinical_scope == "dental_assistant_support_no_independent_write"

    if role is Role.RECEPTIONIST and clinical:
        if not (assistant_support_scope and department is Department.DENTAL and action is AccessAction.CLINICAL_READ):
            return AccessDecision(False, DenialReason.ROLE_FORBIDDEN.value, department)
    if role is Role.DENTAL_ASSISTANT and action is AccessAction.CLINICAL_WRITE:
        return AccessDecision(False, DenialReason.ROLE_FORBIDDEN.value, department)

    if role is Role.MANAGER and action is AccessAction.CLINICAL_WRITE and not manager_therapist_scope:
        return AccessDecision(False, DenialReason.ROLE_FORBIDDEN.value, department)

    if action is AccessAction.CLINICAL_WRITE and (
        role in {Role.THERAPIST, Role.DENTIST} or (role is Role.MANAGER and manager_therapist_scope)
    ):
        if not assigned_or_cross_cover:
            return AccessDecision(False, DenialReason.ASSIGNMENT_REQUIRED.value, department)
        existing_author = str(author_id or "").strip()
        staff_id = str(staff.get("Staff_ID", "")).strip()
        if existing_author and existing_author != staff_id:
            return AccessDecision(False, DenialReason.AUTHOR_MISMATCH.value, department)

    return AccessDecision(True, "allowed", department)
