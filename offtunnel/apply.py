"""Applying and removing routes — the part v0.1.0 got wrong.

Bugs fixed here (found by testing v0.1.0 on this VM):

  * Manual rules were stored but **never applied**: the updater
    only ever applied the Iran pack. Adding a domain did nothing
    to the route table.
  * Removing a manual rule did not remove its routes either.
  * ``check_once`` reported success even when ``route add`` failed
    — return codes were ignored.
  * On first run with no network, the updater fetched RIPE, failed,
    and never applied the shipped snapshot, so a fresh offline
    install did nothing at all.

``apply_all`` is now the single place that applies everything:
the Iran pack (diff-only, from the snapshot) plus every enabled
manual rule. It remembers what it applied in ``applied.json`` so
removal deletes exactly those networks, and it reports failures
instead of claiming success.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path

from .cidr import diff_networks, strings_to_networks
from .iran_ranges import RangeSnapshot, default_data_dir, load_snapshot, shipped_snapshot_path
from .routes import RouteExecutor
from .rules import RuleStore

APPLIED_FILENAME = "applied.json"


@dataclass
class ApplyReport:
    added: list[IPv4Network] = field(default_factory=list)
    removed: list[IPv4Network] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    total_expected: int = 0

    @property
    def ok(self) -> bool:
        return not self.failed


@dataclass
class AppliedState:
    """Networks OffTunnel previously applied (Iran + manual rules)."""

    iran: list[IPv4Network] = field(default_factory=list)
    rules: list[IPv4Network] = field(default_factory=list)

    @property
    def all_networks(self) -> list[IPv4Network]:
        return sorted(set(self.iran) | set(self.rules))


def applied_path(base_dir: Path | None = None) -> Path:
    return (base_dir or default_data_dir()) / APPLIED_FILENAME


def load_applied(path: Path | None = None) -> AppliedState:
    path = path or applied_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppliedState(
            iran=strings_to_networks(data.get("iran", [])),
            rules=strings_to_networks(data.get("rules", [])),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return AppliedState()


def save_applied(state: AppliedState, path: Path | None = None) -> None:
    path = path or applied_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(
            {
                "iran": [str(n) for n in state.iran],
                "rules": [str(n) for n in state.rules],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def desired_iran_networks(snapshot: RangeSnapshot | None) -> list[IPv4Network]:
    return list(snapshot.networks) if snapshot else []


def apply_all(
    executor: RouteExecutor,
    gateway: IPv4Address,
    snapshot: RangeSnapshot | None,
    store: RuleStore,
    state_path: Path | None = None,
) -> ApplyReport:
    """Apply Iran pack + enabled manual rules (diff only). Returns a report.

    Failures are collected in ``report.failed`` (one line per failed
    ``route`` command) — the caller must show them, not hide them.

    Pass ``snapshot=None`` to leave the Iran pack untouched and
    only apply manual rules (used by the updater when the snapshot
    is unchanged: re-adding 1,748 routes every 15 minutes would
    be pointless, and Windows rejects duplicate ``route add``).
    """
    state = load_applied(state_path)
    want_iran = desired_iran_networks(snapshot) if snapshot is not None else list(state.iran)
    want_rules = store.all_networks()
    report = ApplyReport(total_expected=len(set(want_iran) | set(want_rules)))

    for label, old, new in (("iran", state.iran, want_iran), ("rules", state.rules, want_rules)):
        added, removed = diff_networks(old, new)
        for net in removed:
            rc = executor.delete_route(net, gateway)
            if rc == 0:
                report.removed.append(net)
            else:
                report.failed.append(f"Could not remove {label} route {net} (route delete failed)")
        for net in added:
            rc = executor.add_route(net, gateway)
            if rc == 0:
                report.added.append(net)
            else:
                report.failed.append(f"Could not add {label} route {net} (route add failed)")
    # Only record networks that are actually in place. In dry-run
    # mode every command "succeeds", so the state matches the report.
    # State = what we wanted minus what failed.
    failed_nets = set()
    for line in report.failed:
        # Failed lines look like: "Could not add iran route 2.144.0.0/14 (route add failed)"
        parts = line.split()
        try:
            failed_nets.add(IPv4Network(parts[5], strict=False))
        except Exception:
            pass
    new_state = AppliedState(
        iran=sorted(set(want_iran) - failed_nets),
        rules=sorted(set(want_rules) - failed_nets),
    )
    save_applied(new_state, state_path)
    return report


def remove_all(
    executor: RouteExecutor,
    gateway: IPv4Address,
    state_path: Path | None = None,
) -> ApplyReport:
    """Remove every route OffTunnel applied. Returns a report."""
    state = load_applied(state_path)
    report = ApplyReport(total_expected=0)
    for net in state.all_networks:
        rc = executor.delete_route(net, gateway)
        if rc == 0:
            report.removed.append(net)
        else:
            report.failed.append(f"Could not remove route {net} (route delete failed)")
    if not report.failed:
        save_applied(AppliedState(), state_path)
    return report


def effective_snapshot() -> RangeSnapshot | None:
    """Best Iran snapshot available: saved one, else the shipped one.

    A fresh install with no network must still work — v0.1.0
    returned nothing in that case and applied zero routes.
    """
    from .iran_ranges import snapshot_path

    return load_snapshot(snapshot_path()) or load_snapshot(shipped_snapshot_path())
