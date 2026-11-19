"""VPN detection for OffTunnel.

OffTunnel is deliberately VPN-agnostic: it does not talk to any VPN
client's API and does not assume a particular client is installed.
Instead it looks at Windows itself — adapter/interface names in the
route table — and classifies an interface as a VPN interface when its
name matches a known VPN client or a generic tunnel technology
(WireGuard / OpenVPN / TAP / Wintun).

Target clients first (Javen's request): Windscribe, TorGuard,
NordVPN, ExpressVPN. Anything else that looks like a tunnel is
treated the same way, so an unlisted VPN still works as long as it
uses a virtual adapter and does not actively block direct routes.

Known limits (see README.md for the full list):
  * A VPN kill switch can block traffic that bypasses the tunnel,
    even when the route is correct. OffTunnel can detect that the
    route exists; it cannot override the client's firewall.
  * WireGuard full-tunnel profiles (AllowedIPs 0.0.0.0/0) install
    restrictive firewall rules that can block direct routes.
  * Some clients (e.g. Outline) manage the route table themselves
    and may delete routes OffTunnel adds when they reconnect.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Lower-case substrings that identify a VPN / tunnel interface.
# Kept as substrings (not exact names) because Windows shows names
# like "NordLynx", "Windscribe VPN", "TorGuard WireGuard", etc.
VPN_KEYWORDS = (
    "windscribe",
    "torguard",
    "nordvpn",
    "nordlynx",
    "expressvpn",
    "express vpn",
    "wireguard",
    "openvpn",
    "outline",
    "tap-windows",
    "tap-windows6",
    "wintun",
    "protonvpn",
    "mullvad",
    "surfshark",
    "cyberghost",
    "pia",
    "private internet access",
    "vpn",
    "tunnel",
)

# Per-client notes shown in the GUI/CLI. These are *caveats*, not
# compatibility promises — each client/version behaves differently
# and must be tested on a real Windows machine with that VPN on.
VPN_NOTES = {
    "windscribe": "Windscribe: usually leaves foreign routes alone; test with its firewall (kill switch) on and off.",
    "torguard": "TorGuard: test OpenVPN and WireGuard modes separately — they install different routes.",
    "nordvpn": "NordVPN / NordLynx: kill switch and Threat Protection may block direct traffic; test both on and off.",
    "expressvpn": "ExpressVPN: Network Lock (kill switch) may block direct traffic; test with it on and off.",
    "wireguard": "WireGuard: a full-tunnel profile (AllowedIPs 0.0.0.0/0) can block direct routes; use a profile that permits direct traffic.",
    "openvpn": "OpenVPN: a server-pushed full tunnel can override routes on reconnect; re-apply after reconnecting.",
    "outline": "Outline: manages routes itself and may remove OffTunnel routes on reconnect; re-apply after reconnecting.",
}


@dataclass
class VpnStatus:
    vpn_connected: bool
    vpn_interfaces: list[str]
    notes: list[str]


def is_vpn_interface(name: str) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in VPN_KEYWORDS)


def detect_vpn_interfaces(interface_names: list[str]) -> list[str]:
    return [name for name in interface_names if is_vpn_interface(name)]


def vpn_note_for(name: str) -> str | None:
    lowered = name.lower()
    for keyword, note in VPN_NOTES.items():
        if keyword in lowered:
            return note
    return None


def describe_interfaces(interface_names: list[str]) -> VpnStatus:
    vpn = detect_vpn_interfaces(interface_names)
    notes = []
    for name in vpn:
        note = vpn_note_for(name)
        if note and note not in notes:
            notes.append(note)
    if vpn and not notes:
        notes.append(
            "A VPN interface was detected, but it is not in the known-client list — "
            "routes should still work if the client does not block direct traffic."
        )
    return VpnStatus(vpn_connected=bool(vpn), vpn_interfaces=vpn, notes=notes)


def parse_route_print_interfaces(text: str) -> list[str]:
    """Extract interface names from the 'Interface List' of ``route print``.

    Lines look like: ``  7...........................NordLynx``
    """
    names: list[str] = []
    in_list = False
    for line in text.splitlines():
        if "Interface List" in line:
            in_list = True
            continue
        if in_list:
            if line.strip().startswith("===") or "IPv4 Route Table" in line:
                break
            m = re.match(r"^\s*\d+\.+\s*(.+?)\s*$", line)
            if m and m.group(1):
                names.append(m.group(1))
    return names


def parse_ipconfig_interfaces(text: str) -> list[tuple[str, str]]:
    """Map adapter names to IPv4 addresses from ``ipconfig`` output.

    ``route print`` alone cannot tell which interface IP belongs to
    a VPN adapter (it lists names and IPs in different sections).
    ``ipconfig`` lists them together: an adapter heading followed
    by its "IPv4 Address" line. This is how OffTunnel finds the
    VPN interface IPs, so the regular gateway is never the VPN's
    own default route.
    """
    import ipaddress

    pairs: list[tuple[str, str]] = []
    current_name: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        # Adapter heading, e.g. "NordLynx adapter NordLynx:" or
        # "Wireless LAN adapter Wi-Fi:" — take the text after "adapter".
        if "adapter" in stripped.lower() and stripped.endswith(":"):
            after = stripped.split("adapter", 1)[1].strip().rstrip(":").strip()
            current_name = after or None
            continue
        if current_name:
            m = re.search(r"IPv4 Address[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", stripped)
            if m:
                try:
                    ipaddress.IPv4Address(m.group(1))
                except ValueError:
                    continue
                pairs.append((current_name, m.group(1)))
                current_name = None
    return pairs


def vpn_interface_ips(pairs: list[tuple[str, str]]) -> list[str]:
    """Interface IPs whose adapter name is a known VPN/tunnel name."""
    return [ip for name, ip in pairs if is_vpn_interface(name)]
