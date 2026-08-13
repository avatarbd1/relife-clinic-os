#!/usr/bin/env python3
"""
relife_patch6.py
1) Owner's চলতি হিসাব restructured: 13 flat buttons -> 4 tabs
   (⚖️ ক্যাশ ব্যালেন্স / 📊 Dashboard / 🧾 হিসাব ও খরচ / 🏠 Household Withdrawal),
   with Dashboard and হিসাব ও খরচ opening their own submenus.
   Receptionist/Manager menus keep their existing flat shape (unchanged).
2) New ❌ প্রত্যাখ্যাত খরচ (Rejected Expenses) view: Rejected rows no longer
   clutter 💸 ক্লিনিক খরচ হিসাব — they move to their own report.

Run from ~/relife-clinic-os (repo root):
    python relife_patch6.py

Safe to re-run — already-applied edits are skipped and reported as such.
"""
from pathlib import Path

REPO_ROOT = Path.home() / "relife-clinic-os"
ROLES_PY = REPO_ROOT / "03_Bot" / "roles.py"
BOT_PY = REPO_ROOT / "03_Bot" / "bot.py"
EXISTING_TEST_PY = REPO_ROOT / "07_Testing" / "test_finance_cash_custody.py"
NEW_TEST_PY = REPO_ROOT / "07_Testing" / "test_finance_menu_restructure.py"

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


def create_file(path, content, label):
    if path.exists() and path.read_text(encoding="utf-8").strip() == content.strip():
        results.append((True, f"{label}: ✅ already present (skipped)"))
        return
    if path.exists():
        results.append((True, f"{label}: ✅ already exists (left as-is)"))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    results.append((True, f"{label}: ✅ created"))


# =============================================================================
# roles.py edits
# =============================================================================

# --- Edit R1: new menu constants ---
R_OLD_1 = '''MENU_PHYSIO_FINANCE_DASHBOARD = "🩺 Physio Dashboard"
MENU_DENTAL_FINANCE_DASHBOARD = "🦷 Dental Dashboard"
MENU_COMBINED_BUSINESS_SUMMARY = "🏢 Combined Business Summary"'''

R_NEW_1 = '''MENU_PHYSIO_FINANCE_DASHBOARD = "🩺 Physio Dashboard"
MENU_DENTAL_FINANCE_DASHBOARD = "🦷 Dental Dashboard"
MENU_COMBINED_BUSINESS_SUMMARY = "🏢 Combined Business Summary"
MENU_FINANCE_DASHBOARDS = "📊 Dashboard"
MENU_FINANCE_ACCOUNTS = "🧾 হিসাব ও খরচ"
MENU_REJECTED_EXPENSES = "❌ প্রত্যাখ্যাত খরচ"'''

apply_edit(ROLES_PY, R_OLD_1, R_NEW_1, "roles.py: new menu constants")

# --- Edit R2: ROLE_HIDDEN_MENU_ITEMS gains MENU_REJECTED_EXPENSES ---
R_OLD_2 = '''ROLE_HIDDEN_MENU_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [
        MENU_ATTENDANCE, MENU_TODAY_APPOINTMENTS,
        MENU_PATIENT_REG, MENU_PATIENT_HISTORY, MENU_PATIENT_LIST,
        MENU_TREATMENT_NOTE, MENU_TREATMENT_PLAN, MENU_TREATMENT_HISTORY,
        MENU_DAILY_REGISTER, MENU_STAFF_AI_QUERY, MENU_CASE_STUDY, MENU_CLINICAL_AI,
        MENU_SALARY, MENU_SALARY_HISTORY, MENU_MY_PAYMENTS,
        MENU_OWNER_CLINIC_EXPENSE, MENU_HOUSEHOLD_WITHDRAWAL,
        MENU_EXPENSE_APPROVAL, MENU_EXPENSE_TRACKER,
        MENU_CASH_RECEIVE, MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
        MENU_PHYSIO_FINANCE_DASHBOARD, MENU_DENTAL_FINANCE_DASHBOARD,
        MENU_COMBINED_BUSINESS_SUMMARY,
    ],
    Role.RECEPTIONIST: [
        MENU_ATTENDANCE, MENU_TODAY_APPOINTMENTS,
        MENU_PATIENT_REG, MENU_PATIENT_LIST, MENU_DAILY_REGISTER,
        MENU_SMALL_EXPENSE_REQUEST, MENU_APPROVED_EXPENSES,
        MENU_EXPENSE_TRACKER, MENU_CASH_HANDOVER, MENU_CASH_MOVEMENTS,
        MENU_CUSTODY_BALANCE,
    ],
    Role.THERAPIST: [MENU_ATTENDANCE, MENU_CLINICAL_AI],
    Role.MANAGER: [
        MENU_ATTENDANCE, MENU_TODAY_APPOINTMENTS,
        MENU_PATIENT_REG, MENU_PATIENT_LIST, MENU_TREATMENT_HISTORY,
        MENU_DAILY_REGISTER, MENU_EXPENSE_TRACKER,
        MENU_CASH_RECEIVE, MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
    ],
}'''

R_NEW_2 = '''ROLE_HIDDEN_MENU_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [
        MENU_ATTENDANCE, MENU_TODAY_APPOINTMENTS,
        MENU_PATIENT_REG, MENU_PATIENT_HISTORY, MENU_PATIENT_LIST,
        MENU_TREATMENT_NOTE, MENU_TREATMENT_PLAN, MENU_TREATMENT_HISTORY,
        MENU_DAILY_REGISTER, MENU_STAFF_AI_QUERY, MENU_CASE_STUDY, MENU_CLINICAL_AI,
        MENU_SALARY, MENU_SALARY_HISTORY, MENU_MY_PAYMENTS,
        MENU_OWNER_CLINIC_EXPENSE, MENU_HOUSEHOLD_WITHDRAWAL,
        MENU_EXPENSE_APPROVAL, MENU_EXPENSE_TRACKER, MENU_REJECTED_EXPENSES,
        MENU_CASH_RECEIVE, MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
        MENU_PHYSIO_FINANCE_DASHBOARD, MENU_DENTAL_FINANCE_DASHBOARD,
        MENU_COMBINED_BUSINESS_SUMMARY,
    ],
    Role.RECEPTIONIST: [
        MENU_ATTENDANCE, MENU_TODAY_APPOINTMENTS,
        MENU_PATIENT_REG, MENU_PATIENT_LIST, MENU_DAILY_REGISTER,
        MENU_SMALL_EXPENSE_REQUEST, MENU_APPROVED_EXPENSES,
        MENU_EXPENSE_TRACKER, MENU_REJECTED_EXPENSES,
        MENU_CASH_HANDOVER, MENU_CASH_MOVEMENTS,
        MENU_CUSTODY_BALANCE,
    ],
    Role.THERAPIST: [MENU_ATTENDANCE, MENU_CLINICAL_AI],
    Role.MANAGER: [
        MENU_ATTENDANCE, MENU_TODAY_APPOINTMENTS,
        MENU_PATIENT_REG, MENU_PATIENT_LIST, MENU_TREATMENT_HISTORY,
        MENU_DAILY_REGISTER, MENU_EXPENSE_TRACKER, MENU_REJECTED_EXPENSES,
        MENU_CASH_RECEIVE, MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
    ],
}'''

apply_edit(ROLES_PY, R_OLD_2, R_NEW_2, "roles.py: permission list gains Rejected Expenses")

# --- Edit R3: restructure ROLE_FINANCE_ITEMS + new group dicts ---
R_OLD_3 = '''ROLE_FINANCE_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [
        MENU_PHYSIO_FINANCE_DASHBOARD, MENU_DENTAL_FINANCE_DASHBOARD,
        MENU_COMBINED_BUSINESS_SUMMARY,
        MENU_SALARY, MENU_SALARY_HISTORY, MENU_MY_PAYMENTS,
        MENU_OWNER_CLINIC_EXPENSE, MENU_HOUSEHOLD_WITHDRAWAL,
        MENU_EXPENSE_APPROVAL, MENU_EXPENSE_TRACKER,
        MENU_CASH_RECEIVE, MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
    ],
    Role.RECEPTIONIST: [
        MENU_SMALL_EXPENSE_REQUEST, MENU_APPROVED_EXPENSES,
        MENU_EXPENSE_TRACKER, MENU_CASH_HANDOVER,
        MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
    ],
    Role.MANAGER: [
        MENU_EXPENSE_TRACKER, MENU_CASH_RECEIVE,
        MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
    ],
}'''

R_NEW_3 = '''ROLE_FINANCE_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [
        MENU_CUSTODY_BALANCE,
        MENU_FINANCE_DASHBOARDS,
        MENU_FINANCE_ACCOUNTS,
        MENU_HOUSEHOLD_WITHDRAWAL,
    ],
    Role.RECEPTIONIST: [
        MENU_SMALL_EXPENSE_REQUEST, MENU_APPROVED_EXPENSES,
        MENU_EXPENSE_TRACKER, MENU_REJECTED_EXPENSES, MENU_CASH_HANDOVER,
        MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
    ],
    Role.MANAGER: [
        MENU_EXPENSE_TRACKER, MENU_REJECTED_EXPENSES, MENU_CASH_RECEIVE,
        MENU_CASH_MOVEMENTS, MENU_CUSTODY_BALANCE,
    ],
}

ROLE_FINANCE_DASHBOARD_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [
        MENU_PHYSIO_FINANCE_DASHBOARD, MENU_DENTAL_FINANCE_DASHBOARD,
        MENU_COMBINED_BUSINESS_SUMMARY,
    ],
}

ROLE_FINANCE_ACCOUNTS_ITEMS: dict[Role, list[str]] = {
    Role.OWNER: [
        MENU_SALARY, MENU_SALARY_HISTORY, MENU_MY_PAYMENTS,
        MENU_OWNER_CLINIC_EXPENSE, MENU_EXPENSE_APPROVAL, MENU_EXPENSE_TRACKER,
        MENU_REJECTED_EXPENSES, MENU_CASH_RECEIVE, MENU_CASH_MOVEMENTS,
    ],
}'''

apply_edit(ROLES_PY, R_OLD_3, R_NEW_3, "roles.py: restructure Owner's finance menu into 4 tabs")

# =============================================================================
# bot.py edits
# =============================================================================

# --- Edit B1: _ALL_MENU_ITEMS gains the new labels ---
B_OLD_1 = '''    roles.MENU_PHYSIO_FINANCE_DASHBOARD,
    roles.MENU_DENTAL_FINANCE_DASHBOARD,
    roles.MENU_COMBINED_BUSINESS_SUMMARY,
    roles.MENU_FINANCE,
]'''

B_NEW_1 = '''    roles.MENU_PHYSIO_FINANCE_DASHBOARD,
    roles.MENU_DENTAL_FINANCE_DASHBOARD,
    roles.MENU_COMBINED_BUSINESS_SUMMARY,
    roles.MENU_FINANCE_DASHBOARDS,
    roles.MENU_FINANCE_ACCOUNTS,
    roles.MENU_REJECTED_EXPENSES,
    roles.MENU_FINANCE,
]'''

apply_edit(BOT_PY, B_OLD_1, B_NEW_1, "bot.py: register new labels in _ALL_MENU_ITEMS")

# --- Edit B2: two new submenu handlers ---
B_OLD_2 = '''async def finance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _generic_submenu(update, context, roles.ROLE_FINANCE_ITEMS, "💰 চলতি হিসাব — কী করতে চাও?")'''

B_NEW_2 = '''async def finance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _generic_submenu(update, context, roles.ROLE_FINANCE_ITEMS, "💰 চলতি হিসাব — কী করতে চাও?")


async def finance_dashboard_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _generic_submenu(
        update, context, roles.ROLE_FINANCE_DASHBOARD_ITEMS, "📊 Dashboard — কী দেখতে চাও?"
    )


async def finance_accounts_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _generic_submenu(
        update, context, roles.ROLE_FINANCE_ACCOUNTS_ITEMS, "🧾 হিসাব ও খরচ — কী করতে চাও?"
    )'''

apply_edit(BOT_PY, B_OLD_2, B_NEW_2, "bot.py: Dashboard-group and Accounts-group submenu handlers")

# --- Edit B3: register "rejected" in _FINANCIAL_REPORT_MENUS ---
B_OLD_3 = '''_FINANCIAL_REPORT_MENUS = {
    "expense": roles.MENU_EXPENSE_TRACKER,
    "cash": roles.MENU_CUSTODY_BALANCE,
}'''

B_NEW_3 = '''_FINANCIAL_REPORT_MENUS = {
    "expense": roles.MENU_EXPENSE_TRACKER,
    "cash": roles.MENU_CUSTODY_BALANCE,
    "rejected": roles.MENU_REJECTED_EXPENSES,
}'''

apply_edit(BOT_PY, B_OLD_3, B_NEW_3, "bot.py: register rejected report permission entry")

# --- Edit B4: exclude Rejected rows from the default expense report ---
B_OLD_4 = '''def _expense_report_text(rows, start_date: str, end_date: str, role_str: str) -> str:
    owner = role_str.strip() == roles.Role.OWNER.value
    visible_rows = rows if owner else [
        row for row in rows
        if str(row.get("Paid_From", "")).strip()
        != config.CASH_CUSTODIAN_HOME_TREASURY
    ]
    paid_clinic = sum('''

B_NEW_4 = '''def _expense_report_text(rows, start_date: str, end_date: str, role_str: str) -> str:
    owner = role_str.strip() == roles.Role.OWNER.value
    non_rejected = [
        row for row in rows
        if str(row.get("Status", "")).strip() != "Rejected"
    ]
    visible_rows = non_rejected if owner else [
        row for row in non_rejected
        if str(row.get("Paid_From", "")).strip()
        != config.CASH_CUSTODIAN_HOME_TREASURY
    ]
    paid_clinic = sum('''

apply_edit(BOT_PY, B_OLD_4, B_NEW_4, "bot.py: exclude Rejected rows from ক্লিনিক খরচ হিসাব")

# --- Edit B5: add rejected-report formatter + entry point ---
B_OLD_5 = '''async def costtracker_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _financial_report_start(update, context, "expense")'''

B_NEW_5 = '''def _rejected_expense_report_text(rows, start_date: str, end_date: str) -> str:
    label = start_date if start_date == end_date else f"{start_date} — {end_date}"
    lines = [f"❌ প্রত্যাখ্যাত খরচ — {label}\\n"]
    if not rows:
        lines.append("এই সময়ে কোনো প্রত্যাখ্যাত খরচ নেই।")
    for row in rows:
        lines.append(
            f"• {row.get('Expense_ID', '')} | {row.get('Category', '')} | "
            f"৳{_sheet_amount_value(row.get('Amount', 0) or 0):.0f} | "
            f"{row.get('Paid_From', '')} | {row.get('Approved_By', '')}"
        )
    return "\\n".join(lines)


async def costtracker_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _financial_report_start(update, context, "expense")


async def rejectedexpense_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _financial_report_start(update, context, "rejected")'''

apply_edit(BOT_PY, B_OLD_5, B_NEW_5, "bot.py: Rejected Expenses formatter + entry point")

# --- Edit B6: route "rejected" inside _show_financial_report ---
B_OLD_6 = '''    if report == "cash":
        summary = await async_runtime.run_sheets_read(
            sheets.get_cash_custody_summary, start_date, end_date,
            _finance_departments(staff)
        )
        text = _cash_custody_summary_text(summary, staff.get("Role", ""))
    else:
        rows = await async_runtime.run_sheets_read(
            sheets.get_expenses_for_date, start_date, end_date,
            _finance_departments(staff)
        )
        text = _expense_report_text(
            rows, start_date, end_date, staff.get("Role", "")
        )
    await update.effective_message.reply_text(text)'''

B_NEW_6 = '''    if report == "cash":
        summary = await async_runtime.run_sheets_read(
            sheets.get_cash_custody_summary, start_date, end_date,
            _finance_departments(staff)
        )
        text = _cash_custody_summary_text(summary, staff.get("Role", ""))
    elif report == "rejected":
        rows = await async_runtime.run_sheets_read(
            sheets.get_expenses_for_date, start_date, end_date,
            _finance_departments(staff)
        )
        rejected_rows = [
            row for row in rows
            if str(row.get("Status", "")).strip() == "Rejected"
        ]
        text = _rejected_expense_report_text(rejected_rows, start_date, end_date)
    else:
        rows = await async_runtime.run_sheets_read(
            sheets.get_expenses_for_date, start_date, end_date,
            _finance_departments(staff)
        )
        text = _expense_report_text(
            rows, start_date, end_date, staff.get("Role", "")
        )
    await update.effective_message.reply_text(text)'''

apply_edit(BOT_PY, B_OLD_6, B_NEW_6, "bot.py: route rejected report in _show_financial_report")

# --- Edit B7: register the new handlers, widen finrange callback pattern ---
B_OLD_7 = '''    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_EXPENSE_TRACKER}$"),
            costtracker_start,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_CUSTODY_BALANCE}$"),
            custody_balance_start,
        )
    )
    app.add_handler(CallbackQueryHandler(
        financial_report_range_callback, pattern="^finrange_(expense|cash)_"
    ))'''

B_NEW_7 = '''    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_EXPENSE_TRACKER}$"),
            costtracker_start,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_REJECTED_EXPENSES}$"),
            rejectedexpense_start,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_CUSTODY_BALANCE}$"),
            custody_balance_start,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_FINANCE_DASHBOARDS}$"),
            finance_dashboard_menu,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(f"^{roles.MENU_FINANCE_ACCOUNTS}$"),
            finance_accounts_menu,
        )
    )
    app.add_handler(CallbackQueryHandler(
        financial_report_range_callback, pattern="^finrange_(expense|cash|rejected)_"
    ))'''

apply_edit(BOT_PY, B_OLD_7, B_NEW_7, "bot.py: register new handlers + widen finrange pattern")

# =============================================================================
# Existing test file: fix the one assertion that checked the old flat shape
# =============================================================================
T_OLD_1 = '''    def test_owner_alone_receives_three_financial_dashboard_views(self):
        owner_items = roles.ROLE_FINANCE_ITEMS[roles.Role.OWNER]
        for item in (
            roles.MENU_PHYSIO_FINANCE_DASHBOARD,
            roles.MENU_DENTAL_FINANCE_DASHBOARD,
            roles.MENU_COMBINED_BUSINESS_SUMMARY,
        ):
            self.assertIn(item, owner_items)'''

T_NEW_1 = '''    def test_owner_alone_receives_three_financial_dashboard_views(self):
        # Owner's চলতি হিসাব top level is now 4 grouped tabs; the three
        # dashboard views live one level down, under the Dashboard group.
        dashboard_items = roles.ROLE_FINANCE_DASHBOARD_ITEMS[roles.Role.OWNER]
        for item in (
            roles.MENU_PHYSIO_FINANCE_DASHBOARD,
            roles.MENU_DENTAL_FINANCE_DASHBOARD,
            roles.MENU_COMBINED_BUSINESS_SUMMARY,
        ):
            self.assertIn(item, dashboard_items)'''

apply_edit(EXISTING_TEST_PY, T_OLD_1, T_NEW_1, "test_finance_cash_custody.py: update to nested structure")

# =============================================================================
# New test file
# =============================================================================
NEW_TEST_CONTENT = (Path(__file__).parent / "_test_finance_menu_restructure_content.txt")
if NEW_TEST_CONTENT.exists():
    create_file(
        NEW_TEST_PY, NEW_TEST_CONTENT.read_text(encoding="utf-8"),
        "07_Testing/test_finance_menu_restructure.py",
    )
else:
    results.append((False, "test file: ❌ _test_finance_menu_restructure_content.txt not found next to this script"))

# =============================================================================
print("\n" + "=" * 60)
print("relife_patch6.py — results")
print("=" * 60)
all_ok = True
for ok, msg in results:
    print(msg)
    all_ok = all_ok and ok
print("=" * 60)
if all_ok:
    print("✅ সব ঠিকভাবে হয়েছে। এখন চালাও:")
    print("   cd ~/relife-clinic-os")
    print("   python3 -m py_compile 03_Bot/roles.py 03_Bot/bot.py")
    print("   python3 -m unittest 07_Testing/test_finance_menu_restructure.py 07_Testing/test_finance_cash_custody.py -v")
    print("   git add . && git commit -m 'Restructure Owner finance menu into 4 tabs; split out Rejected Expenses' && git push")
else:
    print("❌ কিছু একটা ধাপ ব্যর্থ হয়েছে — উপরের ❌ লাইনগুলো আমাকে পাঠাও।")
