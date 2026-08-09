# 03_Bot Production Dependency Map — Audit v2

Branch: `audit/prod-rnd-separation`
Date: 2026-08-09
Scope: Read-only dependency audit of GitHub `main` before any repository separation. Audit notes are committed only on this branch; production files remain untouched.

## Executive conclusion

`03_Bot/` is the operational application core and must remain intact until all direct and indirect runtime dependencies are mapped. No production files should be moved yet.

A critical finding remains: GitHub `main` does **not** yet contain the newer module-splitting/relevance-routing implementation described from the laptop session. On `main`, `clinical_ai.py` still loads `clinical_conditions/core_modules.md`, and `split_core_modules.py` still extracts only Modules 3, 4 and 7. Laptop-side changes must therefore be treated as uncommitted/unverified until they appear in GitHub.

## Verified production-core entry point

`03_Bot/bot.py` imports these local modules directly:

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

All are `KEEP_PRODUCTION` until their own dependencies are mapped.

## Newly verified direct dependency chains

### 1. Data/storage chain

`bot.py`
→ `sheets.py`
→ `config.py`
→ Google service-account credentials + Google Sheet ID
→ `data_contract.py`
→ unified record metadata written into operational sheets

`03_Bot/sheets.py` is not a generic helper. It is the production data-access layer and explicitly centralizes Google Sheets reads/writes so the bot does not call `gspread` directly.

`03_Bot/data_contract.py` is also production-critical because `sheets.py` imports and uses its metadata functions when writing unified records.

Classification:

- `03_Bot/sheets.py` → `KEEP_PRODUCTION`
- `03_Bot/data_contract.py` → `KEEP_PRODUCTION`
- `03_Bot/config.py` → `KEEP_PRODUCTION`
- Google credentials/env contract → `KEEP_PRODUCTION_RUNTIME`

### 2. Role/authorization/menu chain

`bot.py`
→ `roles.py`
→ role-specific menus and access rules

`roles.py` defines `OWNER`, `RECEPTIONIST`, `THERAPIST`, and `MANAGER`, plus menu visibility, access checks, and patient-action permissions. It is part of the live authorization/navigation layer, not documentation or R&D.

Classification:

- `03_Bot/roles.py` → `KEEP_PRODUCTION`

### 3. Staff AI query chain

`bot.py`
→ `staff_ai_query.py`
→ `config.py` + `sheets.py`
→ live Google Sheet records
→ Groq for sheet selection
→ OpenRouter for response generation

`staff_ai_query.py` also applies role-based restrictions to sensitive sheet access, so it is both an AI feature and part of production access-control behavior.

Classification:

- `03_Bot/staff_ai_query.py` → `KEEP_PRODUCTION`
- Groq/OpenRouter keys used by this feature → `KEEP_PRODUCTION_RUNTIME`

### 4. Natural-language menu routing chain

`bot.py`
→ `intent_router.py`
→ Groq API

`intent_router.py` does not autonomously start a workflow. It only suggests the closest allowed menu item and requires the user to tap the real menu item before the workflow starts. This is live runtime behavior.

Classification:

- `03_Bot/intent_router.py` → `KEEP_PRODUCTION`

## Verified external/runtime dependencies

Production requires at least:

- Python runtime
- `python-telegram-bot`
- `gspread`
- `google-auth` service-account credentials
- `requests`
- environment variables / `.env`
- Telegram `BOT_TOKEN`
- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDENTIALS_PATH` or the configured default credentials file
- Groq API key for current AI features
- OpenRouter API key for current AI features
- network access to Telegram, Google APIs, Groq and OpenRouter

This is still not a complete package-level dependency inventory.

## Clinical AI dependency chain on GitHub main

Current `main` chain:

`bot.py`
→ `clinical_ai.get_clinical_guidance(case_text)`
→ `03_Bot/clinical_conditions/index.json`
→ one or more condition files under `03_Bot/clinical_conditions/`
→ `03_Bot/clinical_conditions/core_modules.md`
→ Groq selector call
→ OpenRouter guidance call

Therefore the following are currently `KEEP_PRODUCTION`:

- `03_Bot/clinical_ai.py`
- `03_Bot/clinical_conditions/index.json`
- condition files referenced by that index
- `03_Bot/clinical_conditions/core_modules.md`

## Clinical manual relationship

`03_Bot/split_core_modules.py` reads:

`clinical-manual/Relife-Physiotherapy-Clinical-Manual.md`

and generates:

`03_Bot/clinical_conditions/core_modules.md`

This means `clinical-manual/` is a **build/source dependency for regeneration**, but the inspected production `clinical_ai.py` does not directly read the whole manual at runtime.

Classification for now:

- `clinical-manual/` → `KEEP_SHARED` during migration analysis; candidate for future `MOVE_CLINICAL_KNOWLEDGE` only after a reproducible artifact-generation/import boundary is created.
- `03_Bot/clinical_conditions/*` used at runtime → `KEEP_PRODUCTION`.
- split/generation scripts → `KEEP_SHARED` temporarily; later may move to the knowledge/build repo if CI can regenerate and verify artifacts reproducibly.

## Critical state mismatch: laptop report vs GitHub main

The laptop-side report claimed:

- all 10 Part A modules split under `03_Bot/clinical_conditions/modules/`
- a modules `index.json`
- removal of `core_modules.md`
- combined condition+module relevance selection
- forced M7 inclusion

The audited GitHub `main` state currently shows instead:

- `clinical_ai.py` defines and loads `CORE_MODULES_PATH = clinical_conditions/core_modules.md`
- `_load_core_modules_text()` is active
- `_pick_relevant_conditions()` selects only conditions
- `split_core_modules.py` has `wanted = {3,4,7}`
- `core_modules.md` exists

Therefore:

**STATUS: laptop changes are not present on GitHub main as of this audit.**

Do not delete/move the old runtime artifacts based only on the laptop report.

## R&D / AI automation boundary

Based on repo audit and merged PR history:

- `15_AI_Brain/` → candidate `MOVE_AI_LAB`
- `15_BrainOS/` → candidate `MOVE_AI_LAB`
- BrainOS cron/task inbox/dispatcher tooling → candidate `MOVE_AI_LAB`

Migration must preserve a controlled interface if these tools are still expected to propose changes to the production repo. The production repo must remain the authority for deployable `03_Bot` code.

## Current classification

| Path / component | Classification | Reason |
|---|---|---|
| `03_Bot/bot.py` | KEEP_PRODUCTION | Main runtime entry point |
| `03_Bot/config.py` | KEEP_PRODUCTION | Secrets/config and operational sheet mapping |
| `03_Bot/sheets.py` | KEEP_PRODUCTION | Production data-access layer |
| `03_Bot/data_contract.py` | KEEP_PRODUCTION | Unified record metadata used by sheet writes |
| `03_Bot/roles.py` | KEEP_PRODUCTION | Live role/menu/access-control logic |
| `03_Bot/staff_ai_query.py` | KEEP_PRODUCTION | Live staff data/AI feature with access restrictions |
| `03_Bot/intent_router.py` | KEEP_PRODUCTION | Live natural-language menu suggestion helper |
| other local modules imported by `bot.py` | KEEP_PRODUCTION pending deeper audit | Direct runtime dependency |
| `03_Bot/clinical_ai.py` | KEEP_PRODUCTION | Runtime clinical assistant |
| `03_Bot/clinical_conditions/` | KEEP_PRODUCTION | Runtime retrieval corpus |
| `03_Bot/split_core_modules.py` | KEEP_SHARED (temporary) | Build/regeneration tool, not proven runtime-critical |
| `clinical-manual/` | KEEP_SHARED → candidate MOVE_CLINICAL_KNOWLEDGE | Source material used to generate bot knowledge artifacts |
| `15_AI_Brain/` | candidate MOVE_AI_LAB | Dev automation/orchestration layer |
| `15_BrainOS/` | candidate MOVE_AI_LAB | Task/runtime state and orchestration layer |
| BrainOS generated runtime state | MOVE_AI_LAB / runtime-only | Should not define production application source |

## Next audit steps before any move

1. Map remaining direct imports: `calendar_helper`, `case_study_ai`, `photo_extract`, `text_extract`, `ai_helper`, `assessment_defs`, `learning.learning_engine`.
2. Map root-relative paths and `.env`/credential assumptions in `03_Bot`.
3. Map deployment entry points and CI that reference `03_Bot` or root files.
4. Compare laptop/working changes with GitHub `main`; preserve them before repo surgery.
5. Produce final `KEEP / MOVE / ARCHIVE` inventory.
6. Only then create destination repos and migration PRs.

## Safety gate

Until the dependency map is complete:

- no deletion from `main`
- no relocation of `03_Bot`
- no change to production deploy path
- no removal of `clinical_conditions/core_modules.md` from GitHub main unless the replacement implementation is committed and tested
- no BrainOS migration that breaks its Confirm Gate relationship with production changes
