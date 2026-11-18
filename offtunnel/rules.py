"""Manual rules for OffTunnel — domains and IPs, like DirectLane.

A manual rule is one of:
  * ``domain`` — e.g. ``snapp.ir``. OffTunnel resolves its current
    IPv4 addresses with DNS and routes each one (/32) via the regular
    gateway. Re-resolving on refresh picks up address changes.
  * ``ip`` — a single IPv4 address, routed as a /32.
  * ``cidr`` — an IPv4 network, e.g. ``185.120.0.0/22``, routed as-is.

Rules are stored as JSON in the per-user data dir
(``%LOCALAPPDATA%\\OffTunnel\\rules.json`` on Windows). The Iran
country pack is *not* stored here — it lives in its own snapshot
(see ``iran_ranges.py``) so a manual-rule edit can never wipe it.

This is also where Iranian sites hosted *outside* Iran belong: a
site on Cloudflare or a foreign host has no Iranian IP, so the Iran
pack will never catch it. Add its domain here instead.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import time
from dataclasses import asdict, dataclass, field
from ipaddress import IPv4Network
from pathlib import Path
from typing import Callable

from .iran_ranges import default_data_dir

DOMAIN_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})+$")

Resolver = Callable[[str], list[str]]


@dataclass
class Rule:
    kind: str  # "domain" | "ip" | "cidr"
    value: str
    label: str = ""
    enabled: bool = True
    resolved_ips: list[str] = field(default_factory=list)
    updated_at: float = 0.0

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "Rule":
        return cls(
            kind=data["kind"],
            value=data["value"],
            label=data.get("label", ""),
            enabled=bool(data.get("enabled", True)),
            resolved_ips=list(data.get("resolved_ips", [])),
            updated_at=float(data.get("updated_at", 0.0)),
        )


def validate_rule(kind: str, value: str) -> str | None:
    """Return an error message, or ``None`` when the rule is valid."""
    value = value.strip().lower()
    if kind == "domain":
        if not DOMAIN_RE.match(value):
            return f"Not a valid domain: {value!r}"
        return None
    if kind == "ip":
        try:
            ipaddress.IPv4Address(value)
        except ValueError:
            return f"Not a valid IPv4 address: {value!r}"
        return None
    if kind == "cidr":
        try:
            ipaddress.IPv4Network(value, strict=False)
        except ValueError:
            return f"Not a valid IPv4 CIDR: {value!r}"
        return None
    return f"Unknown rule kind: {kind!r}"


def default_resolver(domain: str) -> list[str]:
    """Resolve a domain to its current IPv4 addresses (DNS)."""
    try:
        infos = socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    return sorted({info[4][0] for info in infos})


def resolve_rule(rule: Rule, resolver: Resolver | None = None) -> Rule:
    """(Re-)resolve a rule and record its current IPs. Returns the rule."""
    resolver = resolver or default_resolver
    if rule.kind == "domain":
        rule.resolved_ips = resolver(rule.value)
    elif rule.kind == "ip":
        rule.resolved_ips = [rule.value]
    elif rule.kind == "cidr":
        rule.resolved_ips = []
    rule.updated_at = time.time()
    return rule


def rule_networks(rule: Rule) -> list[IPv4Network]:
    """Expand a rule to the networks OffTunnel should route for it."""
    if not rule.enabled:
        return []
    if rule.kind == "domain" or rule.kind == "ip":
        networks = []
        for ip in rule.resolved_ips:
            networks.append(ipaddress.IPv4Network(f"{ip}/32"))
        return networks
    if rule.kind == "cidr":
        return [ipaddress.IPv4Network(rule.value, strict=False)]
    return []


def rules_path(base_dir: Path | None = None) -> Path:
    return (base_dir or default_data_dir()) / "rules.json"


class RuleStore:
    """Load/save the manual-rule list."""

    def __init__(self, path: Path | None = None):
        self.path = path or rules_path()
        self.rules: list[Rule] = self.load()

    def load(self) -> list[Rule]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [Rule.from_json(item) for item in data]
        except (OSError, ValueError, KeyError, TypeError):
            return []

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps([r.to_json() for r in self.rules], indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    def add(self, kind: str, value: str, label: str = "") -> Rule:
        error = validate_rule(kind, value)
        if error:
            raise ValueError(error)
        value = value.strip().lower()
        for existing in self.rules:
            if existing.kind == kind and existing.value == value:
                raise ValueError(f"Rule already exists: {kind} {value}")
        rule = Rule(kind=kind, value=value, label=label)
        self.rules.append(rule)
        self.save()
        return rule

    def remove(self, kind: str, value: str) -> bool:
        before = len(self.rules)
        self.rules = [
            r for r in self.rules
            if not (r.kind == kind and r.value == value.strip().lower())
        ]
        if len(self.rules) != before:
            self.save()
            return True
        return False

    def all_networks(self) -> list[IPv4Network]:
        networks: list[IPv4Network] = []
        for rule in self.rules:
            networks.extend(rule_networks(rule))
        return networks
