from pathlib import Path
import json
from datetime import datetime


OUTPUT = Path(
"15_AI_Brain/Integration/V1/reports/staff_performance.json"
)


def generate():

    performance = {

        "generated":
        str(datetime.now()),

        "module":
        "Staff Performance Engine",

        "staff_summary":
        {

            "total_staff":0,

            "active_staff":0,

            "attendance":0

        },

        "performance_metrics":
        {

            "patient_handled":0,

            "task_completed":0,

            "discipline_score":0

        },

        "status":
        "READY_FOR_STAFF_DATA_CONNECTION"

    }


    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    OUTPUT.write_text(
        json.dumps(
            performance,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


    return performance



if __name__=="__main__":

    data=generate()

    print("="*40)
    print("STAFF PERFORMANCE ENGINE")
    print("="*40)
    print("Status:",data["status"])
