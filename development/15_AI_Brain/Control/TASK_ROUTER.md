# TASK ROUTER

Purpose:
Connect AI Brain decisions with TASK_QUEUE.

## Routing Logic

1. Receive approved owner decision.

2. Check TASK_QUEUE:
- Pending tasks
- In-Progress conflicts

3. Check AI_REGISTRY:
- Available AI ID
- Current responsibility

4. Create assignment.

5. Monitor:
Pending → In-Progress → Review → Done

## Conflict Handling

If same module is locked:
- Stop assignment
- Request owner decision

## Completion

A task is complete only when:
- Work evidence exists
- Handover updated
- Review completed
