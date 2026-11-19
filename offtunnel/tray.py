"""Windows system tray for OffTunnel.

What Javen asked for in v0.1.1: closing the window should not kill
the app — it should minimise to the Windows tray, keep the routes
and the auto-updater running, and let him bring the window back
from the tray. The tray menu offers Show / Apply / Exit.

Implementation notes (read before changing this file):
  * Windows only, stdlib only: the tray icon is built with
    ``ctypes`` + ``Shell_NotifyIconW`` on a small hidden message
    window. No pystray / no new dependency — the app stays
    lightweight and the exe stays small.
  * On non-Windows (this Linux VM, tests) the tray is a no-op stub:
    ``available`` is False, but the *state machine* still works, so
    the GUI logic and the tests exercise the same decisions.
  * A tray failure must never crash the app: every Win32 call is
    guarded, and on failure the tray simply reports unavailable
    and the window behaves like a normal window.

The decision logic lives in :class:`TrayController` (pure Python,
fully tested). The Win32 plumbing lives in :class:`TrayIcon`.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass


@dataclass
class TrayController:
    """Pure decision logic for minimise-to-tray. No Win32 here."""

    tray_available: bool = False
    minimize_on_close: bool = True
    window_visible: bool = True
    minimized_to_tray: bool = False

    def on_close(self) -> str:
        """What the close button should do: "minimize" or "exit"."""
        if self.minimize_on_close and self.tray_available:
            self.window_visible = False
            self.minimized_to_tray = True
            return "minimize"
        self.window_visible = False
        self.minimized_to_tray = False
        return "exit"

    def on_tray_activate(self) -> str:
        """Double-click / single click on the tray icon: show the window."""
        self.window_visible = True
        self.minimized_to_tray = False
        return "show"

    def on_tray_show(self) -> str:
        return self.on_tray_activate()

    def on_tray_exit(self) -> str:
        self.window_visible = False
        self.minimized_to_tray = False
        return "exit"


class TrayIcon:
    """Win32 tray icon (Windows) / no-op stub (everywhere else).

    Callbacks: ``on_show``, ``on_apply`` and ``on_exit`` are plain
    callables, invoked on the GUI thread via the message window.
    """

    def __init__(self, on_show=None, on_apply=None, on_exit=None, tooltip="OffTunnel"):
        self.on_show = on_show
        self.on_apply = on_apply
        self.on_exit = on_exit
        self.tooltip = tooltip
        self.available = False
        self._hwnd = None
        self._icon_handle = None
        self._uid = 1
        try:
            import os

            if os.name == "nt":
                self._setup_windows()
        except Exception:
            self.available = False

    # -- Windows plumbing -------------------------------------------------
    def _setup_windows(self) -> None:
        import ctypes
        import ctypes.wintypes as wt

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32

        WM_USER = 0x0400
        self._callback_msg = WM_USER + 1
        WM_LBUTTONDBLCLK = 0x0203
        WM_LBUTTONUP = 0x0202
        WM_RBUTTONUP = 0x0205
        WM_COMMAND = 0x0111
        NIM_ADD = 0x00000000
        NIM_DELETE = 0x00000002
        NIF_MESSAGE = 0x00000001
        NIF_ICON = 0x00000002
        NIF_TIP = 0x00000004
        IDI_APPLICATION = 32512

        self._WNDPROC = ctypes.WINFUNCTYPE(wt.LPARAM, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        self._user32 = user32
        self._shell32 = shell32
        self._consts = {
            "WM_LBUTTONDBLCLK": WM_LBUTTONDBLCLK,
            "WM_LBUTTONUP": WM_LBUTTONUP,
            "WM_RBUTTONUP": WM_RBUTTONUP,
            "WM_COMMAND": WM_COMMAND,
            "NIM_ADD": NIM_ADD,
            "NIM_DELETE": NIM_DELETE,
            "NIF_MESSAGE": NIF_MESSAGE,
            "NIF_ICON": NIF_ICON,
            "NIF_TIP": NIF_TIP,
        }

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == self._callback_msg:
                if lparam in (WM_LBUTTONDBLCLK, WM_LBUTTONUP):
                    if self.on_show:
                        self.on_show()
                elif lparam == WM_RBUTTONUP:
                    self._show_menu(hwnd)
                return 0
            if msg == WM_COMMAND:
                item = wparam & 0xFFFF
                if item == 1 and self.on_show:
                    self.on_show()
                elif item == 2 and self.on_apply:
                    self.on_apply()
                elif item == 3 and self.on_exit:
                    self.on_exit()
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = self._WNDPROC(wndproc)

        class WNDCLASS(ctypes.Structure):
            _fields_ = [
                ("style", wt.UINT), ("lpfnWndProc", ctypes.c_void_p),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HCURSOR), ("hbrBackground", wt.HBRUSH),
                ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR),
            ]

        hinst = ctypes.windll.kernel32.GetModuleHandleW(None)
        cls_name = "OffTunnelTrayWindow"
        wc = WNDCLASS()
        wc.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p)
        wc.hInstance = hinst
        wc.lpszClassName = cls_name
        if not user32.RegisterClassW(ctypes.byref(wc)):
            return
        hwnd = user32.CreateWindowExW(
            0, cls_name, "OffTunnel", 0, 0, 0, 0, 0, None, None, hinst, None
        )
        if not hwnd:
            return
        self._hwnd = hwnd
        # Icon: the bundled .ico if present, else the default app icon.
        hicon = user32.LoadIconW(None, IDI_APPLICATION)
        try:
            from pathlib import Path

            for candidate in (
                Path(__file__).resolve().parent.parent / "assets" / "logo.ico",
            ):
                if candidate.exists():
                    loaded = user32.LoadImageW(
                        None, str(candidate), 1, 0, 0, 0x00000010
                    )
                    if loaded:
                        hicon = loaded
                        break
        except Exception:
            pass
        self._icon_handle = hicon

        class NOTIFYICONDATA(ctypes.Structure):
            _fields_ = [
                ("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT),
                ("uFlags", wt.UINT), ("uCallbackMessage", wt.UINT),
                ("hIcon", wt.HICON), ("szTip", wt.WCHAR * 128),
                ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD),
                ("szInfo", wt.WCHAR * 256), ("uVersion", wt.UINT),
                ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", wt.DWORD),
                ("guidItem", ctypes.c_byte * 16), ("hBalloonIcon", wt.HICON),
            ]

        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = hwnd
        nid.uID = self._uid
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = self._callback_msg
        nid.hIcon = hicon
        nid.szTip = self.tooltip[:127]
        if shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            self.available = True
            self._nid = nid
        else:
            self.available = False

    def _show_menu(self, hwnd) -> None:
        try:
            user32 = self._user32
            user32.SetForegroundWindow(hwnd)
            menu = user32.CreatePopupMenu()
            for item_id, label in ((1, "Show OffTunnel"), (2, "Apply protection"), (3, "Exit")):
                user32.AppendMenuW(menu, 0x00000000, item_id, label)
            pt = self._POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.TrackPopupMenu(menu, 0x00000000, pt.x, pt.y, 0, hwnd, None)
            user32.DestroyMenu(menu)
        except Exception:
            pass

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    # -- public API -------------------------------------------------------
    def remove(self) -> None:
        """Remove the tray icon (call on exit). Never raises."""
        if not self.available:
            return
        try:
            self._shell32.Shell_NotifyIconW(
                self._consts["NIM_DELETE"], ctypes.byref(self._nid)
            )
        except Exception:
            pass
        self.available = False
