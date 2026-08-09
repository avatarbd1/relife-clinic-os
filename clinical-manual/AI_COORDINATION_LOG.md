# AI Coordination Log — Relife Clinical Manual Reconstruction

> **Purpose:** This file lets any AI assistant (Claude, ChatGPT, or another) working on `clinical-manual/Relife-Physiotherapy-Clinical-Manual.md` self-orient at the start of a session—without the owner needing to re-explain status. Read this file **before** touching the manual or its Progress Tracker.

**Owner:** Esmail (Relife Physiotherapy Centre)  
**Repository:** `avatarbd1/relife-clinic-os`  
**Working branch:** `agent/clinical-manual-governance`  
**Pull request:** #5 (Draft — “Establish clinical manual governance and evidence-audit baseline”)

---

## How this file works

1. Before starting work, read the Claims Log to avoid duplicate or conflicting edits.
2. Before starting a new module/condition, add a row with AI name, section, date/time and status `IN PROGRESS`.
3. After finishing a batch, update the row to `DONE` with a one-line summary and commit SHA—or identify an unmerged delivery precisely.
4. If an AI cannot write to GitHub, it must deliver its patch/file and report the exact base commit. Work is not considered merged until an AI with repository access verifies and commits it.
5. Never mark a section `DONE` unless the actual manual content was verifiably changed. `DONE` means the claimed editing batch landed; it does **not** mean clinical approval.
6. Clinical evidence/approval status is recorded only in the manual Progress Tracker and section audit notes.
7. When a claim is corrected for safety or accuracy, replace the unsafe live text and explain the correction in the commit/PR. Git history preserves the old version; do not leave hazardous instructions in the live manual merely as strikethrough text.

---

## Claims Log

| Date | AI | Section | Status | Summary | Commit / Delivery |
|---|---|---|---|---|---|
| 2026-08-09 | ChatGPT | Document governance baseline | DONE | Draft warning, Markdown source-of-truth, RAG boundary and evidence vocabulary | `7fcaa3e` |
| 2026-08-09 | ChatGPT | Module 1.2 (Serious-Pathology Screening) | DONE | Rewrote red-flag table, escalation rule and cervical vascular caution | `d8a78d7` |
| 2026-08-09 | ChatGPT | Module 7 (Contraindications/Precautions) | DONE | Added three-level decision framework and DVT/pregnancy/cancer screens | `ee5f942` |
| 2026-08-09 | ChatGPT | Module 6 (Dry Needling) | DONE | Needling gated; not authorized pending Bangladesh scope and competency verification | `83a8830` |
| 2026-08-09 | ChatGPT | Module 5 (Electrotherapy) | DONE | Generic parameters withdrawn; exact-device IFU and authorization gate added | `2a022b4` |
| 2026-08-09 | ChatGPT | Module 3 (Manual Therapy) | DONE | Cervical HVLA prohibited; generic technique dosage withdrawn; tracker made truthful | `35b4de4`, `fea1e07` |
| 2026-08-09 | Claude | B8 electrotherapy/acupuncture subsections (pre-governance baseline) | SUPERSEDED / NOT MERGED | Owner reports sandbox-only work predating the governance baseline; requires re-audit | Not pushed |
| 2026-08-09 | Claude | Module 9 (Outcome Measures) | OWNER-REPORTED / NOT MERGED | Owner reports ODI/NDI MCID corrections in a download; content and citations have not been verified or merged on this branch | Download/base commit not yet supplied |
| 2026-08-09 | ChatGPT | Module 2 (Clinical Management) | DONE | Withdrew fixed phase/session/reassessment recipes; added shared-decision, monitoring, AI verification and escalation gates | `5781855` |

## Next Available Sections

- Module 4: Exercise Prescription Library
- Module 8: Differential Diagnosis Matrices
- Module 9: all unmerged content; eight remaining instruments reported unverified
- Module 10: Home Exercise Program Templates
- Part B: B1–B30 all require governance-era condition-level audit; any pre-baseline work must be rechecked

## Rules All AIs Must Follow

- Preserve audited content unless new evidence or a safety issue requires correction. When correction is required, make it explicit in the commit and coordination log.
- Never fabricate a citation, DOI, guideline, quotation or statistic.
- Unverified claims receive `EVIDENCE NOT VERIFIED — CLINICAL REVIEW REQUIRED`.
- Bangladesh-specific legal/scope claims remain `LOCAL POLICY — APPROVAL REQUIRED` until checked against an authoritative local source.
- No AI may mark a module or condition clinically approved. Named human clinical review and sign-off are required.
- Work for this reconstruction stays on `agent/clinical-manual-governance`; PR #5 remains Draft until its stated gates are satisfied.
- The Markdown manual is the sole master source. DOCX/PDF files are derivative outputs only.
- The whole manual must not be sent to a production AI API; future production retrieval is limited to approved, traceable Condition Cards.
