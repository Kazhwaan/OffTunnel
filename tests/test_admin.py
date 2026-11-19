import os
import unittest

from offtunnel.admin import ensure_admin_or_warn, is_admin, relaunch_elevated


class TestAdmin(unittest.TestCase):
    def test_non_windows_is_not_admin_and_cannot_relaunch(self):
        # This VM is Linux: no admin, no elevation, no crash.
        if os.name == "nt":
            self.skipTest("Windows-only behaviour differs here")
        self.assertFalse(is_admin())
        self.assertFalse(relaunch_elevated())
        self.assertEqual(ensure_admin_or_warn(), "non-windows")


if __name__ == "__main__":
    unittest.main()
