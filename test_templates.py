"""
Автотесты шаблонов заметок.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import templates as templates_mod


class TemplatesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "templates.json"
        self.patcher = mock.patch.object(templates_mod, "TEMPLATES_PATH", self.path)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.tmp.cleanup()

    def test_seed_defaults(self) -> None:
        items = templates_mod.load_templates()
        names = {t["name"] for t in items}
        self.assertEqual(names, {"Идея", "Баг", "Задача", "Встреча"})
        self.assertTrue(self.path.exists())

    def test_add_and_delete(self) -> None:
        templates_mod.load_templates()
        item = templates_mod.add_template("Свой", "# hi\n")
        self.assertTrue(any(t["id"] == item["id"] for t in templates_mod.load_templates()))
        templates_mod.delete_template(item["id"])
        self.assertFalse(any(t["id"] == item["id"] for t in templates_mod.load_templates()))


if __name__ == "__main__":
    unittest.main()
