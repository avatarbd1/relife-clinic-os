import re

path = "/data/data/com.termux/files/home/relife-clinic-os/03_Bot/photo_extract.py"
src = open(path, encoding="utf-8").read()

old = '''    text = resp.json()["choices"][0]["message"]["content"].strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"JSON parse failed, raw model output: {text[:300]}")'''

new = '''    text = resp.json()["choices"][0]["message"]["content"].strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = text.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\\{.*\\}", text, flags=re.DOTALL)
    if match:
        text = match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"JSON parse failed, raw model output: {text[:300]}")'''

assert src.count(old) == 1, f"anchor found {src.count(old)} times"
src = src.replace(old, new, 1)

old_import = "import requests\n"
new_import = "import re\nimport requests\n"
assert src.count(old_import) == 1, f"import anchor found {src.count(old_import)} times"
src = src.replace(old_import, new_import, 1)

open(path, "w", encoding="utf-8").write(src)
print("✅ <think> ব্লক বাদ দিয়ে JSON extract করবে")
