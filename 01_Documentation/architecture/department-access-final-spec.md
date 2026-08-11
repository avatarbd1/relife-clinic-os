# Department Access, Dental Scope, and Cash Custody — Final Specification

**Status:** Approved for implementation  
**Approved:** 2026-08-11  
**Repository:** `avatarbd1/relife-clinic-os`  
**Implementation policy:** Small, reviewable pull requests; controlled rollout; no big-bang rewrite.

## 1. Purpose

Relife Clinic OS must support Physio and Dental as separate operational departments while preserving shared business records where appropriate. Department scope and role permissions are independent dimensions. Every data access path must use one centralized, fail-closed authorization layer.

This document is the canonical implementation specification for department isolation, Dental roles and records, clinical permissions, finance visibility, cash custody, migration, dashboards, and rollout.

## 2. Core model

### 2.1 Standard department values

Only these normalized values are valid:

- `Physio`
- `Dental`
- `All`

`All` is an explicit scope and must not be inferred from a missing or blank value.

### 2.2 Role and department are separate dimensions

Do not create a `Dental_Manager` role.

Examples:

| Role | Department |
|---|---|
| Manager | Physio |
| Manager | Dental |
| Receptionist | Physio or Dental |
| Dentist | Dental |
| Dental_Assistant | Dental |
| Owner | All |

New roles:

- `Dentist`
- `Dental_Assistant`

Owner has explicit `All` department scope. System Admin does not automatically receive clinical access.

### 2.3 Staff fields and mapping

Add these fields to `08_Staff`:

- `Primary_Department`
- `Department_Access`
- `Clinical_Write_Scope`
- `Financial_Access`

A staff member who works in multiple departments must be represented through a `Staff_Department_Access` mapping tab. Authorization must not depend on comma-separated free text.

The mapping tab is the authoritative source for multi-department access. Any summary field in `08_Staff` is informational or cached only and must not weaken the mapping-based decision.

## 3. Centralized authorization and scope layer

All reads and writes must follow one shared pipeline:

```text
current staff
    ↓
allowed departments
    ↓
scoped patient/appointment/payment/report query
    ↓
role-specific permission
```

The centralized layer must protect:

- patient search and list operations;
- callbacks;
- reports;
- direct Patient ID and other direct record-ID lookups;
- create, update, append, void, and approval flows;
- background jobs and exported data.

Menu visibility is not a security boundary. A hidden menu must not allow access through a callback payload, stale keyboard, guessed ID, or direct command.

### 3.1 Fail-closed rules

- Missing Department on a protected record → do not show the data.
- Department mismatch → access denied.
- Owner → explicit `All` scope.
- System Admin → no clinical access unless separately and explicitly granted under an approved clinical role/scope.
- Unknown role, unknown department, missing staff mapping, malformed callback scope, or unresolved record scope → deny access and record an audit event.
- No query may silently fall back to unscoped data.

Authorization must validate both department scope and role permission. Department access alone is insufficient for a write.

## 4. Records requiring Department

Department is mandatory on:

- staff access mapping;
- Patients;
- Appointments;
- Daily Visits;
- Invoices;
- Payments;
- Treatments;
- Assessments;
- Treatment Plans;
- Packages;
- Expenses;
- Cash Movements;
- Inventory;
- Inventory Log;
- Reports;
- Dental-specific records;
- audit and void records.

Existing treatment notes remain append-only. Every new note must store Department and author identity, and write authorization must be validated against department plus author/assignment rules. Other staff members' notes must not be overwritten or edited.

Shared core records must preserve Department throughout creation, lookup, updates, callbacks, reporting, audit, and downstream derived records.

## 5. Clinical permissions

### 5.1 Therapist (Physio)

A Therapist may:

- read all Physio clinical data;
- write a note only for a patient assigned to that therapist or explicitly cross-covered by that therapist for the current day;
- view package/session remaining and payment-clearance status.

A Therapist may not:

- overwrite or edit another author's note;
- see financial amounts;
- see any Dental data.

Cross-cover authorization must be explicit, date-bound, auditable, and fail closed when absent or expired.

### 5.2 Dentist (Dental)

The same rules apply within Dental scope:

- read all Dental clinical data;
- write only for assigned or explicitly current-day cross-covered patients;
- never overwrite or edit another author's note;
- financial amounts hidden;
- package/session remaining and payment-clearance status visible;
- Physio clinical data inaccessible.

### 5.3 Dental Assistant

Dental Assistant permissions must be explicitly allowlisted. Department membership alone does not grant Dentist-equivalent clinical write access. The implementation PR for this role must define its exact allowed actions and tests before enabling production access.

## 6. Department-aware finance and cash custody

### 6.1 Shared finance records

Invoices and Payments remain shared core tabs but require Department. Department must propagate from the authorized patient/visit/service context and must be validated; it must not be accepted blindly from user-provided callback data.

Therapists and Dentists see clearance state and remaining sessions, not monetary amounts, unless an explicit financial permission grants more.

### 6.2 Cash Movement fields

Add:

- `Department`
- `From_Custodian_ID`
- `From_Staff_ID`
- `To_Custodian_ID`
- `Requested_Amount`
- `Received_Amount`
- `Difference`
- `Status`
- `Accepted_By`
- request, acceptance, completion, and update timestamps as applicable.

### 6.3 Custodians

Maintain distinct custody accounts:

- Physio Reception Cash
- Dental Reception Cash
- Home Treasury
- Digital/Bank

Reception-to-Home-Treasury movement is a cash transfer, not an expense.

Owner may see combined totals, but every balance and movement must retain its source Department. Combined reporting must be computed from department-preserving records, never by erasing or rewriting the source scope.

Requested and received values must be retained separately. Difference and status changes must be auditable.

## 7. Dental records

Create these Dental-specific tabs:

- `Dental_Procedures`
- `Dental_Tooth_Chart`
- `Dental_Treatment_Plans`
- `Dental_Lab_Orders`
- `Dental_Material_Usage`

The following remain shared core tabs with mandatory Department filtering:

- Patients
- Appointments
- Daily Visits
- Invoices
- Payments

All Dental-specific records must carry Department and the relevant shared-core reference IDs. They must pass the same centralized scope and role checks as shared records.

## 8. Owner dashboards

Provide three explicit views:

- 🩺 Physio Dashboard
- 🦷 Dental Dashboard
- 🏢 Combined Business Summary

The combined view may show department totals and business-level comparisons. It must not merge or expose patient clinical details across departments.

Every displayed total must be traceable back to department-preserving source records.

## 9. Migration and enforcement

Migration must run in this sequence:

1. Create a full backup and schema snapshot.
2. Establish the standard Department values.
3. Map staff departments and access.
4. Normalize existing Patient departments.
5. Backfill Appointment and Payment Department through patient references.
6. Match Treatment, Assessment, and Package ownership.
7. Send ambiguous rows to an `Unclassified` review queue.
8. Never automatically classify an ambiguous record as Physio or Dental.
9. Reconcile row counts, billed totals, collections, and dues.
10. Do not enable enforcement until the Unclassified queue reaches zero.
11. After enforcement is enabled, missing Department fails closed.

Migration tooling must be idempotent or safely restartable, produce a reviewable report, and preserve source values needed for audit and rollback. Reconciliation results must be approved before enforcement.

No live migration may proceed without a verified backup, schema snapshot, dry-run output, and rollback plan.

## 10. Final build sequence

1. Schema and migration tooling
2. Standard department model
3. Staff department access
4. Centralized authorization/filter layer
5. Department propagation across core records
6. Physio clinical permissions
7. Dental roles and clinical tabs
8. Department-aware invoice/payment
9. Department-aware cash custody
10. Owner dashboards
11. Menu redesign
12. Security, tenant-isolation, and migration tests
13. Live sheet migration
14. PR, CI, and controlled rollout

Each step must be delivered through a small, reviewable PR with focused tests and explicit compatibility notes.

## 11. First implementation PR

**Title/scope:** Department Schema + Central Access Foundation

This PR must:

- define normalized department constants and validation;
- add or prepare the staff access model and mapping contract;
- introduce the centralized authorization/filter interface;
- implement fail-closed primitives and audit-ready denial reasons;
- add characterization and unit tests for department scope, direct-ID access, callbacks, Owner `All`, System Admin non-clinical behavior, unknown/missing scope, and role/department separation;
- preserve existing menu behavior;
- avoid wiring an incomplete enforcement path into live production queries;
- include migration dry-run/schema tooling only where it cannot mutate live sheets by default.

This PR must not:

- redesign menus;
- perform the live sheet migration;
- automatically classify ambiguous records;
- enable global enforcement before migration reconciliation;
- introduce `Dental_Manager`;
- grant System Admin clinical access;
- expose a partially migrated dataset through permissive fallbacks.

## 12. Test and review gates

Before controlled rollout, tests must cover at minimum:

- missing Department denied;
- mismatched Department denied;
- direct ID and callback bypass attempts denied;
- stale or forged callback scope denied;
- Owner explicit `All` behavior;
- System Admin denied clinical access;
- Therapist Physio-only reads and assignment/cross-cover writes;
- Dentist Dental-only reads and assignment/cross-cover writes;
- author-based append-only note protection;
- hidden financial amounts with visible clearance/session status;
- department propagation across shared records;
- department-preserving cash transfers and reconciliation;
- unclassified migration behavior;
- cross-tenant and cross-department isolation;
- pre-existing menu behavior remains unchanged in PR 1.

CI must pass. Production-impacting rollout remains controlled and must not bypass the existing owner confirmation/governance gate.

## 13. Architectural invariants

These rules are non-negotiable:

1. Role and Department remain separate.
2. Missing scope never broadens access.
3. Every protected lookup uses the centralized layer.
4. Callback/menu state is never trusted as authorization.
5. Shared tabs always retain Department.
6. Combined totals never erase source Department.
7. Clinical writes require department plus role plus assignment/cross-cover validation.
8. Treatment notes remain append-only and author-protected.
9. Ambiguous migration data remains Unclassified until reviewed.
10. Enforcement starts only after reconciliation and zero Unclassified records.
