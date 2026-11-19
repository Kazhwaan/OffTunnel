"""Regenerate the binary icon files from the base64 text in assets/.

Why this exists: the .ico/.png are binary, and the GitHub contents
API used to push this repo only accepts text files, so the binaries
are stored as base64 text (``assets/logo.ico.b64``,
``assets/logo.png.b64``). This script decodes them back to
``assets/logo.ico`` / ``assets/logo.png``. It uses only the stdlib,
so it runs anywhere Python runs — including the GitHub Actions
runner, before PyInstaller needs the .ico.

Run it directly, or let ``build.ps1`` do it:

    python scripts/generate_icons.py
"""

import base64
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ASSETS = HERE / "assets"


def main() -> None:
    for name in ("logo.ico", "logo.png"):
        b64_path = ASSETS / f"{name}.b64"
        out_path = ASSETS / name
        data = base64.b64decode(b64_path.read_text(encoding="utf-8"))
        out_path.write_bytes(data)
        print(f"Wrote {out_path} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
