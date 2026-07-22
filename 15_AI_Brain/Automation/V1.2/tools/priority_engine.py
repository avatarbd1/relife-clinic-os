from pathlib import Path


TASK="13_AI_Tasks/TASK_QUEUE.md"


data=Path(TASK).read_text(
    encoding="utf-8"
)


print("="*40)
print("PRIORITY ENGINE")
print("="*40)


if "High" in data:
    print("HIGH priority tasks exist")

if "Medium" in data:
    print("MEDIUM priority tasks exist")

print("Priority analysis completed")
