"""Entry point: ``python -m offtunnel`` — GUI if a display is available, else CLI help.

On Windows the app needs Administrator rights to change routes.
If it was started without them, it tries once to relaunch itself
elevated (normal Windows UAC prompt). If the user cancels, it
keeps running and says so plainly on the Home screen instead of
pretending Apply worked.
"""

from .admin import is_admin, relaunch_elevated


def main() -> int:
    import os
    import sys

    if os.name == "nt" and not is_admin():
        if relaunch_elevated():
            return 0  # the elevated copy takes over from here
    try:
        from .gui import launch

        launch()
        return 0
    except Exception:
        # No display / no tkinter: fall back to the CLI so the user
        # still gets something useful instead of a traceback.
        from .cli import main as _cli_main

        return _cli_main(sys.argv[1:] or ["status"])


if __name__ == "__main__":
    raise SystemExit(main())
