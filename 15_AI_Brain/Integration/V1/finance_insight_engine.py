from pathlib import Path
import json
from datetime import datetime


OUTPUT = Path(
"15_AI_Brain/Integration/V1/reports/finance_insight.json"
)


def generate():

    finance = {

        "generated":
        str(datetime.now()),

        "module":
        "Finance Insight Engine",

        "financial_summary":
        {

            "total_income":0,

            "total_expense":0,

            "net_profit":0

        },

        "cash_flow":
        {

            "status":
            "WAITING_FOR_FINANCE_DATA",

            "monthly_target":0

        },

        "business_health":
        {

            "score":0,

            "status":
            "READY"

        }

    }


    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    OUTPUT.write_text(
        json.dumps(
            finance,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


    return finance



if __name__=="__main__":

    data=generate()

    print("="*40)
    print("FINANCE INSIGHT ENGINE")
    print("="*40)
    print("Status:",data["cash_flow"]["status"])
