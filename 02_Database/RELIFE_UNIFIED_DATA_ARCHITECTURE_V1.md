# Relife Unified Data Architecture v1

Status: foundation contract for Clinic OS, AI Brain, analytics, future SaaS and research exports.

## One data spine

`Organization -> Clinic -> Branch -> Patient -> Encounter -> Assessment/Plan/Treatment/Outcome`

Staff, appointments, finance, inventory, reports, learning and AI outputs attach to the same organization/clinic identity. Clinical records attach to Patient_ID, and encounter-level records use Encounter_ID.

## Identity rules

- Existing business IDs (`PT0001`, `AP0001`, `TR0001`, etc.) remain unchanged.
- `Record_ID` is namespaced by clinic, preventing collisions when multiple clinics are merged.
- Every domain record gains Organization_ID, Clinic_ID, Branch_ID and Schema_Version.
- Treatment rows gain a stable Encounter_ID derived from the existing Treatment_ID in v1.
- Staff identity should migrate toward Staff_ID/Provider_ID; display names are not durable identifiers.

## Provenance rules

Every migrated table can store Source_System, Source_Type, AI_Generated, Human_Verified and Provenance_Timestamp. Historical rows are backfilled as `legacy_record` and are **not** silently marked human-verified.

New bot-created records are marked human entry/verified by default. AI-produced content must explicitly set AI_Generated and should remain unverified until a person approves it.

## Domain map

| Domain | Current source | Stable link |
|---|---|---|
| Patient | 02_Patients | Patient_ID |
| Staff/provider | 08_Staff | Staff_ID / Provider_ID |
| Appointment | 04_Appointments | Appointment_ID + Patient_ID |
| Encounter/treatment | 05_Treatments | Treatment_ID + Encounter_ID + Patient_ID |
| Assessment | 10_Assessments | Assessment_ID + Patient_ID |
| Treatment plan | 12_Treatment_Plans | Plan_ID + Patient_ID |
| Reports | 14_Reports | Report_ID + Patient_ID |
| Case study | 15_Case_Studies | Case_Study_ID + Patient_ID |
| Payment/package | 06_Payments / 11_Packages | Patient_ID |
| Staff attendance/salary/learning | 03 / 13 / 18 | Staff_ID / Provider_ID |
| Expense/inventory | 07 / 09 / 17 | Clinic_ID |
| Consent | 19_Consent | Consent_ID + Patient_ID + Purpose |
| Audit | 20_Data_Audit | Entity_ID + Actor_ID |

## Migration policy

1. Never rename/delete legacy columns in v1.
2. Append unified metadata columns only.
3. Backfill deterministic identity fields; never invent clinical facts or consent.
4. Keep Google Sheets as the operational store until the schema is proven in the real clinic.
5. A future PostgreSQL migration should preserve all legacy IDs and this v1 envelope.

## AI boundary

AI Brain may read the unified data layer for analysis, but model output is not a clinical fact merely because it was generated. AI output must carry provenance and verification state. Research/secondary-use eligibility must be determined from explicit consent/governance rules, not inferred from routine treatment records.

## v1 success criteria

- Every new operational record is attributable to a clinic and record identity.
- Clinical encounters join reliably to the patient and treatment plan.
- AI vs human origin is distinguishable.
- Historical data is retained without claiming unrecorded consent or verification.
- The same structure can be exported to analytics/PostgreSQL and later mapped to interoperability standards without redesigning core identity.
