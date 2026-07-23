import sys

sys.path.append(
    "15_AI_Brain/Integration/V2"
)

from decision.decision_engine import DecisionEngine
from reports.owner_report_generator import create


engine = DecisionEngine()

decision = engine.run()


report = {
    "PATIENT": decision["patient_decision"],
    "STAFF": decision["staff_decision"],
    "FINANCE": decision["finance_decision"],
    "NEXT_ACTION": decision["next_action"]
}


file = create(report)


print("="*40)
print("RELIFE AI BRAIN INTEGRATION V2")
print("="*40)
print("REPORT:")
print(file)
print("STATUS: READY")
