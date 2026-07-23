import re
import subprocess
import sys
from datetime import date

if len(sys.argv) < 3:
    print("ব্যবহার: python3 close_task.py <AI-ID> <কাজ-কীওয়ার্ড> [\"নোট (ঐচ্ছিক)\"]")
    print('উদাহরণ: python3 close_task.py Claude-2 Salary "sheets.py+bot.py+roles.py আপডেট হয়েছে"')
    sys.exit(1)

AI_ID = sys.argv[1]
TASK_MATCH = sys.argv[2]
NOTE = sys.argv[3] if len(sys.argv) > 3 else ""

REG = "11_AIOS/AI_REGISTRY.md"
TQ = "13_AI_Tasks/TASK_QUEUE.md"
HO = "12_Handover/HANDOVER.md"

reg_text = open(REG, encoding="utf-8").read()
tq_text = open(TQ, encoding="utf-8").read()
ho_text = open(HO, encoding="utf-8").read()

m = re.search(r"## In-Progress\n\n(\|[^\n]*কাজ[^\n]*AI ID[^\n]*\n\|[-|\s]+\|\n)(.*?)(?=\n\n##|\Z)", tq_text, re.S)
if not m:
    print("❌ In-Progress সেকশন পার্স করা যায়নি।")
    sys.exit(1)

header_block = m.group(1)
rows_block = m.group(2)
row_lines = rows_block.splitlines()

target_row = None
target_idx = None
for i, line in enumerate(row_lines):
    stripped = line.strip()
    if not stripped.startswith("|"):
        continue
    cols = [c.strip() for c in stripped.strip("|").split("|")]
    if len(cols) < 4:
        continue
    task_name, ai_id, start_date, module = cols[0], cols[1], cols[2], cols[3]
    if ai_id == AI_ID and TASK_MATCH in task_name:
        target_row = cols
        target_idx = i
        break

if not target_row:
    print(f"❌ {AI_ID}-এর '{TASK_MATCH}'-সংক্রান্ত কোনো In-Progress কাজ পাওয়া যায়নি।")
    sys.exit(1)

task_name, ai_id, start_date, module = target_row

new_row_lines = [l for j, l in enumerate(row_lines) if j != target_idx]
new_rows_block = "\n".join(new_row_lines)
old_full_block = header_block + rows_block
new_full_block = header_block + new_rows_block
tq_text = tq_text.replace(old_full_block, new_full_block, 1)

today = date.today().isoformat()
done_row = f"| {task_name} | {ai_id} | {today} | {module} |"
done_pattern = r"(## Done\n\n\|[^\n]*কাজ[^\n]*AI ID[^\n]*\n\|[-|\s]+\|\n)"
tq_text, n = re.subn(done_pattern, r"\1" + done_row + "\n", tq_text, count=1)
if n == 0:
    print("❌ Done টেবিলের হেডার খুঁজে পাওয়া যায়নি।")
    sys.exit(1)

open(TQ, "w", encoding="utf-8").write(tq_text)

reg_lines = reg_text.splitlines()
for i, line in enumerate(reg_lines):
    stripped = line.strip()
    if not stripped.startswith("|"):
        continue
    cols = [c.strip() for c in stripped.strip("|").split("|")]
    if len(cols) < 4:
        continue
    if cols[0] == AI_ID:
        platform = cols[1]
        new_line = f"| {AI_ID:<10} | {platform:<8} | {'':<34} | {'':<9} |"
        reg_text = reg_text.replace(line, new_line, 1)
        break
open(REG, "w", encoding="utf-8").write(reg_text)

note_line = NOTE if NOTE else "কিছু উল্লেখযোগ্য নোট নেই।"
entry = f"""### {today} — {ai_id}
- কাজ: {task_name}
- করা হয়েছে: {note_line}
- পরিবর্তিত ফাইল: {module}
- স্ট্যাটাস: Done
- পরের AI-এর জন্য নোট: -

"""
ho_text = ho_text.replace("## Log Entries (নিচে যোগ হবে)\n", "## Log Entries (নিচে যোগ হবে)\n\n" + entry, 1)
open(HO, "w", encoding="utf-8").write(ho_text)

subprocess.run(["git", "add", REG, TQ, HO], check=True)
subprocess.run(["git", "commit", "-m", f"{ai_id}: closed task '{task_name}'"], check=True)
push = subprocess.run(["git", "push"], capture_output=True, text=True)
if push.returncode != 0:
    print("⚠️ commit হয়েছে কিন্তু push ব্যর্থ — ম্যানুয়ালি 'git push' দাও।")
    print(push.stderr)

print(f"✅ '{task_name}' ({ai_id}) — Done করা হয়েছে, {AI_ID} আবার খালি।")
