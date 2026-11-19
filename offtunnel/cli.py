"""Headless CLI for OffTunnel — same logic as the GUI, no window.

Usage (Windows, run as Administrator to actually change routes)::

    python -m offtunnel status
    python -m offtunnel apply --dry-run
    python -m offtunnel refresh
    python -m offtunnel verify
    python -m offtunnel test snapp.ir
    python -m offtunnel rules add domain snapp.ir
    python -m offtunnel rules list

On Linux/macOS every apply is a dry run: commands are printed,
nothing is executed, which is how the scaffold is tested here.

Plain language on purpose: the CLI is the fallback for a user who
cannot see the GUI, so errors say what to do next.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import sys

from .admin import ensure_admin_or_warn
from .apply import apply_all, effective_snapshot, remove_all
from .config import APP_NAME, APP_VERSION
from .iran_ranges import fetch_country_snapshot, load_snapshot, shipped_snapshot_path, snapshot_path
from .routes import RouteExecutor, current_routes, find_regular_gateway
from .rules import RuleStore, resolve_rule
from .updater import check_once
from .verify import check_target, public_ip, verify_applied
from .vpn import describe_interfaces, parse_route_print_interfaces


def _gateway_and_vpn() -> tuple[str | None, list[ipaddress.IPv4Address], object]:
    """Regular gateway, VPN interface IPs, VPN status.

    The regular gateway must NOT be the VPN's default route — v0.1.0
    called find_regular_gateway() with no VPN interfaces, so with
    the VPN on it could pick the VPN gateway as "regular" and route
    Iranian traffic straight into the VPN. VPN interface IPs come
    from ``ipconfig`` (see vpn.parse_ipconfig_interfaces).
    """
    routes = current_routes()
    vpn_ips: list[ipaddress.IPv4Address] = []
    vpn_status = describe_interfaces([])
    if os.name == "nt":
        import subprocess

        raw = subprocess.run(["route", "print", "-4"], capture_output=True, text=True).stdout
        names = parse_route_print_interfaces(raw)
        vpn_status = describe_interfaces(names)
        try:
            ipconfig = subprocess.run(["ipconfig"], capture_output=True, text=True).stdout
            from .vpn import parse_ipconfig_interfaces, vpn_interface_ips

            vpn_ips = [
                ipaddress.IPv4Address(ip)
                for ip in vpn_interface_ips(parse_ipconfig_interfaces(ipconfig))
            ]
        except Exception:
            vpn_ips = []
    route = find_regular_gateway(routes, vpn_ips)
    return (str(route.gateway) if route else None, vpn_ips, vpn_status)


def _gateway() -> str | None:
    gateway, _vpn_ips, _status = _gateway_and_vpn()
    return gateway


def cmd_status(_args) -> int:
    print(f"{APP_NAME} {APP_VERSION}")
    print(f"Platform: {'Windows' if os.name == 'nt' else 'non-Windows (dry-run only)'}")
    admin = ensure_admin_or_warn()
    if admin == "not-admin":
        print("Administrator: NO — run as Administrator, or Apply will not work.")
    elif admin == "admin":
        print("Administrator: yes")
    gateway, _vpn_ips, vpn_status = _gateway_and_vpn()
    print(f"Regular gateway: {gateway or 'not found'}")
    print(f"VPN connected: {vpn_status.vpn_connected} — {', '.join(vpn_status.vpn_interfaces) or 'none detected'}")
    snap = load_snapshot(snapshot_path()) or load_snapshot(shipped_snapshot_path())
    if snap:
        print(
            f"Iran pack: {len(snap.networks):,} merged CIDRs, "
            f"{snap.total_addresses:,} addresses, source {snap.source_url}"
        )
        result = verify_applied(snap.networks, gateway=gateway)
        state = "PROTECTED" if result["applied"] == result["total"] and result["total"] else "NOT protected"
        print(
            f"Status: {state} — {result['applied']:,} of {result['total']:,} Iran routes "
            f"are in the route table ({result['missing']:,} missing)"
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
        print(
            "No regular gateway found — cannot apply routes.\n"
            "Connect to the internet first (VPN off, or with a second connection), then try again.",
            file=sys.stderr,
        )
        return 2
    if ensure_admin_or_warn() == "not-admin":
        print(
            "Not running as Administrator — routes cannot be changed.\n"
            "Right-click OffTunnel.exe and choose 'Run as administrator', then try again.",
            file=sys.stderr,
        )
        return 2
    executor = RouteExecutor(dry_run=args.dry_run)
    result = check_once(executor, gateway)
    for line in executor.log:
        print(line)
    print(
        f"changed={result.changed} added={result.added} removed={result.removed} "
        f"total_networks={result.total_networks}"
    )
    if result.failed:
        print("Some routes failed:")
        for line in result.failed[:10]:
            print(f"  - {line}")
        return 1
    return 0


def cmd_refresh(_args) -> int:
    snap = fetch_country_snapshot()
    print(
        f"Fetched {snap.country}: {snap.rows} delegated rows, "
        f"{len(snap.networks):,} merged CIDRs, {snap.total_addresses:,} addresses"
    )
    print(f"SHA-256: {snap.source_sha256}")
    return 0


def cmd_verify(_args) -> int:
    """Check the route table and report Protected / Not protected."""
    gateway = _gateway()
    snap = effective_snapshot()
    if snap is None:
        print("No Iran snapshot found — run `refresh` first.", file=sys.stderr)
        return 2
    result = verify_applied(snap.networks, gateway=gateway)
    protected = result["applied"] == result["total"] and result["total"] > 0
    print("PROTECTED" if protected else "NOT protected")
    print(
        f"{result['applied']:,} of {result['total']:,} Iran routes in the route table, "
        f"{result['missing']:,} missing, {result['wrong_gateway']:,} pointing at the wrong gateway."
    )
    if result["missing_sample"]:
        print("Missing (first few): " + ", ".join(result["missing_sample"]))
    return 0 if protected else 1


def cmd_test(args) -> int:
    """Test one Iranian IP/domain: show its route, ping and a PASS/FAIL."""
    gateway = _gateway()
    if not gateway:
        print("No regular gateway found — cannot tell direct from VPN.", file=sys.stderr)
        return 2
    target = args.target
    print(f"Your public IP right now: {public_ip() or 'unknown (no internet?)'}")
    print("(That is your VPN IP when the VPN is on — other sites still use the VPN.)")
    check = check_target(target, gateway)
    print(check.message)
    if check.via == "direct":
        print("PASS — this traffic goes direct, off the VPN.")
        return 0
    print("FAIL — this traffic is not going direct.")
    return 1


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
        print("Note: run `apply` to route this rule (or Apply in the app).")
        return 0
    if args.action == "remove":
        gateway = _gateway()
        rule = next((r for r in store.rules if r.kind == args.kind and r.value == args.value), None)
        if rule is None:
            print(f"No such rule: {args.kind} {args.value}", file=sys.stderr)
            return 2
        # Remove its routes first, then the rule itself.
        if gateway and ensure_admin_or_warn() != "not-admin":
            from .apply import load_applied

            state = load_applied()
            nets = [n for n in state.rules if n in _rule_networks(rule)]
            if nets:
                executor = RouteExecutor(dry_run=False)
                for net in nets:
                    executor.delete_route(net, ipaddress.IPv4Address(gateway))
                print(f"Removed {len(nets)} route(s) for this rule.")
        store.remove(args.kind, args.value)
        print(f"Removed {args.kind} {args.value}")
        return 0
    return 2


def _rule_networks(rule):
    from .rules import rule_networks

    return rule_networks(rule)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="offtunnel", description=f"{APP_NAME} — Windows VPN split tunneling")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show gateway, VPN, Iran pack and whether you are protected")
    apply_p = sub.add_parser("apply", help="Apply the Iran pack and manual rules (diff only)")
    apply_p.add_argument("--dry-run", action="store_true", help="Print route commands instead of running them")
    sub.add_parser("refresh", help="Fetch the latest Iran ranges from RIPE (no routes changed)")
    sub.add_parser("verify", help="Check the route table: Protected or Not protected")
    test_p = sub.add_parser("test", help="Test one Iranian IP/domain and show its route + ping")
    test_p.add_argument("target", nargs="?", default="snapp.ir", help="IP or domain to test (default: snapp.ir)")
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
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "test":
        return cmd_test(args)
    if args.command == "rules":
        return cmd_rules(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
