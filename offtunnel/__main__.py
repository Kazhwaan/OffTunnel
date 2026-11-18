"""Entry point: ``python -m offtunnel`` — GUI if a display is available, else CLI help."""

from .cli import main as _cli_main


def main() -> int:
    try:
        from .gui import launch

        launch()
        return 0
    except Exception:
        # No display / no tkinter: fall back to the CLI so the user
        # still gets something useful instead of a traceback.
        import sys

        return _cli_main(sys.argv[1:] or ["status"])


if __name__ == "__main__":
    raise SystemExit(main())
