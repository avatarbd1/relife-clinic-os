#!/usr/bin/env python3
import pathlib
import sys

SHEETS_PY = pathlib.Path("03_Bot/sheets.py")

CHANGES = [
    {
        "name": "add helper: _patient_department()",
        "file": SHEETS_PY,
        "old": (
            'def add_assessment(patient_id: str, category: str, test_data: dict, created_by: str) -> str:\n'
        ),
        "new": (
            'def _patient_department(patient_id: str) -> str:\n'
            '    """রোগীর নিজের Department রেকর্ড থেকে খুঁজে আনে; না পেলে ফাঁকা।"""\n'
            '    patient = get_patient_by_id(patient_id)\n'
            '    if not patient:\n'
            '        return ""\n'
            '    return str(patient.get("Department", "")).strip()\n'
            '\n'
            '\n'
            'def _set_department_by_header(ws, row: list, department: str) -> None:\n'
            '    """headers-এ Department কলাম থাকলে, সঠিক পজিশনে বসিয়ে দেয় (কলাম অর্ডার বদলালেও নিরাপদ)।"""\n'
            '    headers = ws.row_values(1)\n'
            '    if "Department" not in headers:\n'
            '        return\n'
            '    idx = headers.index("Department")\n'
            '    if len(row) <= idx:\n'
            '        row.extend([""] * (idx + 1 - len(row)))\n'
            '    row[idx] = department\n'
            '\n'
            '\n'
            'def add_assessment(patient_id: str, category: str, test_data: dict, created_by: str) -> str:\n'
        ),
    },
    {
        "name": "add_assessment: fill Department before append",
        "file": SHEETS_PY,
        "old": (
            '    _append_unified_row(\n'
            '        ws, row, "assessment", assessment_id,\n'
            '        provider_id=created_by,\n'
            '    )\n'
            '    return assessment_id\n'
        ),
        "new": (
            '    _set_department_by_header(ws, row, _patient_department(patient_id))\n'
            '    _append_unified_row(\n'
            '        ws, row, "assessment", assessment_id,\n'
            '        provider_id=created_by,\n'
            '    )\n'
            '    return assessment_id\n'
        ),
    },
    {
        "name": "add_treatment_plan: fill Department before append",
        "file": SHEETS_PY,
        "old": (
            '    _append_unified_row(\n'
            '        ws, row, "treatment_plan", plan_id,\n'
            '        provider_id=created_by,\n'
            '    )\n'
            '    _invalidate_cache(ws)\n'
            '    return plan_id\n'
        ),
        "new": (
            '    _set_department_by_header(ws, row, _patient_department(data.get("Patient_ID", "")))\n'
            '    _append_unified_row(\n'
            '        ws, row, "treatment_plan", plan_id,\n'
            '        provider_id=created_by,\n'
            '    )\n'
            '    _invalidate_cache(ws)\n'
            '    return plan_id\n'
        ),
    },
    {
        "name": "add_package: fill Department before append",
        "file": SHEETS_PY,
        "old": (
            '    _append_unified_row(ws, row, "package", package_id)\n'
            '    return package_id\n'
        ),
        "new": (
            '    _set_department_by_header(ws, row, _patient_department(patient_id))\n'
            '    _append_unified_row(ws, row, "package", package_id)\n'
            '    return package_id\n'
        ),
    },
    {
        "name": "add_report: fill Department before append",
        "file": SHEETS_PY,
        "old": (
            '    _append_unified_row(\n'
            '        ws, row, "report", report_id,\n'
            '        provider_id=uploaded_by,\n'
            '    )\n'
            '    return report_id\n'
        ),
        "new": (
            '    _set_department_by_header(ws, row, _patient_department(data.get("Patient_ID", "")))\n'
            '    _append_unified_row(\n'
            '        ws, row, "report", report_id,\n'
            '        provider_id=uploaded_by,\n'
            '    )\n'
            '    return report_id\n'
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
