from pathlib import Path
from datetime import datetime


BASE = Path(".")
REPORT_DIR = Path("15_AI_Brain/Automation/V1/reports")


def read_file(path):
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def count_status(text, keyword):
    return text.count(keyword)


def scan_tasks():
    file = BASE / "13_AI_Tasks/TASK_QUEUE.md"

    if not file.exists():
        return {
            "pending": 0,
            "in_progress": 0,
            "done": 0
        }

    data = read_file(file)

    return {
        "pending": count_status(data, "Pending"),
        "in_progress": count_status(data, "In-Progress"),
        "done": count_status(data, "Done")
    }


def scan_ai_registry():
    file = BASE / "11_AIOS/AI_REGISTRY.md"

    if not file.exists():
        return 0

    data = read_file(file)

    return data.count("ChatGPT") + data.count("Claude") + data.count("Gemini")


def generate_report():

    tasks = scan_tasks()

    report = {
        "system": "Relife Clinic OS AI Brain",
        "time": str(datetime.now()),

        "tasks": tasks,

        "registered_ai":
            scan_ai_registry(),

        "health":
            "OK"
    }

    return report


if __name__ == "__main__":

    result = generate_report()

    print("="*40)
    print("AI BRAIN STATUS ENGINE")
    print("="*40)

    for key,value in result.items():
        print(key, ":", value)
