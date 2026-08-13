#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parent / "07_Testing" / "test_dual_department_finance.py"
if not path.exists():
    raise SystemExit(f"❌ Test file পাওয়া যায়নি: {path}")

text = path.read_text(encoding="utf-8")
old = '''    def test_live_dental_reception_has_only_two_dental_balances(self):
        text=bot._department_live_balance_text({"Dental":{
            "Reception_Balance":300,"Home_Balance":100,"Bank_Balance":50
        }}, "Receptionist")
        self.assertIn("🦷 Dental", text)
        self.assertIn("Reception: ৳300", text)
        self.assertIn("Home Treasury: ৳100", text)
        self.assertNotIn("Bank", text)
        self.assertNotIn("Physio", text)
'''
new = '''    def test_live_dental_reception_has_only_reception_balance(self):
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
        self.assertIn("🩺 Physio\\n⚖️ Reception: ৳10\\n🏠 Home Treasury: ৳20", text)
        self.assertIn("🦷 Dental\\n⚖️ Reception: ৳40\\n🏠 Home Treasury: ৳50", text)
        self.assertEqual(text.count("🏦 Bank:"), 1)
'''

if new in text:
    print("✅ Patch 15 আগে থেকেই applied আছে।")
elif old in text:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("✅ Patch 15 applied: stale Live-balance test updated.")
else:
    raise SystemExit("❌ পুরোনো test block পাওয়া যায়নি; কোনো file বদলানো হয়নি।")
