"""Iran (and, later, other country) IP-range source for OffTunnel.

Source of truth: the RIPE NCC delegated-statistics file, published
daily. It lists every IPv4 allocation/assignment by country code, so
OffTunnel does not have to trust a third-party "Iran IP list" website
and does not ship a stale hard-coded list as its only source.

    https://ftp.ripe.net/ripe/stats/delegated-ripencc-latest

Update policy (the lightweight part):
  * Check the file frequently (default: every 15 minutes while the
    app is running, configurable) — a HEAD/hash check is cheap.
  * Only parse + apply when the SHA-256 of the file has changed.
    RIPE publishes daily, so in practice this is at most one small
    diff per day, usually zero.
  * When it has changed, apply only the diff (see ``cidr.diff_networks``).

A snapshot of the last applied list is stored next to the rules file
(``%LOCALAPPDATA%\\OffTunnel\\iran_snapshot.json`` on Windows), plus a
shipped snapshot in ``data/countries/ir.json`` so a fresh install
works offline on first run.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from dataclasses import asdict, dataclass
from ipaddress import IPv4Network
from pathlib import Path

from .cidr import (
    merge_networks,
    networks_to_strings,
    parse_delegated_line,
    parse_delegated_text,
    strings_to_networks,
    total_addresses,
)
from .config import APP_NAME, DATA_DIR_NAME, USER_AGENT

RIPE_URL = "https://ftp.ripe.net/ripe/stats/delegated-ripencc-latest"
RIPE_FALLBACK_URL = "https://ftp.ripe.net/pub/stats/ripencc/delegated-ripencc-latest"
# The same file is mirrored by APNIC; kept as a second fallback.
APNIC_MIRROR_URL = "https://ftp.apnic.net/stats/ripe-ncc/delegated-ripencc-latest"

SOURCE_URLS = (RIPE_URL, RIPE_FALLBACK_URL, APNIC_MIRROR_URL)


@dataclass
class RangeSnapshot:
    country: str
    source_url: str
    source_sha256: str
    fetched_at: float  # unix timestamp
    rows: int  # delegated-stats rows for this country (before merging)
    networks: list[IPv4Network]

    @property
    def total_addresses(self) -> int:
        return total_addresses(self.networks)

    def to_json(self) -> dict:
        data = asdict(self)
        data["networks"] = networks_to_strings(self.networks)
        return data

    @classmethod
    def from_json(cls, data: dict) -> "RangeSnapshot":
        return cls(
            country=data["country"],
            source_url=data["source_url"],
            source_sha256=data["source_sha256"],
            fetched_at=float(data["fetched_at"]),
            rows=int(data.get("rows", 0)),
            networks=strings_to_networks(data["networks"]),
        )


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_text(url: str, timeout: int = 30) -> bytes:
    """Download a URL. Raises on network/HTTP failure (caller decides)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_country_snapshot(country: str = "IR", timeout: int = 30) -> RangeSnapshot:
    """Fetch the RIPE file (trying mirrors in order) and parse ``country``."""
    last_error: Exception | None = None
    for url in SOURCE_URLS:
        try:
            raw = fetch_text(url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            last_error = exc
            continue
        text = raw.decode("utf-8", "ignore")
        rows = sum(1 for line in text.splitlines() if parse_delegated_line(line, country))
        networks = parse_delegated_text(text, country)
        return RangeSnapshot(
            country=country,
            source_url=url,
            source_sha256=sha256_hex(raw),
            fetched_at=time.time(),
            rows=rows,
            networks=merge_networks(networks),
        )
    raise RuntimeError(f"Could not fetch Iran ranges from any mirror: {last_error}")


def snapshot_path(base_dir: Path | None = None) -> Path:
    return (base_dir or default_data_dir()) / "iran_snapshot.json"


def default_data_dir() -> Path:
    """Per-user data dir: %LOCALAPPDATA%\\OffTunnel on Windows, ~/.config/OffTunnel elsewhere."""
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / DATA_DIR_NAME
    return Path.home() / ".config" / DATA_DIR_NAME


def load_snapshot(path: Path) -> RangeSnapshot | None:
    try:
        return RangeSnapshot.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_snapshot(snapshot: RangeSnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot.to_json(), indent=2), encoding="utf-8")
    os.replace(tmp, path)


def shipped_snapshot_path() -> Path:
    """Snapshot bundled with the app (``data/countries/ir.json``)."""
    return Path(__file__).resolve().parent.parent / "data" / "countries" / "ir.json"
