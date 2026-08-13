import os, sys, unittest
from unittest.mock import patch
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "03_Bot"))
os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("GOOGLE_SHEET_ID", "physio")
os.environ.setdefault("DENTAL_GOOGLE_SHEET_ID", "dental")
_CREDENTIALS = Path(ROOT) / "credentials.json"
_CREATED_CREDENTIALS = False
if not _CREDENTIALS.exists():
    _CREDENTIALS.write_text("{}", encoding="utf-8")
    _CREATED_CREDENTIALS = True

import bot, config, sheets


class DualDepartmentFinanceTests(unittest.TestCase):
    def test_owner_dashboard_reads_both_workbooks(self):
        rows = {
            ("physio", config.SHEET_PAYMENTS): [{"Department":"Physio","Date":"2026-08-14","Amount":10,"Payment_Method":"Cash"}],
            ("dental", config.SHEET_PAYMENTS): [{"Department":"Dental","Date":"2026-08-14","Amount":400,"Payment_Method":"Cash"}],
        }
        class WS:
            def __init__(self, title): self.title=title
        with patch.object(sheets, "_worksheet", side_effect=lambda title: WS(title)), patch.object(
            sheets, "safe_get_all_records",
            side_effect=lambda ws: rows.get((sheets._active_sheet_id(), ws.title), []),
        ):
            data=sheets.get_owner_financial_dashboard("2026-08-14")
        self.assertEqual(data["Physio"]["Today_Collection"], 10)
        self.assertEqual(data["Dental"]["Today_Collection"], 400)

    def test_live_dental_reception_has_only_reception_balance(self):
        text=bot._department_live_balance_text({"Dental":{
            "Reception_Balance":300,"Home_Balance":100,"Bank_Balance":50
        }}, "Receptionist")
        self.assertIn("🦷 Dental", text)
        self.assertIn("Reception: ৳300", text)
        self.assertNotIn("Home Treasury", text)
        self.assertNotIn("Bank", text)
        self.assertNotIn("Physio", text)

    def test_owner_live_separates_physio_and_dental_treasury(self):
        text=bot._department_live_balance_text({
            "Physio":{"Reception_Balance":10,"Home_Balance":20,"Bank_Balance":30},
            "Dental":{"Reception_Balance":40,"Home_Balance":50,"Bank_Balance":60},
        }, "Owner")
        self.assertIn("🩺 Physio\n⚖️ Reception: ৳10\n🏠 Home Treasury: ৳20", text)
        self.assertIn("🦷 Dental\n⚖️ Reception: ৳40\n🏠 Home Treasury: ৳50", text)
        self.assertEqual(text.count("🏦 Bank:"), 1)

    def test_dental_provider_never_falls_back_to_physio_therapists(self):
        with patch.object(sheets, "get_active_provider_names", return_value=[]):
            keyboard=bot._therapist_keyboard(config.DEPARTMENT_DENTAL)
        labels=[button.text for row in keyboard.inline_keyboard for button in row]
        self.assertNotIn("Saiful", labels)
        self.assertNotIn("Nipa", labels)


if __name__ == "__main__": unittest.main()
