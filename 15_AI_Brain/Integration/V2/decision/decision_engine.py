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
            "message":(
                f"Patient database active. "
                f"Total records: {data['records']}. "
                "Follow-up and diagnosis trend monitoring required."
            )
        }



    def staff_decision(self, data):

        if data["records"] == 0:

            return {
                "status":"WAITING_FOR_DATA",
                "message":"Staff data required"
            }


        return {
            "status":"ANALYZED",
            "message":(
                f"Staff records active. "
                f"Total records: {data['records']}. "
                "Attendance and performance tracking required."
            )
        }



    def finance_decision(self, payment, expense):

        return {

            "income":
            payment["amount"],

            "expense":
            expense["amount"],

            "status":
            "CONNECTED"

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
            "Review patient follow-up, monitor collection, and improve staff performance tracking."

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
