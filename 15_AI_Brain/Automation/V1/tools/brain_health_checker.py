from pathlib import Path


def check_file(path):

    if Path(path).exists():
        return "OK"

    return "MISSING"


checks = {

"Task Queue":
"13_AI_Tasks/TASK_QUEUE.md",

"Handover":
"12_Handover/HANDOVER.md",

"Registry":
"11_AIOS/AI_REGISTRY.md",

"Brain":
"15_AI_Brain/README.md"

}


print("="*40)
print("AI BRAIN HEALTH CHECK")
print("="*40)


for name,path in checks.items():

    print(
        name,
        ":",
        check_file(path)
    )
