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


@dataclass(frozen=True)
class DepartmentRoleAssignment:
    """One active role held by a staff member inside one department."""

    staff_id: str
    department: Department
    role: Role


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
    """Resolve department scope from explicit assignments, fail closed on migration gaps."""
    if not staff:
        return frozenset()
    mapping_rows = list(mappings)
    assignments = effective_assignments(staff, mapping_rows)
    if assignments:
        return frozenset(assignment.department for assignment in assignments)
    if mapping_rows:
        return frozenset()

    # Compatibility only for isolated legacy callers with no mapping rows.
    role = normalize_role(staff.get("Role"))
    primary = normalize_department(staff.get("Primary_Department"))
    if role is Role.OWNER and primary is Department.ALL:
        return frozenset({Department.ALL})
    if primary in {Department.PHYSIO, Department.DENTAL}:
        return frozenset({primary})
    return frozenset()


def effective_assignments(
    staff: Mapping[str, object] | None,
    mappings: Iterable[Mapping[str, object]] = (),
) -> frozenset[DepartmentRoleAssignment]:
    """Resolve active department-role tuples from the authoritative mapping.

    A role stored only on 08_Staff is not an assignment. Mapping rows without
    an explicit valid Role fail closed so migration cannot accidentally grant
    global access.
    """
    if not staff:
        return frozenset()
    staff_id = str(staff.get("Staff_ID", "")).strip()
    if not staff_id:
        return frozenset()

    resolved: set[DepartmentRoleAssignment] = set()
    for row in mappings:
        if str(row.get("Staff_ID", "")).strip() != staff_id:
            continue
        if str(row.get("Status", "Active")).strip().casefold() != "active":
            continue
        department = normalize_department(row.get("Department"))
        role = normalize_role(row.get("Role"))
        if department is None or role is None:
            continue
        if department is Department.ALL and role is not Role.OWNER:
            continue
        resolved.add(DepartmentRoleAssignment(staff_id, department, role))
    return frozenset(resolved)


def roles_for_department(
    staff: Mapping[str, object] | None,
    department: object,
    mappings: Iterable[Mapping[str, object]] = (),
) -> frozenset[Role]:
    """Return roles explicitly assigned inside department (or explicit All owner)."""
    target = normalize_department(department)
    if target is None:
        return frozenset()
    roles: set[Role] = set()
    for assignment in effective_assignments(staff, mappings):
        if assignment.department is target:
            roles.add(assignment.role)
        elif (
            assignment.department is Department.ALL
            and assignment.role is Role.OWNER
        ):
            roles.add(Role.OWNER)
    return frozenset(roles)


def has_department_role(
    staff: Mapping[str, object] | None,
    department: object,
    role: object,
    mappings: Iterable[Mapping[str, object]] = (),
) -> bool:
    """Fail-closed check for one explicit department-role tuple."""
    expected_role = normalize_role(role)
    if expected_role is None:
        return False
    return expected_role in roles_for_department(staff, department, mappings)


def _authorize_role_for_record(
    staff: Mapping[str, object],
    role: Role,
    department: Department,
    action: AccessAction,
    *,
    assigned_or_cross_cover: bool,
    author_id: object,
) -> AccessDecision:
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
    assistant_support_scope = (
        clinical_scope == "dental_assistant_support_no_independent_write"
    )

    if role is Role.RECEPTIONIST and clinical:
        if not (
            assistant_support_scope
            and department is Department.DENTAL
            and action is AccessAction.CLINICAL_READ
        ):
            return AccessDecision(False, DenialReason.ROLE_FORBIDDEN.value, department)
    if role is Role.DENTAL_ASSISTANT and action is AccessAction.CLINICAL_WRITE:
        return AccessDecision(False, DenialReason.ROLE_FORBIDDEN.value, department)
    if (
        role is Role.MANAGER
        and action is AccessAction.CLINICAL_WRITE
        and not manager_therapist_scope
    ):
        return AccessDecision(False, DenialReason.ROLE_FORBIDDEN.value, department)

    clinical_writer = role in {Role.THERAPIST, Role.DENTIST} or (
        role is Role.MANAGER and manager_therapist_scope
    )
    if action is AccessAction.CLINICAL_WRITE and clinical_writer:
        if not assigned_or_cross_cover:
            return AccessDecision(
                False, DenialReason.ASSIGNMENT_REQUIRED.value, department
            )
        existing_author = str(author_id or "").strip()
        staff_id = str(staff.get("Staff_ID", "")).strip()
        if existing_author and existing_author != staff_id:
            return AccessDecision(False, DenialReason.AUTHOR_MISMATCH.value, department)

    return AccessDecision(True, "allowed", department)


def authorize_record(
    staff: Mapping[str, object] | None,
    record: Mapping[str, object],
    action: AccessAction,
    mappings: Iterable[Mapping[str, object]] = (),
    *,
    assigned_or_cross_cover: bool = False,
    author_id: object = None,
) -> AccessDecision:
    """Authorize a record against every explicit role in its department."""
    if not staff:
        return AccessDecision(False, DenialReason.STAFF_MISSING.value)

    raw_department = str(record.get("Department", "")).strip()
    if not raw_department:
        return AccessDecision(False, DenialReason.DEPARTMENT_MISSING.value)
    department = normalize_department(raw_department)
    if department not in {Department.PHYSIO, Department.DENTAL}:
        return AccessDecision(False, DenialReason.DEPARTMENT_UNKNOWN.value)

    mapping_rows = list(mappings)
    assignments = effective_assignments(staff, mapping_rows)
    if mapping_rows:
        if not assignments:
            return AccessDecision(
                False, DenialReason.STAFF_SCOPE_MISSING.value, department
            )
        effective_roles = roles_for_department(staff, department, mapping_rows)
        if not effective_roles:
            return AccessDecision(
                False, DenialReason.DEPARTMENT_MISMATCH.value, department
            )
    else:
        raw_role = str(staff.get("Role", "")).strip()
        if not raw_role:
            return AccessDecision(False, DenialReason.ROLE_MISSING.value)
        role = normalize_role(raw_role)
        if role is None:
            return AccessDecision(False, DenialReason.ROLE_UNKNOWN.value)
        scopes = allowed_departments(staff, ())
        if not scopes:
            return AccessDecision(
                False, DenialReason.STAFF_SCOPE_MISSING.value, department
            )
        if Department.ALL not in scopes and department not in scopes:
            return AccessDecision(
                False, DenialReason.DEPARTMENT_MISMATCH.value, department
            )
        effective_roles = frozenset({role})

    denials: list[AccessDecision] = []
    for role in effective_roles:
        decision = _authorize_role_for_record(
            staff,
            role,
            department,
            action,
            assigned_or_cross_cover=assigned_or_cross_cover,
            author_id=author_id,
        )
        if decision.allowed:
            return decision
        denials.append(decision)

    priority = {
        DenialReason.AUTHOR_MISMATCH.value: 0,
        DenialReason.ASSIGNMENT_REQUIRED.value: 1,
        DenialReason.ROLE_FORBIDDEN.value: 2,
        DenialReason.DEPARTMENT_MISMATCH.value: 3,
    }
    return min(
        denials,
        key=lambda decision: priority.get(decision.reason, 99),
        default=AccessDecision(
            False, DenialReason.ROLE_FORBIDDEN.value, department
        ),
    )

