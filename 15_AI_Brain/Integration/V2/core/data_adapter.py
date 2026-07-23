from datetime import datetime

from readers.google_sheet_reader import GoogleSheetReader


class ClinicDataAdapter:

    def __init__(self):
        self.generated = str(datetime.now())
        self.reader = GoogleSheetReader()


    def patient_data(self):

        data = self.reader.read_patients()

        records = data.get("data", [])

        return {
            "total": len(records),
            "new": len(records),
            "follow_up": 0,
            "status": data.get("status")
        }


    def staff_data(self):

        data = self.reader.read_staff()

        records = data.get("data", [])

        active = 0

        for staff in records:
            if staff.get("Status", "").lower() == "active":
                active += 1

        return {
            "total": len(records),
            "active": active,
            "performance": 0,
            "status": data.get("status")
        }


    def finance_data(self):

        payments = self.reader.read_payments()
        expenses = self.reader.read_expenses()

        income = 0
        expense = 0

        for item in payments.get("data", []):
            try:
                income += float(item.get("Amount", 0) or 0)
            except:
                pass

        for item in expenses.get("data", []):
            try:
                expense += float(item.get("Amount", 0) or 0)
            except:
                pass

        return {
            "income": income,
            "expense": expense,
            "profit": income - expense,
            "status": "connected"
        }
