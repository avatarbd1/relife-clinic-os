from pathlib import Path
import re
import json
from datetime import datetime


REGISTRY = Path("11_AIOS/AI_REGISTRY.md")

OUTPUT = Path(
    "15_AI_Brain/Automation/V1/reports/ai_registry_report.json"
)


def read_registry():

    if not REGISTRY.exists():
        return []

    text = REGISTRY.read_text(
        encoding="utf-8"
    )

    return text


def extract_ai():

    text = read_registry()

    pattern = r'\|\s*([A-Za-z0-9\-]+)\s*\|\s*([A-Za-z]+)'

    matches = re.findall(
        pattern,
        text
    )

    result = []

    for ai_id, platform in matches:

        if ai_id in [
            "ID",
            "------------"
        ]:
            continue

        result.append(
            {
                "id": ai_id,
                "platform": platform,
                "status": "registered"
            }
        )

    return result


def create_report():

    data = extract_ai()

    report = {
        "generated":
            str(datetime.now()),

        "total_ai":
            len(data),

        "workers":
            data
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            report,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return report


if __name__ == "__main__":

    report = create_report()

    print("="*40)
    print("AI REGISTRY REPORT")
    print("="*40)

    print(
        "Total AI:",
        report["total_ai"]
    )

    for ai in report["workers"]:
        print(
            ai["id"],
            "-",
            ai["platform"]
        )
