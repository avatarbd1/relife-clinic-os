#!/usr/bin/env python3
import pathlib
import sys

BOT_PY = pathlib.Path("03_Bot/bot.py")

CHANGES = [
    {
        "name": "reg_start: seed new_patient dict with staff's Primary_Department",
        "file": BOT_PY,
        "old": (
            '    context.user_data["new_patient"] = {}\n'
            '    context.user_data.pop("new_patient_dup_checked", None)\n'
            '    context.user_data.pop("new_patient_missing", None)\n'
        ),
        "new": (
            '    context.user_data["new_patient"] = {\n'
            '        "Department": staff.get("Primary_Department", "")\n'
            '    }\n'
            '    context.user_data.pop("new_patient_dup_checked", None)\n'
            '    context.user_data.pop("new_patient_missing", None)\n'
        ),
    },
]


def main():
    ok = True
    for change in CHANGES:
        path = change["file"]
        if not path.exists():
            print(f"❌ {change['name']}: file not found ({path})")
            ok = False
            continue
        text = path.read_text(encoding="utf-8")

        if change["new"] in text:
            print(f"✅ {change['name']}: already present, skipping")
            continue

        count = text.count(change["old"])
        if count == 0:
            print(f"❌ {change['name']}: anchor not found in {path}")
            ok = False
            continue
        if count > 1:
            print(f"❌ {change['name']}: anchor matched {count} times (expected 1) in {path}")
            ok = False
            continue

        text = text.replace(change["old"], change["new"], 1)
        path.write_text(text, encoding="utf-8")
        print(f"✅ {change['name']}: applied")

    if not ok:
        print("\nSome changes failed — check messages above.")
        sys.exit(1)

    print("\nAll changes applied successfully.")


if __name__ == "__main__":
    main()
