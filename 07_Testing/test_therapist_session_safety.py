"""Stage 0 — Therapist session safety foundation.

Covers the four guarantees Stage 0 must provide before the Clinical Workspace
redesign can safely build on top of it:

1. a Therapist's queue shows their own patients, not the whole department
2. two people cannot hold the same patient's session at once
3. the same session cannot be saved twice
4. a partial write reports exactly which step failed instead of a generic error
"""
import ast
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("GOOGLE_SHEET_ID", "test-sheet")

_CREDENTIALS = ROOT / "credentials.json"
_CREATED = False
if not _CREDENTIALS.exists():
    _CREDENTIALS.write_text("{}", encoding="utf-8")
    _CREATED = True

BOT_SOURCE = (BOT_DIR / "bot.py").read_text(encoding="utf-8")
SHEETS_SOURCE = (BOT_DIR / "sheets.py").read_text(encoding="utf-8")


def tearDownModule():
    if _CREATED:
        _CREDENTIALS.unlink(missing_ok=True)


def func(source, name):
    tree = ast.parse(source)
    node = next(
        item for item in ast.walk(tree)
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == name
    )
    return ast.unparse(node)


def load(name):
    """Execute one standalone helper in isolation and return it."""
    namespace = {}
    exec(func(BOT_SOURCE, name), namespace)
    return namespace[name]


class QueueScopingTests(unittest.TestCase):
    """A Therapist should not see every patient in the department."""

    def setUp(self):
        self.belongs = load("_queue_belongs_to")

    def test_own_patient_is_included(self):
        self.assertTrue(
            self.belongs({"Full_Name": "Nipa"}, {"Therapist": "Nipa"}, {})
        )

    def test_another_therapists_patient_is_excluded(self):
        self.assertFalse(
            self.belongs({"Full_Name": "Nipa"}, {"Therapist": "Saiful"}, {})
        )

    def test_patient_record_therapist_also_counts(self):
        self.assertTrue(
            self.belongs({"Full_Name": "Nipa"}, {}, {"Therapist": "Nipa"})
        )

    def test_name_match_ignores_case_and_spacing(self):
        self.assertTrue(
            self.belongs({"Full_Name": " nipa "}, {"Therapist": "Nipa"}, {})
        )

    def test_unassigned_patient_is_visible_to_everyone(self):
        """Nobody should silently vanish from the queue."""
        self.assertTrue(self.belongs({"Full_Name": "Nipa"}, {}, {}))

    def test_queue_accepts_a_show_all_override(self):
        body = func(BOT_SOURCE, "_therapist_today_queue")
        self.assertIn("show_all", body)
        self.assertIn("own_only", body)

    def test_scoping_only_applies_to_clinical_only_staff(self):
        body = func(BOT_SOURCE, "_is_therapist_only")
        for role in ("OWNER", "MANAGER", "RECEPTIONIST"):
            with self.subTest(role=role):
                self.assertIn(role, body)


class SingleQueueBuildTests(unittest.TestCase):
    """The queue was previously rebuilt twice per dashboard render."""

    def test_a_shared_view_helper_exists(self):
        body = func(BOT_SOURCE, "_pt_dashboard_view")
        self.assertIn("_therapist_today_queue", body)
        self.assertIn("_pt_dashboard_text", body)
        self.assertIn("_pt_dashboard_keyboard", body)

    def test_text_and_keyboard_accept_a_prebuilt_queue(self):
        for name in ("_pt_dashboard_text", "_pt_dashboard_keyboard"):
            with self.subTest(fn=name):
                self.assertIn("queue", func(BOT_SOURCE, name))

    def test_dashboard_entry_point_uses_the_shared_view(self):
        self.assertIn("_pt_dashboard_view", func(BOT_SOURCE, "pt_dashboard"))


class DoubleReceiveTests(unittest.TestCase):
    def test_receive_checks_for_an_existing_holder(self):
        body = func(BOT_SOURCE, "pt_dashboard_receive_callback")
        self.assertIn("_active_session_holder", body)
        self.assertIn("_same_staff", body)

    def test_holder_is_only_reported_while_in_treatment(self):
        self.assertIn("In Treatment", func(BOT_SOURCE, "_active_session_holder"))

    def test_same_staff_comparison_is_case_insensitive(self):
        same = load("_same_staff")
        self.assertTrue(same({"Full_Name": "Nipa"}, "nipa"))
        self.assertFalse(same({"Full_Name": "Nipa"}, "Saiful"))

    def test_receiver_identity_is_recorded(self):
        self.assertIn(
            "set_appointment_received_by",
            func(BOT_SOURCE, "pt_dashboard_receive_callback"),
        )

    def test_identity_writer_is_optional_on_the_schema(self):
        """Stage 0 changes no schema — a missing column must not raise."""
        body = func(SHEETS_SOURCE, "set_appointment_received_by")
        self.assertIn("'Received_By' not in headers", body)
        self.assertIn("return False", body)


class DoubleCompleteTests(unittest.TestCase):
    def setUp(self):
        self.existing = load("_existing_session_note")

    def test_same_plan_and_session_is_detected(self):
        notes = [{"Plan_ID": "PL01", "Session_No": "6", "Treatment_ID": "TR09"}]
        found = self.existing(notes, "PL01", 6)
        self.assertIsNotNone(found)
        self.assertEqual(found["Treatment_ID"], "TR09")

    def test_a_different_session_is_not_a_duplicate(self):
        notes = [{"Plan_ID": "PL01", "Session_No": "5"}]
        self.assertIsNone(self.existing(notes, "PL01", 6))

    def test_a_different_plan_is_not_a_duplicate(self):
        notes = [{"Plan_ID": "PL02", "Session_No": "6"}]
        self.assertIsNone(self.existing(notes, "PL01", 6))

    def test_missing_identifiers_never_block_a_save(self):
        self.assertIsNone(self.existing([{"Plan_ID": "", "Session_No": ""}], "", ""))

    def test_completion_refuses_a_second_tap_while_saving(self):
        body = func(BOT_SOURCE, "pt_dashboard_done_callback")
        self.assertIn("pt_saving", body)

    def test_completion_checks_for_an_existing_note_first(self):
        self.assertIn(
            "_existing_session_note", func(BOT_SOURCE, "pt_dashboard_done_callback")
        )


class PartialWriteTests(unittest.TestCase):
    """Each write step must fail with its own message."""

    def test_the_three_writes_are_separately_guarded(self):
        body = func(BOT_SOURCE, "pt_dashboard_done_callback")
        self.assertGreaterEqual(body.count("except Exception:"), 3)

    def test_a_failed_note_says_nothing_was_written(self):
        self.assertIn("কিছুই লেখা হয়নি", func(BOT_SOURCE, "pt_dashboard_done_callback"))

    def test_a_failed_increment_warns_against_resaving(self):
        body = func(BOT_SOURCE, "pt_dashboard_done_callback")
        self.assertIn("session count বাড়েনি", body)

    def test_session_context_is_cleared_through_one_helper(self):
        body = func(BOT_SOURCE, "_clear_session_context")
        for key in ("pt_treatment", "pt_patient_id", "pt_appointment_id"):
            with self.subTest(key=key):
                self.assertIn(key, body)


if __name__ == "__main__":
    unittest.main()
