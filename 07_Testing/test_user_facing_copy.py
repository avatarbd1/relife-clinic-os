import ast
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_SOURCE = (ROOT / "03_Bot" / "bot.py").read_text(encoding="utf-8")


class UserFacingCopyTests(unittest.TestCase):
    def test_deprecated_processing_messages_are_removed(self):
        deprecated = [
            "ছবিটা পড়া হচ্ছে",
            "Manual খুঁজছি",
            "🤔 খুঁজছি",
            "Lesson 1 তৈরি হচ্ছে",
            "লিখো (খুঁজতে)",
            "লেখো (খুঁজতে)",
            "গত সপ্তাহে income কত হয়েছে",
            "আজকের মোট আয় কত",
        ]
        for phrase in deprecated:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, BOT_SOURCE)

    def test_context_specific_status_messages_exist(self):
        expected = [
            "ছবি/রিপোর্টের তথ্য বিশ্লেষণ করছি",
            "ক্লিনিক্যাল তথ্য ও প্রাসঙ্গিক ম্যানুয়াল বিশ্লেষণ করছি",
            "ক্লিনিকের তথ্য বিশ্লেষণ করে উত্তর প্রস্তুত করছি",
            "রোগী শনাক্ত করতে নাম, ফোন নম্বর অথবা Patient ID লিখুন",
        ]
        for phrase in expected:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, BOT_SOURCE)


    def test_staff_ai_examples_use_natural_clinic_language(self):
        expected = [
            "আজকে মোট কত টাকা জমা হয়েছে?",
            "আজকে ফিজিও থেকে কত টাকা এসেছে?",
            "এই মাসে মোট খরচ কত হয়েছে?",
            "আজকে কতজন নতুন রোগী রেজিস্ট্রেশন করেছেন?",
            "আজকে কতজন স্টাফ দেরিতে এসেছেন?",
        ]
        for phrase in expected:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, BOT_SOURCE)


    def test_current_and_legacy_attendance_labels_share_handler(self):
        tree = ast.parse(BOT_SOURCE)
        labels_assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "_ATTENDANCE_MENU_LABELS"
                for target in node.targets
            )
        )
        labels = labels_assignment.value.elts
        self.assertTrue(
            any(
                isinstance(label, ast.Attribute)
                and isinstance(label.value, ast.Name)
                and label.value.id == "roles"
                and label.attr == "MENU_ATTENDANCE"
                for label in labels
            )
        )
        self.assertTrue(
            any(isinstance(label, ast.Constant) and label.value == "🏠 হাজিরা" for label in labels)
        )
        self.assertIn(
            're.escape(label) for label in _ATTENDANCE_MENU_LABELS',
            BOT_SOURCE,
        )
        self.assertIn(
            'MessageHandler(filters.Regex(_ATTENDANCE_MENU_REGEX), attendance_menu)',
            BOT_SOURCE,
        )

        route_pattern = re.compile(
            "^(?:" + "|".join(re.escape(label) for label in ("🕐 হাজিরা", "🏠 হাজিরা")) + ")$"
        )
        for label in ("🕐 হাজিরা", "🏠 হাজিরা"):
            with self.subTest(label=label):
                self.assertIsNotNone(route_pattern.fullmatch(label))


if __name__ == "__main__":
    unittest.main()
