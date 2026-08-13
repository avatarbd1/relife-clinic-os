#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOT = ROOT / "03_Bot" / "bot.py"

old = '''def _department_live_balance_text(summaries: dict, role_str: str) -> str:
    lines = ["💰 এখন কত আছে (Live)"]
    for department in (config.DEPARTMENT_PHYSIO, config.DEPARTMENT_DENTAL):
        if department not in summaries:
            continue
        summary = summaries[department]
        lines += ["", f"{'🩺' if department == config.DEPARTMENT_PHYSIO else '🦷'} {department}",
                  f"⚖️ Reception: ৳{summary['Reception_Balance']:.0f}",
                  f"🏠 Home Treasury: ৳{summary['Home_Balance']:.0f}"]
        if role_str.strip() == roles.Role.OWNER.value:
            lines.append(f"🏦 Bank: ৳{summary.get('Bank_Balance', 0):.0f}")
    return "\\n".join(lines)
'''

new = '''def _department_live_balance_text(summaries: dict, role_str: str) -> str:
    lines = ["💰 এখন কত আছে (Live)"]
    is_owner = role_str.strip() == roles.Role.OWNER.value
    for department in (config.DEPARTMENT_PHYSIO, config.DEPARTMENT_DENTAL):
        if department not in summaries:
            continue
        summary = summaries[department]
        lines += ["", f"{'🩺' if department == config.DEPARTMENT_PHYSIO else '🦷'} {department}",
                  f"⚖️ Reception: ৳{summary['Reception_Balance']:.0f}"]
        if is_owner:
            lines.append(f"🏠 Home Treasury: ৳{summary['Home_Balance']:.0f}")
        if is_owner and department == config.DEPARTMENT_PHYSIO:
            lines.append(f"🏦 Bank: ৳{summary.get('Bank_Balance', 0):.0f}")
    return "\\n".join(lines)
'''

if not BOT.exists():
    raise SystemExit(f"❌ পাওয়া যায়নি: {BOT}")

text = BOT.read_text(encoding="utf-8")
if new in text:
    print("✅ Patch 13B আগে থেকেই applied আছে।")
elif old in text:
    BOT.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("✅ Patch 13B applied: Receptionist শুধু Reception; Owner-এর treasury আলাদা।")
else:
    raise SystemExit(
        "❌ Expected Patch 13 code পাওয়া যায়নি। bot.py পরিবর্তিত হতে পারে; কিছু overwrite করা হয়নি।"
    )
