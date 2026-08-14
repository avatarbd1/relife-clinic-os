"""Department and role authorization primitives for Relife Clinic OS."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

class Department(str, Enum):
    PHYSIO="Physio"; DENTAL="Dental"; ALL="All"
class Role(str, Enum):
    OWNER="Owner"; MANAGER="Manager"; RECEPTIONIST="Receptionist"; THERAPIST="Therapist"; DENTIST="Dentist"; DENTAL_ASSISTANT="Dental_Assistant"; AUDITOR="Auditor"; SYSTEM_ADMIN="System Admin"
class AccessAction(str, Enum):
    READ="read"; WRITE="write"; CLINICAL_READ="clinical_read"; CLINICAL_WRITE="clinical_write"; FINANCIAL_READ="financial_read"
class DenialReason(str, Enum):
    STAFF_MISSING="staff_missing"; ROLE_MISSING="role_missing"; ROLE_UNKNOWN="role_unknown"; DEPARTMENT_MISSING="department_missing"; DEPARTMENT_UNKNOWN="department_unknown"; STAFF_SCOPE_MISSING="staff_scope_missing"; DEPARTMENT_MISMATCH="department_mismatch"; ROLE_FORBIDDEN="role_forbidden"; ASSIGNMENT_REQUIRED="assignment_required"; AUTHOR_MISMATCH="author_mismatch"
@dataclass(frozen=True)
class AccessDecision:
    allowed: bool; reason: str; department: Department|None=None
@dataclass(frozen=True)
class DepartmentRoleAssignment:
    staff_id:str; department:Department; role:Role

def normalize_department(value):
    if isinstance(value,Department): return value
    return {"physio":Department.PHYSIO,"dental":Department.DENTAL,"all":Department.ALL}.get(str(value or "").strip().casefold())
def normalize_role(value):
    if isinstance(value,Role): return value
    text=str(value or "").strip().replace("-","_").replace(" ","_").casefold()
    return {"owner":Role.OWNER,"manager":Role.MANAGER,"receptionist":Role.RECEPTIONIST,"therapist":Role.THERAPIST,"dentist":Role.DENTIST,"dental_assistant":Role.DENTAL_ASSISTANT,"auditor":Role.AUDITOR,"system_admin":Role.SYSTEM_ADMIN,"systemadmin":Role.SYSTEM_ADMIN}.get(text)

def effective_assignments(staff,mappings=()):
    if not staff:return frozenset()
    sid=str(staff.get("Staff_ID","")).strip()
    if not sid:return frozenset()
    out=set()
    for row in mappings:
        if str(row.get("Staff_ID","")).strip()!=sid or str(row.get("Status","Active")).strip().casefold()!="active":continue
        dep=normalize_department(row.get("Department")); role=normalize_role(row.get("Role"))
        if dep is None or role is None or (dep is Department.ALL and role is not Role.OWNER):continue
        out.add(DepartmentRoleAssignment(sid,dep,role))
    return frozenset(out)

def allowed_departments(staff,mappings=()):
    if not staff:return frozenset()
    rows=list(mappings); assignments=effective_assignments(staff,rows)
    if assignments:return frozenset(a.department for a in assignments)
    if rows:return frozenset()
    role=normalize_role(staff.get("Role")); primary=normalize_department(staff.get("Primary_Department"))
    if role is Role.OWNER and primary is Department.ALL:return frozenset({Department.ALL})
    if primary in {Department.PHYSIO,Department.DENTAL}:return frozenset({primary})
    return frozenset()

def roles_for_department(staff,department,mappings=()):
    target=normalize_department(department)
    if target is None:return frozenset()
    out=set()
    for a in effective_assignments(staff,mappings):
        if a.department is target:out.add(a.role)
        elif a.department is Department.ALL and a.role is Role.OWNER:out.add(Role.OWNER)
    return frozenset(out)
def has_department_role(staff,department,role,mappings=()):
    expected=normalize_role(role); return expected is not None and expected in roles_for_department(staff,department,mappings)

def _temporary_dental_operational(staff,department):
    """Temporary migration/data-entry override; never crosses into Physio."""
    return department is Department.DENTAL and str(staff.get("Clinical_Write_Scope","")).strip().casefold()=="dental_temporary_full_operational" and str(staff.get("Financial_Access","")).strip().casefold()=="dental_operational"

def _authorize_role_for_record(staff,role,department,action,*,assigned_or_cross_cover,author_id):
    clinical=action in {AccessAction.CLINICAL_READ,AccessAction.CLINICAL_WRITE}
    if clinical and role in {Role.SYSTEM_ADMIN,Role.AUDITOR}:return AccessDecision(False,DenialReason.ROLE_FORBIDDEN.value,department)
    if role is Role.AUDITOR and action is AccessAction.WRITE:return AccessDecision(False,DenialReason.ROLE_FORBIDDEN.value,department)
    if role is Role.THERAPIST:
        if department is not Department.PHYSIO:return AccessDecision(False,DenialReason.DEPARTMENT_MISMATCH.value,department)
        if action is AccessAction.FINANCIAL_READ:return AccessDecision(False,DenialReason.ROLE_FORBIDDEN.value,department)
    if role is Role.DENTIST and department is not Department.DENTAL:return AccessDecision(False,DenialReason.DEPARTMENT_MISMATCH.value,department)

    # Explicit temporary Dental mode: receptionist/dentist/assistant can enter and
    # maintain Dental operational data, including Dental financial records.
    # Department authorization is resolved before this function, so Physio remains closed.
    if _temporary_dental_operational(staff,department) and role in {Role.RECEPTIONIST,Role.DENTIST,Role.DENTAL_ASSISTANT,Role.MANAGER}:
        return AccessDecision(True,"temporary_dental_operational",department)

    scope=str(staff.get("Clinical_Write_Scope","")).strip().casefold()
    manager_scope=scope=="assigned_or_today_cross_cover"
    assistant_scope=scope=="dental_assistant_support_no_independent_write"
    if role is Role.RECEPTIONIST and clinical:
        if not (assistant_scope and department is Department.DENTAL and action is AccessAction.CLINICAL_READ):return AccessDecision(False,DenialReason.ROLE_FORBIDDEN.value,department)
    if role is Role.DENTAL_ASSISTANT and action is AccessAction.CLINICAL_WRITE:return AccessDecision(False,DenialReason.ROLE_FORBIDDEN.value,department)
    if role is Role.MANAGER and action is AccessAction.CLINICAL_WRITE and not manager_scope:return AccessDecision(False,DenialReason.ROLE_FORBIDDEN.value,department)
    writer=role in {Role.THERAPIST,Role.DENTIST} or (role is Role.MANAGER and manager_scope)
    if action is AccessAction.CLINICAL_WRITE and writer:
        if not assigned_or_cross_cover:return AccessDecision(False,DenialReason.ASSIGNMENT_REQUIRED.value,department)
        existing=str(author_id or "").strip(); sid=str(staff.get("Staff_ID","")).strip()
        if existing and existing!=sid:return AccessDecision(False,DenialReason.AUTHOR_MISMATCH.value,department)
    return AccessDecision(True,"allowed",department)

def authorize_record(staff,record,action,mappings=(),*,assigned_or_cross_cover=False,author_id=None):
    if not staff:return AccessDecision(False,DenialReason.STAFF_MISSING.value)
    raw=str(record.get("Department","")).strip()
    if not raw:return AccessDecision(False,DenialReason.DEPARTMENT_MISSING.value)
    dep=normalize_department(raw)
    if dep not in {Department.PHYSIO,Department.DENTAL}:return AccessDecision(False,DenialReason.DEPARTMENT_UNKNOWN.value)
    rows=list(mappings); assignments=effective_assignments(staff,rows)
    if rows:
        if not assignments:return AccessDecision(False,DenialReason.STAFF_SCOPE_MISSING.value,dep)
        roles=roles_for_department(staff,dep,rows)
        if not roles:return AccessDecision(False,DenialReason.DEPARTMENT_MISMATCH.value,dep)
    else:
        raw_role=str(staff.get("Role","")).strip()
        if not raw_role:return AccessDecision(False,DenialReason.ROLE_MISSING.value)
        role=normalize_role(raw_role)
        if role is None:return AccessDecision(False,DenialReason.ROLE_UNKNOWN.value)
        scopes=allowed_departments(staff,())
        if not scopes:return AccessDecision(False,DenialReason.STAFF_SCOPE_MISSING.value,dep)
        if Department.ALL not in scopes and dep not in scopes:return AccessDecision(False,DenialReason.DEPARTMENT_MISMATCH.value,dep)
        roles=frozenset({role})
    denials=[]
    for role in roles:
        d=_authorize_role_for_record(staff,role,dep,action,assigned_or_cross_cover=assigned_or_cross_cover,author_id=author_id)
        if d.allowed:return d
        denials.append(d)
    priority={DenialReason.AUTHOR_MISMATCH.value:0,DenialReason.ASSIGNMENT_REQUIRED.value:1,DenialReason.ROLE_FORBIDDEN.value:2,DenialReason.DEPARTMENT_MISMATCH.value:3}
    return min(denials,key=lambda d:priority.get(d.reason,99),default=AccessDecision(False,DenialReason.ROLE_FORBIDDEN.value,dep))
