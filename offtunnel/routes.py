"""Windows route-table management for OffTunnel.

How split tunneling works here (route-based, v1):
  * When a VPN connects in full-tunnel mode it normally installs a
    default route (0.0.0.0/0) through its virtual adapter, so all
    traffic goes into the tunnel.
  * A *more specific* route always wins over the default route in
    Windows. So for each Iran CIDR (e.g. 2.144.0.0/14) OffTunnel adds
    ``route add <network> mask <netmask> <regular-gateway>`` — traffic
    to that network then leaves through the regular (non-VPN) gateway
    while everything else stays in the VPN.
  * Removing a network deletes exactly that route again.

This module never runs ``route`` for real unless asked: on
non-Windows systems, and whenever ``dry_run=True``, commands are
recorded and logged instead of executed. That is what the unit tests
and this Linux VM use. On Windows, changing routes requires running
as Administrator — the GUI warns about that instead of failing
silently.

Caveat, stated plainly: some VPN clients actively delete or override
foreign routes, or block non-tunnel traffic with a kill switch. In
that case the routes may be added and then removed/blocked by the
VPN itself. See README.md "VPN compatibility" and ``vpn.py``.
"""

from __future__ import annotations

import ipaddress
import os
import re
import subprocess
from dataclasses import dataclass, field
from ipaddress import IPv4Address, IPv4Network
from typing import Sequence

from .cidr import diff_networks

# ``route print -4`` columns, in order.
_ROUTE_RE = re.compile(
    r"^\s*(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+"
    r"(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+)\s*$"
)


@dataclass(frozen=True)
class Route:
    destination: IPv4Network
    gateway: IPv4Address
    interface: IPv4Address
    metric: int


def netmask_to_prefix(netmask: str) -> int:
    return ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen


def parse_route_print(text: str) -> list[Route]:
    """Parse the IPv4 route table section of ``route print -4``."""
    routes: list[Route] = []
    for line in text.splitlines():
        m = _ROUTE_RE.match(line)
        if not m:
            continue
        dest, mask, gateway, iface, metric = m.groups()
        try:
            network = ipaddress.IPv4Network(f"{dest}/{mask}", strict=False)
            routes.append(
                Route(
                    destination=network,
                    gateway=ipaddress.IPv4Address(gateway),
                    interface=ipaddress.IPv4Address(iface),
                    metric=int(metric),
                )
            )
        except ValueError:
            continue
    return routes


def find_regular_gateway(
    routes: Sequence[Route], vpn_interface_ips: Sequence[IPv4Address] = ()
) -> Route | None:
    """Find the default route (0.0.0.0/0) that does NOT go via a VPN interface.

    Prefers the lowest metric among non-VPN default routes. Returns
    ``None`` when every default route points at a VPN interface (or
    there is no default route at all) — in that case OffTunnel cannot
    know the regular gateway and must tell the user, not guess.
    """
    vpn_set = set(vpn_interface_ips)
    candidates = [
        r
        for r in routes
        if r.destination == IPv4Network("0.0.0.0/0") and r.interface not in vpn_set
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda r: r.metric)


@dataclass
class RouteExecutor:
    """Runs (or, in dry-run mode, records) Windows ``route`` commands."""

    dry_run: bool = False
    executed: list[list[str]] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if os.name != "nt":
            # There is no Windows routing table on Linux/macOS.
            self.dry_run = True

    def run(self, cmd: list[str]) -> int:
        """Run one command; in dry-run mode just record + log it."""
        self.executed.append(list(cmd))
        if self.dry_run:
            self.log.append("[dry-run] " + " ".join(cmd))
            return 0
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.stdout.strip():
            self.log.append(result.stdout.strip())
        if result.returncode != 0:
            self.log.append(f"[error] {' '.join(cmd)}: {result.stderr.strip()}")
        return result.returncode

    @staticmethod
    def add_command(network: IPv4Network, gateway: IPv4Address) -> list[str]:
        return [
            "route", "add", str(network.network_address),
            "mask", str(network.netmask), str(gateway),
            "metric", "5",
        ]

    @staticmethod
    def delete_command(network: IPv4Network, gateway: IPv4Address) -> list[str]:
        return [
            "route", "delete", str(network.network_address),
            "mask", str(network.netmask), str(gateway),
        ]

    def add_route(self, network: IPv4Network, gateway: IPv4Address) -> int:
        return self.run(self.add_command(network, gateway))

    def delete_route(self, network: IPv4Network, gateway: IPv4Address) -> int:
        return self.run(self.delete_command(network, gateway))

    def apply_diff(
        self,
        old: Sequence[IPv4Network],
        new: Sequence[IPv4Network],
        gateway: IPv4Address,
    ) -> tuple[list[IPv4Network], list[IPv4Network], list[str]]:
        """Add only new networks, delete only removed ones.

        Returns ``(added, removed, failed)`` — ``failed`` holds one
        plain-language line per ``route`` command that returned a
        non-zero exit code. v0.1.0 ignored those return codes and
        reported success anyway; callers must show failures.
        """
        added, removed = diff_networks(old, new)
        failed: list[str] = []
        done_added: list[IPv4Network] = []
        done_removed: list[IPv4Network] = []
        for net in removed:
            if self.delete_route(net, gateway) == 0:
                done_removed.append(net)
            else:
                failed.append(f"Could not remove route {net} (route delete failed)")
        for net in added:
            if self.add_route(net, gateway) == 0:
                done_added.append(net)
            else:
                failed.append(f"Could not add route {net} (route add failed)")
        return done_added, done_removed, failed


def current_routes() -> list[Route]:
    """Read the live Windows route table. Empty list on non-Windows."""
    if os.name != "nt":
        return []
    result = subprocess.run(
        ["route", "print", "-4"], capture_output=True, text=True, check=False
    )
    return parse_route_print(result.stdout)
