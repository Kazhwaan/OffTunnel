"""Background updater for OffTunnel.

Checks the Iran range source on a timer, but — critically — only
does expensive work when the source actually changed:

  1. Fetch the RIPE file (or fail quietly and retry next time; a
     failed fetch must never remove existing routes).
  2. Compare its SHA-256 with the last applied snapshot.
  3. If identical: do nothing. Log one line, sleep.
  4. If different: parse, diff against the applied snapshot, apply
     only the added/removed networks, save the new snapshot.

Default check interval is 15 minutes. That is frequent enough that
a daily RIPE change is picked up the same day, and cheap enough
that a failed/no-change check costs one ~8 MB download (or, in a
future version, a HEAD request) and no route changes at all. The
interval is configurable; checking more often does not make routes
update more often, because RIPE only publishes daily.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

from .cidr import diff_networks
from .iran_ranges import (
    RangeSnapshot,
    fetch_country_snapshot,
    load_snapshot,
    save_snapshot,
    snapshot_path,
)
from .routes import RouteExecutor

LogFn = Callable[[str], None]


@dataclass
class CheckResult:
    changed: bool
    added: int = 0
    removed: int = 0
    total_networks: int = 0
    total_addresses: int = 0
    error: str = ""


def check_once(
    executor: RouteExecutor,
    gateway: str | None,
    log: LogFn = print,
    country: str = "IR",
) -> CheckResult:
    """One update cycle. Returns what happened; never raises on fetch failure."""
    path = snapshot_path()
    old_snapshot = load_snapshot(path)
    try:
        new_snapshot = fetch_country_snapshot(country)
    except Exception as exc:  # noqa: BLE001 - network failure is expected sometimes
        log(f"[updater] fetch failed, keeping current routes: {exc}")
        return CheckResult(changed=False, error=str(exc))

    old_networks = old_snapshot.networks if old_snapshot else []
    if old_snapshot and old_snapshot.source_sha256 == new_snapshot.source_sha256:
        log("[updater] Iran ranges unchanged — no routes touched.")
        return CheckResult(
            changed=False,
            total_networks=len(new_snapshot.networks),
            total_addresses=new_snapshot.total_addresses,
        )

    added, removed = diff_networks(old_networks, new_snapshot.networks)
    log(
        f"[updater] Iran ranges changed: +{len(added)} -{len(removed)} networks, "
        f"{len(new_snapshot.networks)} total, {new_snapshot.total_addresses:,} addresses."
    )
    if gateway:
        from ipaddress import IPv4Address

        executor.apply_diff(old_networks, new_snapshot.networks, IPv4Address(gateway))
    else:
        log("[updater] No regular gateway known — snapshot saved, routes not applied.")
    save_snapshot(new_snapshot, path)
    return CheckResult(
        changed=True,
        added=len(added),
        removed=len(removed),
        total_networks=len(new_snapshot.networks),
        total_addresses=new_snapshot.total_addresses,
    )


class Updater(threading.Thread):
    """Daemon thread that runs :func:`check_once` every ``interval_seconds``."""

    def __init__(
        self,
        executor: RouteExecutor,
        gateway_fn: Callable[[], str | None],
        interval_seconds: int = 15 * 60,
        log: LogFn = print,
    ):
        super().__init__(daemon=True, name="offtunnel-updater")
        self.executor = executor
        self.gateway_fn = gateway_fn
        self.interval_seconds = interval_seconds
        self.log = log
        self.stop_event = threading.Event()

    def run(self) -> None:  # noqa: D102
        while not self.stop_event.wait(self.interval_seconds):
            try:
                check_once(self.executor, self.gateway_fn(), log=self.log)
            except Exception as exc:  # noqa: BLE001 - updater must never kill the app
                self.log(f"[updater] unexpected error: {exc}")

    def stop(self) -> None:
        self.stop_event.set()
        # Wake immediately instead of waiting out the interval.
        self.join(timeout=5)
