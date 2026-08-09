# AI WORKFLOW ENGINE

Purpose:
Define automatic movement of tasks through AI workflow.

## Lifecycle

NEW
↓
ANALYSIS
↓
ASSIGNMENT
↓
IN_PROGRESS
↓
REVIEW
↓
APPROVAL
↓
DONE
↓
MEMORY UPDATE


## Status Meaning

NEW:
Owner idea received.

ANALYSIS:
Brain checks requirements and risks.

ASSIGNMENT:
AI worker selected from AI_REGISTRY.

IN_PROGRESS:
Worker is active and TASK_QUEUE locked.

REVIEW:
Evidence checked.

APPROVAL:
Owner decision required.

DONE:
Task completed and recorded.

MEMORY UPDATE:
Decision and learning stored.


## Rules

- No skipping review for production changes.
- No DONE without HANDOVER update.
- Owner remains final authority.
- Brain coordinates, AI workers execute.
