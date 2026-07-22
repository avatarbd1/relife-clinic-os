import subprocess
import json
from datetime import datetime
from pathlib import Path


OUTPUT = Path(
    "15_AI_Brain/Automation/V1/reports/git_progress.json"
)


def run_command(command):

    try:
        result = subprocess.check_output(
            command,
            shell=True,
            text=True
        )

        return result.strip()

    except Exception:
        return "Unavailable"



def create_report():

    report = {

        "generated":
            str(datetime.now()),

        "branch":
            run_command(
                "git branch --show-current"
            ),

        "latest_commit":
            run_command(
                "git log -1 --oneline"
            ),

        "recent_commits":
            run_command(
                "git log --oneline -5"
            ),

        "status":
            run_command(
                "git status --short"
            )

    }


    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    OUTPUT.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


    return report



if __name__ == "__main__":

    data = create_report()

    print("="*40)
    print("GIT PROGRESS TRACKER")
    print("="*40)

    print(
        "Branch:",
        data["branch"]
    )

    print(
        "Latest:",
        data["latest_commit"]
    )
