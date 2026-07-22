from pathlib import Path
from datetime import datetime

TASK="13_AI_Tasks/TASK_QUEUE.md"


data=Path(TASK).read_text(
    encoding="utf-8"
)


print("="*40)
print("TASK AGING CHECK")
print("="*40)


if "In-Progress" in data:

    print(
        "Active tasks detected"
    )

    print(
        "Review required"
    )

else:

    print(
        "No active tasks"
    )
