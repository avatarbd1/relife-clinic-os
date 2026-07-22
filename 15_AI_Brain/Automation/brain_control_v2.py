import subprocess
from pathlib import Path
from datetime import datetime


REPORT = Path(
"15_AI_Brain/Automation/reports/BRAIN_DAILY_REPORT.md"
)


def run(name, command):

    try:
        output = subprocess.check_output(
            command,
            shell=True,
            text=True,
            stderr=subprocess.STDOUT
        )

        return {
            "name": name,
            "status": "OK",
            "output": output.strip()
        }

    except Exception as e:

        return {
            "name": name,
            "status": "ERROR",
            "output": str(e)
        }



modules = [

(
"Health Check",
"python 15_AI_Brain/Automation/V1/tools/brain_health_checker.py"
),

(
"Registry",
"python 15_AI_Brain/Automation/V1/tools/brain_registry_parser.py"
),

(
"Task Parser",
"python 15_AI_Brain/Automation/V1.2/tools/task_parser.py"
),

(
"Conflict Detector",
"python 15_AI_Brain/Automation/V1/tools/conflict_detector.py"
),

(
"Priority Engine",
"python 15_AI_Brain/Automation/V1.2/tools/priority_engine.py"
),

(
"Git Tracker",
"python 15_AI_Brain/Automation/V1/tools/git_progress_tracker.py"
),

(
"Session Brief",
"python 15_AI_Brain/Automation/V1/tools/session_brief_v2.py"
)

]



results=[]


for name,cmd in modules:

    results.append(
        run(name,cmd)
    )



report=[]

report.append(
"# AI BRAIN DAILY REPORT\n"
)

report.append(
f"Generated:\n{datetime.now()}\n"
)


report.append(
"## SYSTEM STATUS\n"
)


error_count=0


for item in results:

    report.append(
        f"""
### {item['name']}

Status:
{item['status']}

"""
    )

    if item["status"]=="ERROR":
        error_count +=1



report.append(
"## FINAL HEALTH\n"
)


if error_count==0:

    report.append(
        "HEALTH: OK ✅\n"
    )

    report.append(
        "NEXT ACTION:\nContinue planned development.\n"
    )

else:

    report.append(
        f"HEALTH: WARNING ⚠️\nErrors: {error_count}\n"
    )



REPORT.parent.mkdir(
    parents=True,
    exist_ok=True
)


REPORT.write_text(
    "\n".join(report),
    encoding="utf-8"
)



print("="*40)
print("AI BRAIN CONTROL CENTER V2")
print("="*40)

print(
"Report:",
REPORT
)

print(
"Health:",
"OK" if error_count==0 else "WARNING"
)

