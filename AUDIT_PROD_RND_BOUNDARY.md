# Production vs R&D Boundary Audit

Status: IN PROGRESS
Branch: `audit/prod-rnd-separation`

## Verified so far

### Production core
- `03_Bot/` is the operational Telegram clinic application.
- `03_Bot/bot.py` imports the clinic runtime modules used for patient, appointment, treatment, AI, assessment, and learning flows.
- `03_Bot/config.py` loads the live Telegram bot token, Google Sheets ID/credentials, and the operational sheet names for patients, attendance, appointments, treatments, payments, staff, salary, expenses, learning, consent, and data audit.

### Development / automation layer
- `15_AI_Brain/` and `15_BrainOS/` implement autonomous task routing, scheduling, provider execution, validation, Confirm Gate, logging, TaskInbox, and runtime state.
- Existing merged BrainOS PRs explicitly protect `03_Bot/` from automatic production writes and require the Confirm Gate/manual review boundary.

### Clinical knowledge / R&D layer
- `clinical-manual/` is a draft knowledge/governance workstream, not a verified production runtime source.
- Current draft governance work explicitly states the whole manual must not be sent directly to a production AI API; future production retrieval should use separately reviewed Condition Cards.

## Current boundary decision

Do NOT move `03_Bot/`.
Do NOT delete or relocate any existing code yet.
Do NOT change deployment paths during this audit.

Target architecture under evaluation:

1. `relife-clinic-os`
   - production application core
   - bot runtime
   - production-specific tests and deployment configuration

2. `relife-ai-lab`
   - BrainOS / AI orchestration
   - experimental automation
   - prototypes
   - market/product experiments

3. `relife-clinical-knowledge`
   - master clinical manual
   - evidence audit
   - reviewed Condition Cards
   - clinical governance artifacts

## Required dependency audit before any move

For every top-level path, classify as one of:

- KEEP_PRODUCTION
- KEEP_SHARED
- MOVE_AI_LAB
- MOVE_CLINICAL_KNOWLEDGE
- ARCHIVE_CANDIDATE
- UNKNOWN_REQUIRES_CHECK

Before moving a path, verify:

1. whether `03_Bot/` imports it directly or indirectly;
2. whether runtime files read it by filesystem path;
3. whether CI/deployment references it;
4. whether Render/Termux/start scripts depend on its current location;
5. whether BrainOS references it as a production target;
6. whether any environment/config paths assume the monorepo layout.

## Safety policy during separation

- `03_Bot/` remains the production source of truth unless explicitly migrated later.
- No automated migration of production files.
- R&D changes must not enter `03_Bot/` without test + review + approval.
- New repo creation or large file moves happen only after the dependency map is complete.
- Existing Confirm Gate protections remain in place.

## Next audit outputs

1. top-level KEEP / MOVE / ARCHIVE map;
2. exact `03_Bot` dependency map;
3. cross-repo interface proposal;
4. safe migration order;
5. rollback plan;
6. final approval gate before any production-affecting move.
