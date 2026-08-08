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

    DOMAIN_SHEETS = {
        "patients": "02_Patients",
        "attendance": "03_Attendance",
        "appointments": "04_Appointments",
        "treatments": "05_Treatments",
        "payments": "06_Payments",
        "expenses": "07_Expenses",
        "staff": "08_Staff",
        "inventory": "09_Inventory",
        "assessments": "10_Assessments",
        "packages": "11_Packages",
        "treatment_plans": "12_Treatment_Plans",
        "salary": "13_Salary",
        "reports": "14_Reports",
        "case_studies": "15_Case_Studies",
        "inventory_log": "17_Inventory_Log",
        "learning_progress": "18_Learning_Progress",
        "consent": "19_Consent",
        "data_audit": "20_Data_Audit",
    }

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


    def read_domain(self, domain):
        """Read any registered Clinic OS domain through one stable AI interface."""
        if domain not in self.DOMAIN_SHEETS:
            raise ValueError(f"Unknown Relife data domain: {domain}")
        tab = self.DOMAIN_SHEETS[domain]
        try:
            records = self._get_records(tab)
            return {
                "domain": domain,
                "sheet": tab,
                "records": len(records),
                "data": records,
                "status": "connected",
            }
        except gspread.exceptions.WorksheetNotFound:
            # Consent/audit tabs are introduced by UDA v1 and may not have been
            # migrated yet. Missing optional domains must not crash AI Brain.
            return {
                "domain": domain,
                "sheet": tab,
                "records": 0,
                "data": [],
                "status": "not_migrated",
            }


    def read_unified_snapshot(self):
        return {
            domain: self.read_domain(domain)
            for domain in self.DOMAIN_SHEETS
        }


    def read_patients(self):
        return self.read_domain("patients")


    def read_staff(self):
        return self.read_domain("staff")


    def read_payments(self):
        return self.read_domain("payments")


    def read_expenses(self):
        return self.read_domain("expenses")


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
