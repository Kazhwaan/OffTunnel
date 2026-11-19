"""Administrator rights for OffTunnel (Windows only).

Changing Windows routes requires admin rights. v0.1.0 only *warned*
about this after the user clicked Apply — and the exe did not ask
for admin at launch, so a normal double-click silently did nothing
useful. v0.1.1 fixes both ends:

  * The PyInstaller build requests admin at launch
    (``--uac-admin`` in build.ps1 / OffTunnel.spec, i.e. a
    ``requireAdministrator`` manifest). That is the real fix for the
    built exe; it needs the workflow to use those build flags
    (see BUILD_LOG.md).
  * The app itself also detects a non-admin launch and relaunches
    elevated (``ShellExecuteEx`` with the ``runas`` verb, which shows
    the normal Windows UAC prompt). If the user cancels the prompt,
    the app keeps running in read-only mode and says so plainly
    instead of pretending Apply worked.

On non-Windows this module is a harmless no-op: ``is_admin()``
returns False and ``relaunch_elevated()`` returns False.
"""

from __future__ import annotations

import os
import sys

# Guard so a relaunch never loops: the elevated child sets this env
# var, and if it is still not admin we stop trying.
_ATTEMPT_ENV = "OFFTUNNEL_ELEVATE_ATTEMPT"


def is_admin() -> bool:
    """True when running as Administrator on Windows."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_elevated(argv: list[str] | None = None) -> bool:
    """Relaunch this process elevated (Windows UAC prompt).

    Returns True when the elevated process was started (the caller
    should then exit), False when elevation is unavailable, was
    cancelled, or this is not Windows. Never raises.
    """
    if os.name != "nt":
        return False
    if os.environ.get(_ATTEMPT_ENV) == "1":
        return False  # already tried once — do not loop
    try:
        import ctypes

        args = " ".join(f'"{a}"' for a in (argv if argv is not None else sys.argv[1:]))
        executable = sys.executable
        params = f'"{sys.argv[0]}" {args}'.strip()
        # Mark the attempt in our own environment so the elevated
        # child (which inherits it) does not try to elevate again.
        os.environ[_ATTEMPT_ENV] = "1"
        # ShellExecuteEx with "runas" shows the UAC prompt.
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", executable, params, None, 1
        )
        return int(result) > 32
    except Exception:
        return False


def ensure_admin_or_warn() -> str:
    """One-line plain-language admin state for the UI/CLI.

    Returns "admin", "not-admin" or "non-windows".
    """
    if os.name != "nt":
        return "non-windows"
    return "admin" if is_admin() else "not-admin"
