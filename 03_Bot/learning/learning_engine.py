"""
learning/learning_engine.py
Daily Learning Engine — প্রতিদিন প্রথম /start-এ একটা Quiz + একটা Tip দেখানোর লজিক।
bot.py শুধু এই মডিউলের ফাংশন কল করবে; নিজে কোনো quiz/tip লজিক রাখবে না।
আসল ডেটা 18_Learning_Progress শীটে থাকে (sheets.py-এর মধ্য দিয়ে), তাই Render redeploy
হলেও প্রোগ্রেস হারায় না।
"""

import config
import sheets
from learning import tip_bank, quiz_bank


def _today_str() -> str:
    return config.bd_now().strftime("%Y-%m-%d")


def has_seen_quiz_today(staff_id: str) -> bool:
    today = _today_str()
    events = sheets.get_learning_events_for_staff(staff_id)
    return any(e.get("Type") == "Quiz" and e.get("Date") == today for e in events)


def has_seen_tip_today(staff_id: str) -> bool:
    today = _today_str()
    events = sheets.get_learning_events_for_staff(staff_id)
    return any(e.get("Type") == "Tip" and e.get("Date") == today for e in events)


def get_next_quiz(staff_id: str) -> dict:
    """এই স্টাফ এখন পর্যন্ত মোট কতগুলো কুইজ দেখেছে তার উপর ভিত্তি করে পরের কুইজ বেছে দেয়
    (rotation — পুল শেষ হলে আবার প্রথম থেকে শুরু হয়)।"""
    events = sheets.get_learning_events_for_staff(staff_id)
    seen_count = sum(1 for e in events if e.get("Type") == "Quiz")
    pool = quiz_bank.QUIZZES
    return pool[seen_count % len(pool)]


def get_next_tip(staff_id: str, role: str) -> dict:
    events = sheets.get_learning_events_for_staff(staff_id)
    seen_count = sum(1 for e in events if e.get("Type") == "Tip")
    pool = tip_bank.get_pool_for_role(role)
    return pool[seen_count % len(pool)]


def get_todays_tip(staff_id: str, role: str) -> dict:
    """আজকের জন্য আগে থেকেই একটা টিপ দেখানো হয়ে থাকলে সেটাই আবার রিটার্ন করে
    (একই দিনে দ্বিতীয়/তৃতীয় লগইনে নতুন টিপ না দেখিয়ে আজকেরটাই আবার দেখানোর জন্য)।"""
    today = _today_str()
    events = sheets.get_learning_events_for_staff(staff_id)
    todays_tip_events = [e for e in events if e.get("Type") == "Tip" and e.get("Date") == today]
    if todays_tip_events:
        item_id = todays_tip_events[-1].get("Item_ID")
        found = tip_bank.get_tip_by_id(item_id)
        if found:
            return found
    return get_next_tip(staff_id, role)


def record_quiz_answer(staff_id: str, full_name: str, role: str, quiz: dict, selected_index: int) -> bool:
    correct = (selected_index == quiz["correct_index"])
    sheets.add_learning_event(
        staff_id=staff_id, full_name=full_name, role=role,
        event_type="Quiz", item_id=quiz["id"], category=quiz.get("category", ""),
        selected=str(selected_index), correct="Yes" if correct else "No",
    )
    return correct


def record_tip_shown(staff_id: str, full_name: str, role: str, tip: dict) -> None:
    sheets.add_learning_event(
        staff_id=staff_id, full_name=full_name, role=role,
        event_type="Tip", item_id=tip["id"], category=tip.get("category", ""),
    )
