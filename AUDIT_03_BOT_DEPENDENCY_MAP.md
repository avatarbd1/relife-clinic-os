# 03_Bot Production Dependency Map — Audit v3

Branch: `audit/prod-rnd-separation`
Date: 2026-08-09
Scope: Read-only dependency audit of GitHub `main` before any repository separation. Audit notes are committed only on this branch; production files remain untouched.

## Executive conclusion

`03_Bot/` is the operational application core. All modules directly imported by `bot.py` have now been mapped at a first dependency level and are confirmed production runtime components. No production files should be moved.

A critical finding remains: GitHub `main` does **not** yet contain the newer module-splitting/relevance-routing implementation described from the laptop session. On `main`, `clinical_ai.py` still loads `clinical_conditions/core_modules.md`, and `split_core_modules.py` still extracts only Modules 3, 4 and 7. Laptop-side changes must therefore be treated as uncommitted/unverified until they appear in GitHub.

## Verified production-core entry point

`03_Bot/bot.py` directly imports:

- `config`
- `sheets`
- `roles`
- `calendar_helper`
- `staff_ai_query`
- `case_study_ai`
- `photo_extract`
- `text_extract`
- `intent_router`
- `ai_helper`
- `assessment_defs`
- `clinical_ai`
- `learning.learning_engine`

All are classified `KEEP_PRODUCTION`.

## Direct dependency chains

### Data/storage

`bot.py` → `sheets.py` → `config.py` + `data_contract.py` → Google Sheets + Google service account

Classification:
- `03_Bot/sheets.py` → `KEEP_PRODUCTION`
- `03_Bot/data_contract.py` → `KEEP_PRODUCTION`
- `03_Bot/config.py` → `KEEP_PRODUCTION`
- Google credentials/env contract → `KEEP_PRODUCTION_RUNTIME`

### Role/menu/access control

`bot.py` → `roles.py`

`roles.py` defines `OWNER`, `RECEPTIONIST`, `THERAPIST`, and `MANAGER`, menu visibility, access checks, and patient-action permissions.

Classification:
- `03_Bot/roles.py` → `KEEP_PRODUCTION`

### Appointment calendar UI

`bot.py` → `calendar_helper.py` → `python-telegram-bot` inline keyboard types

`calendar_helper.py` builds live Telegram calendar controls used by the appointment flow.

Classification:
- `03_Bot/calendar_helper.py` → `KEEP_PRODUCTION`

### Staff AI query

`bot.py` → `staff_ai_query.py` → `config.py` + `sheets.py` → live Google Sheet records → Groq selector → OpenRouter response

Classification:
- `03_Bot/staff_ai_query.py` → `KEEP_PRODUCTION`

### Case-study learning AI

`bot.py` → `case_study_ai.py` → OpenRouter API

This is a live bot learning/clinical-education feature. It is not an external R&D notebook; it is called from the production bot.

Classification:
- `03_Bot/case_study_ai.py` → `KEEP_PRODUCTION`
- OpenRouter key/network contract → `KEEP_PRODUCTION_RUNTIME`

### Patient photo extraction

`bot.py` → `photo_extract.py` → Groq vision-compatible API call

It extracts registration fields from uploaded patient documents/images. That makes it part of production patient-registration workflow.

Classification:
- `03_Bot/photo_extract.py` → `KEEP_PRODUCTION`
- Groq key/network contract → `KEEP_PRODUCTION_RUNTIME`

### Patient free-text extraction

`bot.py` → `text_extract.py` → Groq text model

It extracts structured registration fields from staff-entered free text.

Classification:
- `03_Bot/text_extract.py` → `KEEP_PRODUCTION`

### Generic AI structured-data helper

`bot.py` → `ai_helper.py` → Groq

It parses natural-language payment/register-style input into structured values used by live bot flows.

Classification:
- `03_Bot/ai_helper.py` → `KEEP_PRODUCTION`

### Assessment definitions

`bot.py` → `assessment_defs.py`

`assessment_defs.py` contains live clinical assessment categories, test definitions, button options, normal-range/help text, and the data model used by the treatment-plan assessment flow.

Classification:
- `03_Bot/assessment_defs.py` → `KEEP_PRODUCTION`

Governance note: this is runtime-critical **and** clinically sensitive. It should remain in production, but its clinical content needs evidence/governance review separately from repository migration.

### Daily learning engine

`bot.py` → `learning/learning_engine.py` → `config.py` + `sheets.py` + `learning.tip_bank` + `learning.quiz_bank`

The learning engine persists progress in `18_Learning_Progress` via `sheets.py`, so the entire supporting learning package is a production dependency.

Classification:
- `03_Bot/learning/learning_engine.py` → `KEEP_PRODUCTION`
- `03_Bot/learning/tip_bank.py` → `KEEP_PRODUCTION`
- `03_Bot/learning/quiz_bank.py` → `KEEP_PRODUCTION`
- `03_Bot/learning/` package → `KEEP_PRODUCTION`

### Natural-language menu routing

`bot.py` → `intent_router.py` → Groq API

Classification:
- `03_Bot/intent_router.py` → `KEEP_PRODUCTION`

### Clinical AI

Current GitHub `main` chain:

`bot.py`
→ `clinical_ai.get_clinical_guidance(case_text)`
→ `03_Bot/clinical_conditions/index.json`
→ condition files under `03_Bot/clinical_conditions/`
→ `03_Bot/clinical_conditions/core_modules.md`
→ Groq selector
→ OpenRouter guidance

Classification:
- `03_Bot/clinical_ai.py` → `KEEP_PRODUCTION`
- `03_Bot/clinical_conditions/` → `KEEP_PRODUCTION`
- `03_Bot/clinical_conditions/core_modules.md` → `KEEP_PRODUCTION` in current main state

## Verified external/runtime dependencies

Production requires at least:

- Python runtime
- `python-telegram-bot`
- `gspread`
- `google-auth`
- `requests`
- environment variables / `.env`
- Telegram `BOT_TOKEN`
- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDENTIALS_PATH` or configured default credentials file
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- network access to Telegram, Google APIs, Groq, and OpenRouter

This is still not a complete deploy/package inventory; deployment files and requirements remain to be mapped.

## Clinical manual relationship

`03_Bot/split_core_modules.py` reads `clinical-manual/Relife-Physiotherapy-Clinical-Manual.md` and generates `03_Bot/clinical_conditions/core_modules.md`.

Classification:
- `clinical-manual/` → `KEEP_SHARED` during migration analysis; future `MOVE_CLINICAL_KNOWLEDGE` candidate
- `03_Bot/clinical_conditions/*` used at runtime → `KEEP_PRODUCTION`
- split/generation scripts → `KEEP_SHARED` temporarily; may later move to a knowledge/build repo after a reproducible artifact boundary exists

## Critical state mismatch: laptop report vs GitHub main

Laptop-side report claimed:
- all 10 Part A modules split under `03_Bot/clinical_conditions/modules/`
- modules `index.json`
- removal of `core_modules.md`
- combined condition+module relevance selection
- forced M7 inclusion

Audited GitHub `main` still has:
- active `CORE_MODULES_PATH`
- `_load_core_modules_text()`
- condition-only selector
- `split_core_modules.py` limited to Modules 3, 4, 7
- existing `core_modules.md`

Status: **laptop changes are not present on GitHub main as of this audit.**

## Current classification

| Path / component | Classification | Reason |
|---|---|---|
| `03_Bot/bot.py` | KEEP_PRODUCTION | Main runtime entry point |
| `03_Bot/config.py` | KEEP_PRODUCTION | Secrets/config and sheet mapping |
| `03_Bot/sheets.py` | KEEP_PRODUCTION | Production data-access layer |
| `03_Bot/data_contract.py` | KEEP_PRODUCTION | Unified record metadata |
| `03_Bot/roles.py` | KEEP_PRODUCTION | Live role/menu/access control |
| `03_Bot/calendar_helper.py` | KEEP_PRODUCTION | Live appointment UI helper |
| `03_Bot/staff_ai_query.py` | KEEP_PRODUCTION | Live staff data/AI feature |
| `03_Bot/case_study_ai.py` | KEEP_PRODUCTION | Live learning/education feature |
| `03_Bot/photo_extract.py` | KEEP_PRODUCTION | Live patient image extraction |
| `03_Bot/text_extract.py` | KEEP_PRODUCTION | Live patient text extraction |
| `03_Bot/intent_router.py` | KEEP_PRODUCTION | Live NL menu routing |
| `03_Bot/ai_helper.py` | KEEP_PRODUCTION | Live structured-data helper |
| `03_Bot/assessment_defs.py` | KEEP_PRODUCTION | Live clinical assessment definitions |
| `03_Bot/learning/` | KEEP_PRODUCTION | Runtime learning engine + content banks |
| `03_Bot/clinical_ai.py` | KEEP_PRODUCTION | Runtime clinical assistant |
| `03_Bot/clinical_conditions/` | KEEP_PRODUCTION | Runtime clinical retrieval corpus |
| `03_Bot/split_core_modules.py` | KEEP_SHARED (temporary) | Build/regeneration tool |
| `clinical-manual/` | KEEP_SHARED → candidate MOVE_CLINICAL_KNOWLEDGE | Source used to generate runtime knowledge artifacts |
| `15_AI_Brain/` | candidate MOVE_AI_LAB | Dev automation/orchestration layer |
| `15_BrainOS/` | candidate MOVE_AI_LAB | Task/runtime orchestration layer |
| BrainOS generated runtime state | MOVE_AI_LAB / runtime-only | Not production application source |

## Next audit steps before any move

1. Map root-relative paths, `.env`, credential, and filesystem assumptions in `03_Bot`.
2. Map deployment entry points and CI that reference `03_Bot` or root files.
3. Inspect root requirements/deploy files to determine what must stay with production.
4. Compare laptop/working changes with GitHub `main`; preserve them before repo surgery.
5. Produce final `KEEP / MOVE / ARCHIVE` inventory.
6. Only then create destination repos and migration PRs.

## Safety gate

Until the dependency map is complete:
- no deletion from `main`
- no relocation of `03_Bot`
- no production deploy-path change
- no removal of `core_modules.md` from main unless replacement code is committed and tested
- no BrainOS migration that breaks Confirm Gate relationship with production changes
