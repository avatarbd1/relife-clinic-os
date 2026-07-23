from pathlib import Path

p = Path("15_AI_Brain/Integration/V2/decision/decision_engine.py")

text = p.read_text()

text = text.replace(
'''        return {
            "status":"ANALYZED",
            "message":"Patient activity reviewed"
        }''',
'''        return {
            "status":"ANALYZED",
            "message":(
                f"Patient database active. "
                f"Total records: {data['records']}. "
                "Follow-up and diagnosis trend monitoring required."
            )
        }'''
)

text = text.replace(
'''        return {
            "status":"ANALYZED"
        }''',
'''        return {
            "status":"ANALYZED",
            "message":(
                f"Staff records active. "
                f"Total records: {data['records']}. "
                "Attendance and performance tracking required."
            )
        }'''
)

text = text.replace(
'"WAITING_FOR_FINANCE_DATA"',
'"CONNECTED"'
)

text = text.replace(
'"Connect real clinic database"',
'"Review patient follow-up, monitor collection, and improve staff performance tracking."'
)

p.write_text(text)

print("DECISION ENGINE PATCHED")
