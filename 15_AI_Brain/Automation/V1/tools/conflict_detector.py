from pathlib import Path
from collections import defaultdict
import re


TASK_FILE = Path("13_AI_Tasks/TASK_QUEUE.md")


def load_tasks():

    if not TASK_FILE.exists():
        return []

    text = TASK_FILE.read_text(
        encoding="utf-8"
    )

    tasks = []

    pattern = r'\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(In-Progress|Done|Pending)\s*\|\s*(.*?)\s*\|'

    matches = re.findall(
        pattern,
        text
    )

    for task, ai, status, module in matches:

        if status == "In-Progress":

            tasks.append(
                {
                    "task": task,
                    "ai": ai,
                    "module": module
                }
            )

    return tasks



def detect_conflict(tasks):

    modules = defaultdict(list)

    for item in tasks:
        modules[item["module"]].append(item)


    conflicts = []

    for module, items in modules.items():

        if len(items) > 1:

            conflicts.append(
                {
                    "module": module,
                    "workers": items
                }
            )

    return conflicts



if __name__ == "__main__":

    tasks = load_tasks()

    conflicts = detect_conflict(tasks)


    print("="*40)
    print("AI BRAIN CONFLICT CHECK")
    print("="*40)


    print(
        "Active Tasks:",
        len(tasks)
    )


    if conflicts:

        print("WARNING: Conflict Found")

        for c in conflicts:
            print(
                "Module:",
                c["module"]
            )

    else:

        print(
            "No Conflict Detected"
        )
