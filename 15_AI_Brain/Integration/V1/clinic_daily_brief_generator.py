from pathlib import Path
from datetime import datetime
import json


REPORT = Path(
"15_AI_Brain/Integration/V1/reports/CLINIC_DAILY_BRIEF.md"
)


def load_file(path):

    file = Path(path)

    if file.exists():

        return json.loads(
            file.read_text(
                encoding="utf-8"
            )
        )

    return {}


patient = load_file(
"15_AI_Brain/Integration/V1/reports/patient_insight.json"
)

staff = load_file(
"15_AI_Brain/Integration/V1/reports/staff_performance.json"
)

finance = load_file(
"15_AI_Brain/Integration/V1/reports/finance_insight.json"
)


brief = f"""
# RELIFE CLINIC DAILY BRIEF

Generated:
{datetime.now()}


## PATIENT

Total:
{patient.get('summary',{}).get('total_patient',0)}

New:
{patient.get('summary',{}).get('new_patient',0)}

Follow Up:
{patient.get('summary',{}).get('follow_up',0)}



## STAFF

Total Staff:
{staff.get('staff_summary',{}).get('total_staff',0)}

Active:
{staff.get('staff_summary',{}).get('active_staff',0)}



## FINANCE

Income:
{finance.get('financial_summary',{}).get('total_income',0)}

Expense:
{finance.get('financial_summary',{}).get('total_expense',0)}

Profit:
{finance.get('financial_summary',{}).get('net_profit',0)}



## AI BRAIN STATUS

Integration:
READY


NEXT ACTION:

Connect real clinic database.
"""


REPORT.parent.mkdir(
    parents=True,
    exist_ok=True
)


REPORT.write_text(
    brief,
    encoding="utf-8"
)


print("="*40)
print("CLINIC DAILY BRIEF GENERATOR")
print("="*40)
print("Report:",REPORT)
