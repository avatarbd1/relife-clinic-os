import re
import subprocess

REG = "11_AIOS/AI_REGISTRY.md"
TQ = "13_AI_Tasks/TASK_QUEUE.md"

reg_text = open(REG, encoding="utf-8").read()
tq_text = open(TQ, encoding="utf-8").read()


def parse_table_rows(text, ncols):
    pattern = r"\|(?:[^|\n]*\|){" + str(ncols) + r"}"
    rows = []
    for mm in re.finditer(pattern, text):
        raw = mm.group(0)
        cols = [c.strip() for c in raw.strip("|").split("|")]
        rows.append((raw, cols))
    return rows


ip_match = re.search(r"## In-Progress\n(.*?)(?=\n## |\Z)", tq_text, re.S)
in_progress = {}
if ip_match:
    for raw, cols in parse_table_rows(ip_match.group(1), 4):
        if len(cols) != 4:
            continue
        task, ai_id, start_date, module = cols
        if ai_id in ("AI ID",) or ai_id.startswith("-") or ai_id == "":
            continue
        in_progress[ai_id] = module

reg_rows = parse_table_rows(reg_text, 4)

fixes = []
mismatches_found = 0

for raw, cols in reg_rows:
    if len(cols) != 4:
        continue
    ai_id, platform, module, status = cols
    if ai_id in ("ID",) or ai_id.startswith("-") or ai_id == "":
        continue

    if ai_id in in_progress:
        if status != "Active":
            mismatches_found += 1
            correct_module = in_progress[ai_id]
            new_row = f"| {ai_id:<10} | {platform:<8} | {correct_module:<34} | Active    |"
            reg_text = reg_text.replace(raw, new_row, 1)
            fixes.append(f"  • {ai_id}: স্ট্যাটাস ফাঁকা ছিল কিন্তু TASK_QUEUE-এ '{correct_module}'-এ In-Progress আছে → Active করা হলো")
    else:
        if status == "Active":
            mismatches_found += 1
            new_row = f"| {ai_id:<10} | {platform:<8} | {'':<34} | {'':<9} |"
            reg_text = reg_text.replace(raw, new_row, 1)
            fixes.append(f"  • {ai_id}: Registry-তে Active ছিল কিন্তু TASK_QUEUE-এ কোনো In-Progress কাজ নেই → খালি করা হলো")

if mismatches_found == 0:
    print("✅ কোনো অসঙ্গতি পাওয়া যায়নি — TASK_QUEUE.md ও AI_REGISTRY.md সিঙ্কে আছে।")
else:
    open(REG, "w", encoding="utf-8").write(reg_text)
    print(f"⚠️ {mismatches_found}টা অসঙ্গতি পাওয়া গেছে ও ঠিক করা হয়েছে:")
    for f in fixes:
        print(f)
    subprocess.run(["git", "add", REG], check=True)
    commit = subprocess.run(
        ["git", "commit", "-m", "sync_registry.py: auto-fix Registry/TASK_QUEUE mismatch"],
        capture_output=True, text=True,
    )
    if commit.returncode != 0:
        if "nothing to commit" in commit.stdout or "no changes added to commit" in commit.stdout:
            print("✅ ফাইল ইতিমধ্যে সঠিক অবস্থায় আছে, নতুন commit লাগেনি।")
        else:
            print("⚠️ commit ব্যর্থ হয়েছে — ম্যানুয়ালি চেক করো।")
            print(commit.stdout, commit.stderr)
    else:
        push = subprocess.run(["git", "push"], capture_output=True, text=True)
        if push.returncode != 0:
            print("⚠️ commit হয়েছে কিন্তু push ব্যর্থ — ম্যানুয়ালি 'git push' দাও।")
            print(push.stderr)
        else:
            print("✅ Push সম্পন্ন।")
