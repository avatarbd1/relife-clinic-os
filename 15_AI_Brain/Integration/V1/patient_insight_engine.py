from pathlib import Path
import json
from datetime import datetime


OUTPUT = Path(
"15_AI_Brain/Integration/V1/reports/patient_insight.json"
)


def generate():

    insight = {

        "generated":
        str(datetime.now()),

        "module":
        "Patient Insight Engine",

        "summary":
        {

            "total_patient":0,

            "new_patient":0,

            "follow_up":0

        },

        "conditions":
        {
            "stroke":0,
            "back_pain":0,
            "neck_pain":0,
            "others":0
        },

        "status":
        "READY_FOR_DATABASE_CONNECTION"

    }


    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    OUTPUT.write_text(
        json.dumps(
            insight,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


    return insight



if __name__=="__main__":

    data=generate()

    print("="*40)
    print("PATIENT INSIGHT ENGINE")
    print("="*40)
    print("Status:",data["status"])
