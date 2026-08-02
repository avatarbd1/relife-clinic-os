# -*- coding: utf-8 -*-
import sys

path = "sheets.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

if "add_case_study_lesson" in src:
    sys.exit("sheets.py already patched (add_case_study_lesson exists) — nothing to do.")

addition = '''

# ===== Case Study (AI Lesson) Functions =====

def _next_case_study_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("CS"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"CS{next_num:04d}"


def add_case_study_lesson(session_id: str, patient_id: str, patient_name: str,
                           lesson_number: int, lesson_title: str, content: str,
                           created_by: str) -> str:
    """15_Case_Studies শীটে একটা Lesson সেভ করে। এক Session_ID-এর সব Lesson একসাথে
    থাকে যাতে ভিন্ন রোগীর কেস আলাদা থাকে, গোলানো না যায়।"""
    ws = _worksheet(config.SHEET_CASE_STUDIES)
    case_study_id = _next_case_study_id(ws)
    row = [
        case_study_id,
        session_id,
        patient_id,
        patient_name,
        lesson_number,
        lesson_title,
        content,
        created_by,
        bd_now().strftime("%Y-%m-%d %I:%M %p"),
    ]
    ws.append_row(row, value_input_option="RAW")
    return case_study_id


def get_case_study_sessions_for_patient(patient_id: str) -> list[dict]:
    """একজন রোগীর সব সেভ করা কেস-স্টাডি সেশন লিস্ট করে (Session_ID অনুযায়ী গ্রুপ করা)।"""
    ws = _worksheet(config.SHEET_CASE_STUDIES)
    all_rows = safe_get_all_records(ws)
    sessions = {}
    for r in all_rows:
        if str(r.get("Patient_ID", "")).strip() != str(patient_id).strip():
            continue
        sid = r.get("Session_ID", "")
        if sid not in sessions:
            sessions[sid] = {
                "Session_ID": sid,
                "Patient_ID": patient_id,
                "Patient_Name": r.get("Patient_Name", ""),
                "Timestamp": r.get("Timestamp", ""),
                "Lesson_Count": 0,
            }
        sessions[sid]["Lesson_Count"] += 1
    return list(sessions.values())


def get_case_study_lessons(session_id: str) -> list[dict]:
    """একটা নির্দিষ্ট Session_ID-এর সব Lesson ফেরত দেয় (Lesson_Number অনুযায়ী সাজানো)।"""
    ws = _worksheet(config.SHEET_CASE_STUDIES)
    all_rows = safe_get_all_records(ws)
    lessons = [r for r in all_rows if str(r.get("Session_ID", "")).strip() == str(session_id).strip()]
    lessons.sort(key=lambda r: int(r.get("Lesson_Number", 0) or 0))
    return lessons
'''
src = src + addition
with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("sheets.py: patched OK")
