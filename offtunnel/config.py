"""Brand / app configuration for OffTunnel.

Single source of truth for the app name. The name was chosen by
Javen on 2026-11-18: **OffTunnel** — local traffic goes *off* the VPN
tunnel. (Earlier working title "ParsLane" was rejected: too
Iran-focused and too close to "DirectLane". Do not reintroduce it.)

Country packs live under this brand: IR first, then RU / CN later,
as ``data/countries/<cc>.json`` — the brand itself is not
country-specific, which is the point.
"""

from __future__ import annotations

APP_NAME = "OffTunnel"
APP_SLUG = "offtunnel"
APP_VERSION = "0.1.1"
# Storage folder name under %LOCALAPPDATA% / ~/.config — keep in sync
# with APP_NAME so users can find their rules/snapshot by app name.
DATA_DIR_NAME = "OffTunnel"
USER_AGENT = f"{APP_NAME}/{APP_VERSION}"
