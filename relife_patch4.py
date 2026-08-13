#!/usr/bin/env python3
"""
relife_patch4.py
Cash Handover: show the receptionist's actual computed cash balance
(all-time carry-forward) instead of a static "5000" example, so they can
one-tap handover the full amount or type a different one.

Run from ~/relife-clinic-os (repo root):
    python relife_patch4.py

Safe to re-run — already-applied edits are skipped and reported as such.
"""
from pathlib import Path

REPO_ROOT = Path.home() / "relife-clinic-os"
SHEETS_PY = REPO_ROOT / "03_Bot" / "sheets.py"
BOT_PY = REPO_ROOT / "03_Bot" / "bot.py"
TEST_PY = REPO_ROOT / "07_Testing" / "test_reception_cash_balance.py"

results = []


def apply_edit(path: Path, old: str, new: str, label: str):
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


def create_file(path: Path, content: str, label: str):
    if path.exists() and path.read_text(encoding="utf-8").strip() == content.strip():
        results.append((True, f"{label}: ✅ already present (skipped)"))
        return
    if path.exists():
        results.append((True, f"{label}: ✅ already exists (left as-is)"))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    results.append((True, f"{label}: ✅ created"))


# ---------------------------------------------------------------------------
# Edit 1: sheets.py — new get_reception_cash_balance() helper
# ---------------------------------------------------------------------------
SHEETS_OLD = '_FINANCE_DEPARTMENTS = {config.DEPARTMENT_PHYSIO, config.DEPARTMENT_DENTAL}'

SHEETS_NEW = '''_RECEPTION_BALANCE_EPOCH = "2000-01-01"  # \u09b0\u09c7\u0995\u09b0\u09cd\u09a1\u09c7\u09b0 \u09b6\u09c1\u09b0\u09c1\u09b0 \u0985\u09a8\u09c7\u0995 \u0986\u0997\u09c7, \u09a8\u09bf\u09b0\u09be\u09aa\u09a6 lower bound


def get_reception_cash_balance(department: str) -> float:
    """\u098f\u0995\u099f\u09bf \u09ac\u09bf\u09ad\u09be\u0997\u09c7\u09b0 Reception-\u098f \u098f\u0996\u09a8 \u09b9\u09be\u09a4\u09c7 \u0995\u09a4 \u0995\u09cd\u09af\u09be\u09b6 \u0986\u099b\u09c7 (all-time cumulative)\u0964

    get_cash_custody_summary()-\u098f\u09b0 \u099f\u09c7\u09b8\u09cd\u099f-\u0995\u09b0\u09be \u09b9\u09bf\u09b8\u09be\u09ac\u0987 \u09aa\u09c1\u09a8\u09b0\u09be\u09df \u09ac\u09cd\u09af\u09ac\u09b9\u09be\u09b0 \u0995\u09b0\u09c7 \u2014
    \u09b0\u09c7\u0995\u09b0\u09cd\u09a1\u09c7\u09b0 \u09b6\u09c1\u09b0\u09c1 \u09a5\u09c7\u0995\u09c7 \u0986\u099c \u09aa\u09b0\u09cd\u09af\u09a8\u09cd\u09a4 \u09b0\u09c7\u099e\u09cd\u099c \u09a6\u09bf\u09df\u09c7 \u09a1\u09be\u0995\u09b2\u09c7 period net movement-\u0987
    \u0986\u09b8\u09b2\u09c7 all-time running balance \u09b9\u09df\u09c7 \u09af\u09be\u09df (opening cash = 0 \u09a7\u09b0\u09c7)\u0964
    """
    today = bd_now().strftime("%Y-%m-%d")
    summary = get_cash_custody_summary(
        date_str=_RECEPTION_BALANCE_EPOCH,
        end_date=today,
        departments={department},
    )
    return summary["Reception_Balance"]


_FINANCE_DEPARTMENTS = {config.DEPARTMENT_PHYSIO, config.DEPARTMENT_DENTAL}'''

apply_edit(SHEETS_PY, SHEETS_OLD, SHEETS_NEW, "sheets.py: get_reception_cash_balance()")

# ---------------------------------------------------------------------------
# Edit 2: bot.py — cash_department_callback shows the computed balance
# ---------------------------------------------------------------------------
BOT_OLD = '''    context.user_data["cash_handover"] = {"Department": department}
    await query.edit_message_text(
        f"{department} Reception \u09a5\u09c7\u0995\u09c7 Home Treasury-\u09a4\u09c7 \u0995\u09a4 \u099f\u09be\u0995\u09be \u09b9\u09cd\u09af\u09be\u09a8\u09cd\u09a1\u0993\u09ad\u09be\u09b0 \u0995\u09b0\u09ac\u09c7?\\n"
        "\u09b6\u09c1\u09a7\u09c1 \u099f\u09be\u0995\u09be\u09b0 \u09aa\u09b0\u09bf\u09ae\u09be\u09a3 \u09b2\u09c7\u0996\u09cb (\u09af\u09c7\u09ae\u09a8: 5000):"
    )
    return CASH_AMOUNT'''

BOT_NEW = '''    context.user_data["cash_handover"] = {"Department": department}
    try:
        balance = await async_runtime.run_sheets_read(
            sheets.get_reception_cash_balance, department
        )
    except Exception:
        logger.exception("cash_department_callback: balance calc failed")
        balance = None

    if balance is not None:
        suggested = max(0, round(balance))
        await query.edit_message_text(
            f"{department} Reception-\u098f \u09b9\u09bf\u09b8\u09be\u09ac \u0985\u09a8\u09c1\u09af\u09be\u09df\u09c0 \u098f\u0996\u09a8 \u09f3{balance:.0f} \u0986\u099b\u09c7\u0964\\n\\n"
            "\u09aa\u09c1\u09b0\u09cb\u099f\u09be handover \u0995\u09b0\u09a4\u09c7 \u09a8\u09bf\u099a\u09c7\u09b0 \u09ac\u09be\u099f\u09a8\u09c7 \u099a\u09be\u09aa \u09a6\u09be\u0993, "
            "\u0985\u09a5\u09ac\u09be \u09ad\u09bf\u09a8\u09cd\u09a8 \u09aa\u09b0\u09bf\u09ae\u09be\u09a3 \u099f\u09be\u0987\u09aa \u0995\u09b0\u09cb:"
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="\u0995\u09a4 \u099f\u09be\u0995\u09be handover \u0995\u09b0\u09ac\u09c7?",
            reply_markup=ReplyKeyboardMarkup(
                [[str(suggested)]], resize_keyboard=True, one_time_keyboard=True
            ),
        )
    else:
        await query.edit_message_text(
            f"{department} Reception \u09a5\u09c7\u0995\u09c7 Home Treasury-\u09a4\u09c7 \u0995\u09a4 \u099f\u09be\u0995\u09be \u09b9\u09cd\u09af\u09be\u09a8\u09cd\u09a1\u0993\u09ad\u09be\u09b0 \u0995\u09b0\u09ac\u09c7?\\n"
            "\u09b6\u09c1\u09a7\u09c1 \u099f\u09be\u0995\u09be\u09b0 \u09aa\u09b0\u09bf\u09ae\u09be\u09a3 \u09b2\u09c7\u0996\u09cb (\u09af\u09c7\u09ae\u09a8: 5000):"
        )
    return CASH_AMOUNT'''

apply_edit(BOT_PY, BOT_OLD, BOT_NEW, "bot.py: cash_department_callback shows computed balance")

# ---------------------------------------------------------------------------
# New test file
# ---------------------------------------------------------------------------
TEST_CONTENT = (Path(__file__).parent / "_test_reception_cash_balance_content.txt")
if TEST_CONTENT.exists():
    create_file(TEST_PY, TEST_CONTENT.read_text(encoding="utf-8"), "07_Testing/test_reception_cash_balance.py")
else:
    results.append((False, "test file: ❌ _test_reception_cash_balance_content.txt not found next to this script"))

# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("relife_patch4.py — results")
print("=" * 60)
all_ok = True
for ok, msg in results:
    print(msg)
    all_ok = all_ok and ok
print("=" * 60)
if all_ok:
    print("✅ সব ঠিকভাবে হয়েছে। এখন চালাও:")
    print("   cd ~/relife-clinic-os")
    print("   python3 -m py_compile 03_Bot/sheets.py 03_Bot/bot.py")
    print("   python3 -m unittest 07_Testing/test_reception_cash_balance.py -v")
    print("   git add . && git commit -m 'Show auto-computed reception cash balance in handover prompt' && git push")
else:
    print("❌ কিছু একটা ধাপ ব্যর্থ হয়েছে — উপরের ❌ লাইনগুলো আমাকে পাঠাও।")
