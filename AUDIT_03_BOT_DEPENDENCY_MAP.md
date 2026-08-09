# 03_Bot Production Dependency Map — Audit v1

Branch: `audit/prod-rnd-separation`
Date: 2026-08-09
Scope: Read-only audit of the GitHub `main` state before any repo separation.

## Executive conclusion

`03_Bot/` is the operational application core and must remain intact until all direct and indirect runtime dependencies are mapped. No production files should be moved yet.

A critical finding is that the GitHub `main` branch does **not** yet contain the newer module-splitting/relevance-routing implementation described from the laptop session. On `main`, `clinical_ai.py` still loads `clinical_conditions/core_modules.md`, and `split_core_modules.py` still intentionally extracts only Modules 3, 4 and 7. Therefore any laptop-side changes must be treated as uncommitted/unverified until they appear in GitHub.

## Verified production-core entry point

`03_Bot/bot.py` imports these local modules directly from the `03_Bot` runtime package/directory:

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

These are `KEEP_PRODUCTION` until their own dependencies are mapped.

## Verified external/runtime dependencies

From the inspected code, production requires at least:

- Python runtime
- `python-telegram-bot`
- environment variables / `.env`
- Telegram `BOT_TOKEN`
- Google Sheet ID
- Google credentials file
- Google Sheets integration through the local `sheets` layer
- network access for AI HTTP calls
- Groq API key for `clinical_ai`
- OpenRouter API key for `clinical_ai`

This is not yet a complete package-level dependency inventory; it is the verified set from currently inspected files.

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

Based on prior repo audit and merged PR history:

- `15_AI_Brain/` → candidate `MOVE_AI_LAB`
- `15_BrainOS/` → candidate `MOVE_AI_LAB`
- BrainOS cron/task inbox/dispatcher tooling → candidate `MOVE_AI_LAB`

However, migration must preserve a controlled interface if these tools are still expected to propose changes to the production repo. The production repo must remain the authority for deployable `03_Bot` code.

## Current classification

| Path / component | Classification | Reason |
|---|---|---|
| `03_Bot/bot.py` | KEEP_PRODUCTION | Main runtime entry point |
| `03_Bot/config.py` | KEEP_PRODUCTION | Secrets/config and operational sheet mapping |
| local modules imported by `bot.py` | KEEP_PRODUCTION | Direct runtime dependency |
| `03_Bot/clinical_ai.py` | KEEP_PRODUCTION | Runtime clinical assistant |
| `03_Bot/clinical_conditions/` | KEEP_PRODUCTION | Runtime retrieval corpus |
| `03_Bot/split_core_modules.py` | KEEP_SHARED (temporary) | Build/regeneration tool, not proven runtime-critical |
| `clinical-manual/` | KEEP_SHARED → candidate MOVE_CLINICAL_KNOWLEDGE | Source material used to generate bot knowledge artifacts |
| `15_AI_Brain/` | candidate MOVE_AI_LAB | Dev automation/orchestration layer |
| `15_BrainOS/` | candidate MOVE_AI_LAB | Task/runtime state and orchestration layer |
| BrainOS generated runtime state | MOVE_AI_LAB / runtime-only | Should not define production application source |

## Next audit steps before any move

1. Map imports and file reads for every module directly imported by `bot.py`.
2. Map root-relative paths and `.env`/credential assumptions in `03_Bot`.
3. Map deployment entry points and CI that reference `03_Bot` or root files.
4. Compare laptop/working branch changes with GitHub `main`; preserve them before repo surgery.
5. Produce final `KEEP / MOVE / ARCHIVE` inventory.
6. Only then create destination repos and migration PRs.

## Safety gate

Until the dependency map is complete:

- no deletion from `main`
- no relocation of `03_Bot`
- no change to production deploy path
- no removal of `clinical_conditions/core_modules.md` from GitHub main unless the replacement implementation is committed and tested
- no BrainOS migration that breaks its Confirm Gate relationship with production changes
