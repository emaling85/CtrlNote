"""Tests for first-run onboarding helpers."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock


class NeedsOnboardingTests(unittest.TestCase):
    def test_needs_when_vault_empty(self) -> None:
        with mock.patch("onboarding.is_configured", return_value=False):
            from onboarding import needs_onboarding

            self.assertTrue(needs_onboarding())

    def test_ok_when_configured(self) -> None:
        with mock.patch("onboarding.is_configured", return_value=True):
            from onboarding import needs_onboarding

            self.assertFalse(needs_onboarding())


class VersionTests(unittest.TestCase):
    def test_version_format(self) -> None:
        from version import __version__

        parts = __version__.split(".")
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(p.isdigit() for p in parts))


class ExampleConfigTests(unittest.TestCase):
    def test_example_exists_and_has_vault(self) -> None:
        path = Path(__file__).resolve().parent / "config.example.json"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("vault_path", text)
        self.assertIn("hotkey", text)


if __name__ == "__main__":
    unittest.main()
