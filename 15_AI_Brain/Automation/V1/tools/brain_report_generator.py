import json
from datetime import datetime
from pathlib import Path

from brain_status_engine import generate_report


REPORT = Path(
"15_AI_Brain/Automation/V1/reports/latest_report.json"
)


data = generate_report()

data["generated"] = str(datetime.now())


REPORT.parent.mkdir(
    parents=True,
    exist_ok=True
)


REPORT.write_text(
    json.dumps(
        data,
        indent=4,
        ensure_ascii=False
    ),
    encoding="utf-8"
)


print("Report Generated:")
print(REPORT)
