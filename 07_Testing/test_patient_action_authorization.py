import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))


def function(name):
    tree = ast.parse((BOT_DIR / "bot.py").read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def calls(node):
    found = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        parts = []
        current = item.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        found.add(".".join(reversed(parts)))
    return found


class PatientActionAuthorizationTests(unittest.TestCase):
    def test_sensitive_callbacks_use_central_live_guard(self):
        for name in [
            "plist_action_pay",
            "plist_action_apt",
            "plist_action_treat",
            "plist_action_report",
        ]:
            with self.subTest(name=name):
                self.assertIn("_authorized_patient_action", calls(function(name)))

    def test_live_guard_reloads_staff_and_authorizes_record(self):
        names = calls(function("_authorized_patient_action"))
        self.assertIn("_require_staff", names)
        self.assertIn("sheets.get_patient_by_id_for_staff", names)
        self.assertIn("department_access.authorize_record", names)

    def test_payment_confirmation_reauthorizes_before_write(self):
        node = function("pay_confirm")
        names = calls(node)
        self.assertIn("_authorized_patient_action", names)
        self.assertIn("sheets.record_payment_transaction", names)
        source = ast.unparse(node)
        self.assertLess(
            source.index("_authorized_patient_action"),
            source.index("sheets.record_payment_transaction"),
        )

    def test_patient_keyboard_checks_effective_menu_permissions(self):
        node = function("_patient_card_keyboard")
        names = calls(node)
        self.assertIn("_staff_can_access_menu", names)
        source = ast.unparse(node)
        self.assertIn("MENU_PAYMENT", source)
        self.assertIn("MENU_APPOINTMENT", source)
        self.assertIn("MENU_TREATMENT_NOTE", source)


if __name__ == "__main__":
    unittest.main()
