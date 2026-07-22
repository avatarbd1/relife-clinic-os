from pathlib import Path
import subprocess
from datetime import datetime


def run(title, command):

    print("\n" + "="*40)
    print(title)
    print("="*40)

    try:
        result = subprocess.check_output(
            command,
            shell=True,
            text=True
        )

        print(result)

    except Exception as e:
        print("Error:", e)



print("""
==============================
AI BRAIN CONTROL CENTER
==============================
""")

print(
"Generated:",
datetime.now()
)


run(
"1. HEALTH CHECK",
"python 15_AI_Brain/Automation/V1/tools/brain_health_checker.py"
)


run(
"2. AI REGISTRY",
"python 15_AI_Brain/Automation/V1/tools/brain_registry_parser.py"
)


run(
"3. TASK PARSER",
"python 15_AI_Brain/Automation/V1.2/tools/task_parser.py"
)


run(
"4. CONFLICT CHECK",
"python 15_AI_Brain/Automation/V1/tools/conflict_detector.py"
)


run(
"5. PRIORITY ENGINE",
"python 15_AI_Brain/Automation/V1.2/tools/priority_engine.py"
)


run(
"6. GIT TRACKER",
"python 15_AI_Brain/Automation/V1/tools/git_progress_tracker.py"
)


run(
"7. SESSION BRIEF",
"python 15_AI_Brain/Automation/V1/tools/session_brief_v2.py"
)


print("""
==============================
BRAIN CONTROL COMPLETE
==============================
""")
