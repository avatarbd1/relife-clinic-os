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


if __name__ == "__main__":
    unittest.main()
