import re, json, os

with open("clinical-manual/Relife-Physiotherapy-Clinical-Manual.md", encoding="utf-8") as f:
    content = f.read()

out_dir = "03_Bot/clinical_conditions"
os.makedirs(out_dir, exist_ok=True)

pattern = re.compile(r'\n(?=## B\d+\.)')
parts = pattern.split(content)

index = []
for part in parts:
    m = re.match(r'## (B(\d+))\.\s*([^\n]+)', part.strip())
    if not m:
        continue
    bid, num, title = m.group(1), m.group(2), m.group(3).strip()
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', title)[:40].strip('_')
    fname = f"{bid}_{slug}.md"
    with open(os.path.join(out_dir, fname), "w", encoding="utf-8") as out:
        out.write(part.strip())
    index.append({"id": bid, "title": title, "file": fname})

with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, indent=2)

print(f"Split into {len(index)} condition files.")
