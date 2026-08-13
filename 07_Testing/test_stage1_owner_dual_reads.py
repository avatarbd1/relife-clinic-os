import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_Bot"))
os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("GOOGLE_SHEET_ID", "physio")
os.environ.setdefault("DENTAL_GOOGLE_SHEET_ID", "dental")
credentials = ROOT / "credentials.json"
created_credentials = False
if not credentials.exists():
    credentials.write_text("{}", encoding="utf-8")
    created_credentials = True

import bot
import config
import sheets


def tearDownModule():
    if created_credentials:
        credentials.unlink(missing_ok=True)


class OwnerDualReadTests(unittest.TestCase):
    def test_reports_read_both_workbooks_and_keep_source(self):
        rows = {
            ("physio", config.SHEET_PATIENTS): [{"Patient_ID": "PT0001", "Department": "Physio"}],
            ("dental", config.SHEET_PATIENTS): [{"Patient_ID": "DT0001", "Department": "Dental"}],
            ("physio", config.SHEET_PAYMENTS): [{"Amount": 100, "Department": "Physio"}],
            ("dental", config.SHEET_PAYMENTS): [{"Amount": 200, "Department": "Dental"}],
        }
        class WS:
            def __init__(self, title): self.title = title
        with patch.object(sheets, "_worksheet", side_effect=lambda title: WS(title)), patch.object(
            sheets, "safe_get_all_records",
            side_effect=lambda ws: rows.get((sheets._active_sheet_id(), ws.title), []),
        ):
            data = sheets.get_scoped_report_records({config.DEPARTMENT_ALL})
        patients = data[config.SHEET_PATIENTS]
        self.assertEqual({p["Patient_ID"] for p in patients}, {"PT0001", "DT0001"})
        self.assertEqual({p["_Source_Department"] for p in patients}, {"Physio", "Dental"})

    def test_owner_register_text_has_separate_pt_and_dt_sections(self):
        registers = {
            "Physio": {"date": "2026-08-14", "rows": [{"Sl": 1, "Patient_Name": "P", "Sessions": 2}], "total_patients": 1, "total_sessions": 2},
            "Dental": {"date": "2026-08-14", "rows": [{"Sl": 1, "Patient_Name": "D", "Service": "Filling"}], "total_patients": 1, "total_sessions": 0},
        }
        with patch.object(sheets, "get_daily_register_across_departments", return_value=registers):
            text, _ = bot._register_view_text_and_keyboard({config.DEPARTMENT_ALL})
        self.assertIn("🩺 Physio (PT)", text)
        self.assertIn("🦷 Dental (DT)", text)
        self.assertIn("সেশন: 2", text)
        self.assertIn("Service: Filling", text)

    def test_owner_period_cash_text_has_two_named_sections(self):
        def summary(amount):
            return {
                "Date": "2026-08-01 — 2026-08-14", "Start_Date": "2026-08-01",
                "Cash_Collected": amount, "Reception_Expense": 0, "Reception_Salary": 0,
                "Reception_Handover": 0, "Reception_Balance": amount,
                "Home_Received": 0, "Home_Clinic_Expense": 0, "Home_Salary": 0,
                "Household_Withdrawal": 0, "Home_Transfer_Out": 0, "Home_Balance": 0,
                "Bank_Received": 0, "Bank_Expense": 0, "Bank_Salary": 0,
                "Bank_Transfer_Out": 0, "Bank_Balance": 0,
            }
        text = bot._department_period_cash_text({"Physio": summary(100), "Dental": summary(200)}, "Owner")
        self.assertIn("🩺 Physio (PT)", text)
        self.assertIn("🦷 Dental (DT)", text)
        self.assertIn("Cash collection: ৳100", text)
        self.assertIn("Cash collection: ৳200", text)

    def test_receptionist_register_stays_single_department(self):
        reg = {"date": "2026-08-14", "rows": [], "total_patients": 0, "total_sessions": 0}
        with patch.object(sheets, "get_daily_register", return_value=reg) as get_register:
            text, _ = bot._register_view_text_and_keyboard({config.DEPARTMENT_DENTAL})
        get_register.assert_called_once()
        self.assertNotIn("Physio (PT)", text)


if __name__ == "__main__":
    unittest.main()
