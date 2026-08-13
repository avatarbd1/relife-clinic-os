"""Stage 1 — Daily Clinical Record: structured fields with historical fallback.

Metrics used to live only inside a packed `Remarks` string. Stage 1 adds real
columns while keeping the old string readable, so no historical note is lost.
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

BOT_SOURCE = (BOT_DIR / "bot.py").read_text(encoding="utf-8")
MIGRATION = ROOT / "05_GoogleSheets" / "migrate_treatment_metrics.py"

STRUCTURED = ("Pain_Before", "Pain_After", "Response", "Modification")


def func(name):
    tree = ast.parse(BOT_SOURCE)
    node = next(
        item for item in ast.walk(tree)
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == name
    )
    return ast.unparse(node)


def load(*names):
    """Execute helpers together so they can call each other."""
    namespace = {"re": __import__("re")}
    for name in names:
        exec(func(name), namespace)
    return namespace


class MetricFallbackTests(unittest.TestCase):
    """A dedicated column wins; the old Remarks string still works."""

    def setUp(self):
        ns = load("_extract_metric", "_metric")
        # _metric needs the lookup table defined at module level
        ns["_STRUCTURED_METRIC_COLUMNS"] = eval(
            BOT_SOURCE[
                BOT_SOURCE.index("_STRUCTURED_METRIC_COLUMNS = {")
                + len("_STRUCTURED_METRIC_COLUMNS = ") :
            ].split("\n\n")[0]
        )
        self.metric = ns["_metric"]

    def test_column_is_preferred_over_remarks(self):
        note = {"Pain_After": "3", "Remarks": "Pain: 9 | ROM: 40"}
        self.assertEqual(self.metric(note, "Pain"), "3")

    def test_legacy_note_still_readable(self):
        note = {"Remarks": "Pain: 6 | ROM: 45 | MMT: 4"}
        self.assertEqual(self.metric(note, "Pain"), "6")
        self.assertEqual(self.metric(note, "ROM"), "45")

    def test_pain_falls_back_to_before_when_after_is_empty(self):
        note = {"Pain_Before": "7", "Pain_After": ""}
        self.assertEqual(self.metric(note, "Pain"), "7")

    def test_blank_column_does_not_mask_remarks(self):
        note = {"ROM": "", "Remarks": "ROM: 55"}
        self.assertEqual(self.metric(note, "ROM"), "55")

    def test_missing_everywhere_returns_empty(self):
        self.assertEqual(self.metric({}, "Pain"), "")
        self.assertEqual(self.metric(None, "Pain"), "")

    def test_new_metrics_read_from_their_own_columns(self):
        note = {"Response": "Better", "Modification": "progressed core"}
        self.assertEqual(self.metric(note, "Response"), "Better")
        self.assertEqual(self.metric(note, "Modification"), "progressed core")


class ResponseVocabularyTests(unittest.TestCase):
    """Response must land in a fixed vocabulary so trends stay comparable."""

    def setUp(self):
        ns = load("_normalize_response")
        ns["_RESPONSE_VALUES"] = eval(
            BOT_SOURCE[
                BOT_SOURCE.index("_RESPONSE_VALUES = {")
                + len("_RESPONSE_VALUES = ") :
            ].split("}")[0] + "}"
        )
        self.normalize = ns["_normalize_response"]

    def test_english_synonyms_normalize(self):
        for raw in ("better", "Improved", "IMPROVE"):
            with self.subTest(raw=raw):
                self.assertEqual(self.normalize(raw), "Better")

    def test_same_and_worse_normalize(self):
        self.assertEqual(self.normalize("unchanged"), "Same")
        self.assertEqual(self.normalize("worse"), "Worse")

    def test_bangla_is_accepted(self):
        self.assertEqual(self.normalize("ভালো"), "Better")

    def test_unknown_text_is_kept_not_dropped(self):
        self.assertEqual(self.normalize("mildly sore"), "mildly sore")


class EditParserTests(unittest.TestCase):
    def setUp(self):
        ns = load("_normalize_response", "_parse_pt_edit_message")
        ns["_RESPONSE_VALUES"] = eval(
            BOT_SOURCE[
                BOT_SOURCE.index("_RESPONSE_VALUES = {")
                + len("_RESPONSE_VALUES = ") :
            ].split("}")[0] + "}"
        )
        self.parse = ns["_parse_pt_edit_message"]

    def test_new_fields_are_captured(self):
        parsed = self.parse(
            "Pain Before: 6\nPain After: 4\nResponse: better\nModification: added bridging"
        )
        self.assertEqual(parsed["Pain_Before"], "6")
        self.assertEqual(parsed["Pain_After"], "4")
        self.assertEqual(parsed["Response"], "Better")
        self.assertEqual(parsed["Modification"], "added bridging")

    def test_progression_is_an_alias_for_modification(self):
        self.assertEqual(
            self.parse("Progression: heavier band")["Modification"], "heavier band"
        )

    def test_existing_fields_still_parse(self):
        parsed = self.parse("Pain: 4\nROM: improved\nMachines: TENS")
        self.assertEqual(parsed["Pain"], "4")
        self.assertEqual(parsed["Machines"], "TENS")


class SessionPayloadTests(unittest.TestCase):
    def test_workspace_seeds_pain_before_from_last_session(self):
        body = func("pt_dashboard_receive_callback")
        self.assertIn("Pain_Before", body)
        self.assertIn("Pain_After", body)

    def test_completion_keeps_legacy_pain_in_sync(self):
        body = func("pt_dashboard_done_callback")
        self.assertIn("Pain_After", body)
        self.assertIn("treatment['Pain'] = treatment['Pain_After']", body)

    def test_edit_prompt_explains_the_response_vocabulary(self):
        body = func("pt_dashboard_edit_callback")
        self.assertIn("better", body)
        self.assertIn("worse", body)


class MigrationSafetyTests(unittest.TestCase):
    """The migration must be additive and dry-run by default."""

    def setUp(self):
        self.source = MIGRATION.read_text(encoding="utf-8")

    def test_migration_exists(self):
        self.assertTrue(MIGRATION.exists())

    def test_dry_run_is_the_default(self):
        self.assertIn('"--apply" in sys.argv', self.source)

    def test_all_new_columns_are_declared(self):
        for column in STRUCTURED + ("Received_By",):
            with self.subTest(column=column):
                self.assertIn(column, self.source)

    def test_columns_are_only_appended(self):
        """Inserting a column would corrupt positional writers elsewhere."""
        self.assertIn("start = len(headers) + 1", self.source)
        for forbidden in ("delete_columns", "insert_cols", "clear()", "resize("):
            with self.subTest(op=forbidden):
                self.assertNotIn(forbidden, self.source)

    def test_existing_columns_are_skipped(self):
        self.assertIn("if name not in headers", self.source)


if __name__ == "__main__":
    unittest.main()
