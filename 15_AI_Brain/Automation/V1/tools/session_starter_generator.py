from pathlib import Path
from datetime import datetime


FILES = {
    "Brain": "15_AI_Brain/README.md",
    "Tasks": "13_AI_Tasks/TASK_QUEUE.md",
    "Handover": "12_Handover/HANDOVER.md",
    "Registry": "11_AIOS/AI_REGISTRY.md"
}


OUTPUT = Path(
    "15_AI_Brain/Automation/V1/reports/NEXT_AI_SESSION_BRIEF.md"
)


def read(path):

    file = Path(path)

    if file.exists():
        return file.read_text(
            encoding="utf-8"
        )

    return "FILE NOT FOUND"


content = []

content.append(
"# NEXT AI SESSION BRIEF\n"
)

content.append(
f"Generated: {datetime.now()}\n"
)


for name,path in FILES.items():

    content.append(
        "\n\n## " + name + "\n"
    )

    data = read(path)

    content.append(
        data[-1500:]
    )


content.append(
"""

## SESSION RULES

1. Read previous progress.
2. Check TASK_QUEUE before work.
3. Update HANDOVER after completion.
4. Owner approval required for major changes.

"""
)


OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True
)


OUTPUT.write_text(
    "\n".join(content),
    encoding="utf-8"
)


print("Session Brief Created:")
print(OUTPUT)
