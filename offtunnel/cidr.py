"""CIDR helpers for OffTunnel.

Parses RIR delegated-statistics files (the format published by RIPE
NCC, APNIC, ARIN, etc.) and turns a country's allocated address
ranges into a small, merged list of CIDR networks.

Why merging matters: Iran has ~10.8 million IPv4 addresses in ~1,970
delegated rows. Adding one Windows route per row is already heavy;
adding one per address would be impossible. ``collapse_addresses``
merges adjacent networks (for example two neighbouring /24s become
one /23), which in the live 2026-11-17 RIPE file shrinks 1,973
summarised CIDRs to 1,748 merged CIDRs for Iran.
"""

from __future__ import annotations

import ipaddress
from ipaddress import IPv4Network
from typing import Iterable, Sequence


def parse_delegated_line(line: str, country: str = "IR") -> list[IPv4Network]:
    """Parse one delegated-stats line for ``country`` / IPv4.

    Format (``|``-separated)::

        registry|cc|ipv4|start|count|date|status|...

    ``count`` is a number of addresses, not a prefix length, so a
    single row may span several CIDRs (e.g. 262144 addresses starting
    at 2.144.0.0 is 2.144.0.0/14). Returns ``[]`` for lines that are
    not a matching IPv4 allocation/assignment.
    """
    parts = line.strip().split("|")
    if len(parts) < 7:
        return []
    registry, cc, kind, start, count, _date, status = parts[:7]
    if cc != country or kind != "ipv4":
        return []
    if status not in ("allocated", "assigned"):
        return []
    try:
        first = ipaddress.IPv4Address(start)
        n = int(count)
    except (ValueError, ipaddress.AddressValueError):
        return []
    if n <= 0:
        return []
    last = first + n - 1
    return list(ipaddress.summarize_address_range(first, last))


def parse_delegated_text(text: str, country: str = "IR") -> list[IPv4Network]:
    """Parse a whole delegated-stats file and return merged CIDRs."""
    networks: list[IPv4Network] = []
    for line in text.splitlines():
        networks.extend(parse_delegated_line(line, country))
    return merge_networks(networks)


def merge_networks(networks: Iterable[IPv4Network]) -> list[IPv4Network]:
    """Collapse adjacent/overlapping networks, sorted, deduplicated."""
    return sorted(ipaddress.collapse_addresses(networks))


def diff_networks(
    old: Sequence[IPv4Network], new: Sequence[IPv4Network]
) -> tuple[list[IPv4Network], list[IPv4Network]]:
    """Return ``(added, removed)`` going from ``old`` to ``new``.

    This is the core of the low-overhead updater: OffTunnel only ever
    adds the networks in ``added`` and deletes the ones in ``removed``.
    When the RIPE file has not changed, both lists are empty and no
    Windows route is touched at all.
    """
    old_set, new_set = set(old), set(new)
    return sorted(new_set - old_set), sorted(old_set - new_set)


def total_addresses(networks: Iterable[IPv4Network]) -> int:
    return sum(net.num_addresses for net in networks)


def networks_to_strings(networks: Iterable[IPv4Network]) -> list[str]:
    return [str(net) for net in networks]


def strings_to_networks(values: Iterable[str]) -> list[IPv4Network]:
    networks = []
    for value in values:
        networks.append(ipaddress.IPv4Network(value, strict=False))
    return merge_networks(networks)
