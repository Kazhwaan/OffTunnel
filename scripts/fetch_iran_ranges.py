"""Fetch the latest Iran ranges from RIPE and save the shipped snapshot.

Run from the repository root (needs internet)::

    python scripts/fetch_iran_ranges.py

Writes ``data/countries/ir.json``. This is the snapshot bundled with
OffTunnel so a fresh install works offline on first run; the app
itself re-checks RIPE at runtime and only applies the diff.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from offtunnel.iran_ranges import fetch_country_snapshot  # noqa: E402


def main() -> int:
    snap = fetch_country_snapshot("IR")
    out = Path(__file__).resolve().parent.parent / "data" / "countries" / "ir.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap.to_json(), indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print(
        f"rows={snap.rows} merged_cidrs={len(snap.networks)} "
        f"total_addresses={snap.total_addresses:,} sha256={snap.source_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
