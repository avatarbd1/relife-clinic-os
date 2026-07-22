import sys
from pathlib import Path
import json


sys.path.append(
    "15_AI_Brain/Integration/V2"
)

from config.brain_config import BrainConfig


class GoogleSheetReader:


    def __init__(self):

        self.config = BrainConfig()


    def connection_status(self):

        return self.config.status()



    def read_patients(self):

        return {

            "sheet":
            "02_Patients",

            "records":
            0,

            "status":
            "waiting_for_google_connection"

        }



    def read_staff(self):

        return {

            "sheet":
            "08_Staff",

            "records":
            0,

            "status":
            "waiting_for_google_connection"

        }



    def read_payments(self):

        return {

            "sheet":
            "06_Payments",

            "records":
            0,

            "amount":
            0,

            "status":
            "waiting_for_google_connection"

        }



    def read_expenses(self):

        return {

            "sheet":
            "07_Expenses",

            "records":
            0,

            "amount":
            0,

            "status":
            "waiting_for_google_connection"

        }



if __name__ == "__main__":


    reader = GoogleSheetReader()


    report = {

        "connection":
        reader.connection_status(),

        "patients":
        reader.read_patients(),

        "staff":
        reader.read_staff(),

        "payments":
        reader.read_payments(),

        "expenses":
        reader.read_expenses()

    }


    print("="*40)
    print("AI BRAIN GOOGLE SHEET READER V1")
    print("="*40)

    print(
        json.dumps(
            report,
            indent=4
        )
    )
