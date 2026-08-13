#!/usr/bin/env python3
"""
relife_patch7.py
"💰 এখন কত আছে (Live)" simplified — only 3 balance lines now:
Reception (everyone) + Home Treasury + Bank (Owner only). All the period-style
breakdown lines (Cash collection, Paid expense, Accepted handover/receipt,
Household Withdrawal, Transfer out...) are removed from the Live view; the
regular date-range reports (আজ/গতকাল/এই সপ্তাহ/এই মাস/কাস্টম তারিখ) are
completely unaffected.

Run from ~/relife-clinic-os (repo root):
    python relife_patch7.py

Safe to re-run — already-applied edits are skipped and reported as such.
"""
from pathlib import Path

REPO_ROOT = Path.home() / "relife-clinic-os"
BOT_PY = REPO_ROOT / "03_Bot" / "bot.py"

results = []


def apply_edit(path, old, new, label):
    if not path.exists():
        results.append((False, f"{label}: ❌ file not found: {path}"))
        return
    text = path.read_text(encoding="utf-8")
    if new in text:
        results.append((True, f"{label}: ✅ already present (skipped)"))
        return
    if old not in text:
        results.append((False, f"{label}: ❌ anchor text not found — file may have changed"))
        return
    if text.count(old) != 1:
        results.append((False, f"{label}: ❌ anchor is not unique ({text.count(old)} matches) — aborting this edit"))
        return
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    results.append((True, f"{label}: ✅ applied"))


OLD_1 = 'def _cash_custody_summary_text(summary: dict, role_str: str) -> str:\n    is_owner = role_str.strip() == roles.Role.OWNER.value\n    is_live = summary.get("Start_Date") == _LIVE_BALANCE_START_DATE\n    balance_label = "বর্তমান ব্যালেন্স" if is_live else "নির্বাচিত সময়ের net balance"\n    header = (\n        "💰 এখন কত আছে (Live)" if is_live\n        else f"⚖️ Cash reconciliation — {summary[\'Date\']}"\n    )\n    lines = [\n        header,\n        "",\n        "Reception",\n        f"Cash collection: ৳{summary[\'Cash_Collected\']:.0f}",\n        f"Paid ছোট খরচ: ৳{summary[\'Reception_Expense\']:.0f}",\n    ]\n    reception_salary = summary.get("Reception_Salary", 0)\n    if reception_salary:\n        lines.append(\n            f"{\'বেতন পরিশোধ\' if is_owner else \'অন্যান্য নগদ পরিশোধ\'}: "\n            f"৳{reception_salary:.0f}"\n        )\n    lines.append(f"Accepted handover: ৳{summary[\'Reception_Handover\']:.0f}")\n    in_transit = summary.get("Reception_In_Transit", 0)\n    if in_transit:\n        lines.append(\n            f"⏳ পাঠানো হয়েছে, গ্রহণ বাকি: ৳{in_transit:.0f}"\n        )\n    lines.append(f"{balance_label}: ৳{summary[\'Reception_Balance\']:.0f}")\n\n    if is_owner:\n        lines += [\n            "",\n            "Home Treasury",\n            f"Accepted receipt: ৳{summary[\'Home_Received\']:.0f}",\n            f"বড় clinic expense: ৳{summary[\'Home_Clinic_Expense\']:.0f}",\n            f"বেতন পরিশোধ: ৳{summary.get(\'Home_Salary\', 0):.0f}",\n            f"Household Withdrawal: ৳{summary[\'Household_Withdrawal\']:.0f}",\n            f"Transfer out: ৳{summary[\'Home_Transfer_Out\']:.0f}",\n        ]\n        home_transit = summary.get("Home_In_Transit", 0)\n        if home_transit:\n            lines.append(f"⏳ পাঠানো হয়েছে, গ্রহণ বাকি: ৳{home_transit:.0f}")\n        lines.append(f"{balance_label}: ৳{summary[\'Home_Balance\']:.0f}")\n\n        lines += [\n            "",\n            "Bank",\n            f"Accepted receipt: ৳{summary.get(\'Bank_Received\', 0):.0f}",\n            f"খরচ: ৳{summary.get(\'Bank_Expense\', 0):.0f}",\n            f"বেতন পরিশোধ: ৳{summary.get(\'Bank_Salary\', 0):.0f}",\n            f"Transfer out: ৳{summary.get(\'Bank_Transfer_Out\', 0):.0f}",\n            f"{balance_label}: ৳{summary.get(\'Bank_Balance\', 0):.0f}",\n        ]\n\n        unclassified = summary.get("Unclassified_Total", 0)\n        if unclassified:\n            lines += [\n                "",\n                f"⚠️ Department ছাড়া এন্ট্রি: ৳{unclassified:.0f}",\n                "এগুলো উপরের কোনো হিসাবে ধরা হয়নি। Sheet-এ Department বসালে যোগ হবে।",\n            ]\n\n    if is_live:\n        lines += [\n            "",\n            "✅ এটি এখন পর্যন্ত সব হিসাব যোগ করে বের করা লাইভ ব্যালেন্স — "\n            "আগের সব দিনের residual-ও এতে ধরা আছে।",\n        ]\n    else:\n        lines += [\n            "",\n            "ℹ️ এটি নির্বাচিত সময়ের movement balance; আগের opening cash এতে নেই।",\n        ]\n    return "\\n".join(lines)'

NEW_1 = 'def _live_balance_text(summary: dict, role_str: str) -> str:\n    is_owner = role_str.strip() == roles.Role.OWNER.value\n    lines = [\n        "💰 এখন কত আছে (Live)",\n        "",\n        f"⚖️ Reception: ৳{summary[\'Reception_Balance\']:.0f}",\n    ]\n    if is_owner:\n        lines.append(f"🏠 Home Treasury: ৳{summary[\'Home_Balance\']:.0f}")\n        lines.append(f"🏦 Bank: ৳{summary.get(\'Bank_Balance\', 0):.0f}")\n    return "\\n".join(lines)\n\n\ndef _cash_custody_summary_text(summary: dict, role_str: str) -> str:\n    if summary.get("Start_Date") == _LIVE_BALANCE_START_DATE:\n        return _live_balance_text(summary, role_str)\n\n    is_owner = role_str.strip() == roles.Role.OWNER.value\n    lines = [\n        f"⚖️ Cash reconciliation — {summary[\'Date\']}",\n        "",\n        "Reception",\n        f"Cash collection: ৳{summary[\'Cash_Collected\']:.0f}",\n        f"Paid ছোট খরচ: ৳{summary[\'Reception_Expense\']:.0f}",\n    ]\n    reception_salary = summary.get("Reception_Salary", 0)\n    if reception_salary:\n        lines.append(\n            f"{\'বেতন পরিশোধ\' if is_owner else \'অন্যান্য নগদ পরিশোধ\'}: "\n            f"৳{reception_salary:.0f}"\n        )\n    lines.append(f"Accepted handover: ৳{summary[\'Reception_Handover\']:.0f}")\n    in_transit = summary.get("Reception_In_Transit", 0)\n    if in_transit:\n        lines.append(\n            f"⏳ পাঠানো হয়েছে, গ্রহণ বাকি: ৳{in_transit:.0f}"\n        )\n    lines.append(\n        f"নির্বাচিত সময়ের net balance: ৳{summary[\'Reception_Balance\']:.0f}"\n    )\n\n    if is_owner:\n        lines += [\n            "",\n            "Home Treasury",\n            f"Accepted receipt: ৳{summary[\'Home_Received\']:.0f}",\n            f"বড় clinic expense: ৳{summary[\'Home_Clinic_Expense\']:.0f}",\n            f"বেতন পরিশোধ: ৳{summary.get(\'Home_Salary\', 0):.0f}",\n            f"Household Withdrawal: ৳{summary[\'Household_Withdrawal\']:.0f}",\n            f"Transfer out: ৳{summary[\'Home_Transfer_Out\']:.0f}",\n        ]\n        home_transit = summary.get("Home_In_Transit", 0)\n        if home_transit:\n            lines.append(f"⏳ পাঠানো হয়েছে, গ্রহণ বাকি: ৳{home_transit:.0f}")\n        lines.append(\n            f"নির্বাচিত সময়ের net balance: ৳{summary[\'Home_Balance\']:.0f}"\n        )\n\n        lines += [\n            "",\n            "Bank",\n            f"Accepted receipt: ৳{summary.get(\'Bank_Received\', 0):.0f}",\n            f"খরচ: ৳{summary.get(\'Bank_Expense\', 0):.0f}",\n            f"বেতন পরিশোধ: ৳{summary.get(\'Bank_Salary\', 0):.0f}",\n            f"Transfer out: ৳{summary.get(\'Bank_Transfer_Out\', 0):.0f}",\n            f"নির্বাচিত সময়ের net balance: ৳{summary.get(\'Bank_Balance\', 0):.0f}",\n        ]\n\n        unclassified = summary.get("Unclassified_Total", 0)\n        if unclassified:\n            lines += [\n                "",\n                f"⚠️ Department ছাড়া এন্ট্রি: ৳{unclassified:.0f}",\n                "এগুলো উপরের কোনো হিসাবে ধরা হয়নি। Sheet-এ Department বসালে যোগ হবে।",\n            ]\n\n    lines += [\n        "",\n        "ℹ️ এটি নির্বাচিত সময়ের movement balance; আগের opening cash এতে নেই।",\n    ]\n    return "\\n".join(lines)'

apply_edit(BOT_PY, OLD_1, NEW_1, "bot.py: simplify Live balance view to 3 lines")

TEST_PY = REPO_ROOT / "07_Testing" / "test_live_cash_balance.py"

OLD_2 = '    def test_live_summary_uses_live_header_and_footer(self):\n        summary = self._summary(bot._LIVE_BALANCE_START_DATE)\n        text = bot._cash_custody_summary_text(summary, "Owner")\n        self.assertIn("এখন কত আছে (Live)", text)\n        self.assertIn("বর্তমান ব্যালেন্স", text)\n        self.assertNotIn("এটি নির্বাচিত সময়ের movement balance", text)\n\n    def test_period_summary_keeps_the_old_wording(self):\n        summary = self._summary("2026-08-14")\n        text = bot._cash_custody_summary_text(summary, "Owner")\n        self.assertIn("Cash reconciliation", text)\n        self.assertIn("নির্বাচিত সময়ের net balance", text)\n        self.assertIn("এটি নির্বাচিত সময়ের movement balance", text)\n\n    def test_non_owner_still_only_sees_reception_in_live_mode(self):\n        summary = self._summary(bot._LIVE_BALANCE_START_DATE)\n        text = bot._cash_custody_summary_text(summary, "Receptionist")\n        self.assertIn("Reception", text)\n        self.assertNotIn("Home Treasury", text)\n        self.assertNotIn("Bank", text)'

NEW_2 = '    def test_live_summary_shows_only_the_three_balance_lines(self):\n        summary = self._summary(bot._LIVE_BALANCE_START_DATE)\n        text = bot._cash_custody_summary_text(summary, "Owner")\n        self.assertIn("এখন কত আছে (Live)", text)\n        self.assertIn("Reception: ৳300", text)\n        self.assertIn("Home Treasury: ৳500", text)\n        self.assertIn("Bank: ৳0", text)\n        # None of the period-report breakdown lines should appear.\n        for excluded in (\n            "Cash collection", "Accepted handover", "Accepted receipt",\n            "Household Withdrawal", "Transfer out", "নির্বাচিত সময়ের",\n            "এটি নির্বাচিত সময়ের movement balance",\n        ):\n            with self.subTest(excluded=excluded):\n                self.assertNotIn(excluded, text)\n\n    def test_period_summary_keeps_the_old_wording(self):\n        summary = self._summary("2026-08-14")\n        text = bot._cash_custody_summary_text(summary, "Owner")\n        self.assertIn("Cash reconciliation", text)\n        self.assertIn("নির্বাচিত সময়ের net balance", text)\n        self.assertIn("এটি নির্বাচিত সময়ের movement balance", text)\n\n    def test_non_owner_live_view_shows_only_reception(self):\n        summary = self._summary(bot._LIVE_BALANCE_START_DATE)\n        text = bot._cash_custody_summary_text(summary, "Receptionist")\n        self.assertIn("Reception: ৳300", text)\n        self.assertNotIn("Home Treasury", text)\n        self.assertNotIn("Bank", text)'

apply_edit(TEST_PY, OLD_2, NEW_2, "test_live_cash_balance.py: update to 3-line live assertions")

print("\n" + "=" * 60)
print("relife_patch7.py — results")
print("=" * 60)
all_ok = True
for ok, msg in results:
    print(msg)
    all_ok = all_ok and ok
print("=" * 60)
if all_ok:
    print("✅ সব ঠিকভাবে হয়েছে। এখন চালাও:")
    print("   cd ~/relife-clinic-os")
    print("   python3 -m py_compile 03_Bot/bot.py")
    print("   python3 -m unittest 07_Testing/test_live_cash_balance.py -v")
    print("   git add . && git commit -m 'Simplify Live balance view to 3 lines' && git push")
else:
    print("❌ কিছু একটা ধাপ ব্যর্থ হয়েছে — উপরের ❌ লাইনগুলো আমাকে পাঠাও।")
