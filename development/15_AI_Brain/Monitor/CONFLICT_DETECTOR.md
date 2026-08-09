# CONFLICT DETECTOR

Purpose:
Detect workflow conflicts before AI assignment.

## Checks

File Conflict:
- Same file assigned to multiple AI


Task Conflict:
- Duplicate task
- Missing owner
- Missing AI ID


Documentation Conflict:
- Different source of truth


## Action

If conflict found:

1. Stop assignment
2. Record issue
3. Request owner decision


## Rule

No AI continues when ownership is unclear.
