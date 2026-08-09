# CONTINUITY CHECK

Purpose:
Maintain work continuity between AI sessions.

Before new AI starts:

Check:

1. Previous HANDOVER
2. Current TASK_QUEUE
3. Recent commits
4. Active decisions


New AI must know:

- What is completed
- What is pending
- What changed
- What is next step


Rule:

Never restart from zero if previous context exists.
