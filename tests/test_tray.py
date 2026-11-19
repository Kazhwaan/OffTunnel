import unittest

from offtunnel.tray import TrayController, TrayIcon


class TestTrayController(unittest.TestCase):
    def test_close_minimises_when_tray_available(self):
        c = TrayController(tray_available=True, minimize_on_close=True)
        self.assertEqual(c.on_close(), "minimize")
        self.assertTrue(c.minimized_to_tray)
        self.assertFalse(c.window_visible)

    def test_close_exits_when_minimise_off(self):
        c = TrayController(tray_available=True, minimize_on_close=False)
        self.assertEqual(c.on_close(), "exit")
        self.assertFalse(c.minimized_to_tray)

    def test_close_exits_when_no_tray(self):
        # No tray icon (e.g. tray creation failed): closing must
        # quit, not hide the window somewhere the user cannot find.
        c = TrayController(tray_available=False, minimize_on_close=True)
        self.assertEqual(c.on_close(), "exit")

    def test_tray_activate_restores(self):
        c = TrayController(tray_available=True, minimize_on_close=True)
        c.on_close()
        self.assertEqual(c.on_tray_activate(), "show")
        self.assertTrue(c.window_visible)
        self.assertFalse(c.minimized_to_tray)

    def test_tray_exit(self):
        c = TrayController(tray_available=True, minimize_on_close=True)
        self.assertEqual(c.on_tray_exit(), "exit")


class TestTrayIconStub(unittest.TestCase):
    def test_non_windows_is_unavailable_but_safe(self):
        import os

        if os.name == "nt":
            self.skipTest("Windows tray is real here")
        tray = TrayIcon(on_show=lambda: None, on_apply=lambda: None, on_exit=lambda: None)
        self.assertFalse(tray.available)
        tray.remove()  # must not raise


if __name__ == "__main__":
    unittest.main()
