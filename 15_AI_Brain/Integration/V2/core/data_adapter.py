from datetime import datetime


class ClinicDataAdapter:

    def __init__(self):
        self.generated = str(datetime.now())


    def patient_data(self):

        return {
            "total":0,
            "new":0,
            "follow_up":0,
            "status":"waiting_for_sheet_connection"
        }


    def staff_data(self):

        return {
            "total":0,
            "active":0,
            "performance":0,
            "status":"waiting_for_sheet_connection"
        }


    def finance_data(self):

        return {
            "income":0,
            "expense":0,
            "profit":0,
            "status":"waiting_for_sheet_connection"
        }
