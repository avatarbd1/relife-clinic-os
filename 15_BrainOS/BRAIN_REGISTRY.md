# BRAIN REGISTRY - relife-clinic-os
# Last Updated: 2026-07-25

## Purpose
BrainOS internal component tracker. Separate from AI_REGISTRY (11_AIOS) which tracks AI worker IDs.

## Registered Components

| Component | Path | Status | Version |
|-----------|------|--------|---------|
| Provider Router | 15_AI_Brain/Core/provider_router.py | Active | v1.0 |
| Task Router | 15_AI_Brain/Control/TASK_ROUTER.py | Active | v1.0 |
| Decision Engine | 15_AI_Brain/Decision/DECISION_ENGINE.md | Active | v1.0 |
| Brain Control v2 | 15_AI_Brain/Automation/brain_control_v2.py | Stale | v2.0 |
| Brain Control v1 | 15_AI_Brain/Automation/brain_control.py | Stale | v1.0 |
| Provider Router Backup | 15_AI_Brain/Core/provider_router_backup.py | Backup | v1.0 |
| BRAIN_STATE | 15_BrainOS/BRAIN_STATE.md | Active | v1.0 |
| BRAIN_QUEUE | 15_BrainOS/BRAIN_QUEUE.md | Active | v1.0 |
| BRAIN_REGISTRY | 15_BrainOS/BRAIN_REGISTRY.md | Active | v1.0 |
| BRAIN_DISPATCHER | 15_BrainOS/BRAIN_DISPATCHER.md | Active | v1.0 |
| BRAIN_MEMORY | 15_BrainOS/BRAIN_MEMORY.md | Active | v1.0 |
| MASTER_PROMPT | 11_AIOS/MASTER_PROMPT.md | Active | v1.0 |
| AI_CONSTITUTION | 11_AIOS/AI_CONSTITUTION.md | Active | v1.0 |
| AI_REGISTRY | 11_AIOS/AI_REGISTRY.md | Active | v1.0 |

## Dependency Tree
AI_BRAIN.md (root)
  ├── 11_AIOS/ (AI worker rules)
  │     ├── MASTER_PROMPT.md
  │     ├── AI_CONSTITUTION.md
  │     └── AI_REGISTRY.md
  └── 15_BrainOS/ (operational layer)
        ├── BRAIN_STATE.md
        ├── BRAIN_QUEUE.md
        ├── BRAIN_REGISTRY.md
        ├── BRAIN_DISPATCHER.md
        └── BRAIN_MEMORY.md
