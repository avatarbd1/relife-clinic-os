from pathlib import Path


def check_file(path):

    if Path(path).exists():
        return "OK"

    return "MISSING"


checks = {

"Task Queue":
"development/13_AI_Tasks/TASK_QUEUE.md",

"Handover":
"development/12_Handover/HANDOVER.md",

"Registry":
"development/11_AIOS/AI_REGISTRY.md",

"Brain":
"development/15_AI_Brain/README.md"

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
