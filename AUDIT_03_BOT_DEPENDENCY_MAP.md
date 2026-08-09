# 03_Bot Production Dependency Map — Audit v4

Branch: `audit/prod-rnd-separation`
Date: 2026-08-09
Scope: Read-only dependency and deployment-boundary audit of GitHub `main` before repository separation. Audit notes are committed only on this branch; production files remain untouched.

## Executive conclusion

`03_Bot/` is the operational application core. All modules directly imported by `bot.py` have been mapped at a first dependency level and are production runtime components. The repository split should therefore leave `03_Bot/` intact and move only components proven to be development/R&D tooling.

A critical state mismatch remains: GitHub `main` does not yet contain the newer laptop-side clinical module-splitting/relevance-routing implementation. On `main`, `clinical_ai.py` still loads `clinical_conditions/core_modules.md`, and `split_core_modules.py` still extracts only Modules 3, 4 and 7. Laptop-side changes must be preserved and compared before any repository surgery.

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

## Verified production dependency chains

### Data/storage

`bot.py` → `sheets.py` → `config.py` + `data_contract.py` → Google Sheets + Google service account

Classification:
- `03_Bot/sheets.py` → `KEEP_PRODUCTION`
- `03_Bot/data_contract.py` → `KEEP_PRODUCTION`
- `03_Bot/config.py` → `KEEP_PRODUCTION`
- Google credentials/env contract → `KEEP_PRODUCTION_RUNTIME`

### Role/menu/access control

`bot.py` → `roles.py`

Classification:
- `03_Bot/roles.py` → `KEEP_PRODUCTION`

### Appointment calendar UI

`bot.py` → `calendar_helper.py` → `python-telegram-bot` inline keyboard types

Classification:
- `03_Bot/calendar_helper.py` → `KEEP_PRODUCTION`

### Staff AI query

`bot.py` → `staff_ai_query.py` → `config.py` + `sheets.py` → live Google Sheet records → Groq selector → OpenRouter response

Classification:
- `03_Bot/staff_ai_query.py` → `KEEP_PRODUCTION`

### Case-study learning AI

`bot.py` → `case_study_ai.py` → OpenRouter API

Classification:
- `03_Bot/case_study_ai.py` → `KEEP_PRODUCTION`

### Patient extraction helpers

`bot.py` → `photo_extract.py` → Groq vision-compatible API

`bot.py` → `text_extract.py` → Groq text model

Classification:
- `03_Bot/photo_extract.py` → `KEEP_PRODUCTION`
- `03_Bot/text_extract.py` → `KEEP_PRODUCTION`

### Generic AI structured-data helper

`bot.py` → `ai_helper.py` → Groq

Classification:
- `03_Bot/ai_helper.py` → `KEEP_PRODUCTION`

### Assessment definitions

`bot.py` → `assessment_defs.py`

Classification:
- `03_Bot/assessment_defs.py` → `KEEP_PRODUCTION`

Governance note: runtime-critical and clinically sensitive. Clinical claims/ranges/tests need evidence governance separately from repository migration.

### Daily learning engine

`bot.py` → `learning/learning_engine.py` → `config.py` + `sheets.py` + `learning.tip_bank` + `learning.quiz_bank`

Classification:
- entire `03_Bot/learning/` package → `KEEP_PRODUCTION`

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

## Deployment/runtime boundary audit

### Root Python dependency contract

`requirements.txt` exists on `main` and contains the packages required by the production bot stack, including at least:

- `python-telegram-bot>=21.4`
- `gspread>=6.1.0`
- `google-auth>=2.34.0`
- `requests>=2.32.0`
- `python-dotenv>=1.0.0`
- Google API/auth client packages
- Pydantic and supporting runtime packages

Classification:
- root `requirements.txt` → `KEEP_PRODUCTION`

Reason: it is a deploy/runtime dependency contract shared by the live bot. It must not be moved into an AI-lab repository unless production gets its own equivalent lock/requirements file first.

### Root deploy descriptors

Direct checks against GitHub `main` found:

- root `Procfile` → not present
- root `render.yaml` → not present

Therefore the current GitHub repository does not expose a verified root-level Render blueprint/Procfile deployment definition. This audit must not invent the actual deployment command. Render may be configured in the Render dashboard or through another file/path not yet identified.

Classification:
- no root Procfile/render.yaml can currently be classified because they do not exist on `main`
- actual deployment command/service settings → `UNVERIFIED_EXTERNAL_DEPLOY_CONFIG`

### README

The root README explicitly describes this repository as the complete Relife Clinic Management System with Telegram bot, patient management, billing, appointments, inventory, staff management, reports and owner dashboard.

Classification:
- root `README.md` → `KEEP_PRODUCTION` unless later replaced by a production-specific README after repo separation

### GitHub Actions / BrainOS CI boundary

Recent merged PR history confirms that the current CI added in PRs #1-#4 is specifically BrainOS safety/pipeline/runtime-hygiene CI. Those PRs explicitly state that `03_Bot/` remains protected by Confirm Gate and that BrainOS changes are development/orchestration concerns.

Classification:
- BrainOS-specific GitHub Actions/workflows → `MOVE_AI_LAB` candidate, but only after the exact workflow files and any shared production checks are separated
- any future production bot CI → `KEEP_PRODUCTION`

Do not move `.github/workflows/` wholesale. Workflow-level classification is required.

## Verified external/runtime dependencies

Production requires at least:

- Python runtime
- `python-telegram-bot`
- `gspread`
- `google-auth`
- `requests`
- `.env` / environment variables
- Telegram `BOT_TOKEN`
- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDENTIALS_PATH` or configured service-account path
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- network access to Telegram, Google APIs, Groq and OpenRouter

## Clinical manual relationship

`03_Bot/split_core_modules.py` reads `clinical-manual/Relife-Physiotherapy-Clinical-Manual.md` and generates `03_Bot/clinical_conditions/core_modules.md`.

Classification:
- `clinical-manual/` → `KEEP_SHARED` during migration analysis; future `MOVE_CLINICAL_KNOWLEDGE` candidate
- runtime `03_Bot/clinical_conditions/*` → `KEEP_PRODUCTION`
- split/generation scripts → `KEEP_SHARED` temporarily

Open draft PR #5 further supports separating clinical knowledge governance from runtime application code: it defines the manual as a draft source requiring claim-by-claim review and states that future production AI use should be through reviewed Condition Cards rather than sending the whole manual.

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

## Current KEEP / MOVE / HOLD inventory

| Path / component | Classification | Reason |
|---|---|---|
| `03_Bot/` runtime application | KEEP_PRODUCTION | Real clinic application core |
| root `requirements.txt` | KEEP_PRODUCTION | Production Python dependency contract |
| root `README.md` | KEEP_PRODUCTION | Repository currently documents real Clinic OS |
| production env/secrets contract | KEEP_PRODUCTION_RUNTIME | Required by bot/services |
| `clinical-manual/` | HOLD_SHARED → MOVE_CLINICAL_KNOWLEDGE candidate | Build/source knowledge with separate governance needs |
| `03_Bot/split_core_modules.py` and similar generation scripts | HOLD_SHARED | Build tooling until reproducible boundary exists |
| `15_AI_Brain/` | MOVE_AI_LAB candidate | Development automation/orchestration |
| `15_BrainOS/` | MOVE_AI_LAB candidate | Development task/runtime orchestration |
| BrainOS TaskInbox/cron/dispatcher tooling | MOVE_AI_LAB candidate | Dev automation, not clinic runtime |
| BrainOS-specific CI | MOVE_AI_LAB candidate | Protects dev automation layer |
| unknown Render dashboard/service settings | HOLD / EXTERNAL | Deployment settings not represented by verified root files |
| laptop-only unpushed changes | HOLD_PRESERVE_FIRST | Must be captured before repo split |

## Separation decision now supported by audit

The safest target architecture is:

1. `relife-clinic-os` remains the production source of truth containing `03_Bot/`, production dependencies, production deployment documentation/config, and production CI.
2. `relife-ai-lab` receives BrainOS/AI-development automation after workflow/interface mapping.
3. `relife-clinical-knowledge` may later receive the clinical manual and generation pipeline after a reproducible reviewed artifact boundary is created.
4. Production changes proposed by AI-lab must enter the production repo through review/Confirm Gate/PR; the lab must not become the production source of truth.

## Remaining gates before physical moves

1. Preserve and compare laptop-side unpushed clinical changes with GitHub `main`.
2. Identify the real Render/deploy service command and working directory from the live deployment configuration.
3. Classify each `.github/workflows/*` file individually into production vs BrainOS CI.
4. Map remaining root scripts that reference `15_AI_Brain`, `15_BrainOS`, or `03_Bot`.
5. Create destination repository only after these gates are recorded.
6. Migrate by copy-first, verify, then delete-from-source in a separate reviewed PR — never move/delete in one blind operation.

## Safety gate

Until the above gates are complete:
- no deletion from `main`
- no relocation of `03_Bot`
- no production deploy-path change
- no removal of `core_modules.md` from main unless replacement code is committed and tested
- no wholesale move of `.github/workflows/`
- no BrainOS migration that breaks Confirm Gate relationship with production changes
