"""Proof that OffTunnel is actually routing — checked, not claimed.

v0.1.0 said "applied" after running ``route add`` without ever
looking at the route table again, and it never checked whether the
traffic really went direct. v0.1.1 verifies against the live route
table and shows the result in plain language:

  * :func:`verify_applied` — how many of the expected networks are
    actually present in the route table right now.
  * :func:`check_target` — for one IP or domain: resolve it, find
    the route Windows would actually use (longest-prefix match),
    and say plainly whether it goes via the regular gateway
    (direct, off the VPN) or via the VPN.
  * :func:`ping_once` — one ping, returns success + milliseconds.
  * :func:`public_ip` — the public IP the internet sees right now
    (the VPN IP when the VPN is on; used to show that *other*
    traffic still goes through the VPN).

Nothing here trusts a log line. If a route is missing from the
table, the result says so.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import subprocess
import urllib.request
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
from typing import Sequence

from .routes import Route, current_routes

_PING_TIME_RE = re.compile(r"time[=<]\s*(\d+(?:\.\d+)?)\s*ms", re.IGNORECASE)


@dataclass
class TargetCheck:
    target: str
    resolved_ip: str | None
    route_gateway: str | None
    route_interface: str | None
    route_network: str | None
    via: str  # "direct" | "vpn" | "unknown"
    ping_ok: bool
    ping_ms: float | None
    message: str


def longest_prefix_route(routes: Sequence[Route], ip: IPv4Address) -> Route | None:
    """The route Windows would use for ``ip`` (longest prefix wins)."""
    best: Route | None = None
    for route in routes:
        if ip in route.destination:
            if best is None or route.destination.prefixlen > best.destination.prefixlen:
                best = route
    return best


def verify_applied(
    expected: Sequence[IPv4Network],
    routes: Sequence[Route] | None = None,
    gateway: str | None = None,
) -> dict:
    """Count how many expected networks are really in the route table.

    Returns ``{"total", "applied", "missing", "missing_sample",
    "wrong_gateway"}``. ``wrong_gateway`` counts networks present
    but pointing at a gateway other than the regular gateway —
    those are not protecting anything.
    """
    routes = list(routes) if routes is not None else current_routes()
    present: dict[IPv4Network, Route] = {}
    for route in routes:
        present.setdefault(route.destination, route)
    applied = 0
    wrong_gateway: list[str] = []
    missing: list[str] = []
    for net in expected:
        route = present.get(net)
        if route is None:
            missing.append(str(net))
        elif gateway is not None and str(route.gateway) != str(gateway):
            wrong_gateway.append(str(net))
        else:
            applied += 1
    return {
        "total": len(expected),
        "applied": applied,
        "missing": len(missing),
        "missing_sample": missing[:5],
        "wrong_gateway": len(wrong_gateway),
    }


def resolve_target(target: str) -> str | None:
    """Resolve a domain to an IPv4 address; pass an IP through."""
    target = target.strip()
    try:
        return str(ipaddress.IPv4Address(target))
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(target, None, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror:
        return None
    if not infos:
        return None
    return sorted({info[4][0] for info in infos})[0]


def ping_once(host: str, timeout_ms: int = 2000) -> tuple[bool, float | None]:
    """One ping. Returns (ok, milliseconds or None). Never raises."""
    import os

    if os.name == "nt":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), host]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_ms / 1000 + 5)
    except Exception:
        return False, None
    if result.returncode != 0:
        return False, None
    match = _PING_TIME_RE.search(result.stdout or "")
    return True, float(match.group(1)) if match else None


def check_target(
    target: str,
    regular_gateway: str | None,
    routes: Sequence[Route] | None = None,
    vpn_interface_ips: Sequence[IPv4Address] = (),
) -> TargetCheck:
    """Check one IP/domain end to end and explain the result plainly."""
    routes = list(routes) if routes is not None else current_routes()
    ip_str = resolve_target(target)
    if ip_str is None:
        return TargetCheck(
            target=target, resolved_ip=None, route_gateway=None,
            route_interface=None, route_network=None, via="unknown",
            ping_ok=False, ping_ms=None,
            message=f"Could not resolve {target} — check your internet connection.",
        )
    ip = ipaddress.IPv4Address(ip_str)
    route = longest_prefix_route(routes, ip)
    ping_ok, ping_ms = ping_once(ip_str)
    if route is None:
        return TargetCheck(
            target=target, resolved_ip=ip_str, route_gateway=None,
            route_interface=None, route_network=None, via="unknown",
            ping_ok=ping_ok, ping_ms=ping_ms,
            message=f"No route found for {ip_str} — nothing is routing this traffic.",
        )
    via = "unknown"
    if regular_gateway is not None:
        via = "direct" if str(route.gateway) == str(regular_gateway) else "vpn"
    elif route.interface in vpn_interface_ips:
        via = "vpn"
    if via == "direct":
        message = (
            f"{target} ({ip_str}) goes DIRECT via {route.gateway} — "
            "off the VPN. Ping: "
            + (f"{ping_ms:.0f} ms." if ping_ok and ping_ms is not None else "no reply, but the route is direct.")
        )
    elif via == "vpn":
        message = (
            f"{target} ({ip_str}) goes via {route.gateway} — through the VPN, "
            "NOT direct. The protection is not working for this address."
        )
    else:
        message = (
            f"{target} ({ip_str}) uses gateway {route.gateway}. "
            "Could not tell whether that is the regular gateway."
        )
    return TargetCheck(
        target=target, resolved_ip=ip_str, route_gateway=str(route.gateway),
        route_interface=str(route.interface), route_network=str(route.destination),
        via=via, ping_ok=ping_ok, ping_ms=ping_ms, message=message,
    )


def public_ip(timeout: int = 8) -> str | None:
    """The public IP the internet sees right now (VPN IP when on)."""
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "OffTunnel"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", "ignore").strip()
            ipaddress.IPv4Address(text)
            return text
        except Exception:
            continue
    return None
