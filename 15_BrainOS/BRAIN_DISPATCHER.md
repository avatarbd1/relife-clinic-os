# BRAIN DISPATCHER - relife-clinic-os
# Last Updated: 2026-07-25

## Purpose
BrainOS main execution loop. Reads BRAIN_QUEUE, analyzes via Decision Engine, routes via TaskRouter, executes via ProviderRouter.

## Dispatch Loop (v1.0)
0. HEALTH CHECK -> self_healing_bridge.py pre-flight gate; abort dispatch if unhealthy (added Step 9/10, 2026-07-25)
1. READ BRAIN_STATE -> check LOCK_TOKEN
2. READ BRAIN_QUEUE -> pick next CRITICAL task
3. VALIDATE -> check BRAIN_REGISTRY for conflicts
4. DECISION -> Decision Engine analyzes task
5. ROUTE -> TaskRouter.create_task()
6. EXECUTE -> ProviderRouter.route()
7. LOG -> Write to BRAIN_MEMORY
8. UPDATE -> Update BRAIN_STATE, BRAIN_QUEUE
9. HANDOVER -> Update 12_Handover/HANDOVER.md
10. LOOP -> Back to step 1

## Dispatch Rules
- Only dispatch if LOCK_TOKEN = FREE
- 1 task per dispatch cycle
- On failure: log to BRAIN_MEMORY, mark FAILED in BRAIN_QUEUE
- On success: mark DONE, update HANDOVER

## AIOS Bridge (11_AIOS)
- MASTER_PROMPT.md: AI onboarding rules enforced at dispatch Step 0
- AI_CONSTITUTION.md: Safety rules checked at dispatch Step 3 (VALIDATE)
- AI_REGISTRY.md: Worker IDs resolved at dispatch Step 5 (ROUTE)
- ONBOARDING_MESSAGE.md: New AI session init linked to BRAIN_DISPATCHER

## Integration Points
- Input: BRAIN_QUEUE.md
- Analysis: 15_AI_Brain/Decision/DECISION_ENGINE.md
- Routing: 15_AI_Brain/Control/TASK_ROUTER.py
- Execution: 15_AI_Brain/Core/provider_router.py
- Output: BRAIN_MEMORY.md, HANDOVER.md

## Current Status
State: MANUAL MODE (no autonomous loop yet)
Reason: BrainOS bootstrap phase - human dispatches via Termux
Auto-mode target: After Phase 1 Step 10 completes
