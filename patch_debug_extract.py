path = "/data/data/com.termux/files/home/relife-clinic-os/03_Bot/photo_extract.py"
src = open(path, encoding="utf-8").read()

old = '''    text = resp.json()["choices"][0]["message"]["content"].strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None'''

new = '''    text = resp.json()["choices"][0]["message"]["content"].strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"JSON parse failed, raw model output: {text[:300]}")'''

assert src.count(old) == 1, f"anchor found {src.count(old)} times"
src = src.replace(old, new, 1)

open(path, "w", encoding="utf-8").write(src)
print("✅ photo_extract.py এখন raw output সহ error দেখাবে")
