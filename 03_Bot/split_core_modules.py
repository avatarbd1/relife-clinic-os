import re
with open("../clinical-manual/Relife-Physiotherapy-Clinical-Manual.md", encoding="utf-8") as f:
    content = f.read()
wanted = {"3": "Manual Therapy Library", "4": "Exercise Prescription Library", "7": "Contraindications"}
headers = [(m.start(), m.group(1), m.group(2)) for m in re.finditer(r'^## Module (\d+):\s*([^\n]*)', content, re.M)]
part_b_start = content.find("# PART B — DISEASE-WISE PROTOCOLS")
bounds = [h[0] for h in headers] + [part_b_start if part_b_start != -1 else len(content)]
blocks = []
for i, (start, num, title) in enumerate(headers):
    if num in wanted:
        end = bounds[i + 1]
        blocks.append(content[start:end].strip())
with open("clinical_conditions/core_modules.md", "w", encoding="utf-8") as f:
    f.write("\n\n---\n\n".join(blocks))
print(f"Wrote core_modules.md with {len(blocks)} modules, {sum(len(b) for b in blocks)} chars total")
