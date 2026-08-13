#!/usr/bin/env python3
"""
relife_patch5.py
চলতি হিসাব -> ক্যাশ ব্যালেন্স: adds a "💰 এখন কত আছে (Live)" quick button that
shows the all-time running balance (Reception for everyone, + Home Treasury
and Bank for Owner) instead of only period-movement reports (আজ/গতকাল/...).

Run from ~/relife-clinic-os (repo root):
    python relife_patch5.py

Safe to re-run — already-applied edits are skipped and reported as such.
"""
from pathlib import Path

REPO_ROOT = Path.home() / "relife-clinic-os"
BOT_PY = REPO_ROOT / "03_Bot" / "bot.py"
TEST_PY = REPO_ROOT / "07_Testing" / "test_live_cash_balance.py"

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


# ---------------------------------------------------------------------------
# Edit 1: add the "live" shortcut to the date-range resolver
# ---------------------------------------------------------------------------
OLD_1 = '''def _financial_report_date_range(shortcut: str, today=None) -> tuple[str, str]:
    today = today or bd_now().date()
    if shortcut == "today":
        start = today
    elif shortcut == "yesterday":
        start = today - timedelta(days=1)
        today = start
    elif shortcut == "week":
        start = today - timedelta(days=(today.weekday() + 1) % 7)
    elif shortcut == "month":
        start = today.replace(day=1)
    else:
        raise ValueError("Unknown financial report shortcut")
    return start.isoformat(), today.isoformat()'''

NEW_1 = '''_LIVE_BALANCE_START_DATE = "2000-01-01"  # রেকর্ডের শুরুর অনেক আগে, নিরাপদ lower bound


def _financial_report_date_range(shortcut: str, today=None) -> tuple[str, str]:
    today = today or bd_now().date()
    if shortcut == "today":
        start = today
    elif shortcut == "yesterday":
        start = today - timedelta(days=1)
        today = start
    elif shortcut == "week":
        start = today - timedelta(days=(today.weekday() + 1) % 7)
    elif shortcut == "month":
        start = today.replace(day=1)
    elif shortcut == "live":
        return _LIVE_BALANCE_START_DATE, today.isoformat()
    else:
        raise ValueError("Unknown financial report shortcut")
    return start.isoformat(), today.isoformat()'''

apply_edit(BOT_PY, OLD_1, NEW_1, "bot.py: add 'live' date-range shortcut")

# ---------------------------------------------------------------------------
# Edit 2: add the Live quick button (cash report only)
# ---------------------------------------------------------------------------
OLD_2 = '''def _financial_report_keyboard(report: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("আজ", callback_data=f"finrange_{report}_today"),
            InlineKeyboardButton("গতকাল", callback_data=f"finrange_{report}_yesterday"),
        ],
        [
            InlineKeyboardButton("এই সপ্তাহ", callback_data=f"finrange_{report}_week"),
            InlineKeyboardButton("এই মাস", callback_data=f"finrange_{report}_month"),
        ],
        [InlineKeyboardButton("কাস্টম তারিখ", callback_data=f"finrange_{report}_custom")],
    ])'''

NEW_2 = '''def _financial_report_keyboard(report: str) -> InlineKeyboardMarkup:
    rows = []
    if report == "cash":
        rows.append([
            InlineKeyboardButton(
                "💰 এখন কত আছে (Live)", callback_data=f"finrange_{report}_live"
            ),
        ])
    rows += [
        [
            InlineKeyboardButton("আজ", callback_data=f"finrange_{report}_today"),
            InlineKeyboardButton("গতকাল", callback_data=f"finrange_{report}_yesterday"),
        ],
        [
            InlineKeyboardButton("এই সপ্তাহ", callback_data=f"finrange_{report}_week"),
            InlineKeyboardButton("এই মাস", callback_data=f"finrange_{report}_month"),
        ],
        [InlineKeyboardButton("কাস্টম তারিখ", callback_data=f"finrange_{report}_custom")],
    ]
    return InlineKeyboardMarkup(rows)'''

apply_edit(BOT_PY, OLD_2, NEW_2, "bot.py: add Live quick button")

# ---------------------------------------------------------------------------
# Edit 3: header + is_live/balance_label setup
# ---------------------------------------------------------------------------
OLD_3 = '''def _cash_custody_summary_text(summary: dict, role_str: str) -> str:
    is_owner = role_str.strip() == roles.Role.OWNER.value
    lines = [
        f"⚖️ Cash reconciliation — {summary['Date']}",
        "",
        "Reception",'''

NEW_3 = '''def _cash_custody_summary_text(summary: dict, role_str: str) -> str:
    is_owner = role_str.strip() == roles.Role.OWNER.value
    is_live = summary.get("Start_Date") == _LIVE_BALANCE_START_DATE
    balance_label = "বর্তমান ব্যালেন্স" if is_live else "নির্বাচিত সময়ের net balance"
    header = (
        "💰 এখন কত আছে (Live)" if is_live
        else f"⚖️ Cash reconciliation — {summary['Date']}"
    )
    lines = [
        header,
        "",
        "Reception",'''

apply_edit(BOT_PY, OLD_3, NEW_3, "bot.py: live-aware header + balance_label")

# ---------------------------------------------------------------------------
# Edit 4: Reception balance line uses the shared label
# ---------------------------------------------------------------------------
OLD_4 = '''    lines.append(
        f"নির্বাচিত সময়ের net balance: ৳{summary['Reception_Balance']:.0f}"
    )'''
NEW_4 = '''    lines.append(f"{balance_label}: ৳{summary['Reception_Balance']:.0f}")'''

apply_edit(BOT_PY, OLD_4, NEW_4, "bot.py: Reception balance line uses balance_label")

# ---------------------------------------------------------------------------
# Edit 5: Home Treasury balance line uses the shared label
# ---------------------------------------------------------------------------
OLD_5 = '''        lines.append(
            f"নির্বাচিত সময়ের net balance: ৳{summary['Home_Balance']:.0f}"
        )'''
NEW_5 = '''        lines.append(f"{balance_label}: ৳{summary['Home_Balance']:.0f}")'''

apply_edit(BOT_PY, OLD_5, NEW_5, "bot.py: Home Treasury balance line uses balance_label")

# ---------------------------------------------------------------------------
# Edit 6: Bank balance line uses the shared label
# ---------------------------------------------------------------------------
OLD_6 = '''            f"নির্বাচিত সময়ের net balance: ৳{summary.get('Bank_Balance', 0):.0f}",'''
NEW_6 = '''            f"{balance_label}: ৳{summary.get('Bank_Balance', 0):.0f}",'''

apply_edit(BOT_PY, OLD_6, NEW_6, "bot.py: Bank balance line uses balance_label")

# ---------------------------------------------------------------------------
# Edit 7: footer switches wording for live vs period mode
# ---------------------------------------------------------------------------
OLD_7 = '''    lines += [
        "",
        "ℹ️ এটি নির্বাচিত সময়ের movement balance; আগের opening cash এতে নেই।",
    ]'''

NEW_7 = '''    if is_live:
        lines += [
            "",
            "✅ এটি এখন পর্যন্ত সব হিসাব যোগ করে বের করা লাইভ ব্যালেন্স — "
            "আগের সব দিনের residual-ও এতে ধরা আছে।",
        ]
    else:
        lines += [
            "",
            "ℹ️ এটি নির্বাচিত সময়ের movement balance; আগের opening cash এতে নেই।",
        ]'''

apply_edit(BOT_PY, OLD_7, NEW_7, "bot.py: live-aware footer")

# ---------------------------------------------------------------------------
# New test file
# ---------------------------------------------------------------------------
TEST_CONTENT = (Path(__file__).parent / "_test_live_cash_balance_content.txt")
if TEST_CONTENT.exists():
    create_file(TEST_PY, TEST_CONTENT.read_text(encoding="utf-8"), "07_Testing/test_live_cash_balance.py")
else:
    results.append((False, "test file: ❌ _test_live_cash_balance_content.txt not found next to this script"))

# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("relife_patch5.py — results")
print("=" * 60)
all_ok = True
for ok, msg in results:
    print(msg)
    all_ok = all_ok and ok
print("=" * 60)
if all_ok:
    print("✅ সব ঠিকভাবে হয়েছে। এখন চালাও:")
    print("   cd ~/relife-clinic-os")
    print("   python3 -m py_compile 03_Bot/bot.py")
    print("   python3 -m unittest 07_Testing/test_live_cash_balance.py -v")
    print("   git add . && git commit -m 'Add live cash-balance quick view' && git push")
else:
    print("❌ কিছু একটা ধাপ ব্যর্থ হয়েছে — উপরের ❌ লাইনগুলো আমাকে পাঠাও।")
