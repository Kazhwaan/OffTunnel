# Changelog

## 0.1.0 — 2026-11-18 (scaffold, unreleased)

- Initial rewritten-from-scratch scaffold as **OffTunnel** (name chosen
  by Javen 2026-11-18; earlier working title "ParsLane" was rejected).
- Route-based Windows split tunneling: Iran IPv4 pack by default.
- Iran ranges from RIPE delegated stats, merged CIDRs, hash-checked
  auto-update that applies only the diff.
- Manual domain / IP / CIDR rules with DNS resolution.
- VPN detection (Windscribe, TorGuard, NordVPN, ExpressVPN, WireGuard,
  OpenVPN, Outline, …) — VPN-agnostic, no client API.
- tkinter GUI + headless CLI, dry-run mode on non-Windows.
- Unit tests (unittest, stdlib only).
- Not yet tested on real Windows with a real VPN — see BUILD_LOG.md.
