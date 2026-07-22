from pathlib import Path
from datetime import datetime


FILE=Path(
"15_AI_Brain/Knowledge/DECISION_HISTORY.md"
)


entry=f"""

## Decision Entry

Date:
{datetime.now()}

Decision:
AI Brain V1.2 Intelligence Layer activated.

Reason:
Improve task understanding and automation.

"""

with FILE.open(
    "a",
    encoding="utf-8"
) as f:

    f.write(entry)


print(
"Decision logged"
)
