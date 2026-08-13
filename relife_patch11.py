#!/usr/bin/env python3
"""Keep expense approval/payment on the expense department's workbook."""
from pathlib import Path

ROOT = Path.home() / "relife-clinic-os"
CFG = ROOT / "03_Bot" / "config.py"
SHEETS = ROOT / "03_Bot" / "sheets.py"
BOT = ROOT / "03_Bot" / "bot.py"
CONTRACT = ROOT / "03_Bot" / "data_contract.py"
TEST = ROOT / "07_Testing" / "test_two_sheet_finance_routing.py"


def edit(path, old, new, label):
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: ✅ already applied")
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"❌ {label}: anchor count {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: ✅ applied")


edit(CFG, '''DENTAL_GOOGLE_SHEET_ID = os.getenv("DENTAL_GOOGLE_SHEET_ID")
''', '''DENTAL_GOOGLE_SHEET_ID = os.getenv("DENTAL_GOOGLE_SHEET_ID")


def sheet_id_for_department(department: str) -> str:
    department = str(department or "").strip()
    if department == "Dental":
        if not DENTAL_GOOGLE_SHEET_ID:
            raise RuntimeError("DENTAL_GOOGLE_SHEET_ID is missing")
        return DENTAL_GOOGLE_SHEET_ID
    if department == "Physio":
        if not GOOGLE_SHEET_ID:
            raise RuntimeError("GOOGLE_SHEET_ID is missing")
        return GOOGLE_SHEET_ID
    raise ValueError(f"Invalid department: {department}")
''', "department to sheet mapping")

edit(CONTRACT, '''def metadata(
    record_type,
    *,
    legacy_record_id="",
''', '''def metadata(
    record_type,
    *,
    legacy_record_id="",
    clinic_id="",
''', "metadata accepts clinic id")

edit(CONTRACT, '''    if legacy_record_id:
        record_id = f"{CLINIC_ID}:{legacy_record_id}"
    else:
        record_id = new_record_id(record_type)

    return {
        "Organization_ID": ORGANIZATION_ID,
        "Clinic_ID": CLINIC_ID,
''', '''    active_clinic_id = str(clinic_id or CLINIC_ID).strip()
    if legacy_record_id:
        record_id = f"{active_clinic_id}:{legacy_record_id}"
    else:
        record_id = new_record_id(record_type)

    return {
        "Organization_ID": ORGANIZATION_ID,
        "Clinic_ID": active_clinic_id,
''', "metadata uses active clinic id")

edit(SHEETS, '''    envelope = metadata(
        record_type,
        legacy_record_id=record_id,
''', '''    active_clinic_id = (
        "RELIFE-DENTAL"
        if config.DENTAL_GOOGLE_SHEET_ID
        and str(_active_sheet_id()) == str(config.DENTAL_GOOGLE_SHEET_ID)
        else "RELIFE-PHYSIO"
    )
    envelope = metadata(
        record_type,
        legacy_record_id=record_id,
        clinic_id=active_clinic_id,
''', "unified metadata follows workbook")

insert = '''

def _expense_action_for_department(
    department: str,
    function,
    *args,
    **kwargs,
):
    """Run one expense action against its explicit department workbook."""
    with sheet_scope.use_sheet(config.sheet_id_for_department(department)):
        return function(*args, **kwargs)


def finalize_expense_request_for_department(
    department: str,
    expense_id: str,
    approved_by: str,
    decision: str,
    departments=None,
) -> dict:
    return _expense_action_for_department(
        department,
        finalize_expense_request,
        expense_id,
        approved_by,
        decision,
        departments,
    )


def mark_expense_paid_for_department(
    department: str,
    expense_id: str,
    paid_by: str,
    departments=None,
) -> dict:
    return _expense_action_for_department(
        department,
        mark_expense_paid,
        expense_id,
        paid_by,
        departments,
    )


def _legacy_expense_action_across_departments(
    function,
    expense_id: str,
    *args,
    departments=None,
) -> dict:
    """Compatibility for buttons sent before department was encoded.

    Never updates when the same Expense_ID exists in more than one workbook.
    """
    allowed = _department_scope_values(departments)
    candidates = [
        department for department in _FINANCE_DEPARTMENTS
        if allowed is None or department in allowed
    ]
    matches = []
    for department in candidates:
        with sheet_scope.use_sheet(config.sheet_id_for_department(department)):
            rows = safe_get_all_records(_worksheet(config.SHEET_EXPENSES))
        if any(
            str(row.get("Expense_ID", "")).strip() == str(expense_id).strip()
            for row in rows
        ):
            matches.append(department)
    if not matches:
        return {"ok": False, "reason": "not_found"}
    if len(matches) != 1:
        return {"ok": False, "reason": "ambiguous_department"}
    return _expense_action_for_department(
        matches[0], function, expense_id, *args, departments
    )


def finalize_expense_request_legacy(
    expense_id: str, approved_by: str, decision: str, departments=None
) -> dict:
    return _legacy_expense_action_across_departments(
        finalize_expense_request,
        expense_id,
        approved_by,
        decision,
        departments=departments,
    )


def mark_expense_paid_legacy(
    expense_id: str, paid_by: str, departments=None
) -> dict:
    return _legacy_expense_action_across_departments(
        mark_expense_paid,
        expense_id,
        paid_by,
        departments=departments,
    )
'''

edit(SHEETS, '''def get_expenses_for_date(
''', insert + '''\n\ndef get_expenses_for_date(
''', "department-routed expense actions")

edit(BOT, '''            "✅ অনুমোদন", callback_data=f"expact_approve_{expense_id}"
''', '''            "✅ অনুমোদন", callback_data=(
                f"expact_{expense.get('Department', '')}_approve_{expense_id}"
            )
''', "notification approval callback includes department")

edit(BOT, '''            "❌ বাতিল", callback_data=f"expact_reject_{expense_id}"
''', '''            "❌ বাতিল", callback_data=(
                f"expact_{expense.get('Department', '')}_reject_{expense_id}"
            )
''', "notification rejection callback includes department")

edit(BOT, '''        expense_id = str(row.get("Expense_ID", "")).strip()
        buttons.append([
            InlineKeyboardButton(
                f"✅ {expense_id} অনুমোদন",
                callback_data=f"expact_approve_{expense_id}",
            ),
            InlineKeyboardButton(
                "❌ বাতিল",
                callback_data=f"expact_reject_{expense_id}",
            ),
''', '''        expense_id = str(row.get("Expense_ID", "")).strip()
        department = str(row.get("Department", "")).strip()
        buttons.append([
            InlineKeyboardButton(
                f"✅ {expense_id} অনুমোদন",
                callback_data=f"expact_{department}_approve_{expense_id}",
            ),
            InlineKeyboardButton(
                "❌ বাতিল",
                callback_data=f"expact_{department}_reject_{expense_id}",
            ),
''', "approval list callback includes department")

edit(BOT, '''    payload = query.data.replace("expact_", "", 1)
    action, expense_id = payload.split("_", 1)
    decision = "Approved" if action == "approve" else "Rejected"
''', '''    payload = query.data.replace("expact_", "", 1)
    parts = payload.split("_", 2)
    if len(parts) == 3 and parts[0] in (
        config.DEPARTMENT_PHYSIO, config.DEPARTMENT_DENTAL
    ):
        department, action, expense_id = parts
    else:
        department = ""
        action, expense_id = payload.split("_", 1)
    decision = "Approved" if action == "approve" else "Rejected"
''', "approval callback parses department")

edit(BOT, '''    result = await async_runtime.run_sheets_write(
        sheets.finalize_expense_request, expense_id, actor, decision,
        _finance_departments(staff)
    )
''', '''    if department:
        result = await async_runtime.run_sheets_write(
            sheets.finalize_expense_request_for_department,
            department, expense_id, actor, decision,
            _finance_departments(staff),
        )
    else:
        result = await async_runtime.run_sheets_write(
            sheets.finalize_expense_request_legacy,
            expense_id, actor, decision, _finance_departments(staff),
        )
''', "approval executes on source workbook")

edit(BOT, '''    else:
        await query.edit_message_text(f"❌ {expense_id} পাওয়া যায়নি।")


async def approved_expenses_start(
''', '''    elif result.get("reason") == "ambiguous_department":
        await query.edit_message_text(
            f"⛔ {expense_id} দুই Department-এ আছে; নতুন request list থেকে button চাপো।"
        )
    else:
        await query.edit_message_text(f"❌ {expense_id} পাওয়া যায়নি।")


async def approved_expenses_start(
''', "approval handles duplicate legacy id")

edit(BOT, '''        expense_id = str(row.get("Expense_ID", "")).strip()
        lines.append(
''', '''        expense_id = str(row.get("Expense_ID", "")).strip()
        department = str(row.get("Department", "")).strip()
        lines.append(
''', "paid list reads department")

edit(BOT, '''            callback_data=f"exppaid_{expense_id}",
''', '''            callback_data=f"exppaid_{department}_{expense_id}",
''', "paid callback includes department")

edit(BOT, '''    expense_id = query.data.replace("exppaid_", "", 1)
    actor = (
''', '''    payload = query.data.replace("exppaid_", "", 1)
    parts = payload.split("_", 1)
    if len(parts) == 2 and parts[0] in (
        config.DEPARTMENT_PHYSIO, config.DEPARTMENT_DENTAL
    ):
        department, expense_id = parts
    else:
        department, expense_id = "", payload
    actor = (
''', "paid callback parses department")

edit(BOT, '''    result = await async_runtime.run_sheets_write(
        sheets.mark_expense_paid, expense_id, actor, _finance_departments(staff)
    )
''', '''    if department:
        result = await async_runtime.run_sheets_write(
            sheets.mark_expense_paid_for_department,
            department, expense_id, actor, _finance_departments(staff),
        )
    else:
        result = await async_runtime.run_sheets_write(
            sheets.mark_expense_paid_legacy,
            expense_id, actor, _finance_departments(staff),
        )
''', "paid executes on source workbook")

edit(BOT, '''    else:
        await query.edit_message_text(f"❌ {expense_id} পাওয়া যায়নি।")


_FINANCIAL_REPORT_MENUS = {
''', '''    elif result.get("reason") == "ambiguous_department":
        await query.edit_message_text(
            f"⛔ {expense_id} দুই Department-এ আছে; approved list থেকে নতুন button চাপো।"
        )
    else:
        await query.edit_message_text(f"❌ {expense_id} পাওয়া যায়নি।")


_FINANCIAL_REPORT_MENUS = {
''', "paid handles duplicate legacy id")

TEST.write_text('''import os, sys, unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_Bot"))
os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("GOOGLE_SHEET_ID", "physio")
os.environ.setdefault("DENTAL_GOOGLE_SHEET_ID", "dental")
cred = ROOT / "credentials.json"
made = not cred.exists()
if made:
    cred.write_text("{}")

import config, data_contract, sheet_scope, sheets


def tearDownModule():
    if made:
        cred.unlink(missing_ok=True)


class TwoSheetFinanceRoutingTests(unittest.TestCase):
    def tearDown(self):
        sheet_scope._sheet_override.set(None)

    def test_department_sheet_mapping(self):
        self.assertEqual(config.sheet_id_for_department("Physio"), "physio")
        self.assertEqual(config.sheet_id_for_department("Dental"), "dental")

    def test_dental_metadata_uses_dental_clinic_id(self):
        with sheet_scope.use_sheet("dental"):
            active = "RELIFE-DENTAL" if sheets._active_sheet_id() == config.DENTAL_GOOGLE_SHEET_ID else "RELIFE-PHYSIO"
            value = data_contract.metadata("expense", legacy_record_id="EX0001", clinic_id=active)
        self.assertEqual(value["Clinic_ID"], "RELIFE-DENTAL")
        self.assertEqual(value["Record_ID"], "RELIFE-DENTAL:EX0001")

    def test_explicit_dental_approval_binds_dental_sheet(self):
        seen = []
        def fake(*args, **kwargs):
            seen.append(sheets._active_sheet_id())
            return {"ok": True}
        with patch.object(sheets, "finalize_expense_request", side_effect=fake):
            result = sheets.finalize_expense_request_for_department(
                "Dental", "EX0001", "Owner", "Approved", {"Dental"}
            )
        self.assertTrue(result["ok"])
        self.assertEqual(seen, ["dental"])

    def test_legacy_duplicate_fails_closed(self):
        class WS:
            def __init__(self, sid): self.sid = sid
        def fake_ws(_): return WS(sheets._active_sheet_id())
        def fake_records(ws):
            return [{"Expense_ID": "EX0001", "Department": "Dental"}]
        with patch.object(sheets, "_worksheet", side_effect=fake_ws), patch.object(
            sheets, "safe_get_all_records", side_effect=fake_records
        ):
            result = sheets.finalize_expense_request_legacy(
                "EX0001", "Owner", "Approved", {"Physio", "Dental"}
            )
        self.assertEqual(result["reason"], "ambiguous_department")


if __name__ == "__main__":
    unittest.main()
''', encoding="utf-8")
print("test_two_sheet_finance_routing.py: ✅ created")
print("\nRun:")
print("python3 -m py_compile 03_Bot/config.py 03_Bot/data_contract.py 03_Bot/sheets.py 03_Bot/bot.py")
print("python3 -m unittest 07_Testing/test_two_sheet_finance_routing.py 07_Testing/test_two_sheet_router.py 07_Testing/test_finance_cash_custody.py -v")
print("git add 03_Bot/config.py 03_Bot/data_contract.py 03_Bot/sheets.py 03_Bot/bot.py 07_Testing/test_two_sheet_finance_routing.py relife_patch11.py")
print("git commit -m 'Route financial actions by department workbook' && git push")
