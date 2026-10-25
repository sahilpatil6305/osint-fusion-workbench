"""Offline tests for safe Sarvam key configuration lookup."""
import os
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from sarvam_client import _get_api_key


class SarvamKeyTests(unittest.TestCase):
    def test_streamlit_secret_precedes_environment(self):
        fake_streamlit = ModuleType("streamlit")
        fake_streamlit.secrets = {"SARVAM_API_KEY": "synthetic-secret-value"}
        with patch.dict(os.environ, {"SARVAM_API_KEY": "environment-value"}), \
             patch.dict("sys.modules", {"streamlit": fake_streamlit}):
            self.assertEqual(_get_api_key(), "synthetic-secret-value")

    def test_environment_fallback_when_streamlit_has_no_secret_file(self):
        fake_streamlit = ModuleType("streamlit")
        fake_streamlit.secrets = SimpleNamespace(get=lambda key, default="": default)
        with patch.dict(os.environ, {"SARVAM_API_KEY": "environment-value"}), \
             patch.dict("sys.modules", {"streamlit": fake_streamlit}):
            self.assertEqual(_get_api_key(), "environment-value")

    def test_missing_key_error_does_not_include_secret_value(self):
        fake_streamlit = ModuleType("streamlit")
        fake_streamlit.secrets = SimpleNamespace(get=lambda key, default="": default)
        with patch.dict(os.environ, {"SARVAM_API_KEY": ""}), \
             patch.dict("sys.modules", {"streamlit": fake_streamlit}):
            with self.assertRaisesRegex(EnvironmentError, "SARVAM_API_KEY is not configured"):
                _get_api_key()


if __name__ == "__main__":
    unittest.main()
