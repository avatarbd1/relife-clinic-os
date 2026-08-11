import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_Bot"))

from department_access import (  # noqa: E402
    Department,
    DepartmentRoleAssignment,
    Role,
    effective_assignments,
    has_department_role,
    roles_for_department,
)


class DepartmentRoleAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.staff = {"Staff_ID": "ST010", "Role": "Manager"}
        self.dental_manager = {
            "Staff_ID": "ST010",
            "Department": "Dental",
            "Role": "Manager",
            "Status": "Active",
        }

    def test_bare_staff_role_grants_nothing(self):
        self.assertEqual(effective_assignments(self.staff, []), frozenset())
        self.assertFalse(has_department_role(self.staff, "Dental", "Manager", []))

    def test_mapping_without_role_fails_closed(self):
        mapping = {
            "Staff_ID": "ST010",
            "Department": "Dental",
            "Status": "Active",
        }
        self.assertEqual(effective_assignments(self.staff, [mapping]), frozenset())

    def test_dental_manager_is_not_physio_manager(self):
        mappings = [self.dental_manager]
        self.assertTrue(
            has_department_role(self.staff, "Dental", "Manager", mappings)
        )
        self.assertFalse(
            has_department_role(self.staff, "Physio", "Manager", mappings)
        )

    def test_multiple_roles_inside_one_department(self):
        nipa = {"Staff_ID": "ST005", "Role": "Manager"}
        mappings = [
            {
                "Staff_ID": "ST005",
                "Department": "Physio",
                "Role": "Manager",
                "Status": "Active",
            },
            {
                "Staff_ID": "ST005",
                "Department": "Physio",
                "Role": "Therapist",
                "Status": "Active",
            },
        ]
        self.assertEqual(
            roles_for_department(nipa, "Physio", mappings),
            frozenset({Role.MANAGER, Role.THERAPIST}),
        )
        self.assertEqual(roles_for_department(nipa, "Dental", mappings), frozenset())

    def test_inactive_unknown_and_cross_staff_rows_are_ignored(self):
        mappings = [
            {**self.dental_manager, "Status": "Inactive"},
            {**self.dental_manager, "Department": "Unknown"},
            {**self.dental_manager, "Role": "Unknown"},
            {**self.dental_manager, "Staff_ID": "ST999"},
        ]
        self.assertEqual(effective_assignments(self.staff, mappings), frozenset())

    def test_only_owner_can_hold_all_assignment(self):
        owner = {"Staff_ID": "ST001", "Role": "Owner"}
        mappings = [
            {
                "Staff_ID": "ST001",
                "Department": "All",
                "Role": "Owner",
                "Status": "Active",
            },
            {
                "Staff_ID": "ST010",
                "Department": "All",
                "Role": "Manager",
                "Status": "Active",
            },
        ]
        self.assertEqual(
            effective_assignments(owner, mappings),
            frozenset(
                {DepartmentRoleAssignment("ST001", Department.ALL, Role.OWNER)}
            ),
        )
        self.assertTrue(has_department_role(owner, "Physio", "Owner", mappings))
        self.assertTrue(has_department_role(owner, "Dental", "Owner", mappings))
        self.assertFalse(
            has_department_role(self.staff, "Dental", "Manager", mappings)
        )

    def test_receptionist_and_assistant_can_coexist_in_dental(self):
        rakib = {"Staff_ID": "ST002", "Role": "Receptionist"}
        mappings = [
            {
                "Staff_ID": "ST002",
                "Department": "Dental",
                "Role": "Receptionist",
                "Status": "Active",
            },
            {
                "Staff_ID": "ST002",
                "Department": "Dental",
                "Role": "Dental_Assistant",
                "Status": "Active",
            },
        ]
        self.assertEqual(
            roles_for_department(rakib, "Dental", mappings),
            frozenset({Role.RECEPTIONIST, Role.DENTAL_ASSISTANT}),
        )


if __name__ == "__main__":
    unittest.main()
