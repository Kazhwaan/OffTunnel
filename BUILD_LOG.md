# OffTunnel — Build log

## 2026-11-19 — v0.1.1 (Javen's real Windows test of v0.1.0)

Javen downloaded the v0.1.0 exe and tested it on real Windows:
no icon, no admin by default, no tray, bad Iran-pack UI, and no
way to tell whether it actually worked. v0.1.1 fixes all of it
and rebuilds the UI around a normal user (see CHANGELOG.md for
the full list). Work done on this Linux VM; Windows-only parts
are marked below.

### New / changed code
- `offtunnel/icon.py` + `assets/logo.ico` (9 sizes 16–256px) +
  `assets/logo.png` — icon generated with Pillow from the logo
  design (dark tunnel arch, blue VPN lane straight through, teal
  lane branching off). Embedded PNG (128px) for the window icon.
- `offtunnel/admin.py` — `is_admin()` (ctypes `IsUserAnAdmin`),
  `relaunch_elevated()` (ShellExecuteW `runas`, one attempt only,
  guarded by `OFFTUNNEL_ELEVATE_ATTEMPT` env so it cannot loop).
  `offtunnel/__main__.py` tries it once at startup on Windows.
- `offtunnel/tray.py` — Win32 tray via ctypes
  (`Shell_NotifyIconW`, hidden message window, menu Show / Apply /
  Exit); no-op stub off-Windows. `TrayController` is the pure,
  tested decision logic (close → minimise vs exit).
- `offtunnel/settings.py` — `settings.json` in the data dir,
  defaults: Iran pack on, minimise-on-close on, tray on,
  check interval 15 min. Corrupt file → defaults, never a crash.
- `offtunnel/apply.py` — single `apply_all()` (Iran pack +
  enabled manual rules, diff only, return codes checked,
  failures reported in plain language), `remove_all()`,
  `applied.json` state. `snapshot=None` means "rules only".
- `offtunnel/verify.py` — `verify_applied()` (route-table count),
  `longest_prefix_route()`, `check_target()` (resolve + route +
  ping + plain message), `public_ip()`.
- `offtunnel/gui.py` — rewritten: Home (status banner, VPN,
  admin, gateway, big **Protect Iran traffic**, Test box) /
  Rules (Apply Iran pack next to Add Rule, searchable CIDR list
  with count, catalog sites, manual rules + remove) / Settings /
  Status & log. Window 780×680 so the Rules tab fits.
- `offtunnel/routes.py` — `apply_diff()` now returns
  `(added, removed, failed)` instead of silently ignoring
  failures.
- `offtunnel/vpn.py` — `parse_ipconfig_interfaces()` +
  `vpn_interface_ips()`: VPN interface IPs come from `ipconfig`,
  so the regular gateway is never the VPN's own default route.
- `offtunnel/updater.py` — offline first run falls back to the
  shipped snapshot; unchanged snapshot touches no routes
  (rules only); manual rules are now applied by the updater.
- `offtunnel/cli.py` — `status` (now verifies + shows
  Protected/Not protected), `verify`, `test <target>`
  (public IP + route + ping + PASS/FAIL), `rules remove` now
  deletes the rule's routes first.
- `build.ps1` / `OffTunnel.spec` (new) — PyInstaller with
  `--icon assets/logo.ico --uac-admin --add-data "assets;assets"`.
  `.gitignore` no longer ignores `*.spec` (the spec is hand-written
  and committed on purpose).
- `data/countries/ir.json` — refreshed from RIPE 2026-11-19:
  1,972 rows, 1,749 merged CIDRs, 10,840,832 addresses.

### What was tested (on this Linux VM)
- `python3 -m unittest discover -s tests -v` — **48 tests, all
  pass** (was 21). Bugs found *by* the tests and fixed during the
  run: `RangeSnapshot` has no `total_addresses` kwarg (test
  helpers), `parse_route_print_interfaces` lives in `vpn.py` not
  `routes.py` (import bug — would have crashed the GUI and CLI),
  tray `_POINT` needs `ctypes` at module import, failed-network
  parsing read the wrong token, updater no-change path re-added
  the whole Iran pack.
- CLI smoke: `status` (NOT protected, 0/1,749), `verify` (rc 1),
  `apply --dry-run` (live RIPE fetch, +2 −1 networks, snapshot
  saved, no routes — no gateway on Linux), `rules add/list/remove`,
  `test 2.144.5.6` (rc 2, plain "no regular gateway" message).
- GUI user-journey pass under Xvfb (real tkinter window,
  screenshots checked): Home renders (red Not protected banner,
  big Protect button, Test box), Rules tab (1,749 CIDR list +
  count, catalog sites, Add/Remove), Settings, Status & log;
  clicking Protect shows the plain "no regular gateway" warning;
  Test now runs and reports honestly. One layout bug found and
  fixed: at 760×600 the "Remove selected rule" button was below
  the fold — window is now 780×680 with shorter lists.

### What still needs a real Windows + VPN test (NOT tested here)
- **Cannot be tested on this Linux VM:** the actual Win32 tray
  icon/menu (ctypes code is guarded and the state machine is
  tested, but the real `Shell_NotifyIconW` path only runs on
  Windows), the UAC prompt / `--uac-admin` manifest in the built
  exe, the icon showing in Explorer/taskbar, `route add/delete`
  on a real route table, PyInstaller build itself.
- **First Windows run checklist for Javen:** double-click the
  exe → UAC prompt appears → Home shows VPN detected + green
  **Protected** after one click → **Test now** shows PASS for
  snapp.ir and the sample Iranian IP → close the window → icon
  stays in the tray → double-click tray icon restores the window
  → Exit from the tray removes the routes.
- **Workflow (GitHub Actions) — MUST be updated by hand.**
  The workflow file `.github/workflows/build-windows.yml` cannot
  be written via the Muse GitHub App token (workflows permission
  is denied — same as in v0.1.0), and this v0.1.1 push does NOT
  change it. Until it is updated, the release exe will be built
  with the OLD flags: **no icon, no admin manifest**. Exact change
  needed (edit on github.com, or via a personal access token):
  in both PyInstaller commands add
  `--icon assets/logo.ico --uac-admin --add-data "assets;assets"`,
  and change the release tag default from `v0.1.0` to `v0.1.1`.
  The workflow must also run `py -3 scripts/generate_icons.py`
  before PyInstaller: the `.ico` is stored in the repo as base64
  text (`assets/logo.ico.b64`) because the contents API cannot
  push binary files, and the script decodes it (stdlib only).
  `OffTunnel.spec` in the repo already contains these settings
  for local builds; the workflow could also switch to
  `pyinstaller OffTunnel.spec`.

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
