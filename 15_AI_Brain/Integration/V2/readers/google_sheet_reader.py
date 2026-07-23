import sys
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
import os

sys.path.append(
    "15_AI_Brain/Integration/V2"
)

from config.brain_config import BrainConfig


class GoogleSheetReader:

    def __init__(self):

        load_dotenv()

        self.config = BrainConfig()

        creds_path = self.config.credentials

        self.creds = Credentials.from_service_account_file(
            creds_path,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )

        self.client = gspread.authorize(self.creds)

        self.sheet = self.client.open_by_key(
            self.config.sheet_id
        )


    def connection_status(self):

        return self.config.status()


    def _get_records(self, tab):

        ws = self.sheet.worksheet(tab)

        data = ws.get_all_values()

        if len(data) <= 1:
            return []

        headers = data[0]

        return [
            dict(zip(headers, row))
            for row in data[1:]
            if any(row)
        ]


    def read_patients(self):

        records = self._get_records("02_Patients")

        return {
            "sheet": "02_Patients",
            "records": len(records),
            "data": records,
            "status": "connected"
        }


    def read_staff(self):

        records = self._get_records("08_Staff")

        return {
            "sheet": "08_Staff",
            "records": len(records),
            "data": records,
            "status": "connected"
        }


    def read_payments(self):

        records = self._get_records("06_Payments")

        return {
            "sheet": "06_Payments",
            "records": len(records),
            "data": records,
            "status": "connected"
        }


    def read_expenses(self):

        records = self._get_records("07_Expenses")

        return {
            "sheet": "07_Expenses",
            "records": len(records),
            "data": records,
            "status": "connected"
        }


if __name__ == "__main__":

    reader = GoogleSheetReader()

    print("="*40)
    print("AI BRAIN GOOGLE SHEET READER")
    print("="*40)

    print(reader.connection_status())

    print("Patients:", reader.read_patients()["records"])
    print("Staff:", reader.read_staff()["records"])
    print("Payments:", reader.read_payments()["records"])
    print("Expenses:", reader.read_expenses()["records"])
