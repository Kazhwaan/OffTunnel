import tempfile
import unittest
from pathlib import Path

from offtunnel.settings import DEFAULTS, Settings


class TestSettings(unittest.TestCase):
    def test_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = Settings(Path(tmp) / "settings.json")
            # Iran pack on, minimise-to-tray on: the v0.1.1 defaults
            # for a first-time user.
            self.assertTrue(s.get("iran_pack_enabled"))
            self.assertTrue(s.get("minimize_on_close"))
            self.assertTrue(s.get("tray_enabled"))
            self.assertFalse(s.get("start_minimized"))
            self.assertEqual(s.get("check_interval_minutes"), 15)

    def test_roundtrip_and_bad_values_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            s = Settings(path)
            s.set("minimize_on_close", False)
            s.set("check_interval_minutes", 30)
            s2 = Settings(path)
            self.assertFalse(s2.get("minimize_on_close"))
            self.assertEqual(s2.get("check_interval_minutes"), 30)
            # Wrong type / unknown key must not stick or crash.
            s2.set("check_interval_minutes", "not a number")
            self.assertEqual(s2.get("check_interval_minutes"), 30)
            s2.set("no_such_key", True)
            self.assertIsNone(s2.get("no_such_key"))

    def test_corrupt_file_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            path.write_text("{not json", encoding="utf-8")
            s = Settings(path)
            self.assertEqual(s.values, dict(DEFAULTS))


if __name__ == "__main__":
    unittest.main()
