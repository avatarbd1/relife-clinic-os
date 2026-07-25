# BRAIN QUEUE - relife-clinic-os
# Last Updated: 2026-07-25

## Purpose
BrainOS centralized task queue. TASK_ROUTER.py takes tasks from here, PROVIDER_ROUTER.py assigns AI providers.

## Active Queue

| TASK_ID | Type | Priority | Status | Assigned | Created |
|---------|------|----------|--------|----------|---------|
| BOOT-001 | Bootstrap | CRITICAL | IN-PROGRESS | DeepSeek (user) | 2026-07-25 |

## Completed
(empty)

## Failed / Blocked
(empty)

## Queue Rules
1. Max 1 CRITICAL task active at a time
2. Max 3 concurrent tasks total
3. Same module = no parallel tasks
4. Failed tasks auto-retry 1x, then escalate to HANDOVER
