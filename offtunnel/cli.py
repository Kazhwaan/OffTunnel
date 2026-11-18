"""Headless CLI for OffTunnel — same logic as the GUI, no window.

Usage (Windows, run as Administrator to actually change routes)::

    python -m offtunnel status
    python -m offtunnel apply --dry-run
    python -m offtunnel refresh
    python -m offtunnel rules add domain snapp.ir
    python -m offtunnel rules list

On Linux/macOS every apply is a dry run: commands are printed,
nothing is executed, which is how the scaffold is tested here.
"""

from __future__ import annotations

import argparse
import os
import sys

from .config import APP_NAME, APP_VERSION
from .iran_ranges import fetch_country_snapshot, load_snapshot, shipped_snapshot_path, snapshot_path
from .routes import RouteExecutor, current_routes, find_regular_gateway
from .rules import RuleStore, resolve_rule
from .updater import check_once
from .vpn import describe_interfaces


def _gateway() -> str | None:
    route = find_regular_gateway(current_routes())
    return str(route.gateway) if route else None


def cmd_status(_args) -> int:
    print(f"{APP_NAME} {APP_VERSION}")
    print(f"Platform: {'Windows' if os.name == 'nt' else 'non-Windows (dry-run only)'}")
    print(f"Regular gateway: {_gateway() or 'not found'}")
    snap = load_snapshot(snapshot_path()) or load_snapshot(shipped_snapshot_path())
    if snap:
        print(
            f"Iran pack: {len(snap.networks):,} merged CIDRs, "
            f"{snap.total_addresses:,} addresses, source {snap.source_url}"
        )
    else:
        print("Iran pack: no snapshot found (run `refresh` first)")
    store = RuleStore()
    print(f"Manual rules: {len(store.rules)}")
    for rule in store.rules:
        print(f"  {rule.kind}: {rule.value} -> {', '.join(rule.resolved_ips) or '(unresolved)'}")
    return 0


def cmd_apply(args) -> int:
    gateway = _gateway()
    if not gateway and os.name == "nt":
        print("No regular gateway found — cannot apply routes.", file=sys.stderr)
        return 2
    executor = RouteExecutor(dry_run=args.dry_run)
    result = check_once(executor, gateway)
    for line in executor.log:
        print(line)
    print(
        f"changed={result.changed} added={result.added} removed={result.removed} "
        f"total_networks={result.total_networks}"
    )
    return 0


def cmd_refresh(args) -> int:
    snap = fetch_country_snapshot()
    print(
        f"Fetched {snap.country}: {snap.rows} delegated rows, "
        f"{len(snap.networks):,} merged CIDRs, {snap.total_addresses:,} addresses"
    )
    print(f"SHA-256: {snap.source_sha256}")
    return 0


def cmd_rules(args) -> int:
    store = RuleStore()
    if args.action == "list":
        for rule in store.rules:
            print(f"{rule.kind}: {rule.value} -> {', '.join(rule.resolved_ips) or '(unresolved)'}")
        return 0
    if args.action == "add":
        try:
            rule = store.add(args.kind, args.value)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2
        resolve_rule(rule)
        store.save()
        print(f"Added {rule.kind} {rule.value} -> {', '.join(rule.resolved_ips) or '(unresolved)'}")
        return 0
    if args.action == "remove":
        if store.remove(args.kind, args.value):
            print(f"Removed {args.kind} {args.value}")
            return 0
        print(f"No such rule: {args.kind} {args.value}", file=sys.stderr)
        return 2
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="offtunnel", description=f"{APP_NAME} — Windows VPN split tunneling")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show gateway, Iran pack and manual rules")
    apply_p = sub.add_parser("apply", help="Apply the Iran pack (diff only)")
    apply_p.add_argument("--dry-run", action="store_true", help="Print route commands instead of running them")
    sub.add_parser("refresh", help="Fetch the latest Iran ranges from RIPE (no routes changed)")
    rules_p = sub.add_parser("rules", help="Manage manual domain/IP/CIDR rules")
    rules_p.add_argument("action", choices=["list", "add", "remove"])
    rules_p.add_argument("kind", nargs="?", choices=["domain", "ip", "cidr"])
    rules_p.add_argument("value", nargs="?")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "apply":
        return cmd_apply(args)
    if args.command == "refresh":
        return cmd_refresh(args)
    if args.command == "rules":
        return cmd_rules(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
