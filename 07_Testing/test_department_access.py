import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
if BOT_DIR.exists():
    sys.path.insert(0, str(BOT_DIR))
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from department_access import (  # noqa: E402
    AccessAction,
    Department,
    Role,
    allowed_departments,
    authorize_record,
)


def staff(role, department, staff_id="S1"):
    return {"Staff_ID": staff_id, "Role": role, "Primary_Department": department}


class DepartmentAccessTests(unittest.TestCase):
    def test_missing_department_fails_closed(self):
        decision = authorize_record(staff("Therapist", "Physio"), {}, AccessAction.CLINICAL_READ)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "department_missing")

    def test_department_mismatch_is_denied(self):
        decision = authorize_record(
            staff("Therapist", "Physio"), {"Department": "Dental"}, AccessAction.CLINICAL_READ
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "department_mismatch")

    def test_owner_requires_explicit_all_scope(self):
        permitted = authorize_record(staff("Owner", "All"), {"Department": "Dental"}, AccessAction.CLINICAL_READ)
        denied = authorize_record(staff("Owner", ""), {"Department": "Dental"}, AccessAction.CLINICAL_READ)
        self.assertTrue(permitted.allowed)
        self.assertFalse(denied.allowed)

    def test_system_admin_has_no_clinical_access(self):
        decision = authorize_record(staff("System Admin", "Physio"), {"Department": "Physio"}, AccessAction.CLINICAL_READ)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "role_forbidden")

    def test_mapping_supports_multiple_departments_without_csv_scope(self):
        person = staff("Manager", "Physio")
        mappings = [
            {"Staff_ID": "S1", "Department": "Physio", "Status": "Active"},
            {"Staff_ID": "S1", "Department": "Dental", "Status": "Active"},
        ]
        self.assertEqual(
            allowed_departments(person, mappings),
            frozenset({Department.PHYSIO, Department.DENTAL}),
        )

    def test_therapist_write_requires_assignment_and_preserves_author(self):
        person = staff("Therapist", "Physio")
        record = {"Department": "Physio"}
        self.assertFalse(authorize_record(person, record, AccessAction.CLINICAL_WRITE).allowed)
        self.assertTrue(
            authorize_record(person, record, AccessAction.CLINICAL_WRITE, assigned_or_cross_cover=True).allowed
        )
        decision = authorize_record(
            person, record, AccessAction.CLINICAL_WRITE, assigned_or_cross_cover=True, author_id="S2"
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "author_mismatch")

    def test_dentist_is_dental_only_and_amounts_are_hidden(self):
        person = staff("Dentist", "Dental")
        self.assertTrue(authorize_record(person, {"Department": "Dental"}, AccessAction.CLINICAL_READ).allowed)
        self.assertFalse(authorize_record(person, {"Department": "Physio"}, AccessAction.CLINICAL_READ).allowed)
        self.assertFalse(authorize_record(person, {"Department": "Dental"}, AccessAction.FINANCIAL_READ).allowed)

    def test_dental_assistant_has_no_implicit_clinical_write(self):
        person = staff("Dental_Assistant", "Dental")
        decision = authorize_record(person, {"Department": "Dental"}, AccessAction.CLINICAL_WRITE)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "role_forbidden")

    def test_role_and_department_are_separate_dimensions(self):
        manager = staff(Role.MANAGER.value, Department.DENTAL.value)
        self.assertTrue(authorize_record(manager, {"Department": "Dental"}, AccessAction.READ).allowed)

    def test_auditor_is_business_read_only_without_clinical_access(self):
        person = staff("Auditor", "All")
        mappings = [
            {"Staff_ID": "S1", "Department": "Physio", "Status": "Active"},
            {"Staff_ID": "S1", "Department": "Dental", "Status": "Active"},
        ]
        record = {"Department": "Dental"}
        self.assertTrue(authorize_record(person, record, AccessAction.READ, mappings).allowed)
        self.assertTrue(authorize_record(person, record, AccessAction.FINANCIAL_READ, mappings).allowed)
        self.assertFalse(authorize_record(person, record, AccessAction.WRITE, mappings).allowed)
        self.assertFalse(authorize_record(person, record, AccessAction.CLINICAL_READ, mappings).allowed)

    def test_manager_therapist_secondary_scope_requires_assignment(self):
        person = staff("Manager", "Physio")
        person["Clinical_Write_Scope"] = "Assigned_Or_Today_Cross_Cover"
        record = {"Department": "Physio"}
        self.assertFalse(authorize_record(person, record, AccessAction.CLINICAL_WRITE).allowed)
        self.assertTrue(
            authorize_record(person, record, AccessAction.CLINICAL_WRITE, assigned_or_cross_cover=True).allowed
        )

    def test_dental_receptionist_assistant_can_read_but_not_write_clinical_data(self):
        person = staff("Receptionist", "Dental")
        person["Clinical_Write_Scope"] = "Dental_Assistant_Support_No_Independent_Write"
        record = {"Department": "Dental"}
        self.assertTrue(authorize_record(person, record, AccessAction.CLINICAL_READ).allowed)
        self.assertFalse(authorize_record(person, record, AccessAction.CLINICAL_WRITE).allowed)


if __name__ == "__main__":
    unittest.main()
