import os
import json
from pathlib import Path


class SheetConnector:

    def __init__(self):

        self.status = "initialized"


    def check_environment(self):

        return {

            "GOOGLE_SHEET_ID":
            bool(os.getenv("GOOGLE_SHEET_ID")),

            "CREDENTIAL_FILE":
            Path("credentials.json").exists()

        }


    def patients(self):

        return {

            "module":"patients",

            "source":"Google Sheet",

            "status":
            "waiting_for_safe_reader",

            "total":0

        }


    def staff(self):

        return {

            "module":"staff",

            "source":"Google Sheet",

            "status":
            "waiting_for_safe_reader",

            "total":0

        }


    def finance(self):

        return {

            "module":"finance",

            "source":"Google Sheet",

            "status":
            "waiting_for_safe_reader",

            "income":0

        }



if __name__=="__main__":

    c=SheetConnector()

    print("="*40)
    print("AI BRAIN SAFE SHEET CONNECTOR")
    print("="*40)

    print(
        json.dumps(
            c.check_environment(),
            indent=4
        )
    )

    print(c.patients())
    print(c.staff())
    print(c.finance())
