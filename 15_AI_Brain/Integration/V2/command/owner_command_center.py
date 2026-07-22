import sys
from pathlib import Path
from datetime import datetime
import json


sys.path.append(
    "15_AI_Brain/Integration/V2"
)


from decision.decision_engine import DecisionEngine


OUTPUT = Path(
"15_AI_Brain/Integration/V2/reports/OWNER_COMMAND_CENTER.md"
)



def generate():


    engine = DecisionEngine()

    data = engine.run()


    report = f"""
# RELIFE CLINIC OS
# AI BRAIN OWNER COMMAND CENTER


Generated:
{datetime.now()}


==============================
PATIENT STATUS
==============================

Status:
{data["patient_decision"]["status"]}

Message:
{data["patient_decision"]["message"]}



==============================
STAFF STATUS
==============================

Status:
{data["staff_decision"]["status"]}

Message:
{data["staff_decision"]["message"]}



==============================
FINANCE STATUS
==============================

Income:
{data["finance_decision"]["income"]}

Expense:
{data["finance_decision"]["expense"]}

Status:
{data["finance_decision"]["status"]}



==============================
AI NEXT ACTION
==============================

{data["next_action"]}



SYSTEM:
AI Brain Integration V2 Active
"""


    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    OUTPUT.write_text(
        report,
        encoding="utf-8"
    )


    return OUTPUT




if __name__=="__main__":


    file = generate()


    print("="*40)
    print("AI BRAIN OWNER COMMAND CENTER V2")
    print("="*40)

    print("Report:")
    print(file)
