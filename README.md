# OffTunnel

**Windows VPN split tunneling — local traffic goes *off* the tunnel.**

OffTunnel keeps your VPN on for everything, but routes selected
destinations through your regular (non-VPN) connection. It is
Iranian-first: by default it routes **all Iran IPv4 ranges** direct,
so Iranian sites and services work without turning the VPN off and
on again — and you can also add any domain, IP or CIDR manually.

> **Name:** OffTunnel was chosen by Javen on 2026-11-18. The earlier
> working title "ParsLane" was rejected (too Iran-focused, too close
> to "DirectLane"). Country packs (IR first, RU / CN later) live
> under this one brand — the brand itself is not country-specific.

> **Not a fork.** OffTunnel is written from scratch. It is inspired
> by the *behaviour* of
> [greggubarev/DirectLane](https://github.com/greggubarev/DirectLane)
> (route selected sites direct while the VPN stays on), but it
> contains no DirectLane code, and its logo is an original design
> (`assets/logo.svg`).

---

## What it does

| Feature | How |
|---|---|
| **Iran pack (default)** | All Iran IPv4 ranges, from RIPE delegated stats, merged to CIDRs, routed via the regular gateway |
| **Auto-update** | Checks RIPE frequently; applies **only the diff** when the list changes (see below) |
| **Manual rules** | Add a domain (its current IPs are resolved by DNS), a single IP, or a CIDR — inspect, refresh, remove |
| **Any VPN** | Detects the VPN from Windows interface names; no VPN client API, no assumption about which client you use |
| **Lightweight** | Python stdlib only at runtime, no kernel driver, no background packet interception in v1 |

## How it works

When a VPN connects in full-tunnel mode it normally installs a
default route (`0.0.0.0/0`) through its virtual adapter, so all
traffic goes into the tunnel. A **more specific route always wins**
over the default route in Windows. So for each Iran CIDR (e.g.
`2.144.0.0/14`) OffTunnel adds:

```
route add 2.144.0.0 mask 255.252.0.0 <regular-gateway> metric 5
```

Traffic to that network then leaves through the regular gateway,
while everything else stays in the VPN. Removing a network deletes
exactly that route again.

### Why the Iran list is not "one route per IP"

Iran has about **10.84 million IPv4 addresses**. Verified live on
2026-11-18 against the RIPE file dated 2026-11-17:

- **1,970** delegated IR rows (allocated + assigned)
- **10,840,320** addresses in total
- **1,973** CIDRs after expanding each row to its address range
- **1,748** merged CIDRs after collapsing adjacent networks

OffTunnel ships that merged list as `data/countries/ir.json` so a
fresh install works offline, then re-checks RIPE at runtime.

### Auto-update, without the CPU/RAM cost

RIPE publishes the file **daily**, so checking "every few minutes"
would be wasteful if it re-added thousands of routes each time.
OffTunnel instead:

1. Checks on a timer (default **15 minutes**, configurable).
2. Compares the **SHA-256** of the downloaded file with the last
   applied snapshot.
3. If identical: **does nothing** — no route is touched.
4. If different: parses, diffs against the applied snapshot, and
   adds/deletes **only the changed networks**.

A no-change check costs one download and zero route changes. A
failed fetch never removes existing routes.

## Stack — why Python / tkinter

DirectLane proved this stack works for exactly this job, and it is
the pragmatic choice for v1:

- **Python 3.12+ / tkinter, stdlib only at runtime** — no
  dependencies to install, no .NET runtime, easy for a non-developer
  owner to read and audit. `tkinter` ships with Python on Windows.
- **PyInstaller** builds the Windows `.exe` (portable folder +
  single-file), exactly like DirectLane's release shape.
- **No WinDivert / kernel driver in v1.** Per-application bypass
  (DirectLane's WinDivert mode) needs a signed driver, keeps the app
  open to intercept packets, and is much harder to test safely. v1
  is route-based only, which covers the Iran-pack and domain/IP use
  cases Javen asked for. Per-app rules are a documented v2 option
  (see "Limitations").

If the project later needs a smaller/faster single binary, Go or
C# would be the candidates — but they would trade away the
easy-to-audit Python codebase for a marginal startup gain, so v1
stays with Python.

## Install & build (Windows 10/11)

**Run the app (no build):**

```powershell
py -3 -m pip install -r requirements.txt   # stdlib only — nothing to install
pyw -3 offtunnel.pyw
```

**Build the `.exe`:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

That creates `dist\OffTunnel\OffTunnel.exe` (portable) and a
single-file `dist\OffTunnel.exe`. **Run as Administrator** to change
Windows routes — without admin rights the app warns you instead of
failing silently.

**Tests (also run on Linux, in dry-run mode):**

```powershell
py -3 -m unittest discover -s tests -v
```

**Headless (same logic, no window):**

```powershell
python -m offtunnel status
python -m offtunnel apply --dry-run
python -m offtunnel refresh
python -m offtunnel rules add domain snapp.ir
python -m offtunnel rules list
```

## Usage

1. Connect your VPN as normal.
2. Open OffTunnel **as Administrator**.
3. **Iran pack** tab: click *Apply Iran pack*. Iranian IPs now go
   direct; everything else stays on the VPN.
4. If an Iranian site still goes through the VPN, add it on the
   **Manual rules** tab as a domain — see "Iranian sites hosted
   abroad" below.
5. Leave OffTunnel running (or re-run it) for auto-updates; it
   only touches routes when the RIPE list actually changes.

Settings and data live in `%LOCALAPPDATA%\OffTunnel\`:

- `rules.json` — your manual rules
- `iran_snapshot.json` — the last applied Iran snapshot + its SHA-256

## VPN compatibility

OffTunnel is VPN-agnostic: it reads the Windows route table and
interface names, and works with any VPN that uses a virtual adapter
and does not actively block direct traffic. First targets:
**Windscribe, TorGuard, NordVPN, ExpressVPN** — plus WireGuard,
OpenVPN and Outline, which are handled the same way.

These are **not guarantees**. Each client/version behaves
differently, and every one needs a real Windows + VPN test:

| Client | Caveat to test |
|---|---|
| Windscribe | Usually leaves foreign routes alone; test with its firewall (kill switch) on and off |
| TorGuard | Test OpenVPN and WireGuard modes separately — they install different routes |
| NordVPN / NordLynx | Kill switch and Threat Protection may block direct traffic; test both on and off |
| ExpressVPN | Network Lock (kill switch) may block direct traffic; test on and off |
| WireGuard | A full-tunnel profile (`AllowedIPs 0.0.0.0/0`) installs restrictive firewall rules that can block direct routes — use a profile that permits direct traffic |
| OpenVPN Connect | A server-pushed full tunnel can override routes on reconnect — re-apply after reconnecting |
| Outline | Manages routes itself and may remove OffTunnel routes on reconnect — re-apply after reconnecting |

**General rule:** if a VPN's kill switch blocks all non-tunnel
traffic, OffTunnel's routes can be correct and still not work —
the client's firewall wins. Turn the kill switch off (or use the
client's own exceptions, if it has working ones) and re-test. If
your client already has working website exceptions, use those
instead.

## Limitations — read before trusting it

- **Iranian sites hosted abroad are NOT caught by the Iran pack.**
  Many Iranian services use Cloudflare or foreign hosting, so their
  IPs are not Iranian IPs. Add those sites as **manual domain
  rules** (starter list: `data/catalog_ir.json`). The Iran pack
  covers servers physically in Iran; the domain list covers
  Iranian *services* wherever they are hosted.
- **IPv4 only in v1.** IPv6 routes are not changed. If a site is
  reachable over IPv6, it may still go through the VPN.
- **Routes are per-IP, not per-page.** Sites sharing an IP (shared
  hosting / CDN) go direct together.
- **No per-app rules in v1.** There is no "route only Chrome
  direct" mode yet — routes apply system-wide by destination IP.
  (DirectLane does this with WinDivert; that is a v2 decision, not
  a v1 omission by accident.)
- **DNS may still go through the VPN.** System DNS queries are not
  re-routed by OffTunnel in v1.
- **VPN reconnects can undo routes.** If your VPN replaces the
  route table when it reconnects or switches servers, re-apply the
  Iran pack / refresh the affected domains.
- **Admin rights required** on Windows to add/delete routes.

## Country packs (later)

The brand is not country-specific on purpose. New packs are just
new data files + a country code:

- `data/countries/ir.json` — Iran (v1, default)
- `data/countries/ru.json` — Russia (planned)
- `data/countries/cn.json` — China (planned)

The updater and route logic are already country-parameterised
(`fetch_country_snapshot(country=...)`); only the GUI pack selector
and the per-country source choice need adding.

## Project layout

```
offtunnel.pyw            # launcher (double-click on Windows)
offtunnel/
  config.py              # app name/version — single source of truth
  cidr.py                # RIPE delegated-stats parsing + CIDR merge/diff
  iran_ranges.py         # fetch/hash/snapshot Iran ranges (RIPE + mirrors)
  routes.py              # parse `route print`, find regular gateway, apply diff
  vpn.py                 # VPN interface detection + per-client caveats
  rules.py               # manual domain/IP/CIDR rules (JSON store)
  updater.py             # background timer: hash-check, diff-only apply
  gui.py                 # tkinter GUI (Iran pack / Manual rules / Status)
  cli.py                 # headless CLI: status / apply / refresh / rules
data/
  countries/ir.json      # shipped Iran snapshot (merged CIDRs)
  catalog_ir.json        # starter Iranian domain catalog (manual rules)
assets/logo.svg          # original OffTunnel logo (tunnel + branching lane)
tests/                   # unittest, stdlib only — run on any OS in dry-run
scripts/fetch_iran_ranges.py  # regenerate data/countries/ir.json from RIPE
build.ps1                # PyInstaller build (portable + single-file)
```

## License

MIT — see `LICENSE`. Original code only; no DirectLane source is
included.
