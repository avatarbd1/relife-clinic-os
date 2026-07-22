from pathlib import Path
import re
import json

INPUT = Path("13_AI_Tasks/TASK_QUEUE.md")
OUTPUT = Path("15_AI_Brain/Automation/V1.2/reports/tasks.json")


def parse():

    if not INPUT.exists():
        return []

    text = INPUT.read_text(
        encoding="utf-8"
    )

    tasks=[]

    rows = re.findall(
        r'\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|',
        text
    )

    for row in rows:

        if row[0] in ["কাজ","-----"]:
            continue

        tasks.append(
            {
                "task":row[0].strip(),
                "ai":row[1].strip(),
                "status":row[2].strip(),
                "module":row[3].strip()
            }
        )

    OUTPUT.write_text(
        json.dumps(
            tasks,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return tasks


if __name__=="__main__":

    data=parse()

    print("TASK PARSER")
    print("Total:",len(data))
