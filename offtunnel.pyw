# OffTunnel launcher (Windows: double-click, or `pyw -3 offtunnel.pyw`).
# Kept tiny on purpose: all logic lives in the `offtunnel` package.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from offtunnel.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
