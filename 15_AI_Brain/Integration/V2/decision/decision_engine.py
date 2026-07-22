import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.append(
    "15_AI_Brain/Integration/V2"
)

from readers.google_sheet_reader import GoogleSheetReader


OUTPUT = Path(
"15_AI_Brain/Integration/V2/reports/AI_DECISION_REPORT.json"
)


class DecisionEngine:


    def __init__(self):

        self.reader = GoogleSheetReader()



    def patient_decision(self, data):

        if data["records"] == 0:

            return {
                "status":"WAITING_FOR_DATA",
                "message":"Patient database connection required"
            }


        return {
            "status":"ANALYZED",
            "message":"Patient activity reviewed"
        }



    def staff_decision(self, data):

        if data["records"] == 0:

            return {
                "status":"WAITING_FOR_DATA",
                "message":"Staff data required"
            }


        return {
            "status":"ANALYZED"
        }



    def finance_decision(self, payment, expense):

        return {

            "income":
            payment["amount"],

            "expense":
            expense["amount"],

            "status":
            "WAITING_FOR_FINANCE_DATA"

        }



    def run(self):

        patients = self.reader.read_patients()

        staff = self.reader.read_staff()

        payments = self.reader.read_payments()

        expenses = self.reader.read_expenses()


        result = {

            "generated":
            str(datetime.now()),


            "system":
            "Relife Clinic OS AI Brain",


            "patient_decision":
            self.patient_decision(patients),


            "staff_decision":
            self.staff_decision(staff),


            "finance_decision":
            self.finance_decision(
                payments,
                expenses
            ),


            "next_action":
            "Connect real clinic database"

        }


        OUTPUT.parent.mkdir(
            parents=True,
            exist_ok=True
        )


        OUTPUT.write_text(
            json.dumps(
                result,
                indent=4,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )


        return result




if __name__=="__main__":

    engine = DecisionEngine()

    report = engine.run()


    print("="*40)
    print("AI BRAIN DECISION ENGINE V2")
    print("="*40)

    print(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        )
    )
