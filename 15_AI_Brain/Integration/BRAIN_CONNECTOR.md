# BRAIN CONNECTOR

Purpose:
Connect AI Brain with existing AIOS systems.

Connected Systems:

## AI Identity

Source:
11_AIOS/AI_REGISTRY.md

Use:
- Identify AI worker
- Check availability
- Track responsibility


## Task Management

Source:
13_AI_Tasks/TASK_QUEUE.md

Use:
- Create tasks
- Lock active work
- Track progress


## Memory System

Source:
12_Handover/HANDOVER.md

Use:
- Store completed work
- Save continuation point
- Preserve decisions


## Brain Flow

Owner Request
↓
Decision Engine
↓
Task Router
↓
AI Registry Check
↓
TASK_QUEUE Update
↓
Worker AI
↓
HANDOVER Update
↓
Review


## Rules

- Existing AIOS files remain the source of truth.
- Brain does not replace AIOS.
- Brain coordinates workflow.
- Owner remains final authority.
