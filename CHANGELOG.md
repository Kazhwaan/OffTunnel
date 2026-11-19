# Changelog

## 0.1.1 — 2026-11-19 (Javen's real Windows test of 0.1.0)

Javen downloaded the v0.1.0 exe, tested it on real Windows, and
found it raw, hard to use, and was not sure it actually worked.
v0.1.1 is a rebuild around a normal user, not a developer:

- **App icon.** Real `.ico` (`assets/logo.ico`, 9 sizes 16–256px,
  drawn from the logo design) embedded in the PyInstaller exe
  (`--icon`), set as the window/taskbar icon, and an embedded PNG
  for the window icon at runtime (`offtunnel/icon.py`). The
  binaries are stored in the repo as base64 text
  (`assets/logo.ico.b64` / `logo.png.b64`) because the GitHub
  contents API only accepts text files;
  `scripts/generate_icons.py` (stdlib only) decodes them, and
  `build.ps1` runs it before PyInstaller.
- **Admin by default.** The exe requests Administrator at launch
  (`--uac-admin`, `requireAdministrator` manifest; `OffTunnel.spec`
  has `uac_admin=True`). The app also detects a non-admin launch
  and relaunches elevated once (UAC prompt); if the user cancels,
  the Home tab says so plainly and offers "Restart as
  Administrator" instead of silently failing to apply routes.
- **System tray.** Minimise to the Windows tray (stdlib ctypes,
  no new dependency), close button minimises to tray by default,
  double-click restores, tray menu: Show / Apply / Exit. Settings
  toggles for minimise-on-close, tray icon, start minimised, and
  whether Exit removes the applied routes. Closing never silently
  kills the applied routes unless the user chooses Exit.
- **Home screen, one glance.** Big status banner — **Protected**
  (green) / **Not protected** (red) / **Partly protected** (amber),
  verified against the live route table, never claimed from a log
  line. One big primary button: **Protect Iran traffic**. VPN
  detected, admin state and regular gateway shown in plain words.
  Iran pack is on by default.
- **Built-in proof (Test button).** Checks a real Iranian site
  (default `snapp.ir`) and a real Iranian IP: shows your public IP
  (the VPN IP — other traffic stays on the VPN), the route each
  target takes, the ping, and a plain **PASS / FAIL** line. No
  terminal needed. CLI: `offtunnel test snapp.ir`, `offtunnel verify`.
- **Iran pack UI fixed.** "Apply Iran pack" now lives in the
  **Rules** tab next to the Add Rule buttons. After applying, the
  user sees the Iran CIDRs in a scrollable, searchable list with
  the count (1,749 ranges, 10,840,832 addresses) and the site
  names in the catalog list.
- **Settings that persist** (`settings.json`): tray behaviour,
  start minimised, remove-routes-on-exit, update interval,
  Iran pack on/off. v0.1.0 had no settings at all.
- **Bug hunt — all fixed:**
  - Manual rules were stored but **never applied**; removing a
    rule never removed its routes. Now one `apply_all` applies
    Iran pack + enabled manual rules, and removal deletes the
    routes. Applied state is recorded in `applied.json`.
  - `route add/delete` failures were ignored and reported as
    success. Return codes are now checked and failures are shown
    in plain language, with what to do next.
  - Gateway detection could pick the VPN's own default route as
    the "regular" gateway. VPN interface IPs are now found via
    `ipconfig` and excluded.
  - First run with no network applied nothing. The shipped
    snapshot is now used as a fallback.
  - Updater re-added the whole Iran pack on every no-change check
    in some paths; unchanged snapshots now touch no routes at all
    (manual rules only).
- **Tests:** 21 → **48**, all pass. New: settings, admin, tray
  state machine, apply/remove state, route-table verification,
  updater offline fallback, `ipconfig` VPN-IP parsing. GUI
  user-journey pass under Xvfb: open Home, visit all tabs, click
  Protect, run Test, screenshots checked (Home / Rules / Settings
  / Status all render; Rules tab fits at 780×680).
- Shipped Iran snapshot refreshed from RIPE 2026-11-19:
  1,972 rows, 1,749 merged CIDRs, 10,840,832 addresses.
- Workflow note: the GitHub Actions workflow still builds with
  the old flags (it cannot be updated via the App token — see
  BUILD_LOG.md). The release exe will only get the icon and the
  admin manifest once the workflow is updated to the new flags;
  the exact change is documented in BUILD_LOG.md.

## 0.1.0 — 2026-11-18 (scaffold, released 2026-11-19)

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
