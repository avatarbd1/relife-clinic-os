import hashlib
import hmac
import os
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))

import media_export_http  # noqa: E402


class MediaExportHttpTests(unittest.TestCase):
    def test_header_auth_is_fail_closed_without_secret(self):
        handler = SimpleNamespace(headers={"X-Relife-Media-Key": "anything"})
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(media_export_http._header_authorized(handler))

    def test_header_auth_accepts_exact_secret_only(self):
        good = SimpleNamespace(headers={"X-Relife-Media-Key": "media-test-secret"})
        bad = SimpleNamespace(headers={"X-Relife-Media-Key": "wrong"})
        with patch.dict(
            os.environ,
            {"MEDIA_EXPORT_SECRET": "media-test-secret"},
            clear=True,
        ):
            self.assertTrue(media_export_http._header_authorized(good))
            self.assertFalse(media_export_http._header_authorized(bad))

    def test_batch_signature_is_short_lived_and_bound_to_range(self):
        secret = "media-test-secret"
        department = "Physio"
        start = 25
        limit = 25
        expires = int(time.time()) + 120
        message = media_export_http._batch_signature_message(
            department, start, limit, expires
        )
        signature = hmac.new(
            secret.encode("utf-8"), message, hashlib.sha256
        ).hexdigest()
        query = {"expires": [str(expires)], "sig": [signature]}
        with patch.dict(
            os.environ,
            {"MEDIA_EXPORT_SECRET": secret},
            clear=True,
        ):
            self.assertTrue(
                media_export_http._signed_batch_authorized(
                    query, department, start, limit
                )
            )
            self.assertFalse(
                media_export_http._signed_batch_authorized(
                    query, department, start + 1, limit
                )
            )

    def test_path_components_cannot_escape_zip_folder(self):
        value = media_export_http._safe_path_part(
            '../../PT001 - A/B:C*D?"E<F>G|H', "fallback"
        )
        self.assertNotIn("/", value)
        self.assertNotIn("\\", value)
        self.assertNotIn(":", value)
        self.assertFalse(value.startswith(".."))

    def test_department_is_explicit(self):
        self.assertEqual(media_export_http._department("Physio"), "Physio")
        self.assertEqual(media_export_http._department("dental"), "Dental")
        self.assertIsNone(media_export_http._department("All"))
        self.assertIsNone(media_export_http._department(""))


if __name__ == "__main__":
    unittest.main()
