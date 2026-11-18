# OffTunnel — Build log

## 2026-11-18 — v0.1.0 scaffold (Linux VM, Python 3.12.3)

### Name
- **OffTunnel** — chosen by Javen 2026-11-18. Earlier working title
  "ParsLane" was rejected (too Iran-focused, heard as "Parsley",
  too close to "DirectLane") and is mentioned only in historical
  notes in `README.md` / `CHANGELOG.md` / `offtunnel/config.py`.
  It is **not** the app name anywhere in code, GUI, CLI or build.
- Scaffold moved from `~/workspace/projects/parslane/` to
  `~/workspace/projects/offtunnel/`; no `parslane/` copy remains.
  Package renamed `parslane` → `offtunnel`; app name, GUI title,
  CLI prog, build outputs and `%LOCALAPPDATA%\OffTunnel` all say
  OffTunnel. Single source of truth: `offtunnel/config.py`
  (`APP_NAME = "OffTunnel"`).

### What was built (original code only, no DirectLane source copied)
- `offtunnel/cidr.py` — RIPE delegated-stats parsing, CIDR merge/diff.
- `offtunnel/iran_ranges.py` — fetch RIPE
  `delegated-ripencc-latest` (+ 2 mirrors), SHA-256 snapshot,
  shipped snapshot `data/countries/ir.json`.
- `offtunnel/routes.py` — parse `route print -4`, find the regular
  (non-VPN) gateway, dry-run `RouteExecutor`, diff-only apply.
- `offtunnel/vpn.py` — VPN detection from interface names
  (Windscribe, TorGuard, NordVPN/NordLynx, ExpressVPN, WireGuard,
  OpenVPN, Outline, …) + per-client kill-switch caveats.
- `offtunnel/rules.py` — manual domain / IP / CIDR rules, DNS
  resolution, JSON store in `%LOCALAPPDATA%\OffTunnel\rules.json`.
- `offtunnel/updater.py` — background timer (default 15 min):
  hash-check first, apply only the diff, failed fetch never
  removes routes.
- `offtunnel/gui.py` — tkinter GUI: Iran pack / Manual rules /
  Status & log tabs; admin warning; dry-run badge off-Windows.
- `offtunnel/cli.py` + `offtunnel/__main__.py` + `offtunnel.pyw` —
  headless CLI (`status` / `apply --dry-run` / `refresh` / `rules …`);
  `python -m offtunnel` falls back to CLI when no display exists.
- `data/countries/ir.json` — **real snapshot generated live**
  2026-11-18 from RIPE (file dated 2026-11-17):
  1,970 IR rows, 10,840,320 addresses, 1,748 merged CIDRs,
  SHA-256 `4cda858c807565edd7bc20c8d8a47d3a9c59fdb93a087d1578d73c1c646177e0`.
- `data/catalog_ir.json` — 16 starter Iranian domains (manual rules).
- `assets/logo.svg` — original logo: tunnel arch, one lane straight
  through (VPN, blue), one lane branching off (local, teal).
- `build.ps1` — PyInstaller portable + single-file builds.
- `README.md`, `CHANGELOG.md`, `LICENSE` (MIT), `.gitignore`,
  `requirements.txt` (stdlib only), `requirements-build.txt`
  (PyInstaller ≥ 6.0), `scripts/fetch_iran_ranges.py`.

### Stack decision
Python 3.12+ / tkinter, stdlib-only runtime — the proven
DirectLane path, easiest to audit, no .NET/runtime to install.
No WinDivert / kernel driver in v1: route-based only. Per-app
bypass is a documented v2 option. Justification is in README.md.

### What was tested (on this Linux VM)
- `python3 -m unittest discover -s tests -v` — **21 tests, all pass**
  (CIDR parse/merge/diff, snapshot round-trip, route-print parsing,
  regular-gateway selection skipping the VPN interface, dry-run
  executor + diff-only apply, rules validation/resolution/store,
  VPN detection).
- `python3 scripts/fetch_iran_ranges.py` — live RIPE fetch, wrote
  `data/countries/ir.json` (numbers above).
- `python3 -m offtunnel status` — shows OffTunnel 0.1.0, Iran pack
  1,748 CIDRs / 10,840,320 addresses, 0 manual rules.
- `python3 -m offtunnel apply --dry-run` — reports
  `changed=True added=1748 removed=0`, saves snapshot, applies no
  routes (no gateway / non-Windows).
- `python3 -m offtunnel` (no display) — falls back to CLI status,
  exit 0. `import offtunnel.gui` succeeds (tkinter lazy).
- One test failure was found and fixed during the run:
  `test_parse_route_print` expected 4 routes; the parser correctly
  skips the 2 "On-link" rows (no gateway). Test corrected to 2.

### What still needs a real Windows + VPN test (NOT tested here)
- **Cannot be tested on this Linux VM:** actual `route add/delete`,
  gateway detection on a real Windows route table, PyInstaller
  `.exe` build (`build.ps1`), GUI on Windows, admin-rights flow.
- **Per-VPN tests needed, one by one:** Windscribe, TorGuard
  (OpenVPN *and* WireGuard modes), NordVPN/NordLynx, ExpressVPN —
  with kill switch on *and* off. Verify: Iranian site loads with
  Iranian IP (direct), foreign site still shows VPN IP, routes
  survive a VPN reconnect/server switch, and the updater's diff
  applies cleanly the next day.
- **Iranian-site check:** test the Iran pack *and* the domain
  catalog against real Iranian sites (many are CDN-hosted abroad —
  that is why the domain rules exist).
- **No GitHub repo created, nothing pushed** — per instructions.
  Next step is Javen's call: create the repo under Kazhwaan
  (public/private) and/or run the Windows + VPN test.
