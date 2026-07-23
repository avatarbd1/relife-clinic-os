from core.data_adapter import ClinicDataAdapter
from engines.patient_analysis import analyze as patient
from engines.staff_analysis import analyze as staff
from engines.finance_analysis import analyze as finance
from reports.owner_report_generator import create


adapter=ClinicDataAdapter()


result={

"PATIENT":
patient(adapter.patient_data()),

"STAFF":
staff(adapter.staff_data()),

"FINANCE":
finance(adapter.finance_data())

}


file=create(result)


print("="*40)
print("RELIFE AI BRAIN INTEGRATION V2")
print("="*40)
print("REPORT:")
print(file)
print("STATUS: READY")
