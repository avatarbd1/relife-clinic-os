from pathlib import Path
import subprocess
from datetime import datetime


OUTPUT = Path(
"15_AI_Brain/Automation/V1/reports/NEXT_AI_SESSION_BRIEF_V2.md"
)


def read_file(path):

    p = Path(path)

    if p.exists():
        return p.read_text(
            encoding="utf-8"
        )

    return ""


def git_info():

    try:

        branch = subprocess.check_output(
            "git branch --show-current",
            shell=True,
            text=True
        ).strip()

        commit = subprocess.check_output(
            "git log -1 --oneline",
            shell=True,
            text=True
        ).strip()

        return branch, commit

    except:

        return "N/A", "N/A"



def count_tasks():

    data = read_file(
        "13_AI_Tasks/TASK_QUEUE.md"
    )

    return {
        "pending": data.count("Pending"),
        "progress": data.count("In-Progress"),
        "done": data.count("Done")
    }



branch, commit = git_info()

tasks = count_tasks()


brief = f"""
# NEXT AI SESSION BRIEF V2

Generated:
{datetime.now()}


## SYSTEM

Branch:
{branch}

Last Commit:
{commit}


## TASK STATUS

Pending:
{tasks['pending']}

In Progress:
{tasks['progress']}

Done:
{tasks['done']}


## IMPORTANT FILES

Task Queue:
13_AI_Tasks/TASK_QUEUE.md

Handover:
12_Handover/HANDOVER.md

Brain:
15_AI_Brain/


## SESSION RULES

1. Read current status first.
2. Check Task Queue before work.
3. Do not overwrite another AI task.
4. Update Handover after completion.
5. Owner approval required for major changes.


## NEXT ACTION

Continue from latest Git progress.
"""



OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True
)


OUTPUT.write_text(
    brief,
    encoding="utf-8"
)


print(
"Created:",
OUTPUT
)
