import re
import subprocess
import sys
from datetime import date

if len(sys.argv) < 2:
    print("ব্যবহার: python3 assign_next_ai.py <Platform> [কাজ-এর-কীওয়ার্ড]")
    sys.exit(1)

PLATFORM = sys.argv[1]
TASK_MATCH = sys.argv[2] if len(sys.argv) > 2 else None

REG = "11_AIOS/AI_REGISTRY.md"
TQ = "13_AI_Tasks/TASK_QUEUE.md"
REPO_URL = "https://github.com/avatarbd1/relife-clinic-os"

reg_text = open(REG, encoding="utf-8").read()
tq_text = open(TQ, encoding="utf-8").read()

reg_lines = reg_text.splitlines()
chosen_id = None
chosen_idx = None
for i, line in enumerate(reg_lines):
    stripped = line.strip()
    if not stripped.startswith("|"):
        continue
    cols = [c.strip() for c in stripped.strip("|").split("|")]
    if len(cols) < 4:
        continue
    id_, plat, module, status = cols[0], cols[1], cols[2], cols[3]
    if id_ in ("ID", "") or id_.startswith("-"):
        continue
    if plat == PLATFORM and status == "":
        chosen_id = id_
        chosen_idx = i
        break

if not chosen_id:
    print(f"❌ {PLATFORM}-প্ল্যাটফর্মের কোনো ফাঁকা ID পাওয়া যায়নি।")
    sys.exit(1)

m = re.search(r"## Pending.*?\n\n(.*?)\n\n## ", tq_text, re.S)
if not m:
    print("❌ Pending সেকশন পার্স করা যায়নি।")
    sys.exit(1)

pending_block = m.group(1)
pending_lines = pending_block.splitlines()

task_row = None
task_line_idx = None
for i, line in enumerate(pending_lines):
    stripped = line.strip()
    if not stripped.startswith("|"):
        continue
    cols = [c.strip() for c in stripped.strip("|").split("|")]
    if cols[0] in ("কাজ",) or cols[0].startswith("-"):
        continue
    if TASK_MATCH and TASK_MATCH not in cols[0]:
        continue
    task_row = cols
    task_line_idx = i
    break

if not task_row:
    print("❌ উপযুক্ত কোনো Pending কাজ পাওয়া যায়নি।")
    sys.exit(1)

task_name = task_row[0]
task_module = task_row[1] if len(task_row) > 1 else ""

new_pending_lines = [l for j, l in enumerate(pending_lines) if j != task_line_idx]
new_pending_block = "\n".join(new_pending_lines)
tq_text = tq_text.replace(pending_block, new_pending_block, 1)

tq_text = re.sub(
    r"## In-Progress\n\n\|[^\n]*কাজ[^\n]*AI ID[^\n]*\n\|[-|\s]+\|\n\n(?=## In-Progress)",
    "",
    tq_text,
)

today = date.today().isoformat()
new_row = f"| {task_name} | {chosen_id} | {today} | {task_module} |"

ip_pattern = r"(## In-Progress\n\n\|[^\n]*কাজ[^\n]*AI ID[^\n]*\n\|[-|\s]+\|\n)"
tq_text, n = re.subn(ip_pattern, r"\1" + new_row + "\n", tq_text, count=1)
if n == 0:
    print("❌ In-Progress হেডার খুঁজে পাওয়া যায়নি।")
    sys.exit(1)

open(TQ, "w", encoding="utf-8").write(tq_text)

old_line = reg_lines[chosen_idx]
new_line = f"| {chosen_id:<10} | {PLATFORM:<8} | {task_module:<34} | Active    |"
reg_text = reg_text.replace(old_line, new_line, 1)
open(REG, "w", encoding="utf-8").write(reg_text)

subprocess.run(["git", "add", REG, TQ], check=True)
subprocess.run(["git", "commit", "-m", f"{chosen_id}: claim task '{task_name}'"], check=True)
push = subprocess.run(["git", "push"], capture_output=True, text=True)
if push.returncode != 0:
    print("⚠️ commit হয়েছে কিন্তু push ব্যর্থ — ম্যানুয়ালি 'git push' দাও।")
    print(push.stderr)

print("\n" + "=" * 60)
print("✅ অ্যাসাইনমেন্ট সম্পন্ন — নিচেরটা কপি করে নতুন AI-এর চ্যাটে পেস্ট করো:")
print("=" * 60 + "\n")

msg = f"""GitHub repo: {REPO_URL}

তুমি এই প্রজেক্টে কাজ করছ। তোমার ID: {chosen_id}

শুরুতে এই ফাইলগুলো GitHub থেকে পড়ো:
1. 11_AIOS/MASTER_PROMPT.md
2. 11_AIOS/AI_CONSTITUTION.md
3. 11_AIOS/AI_REGISTRY.md
4. 12_Handover/HANDOVER.md
5. 13_AI_Tasks/TASK_QUEUE.md

তোমার বরাদ্দকৃত কাজ: {task_name}
মডিউল/ফাইল: {task_module}

এই কাজটা ইতিমধ্যে TASK_QUEUE.md-এ তোমার ID দিয়ে In-Progress করে
রাখা হয়েছে এবং AI_REGISTRY.md-এ তোমার ID Active করা হয়েছে —
এগুলো আলাদা করে করতে হবে না।

নিয়ম: শুধু এই মডিউল/ফাইল ছোঁবে, অন্য কিছুতে হাত দেবে না।
03_Bot-এর কোনো ফাইল পুরো ওভাররাইট নয় — sandbox-টেস্টেড patch script দাও।
কাজ শুরুর আগে py_compile ও grep দিয়ে ফাংশন/state নাম যাচাই করে নাও,
ধরে নিও না।
কাজ শেষে HANDOVER.md-এ এন্ট্রি এবং TASK_QUEUE.md-এ Done করার জন্য
কমান্ড আকারে দাও, আমি Termux-এ চালাব।
"""
print(msg)
