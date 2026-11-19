"""User settings for OffTunnel — plain-language options, saved to disk.

v0.1.0 had no settings at all: the updater interval was hard-coded,
and there was no way to choose tray behaviour. v0.1.1 stores settings
in ``settings.json`` next to ``rules.json`` (``%LOCALAPPDATA%\\OffTunnel``
on Windows). A corrupt or missing file falls back to defaults instead
of crashing — a normal user should never see a settings error.

Defaults are chosen for a first-time user:
  * Iran pack is on by default (the whole point of the app).
  * Closing the window minimises to the tray instead of quitting,
    so the applied routes and the auto-updater keep working.
  * Exiting from the tray menu removes the applied routes, so
    "Exit" really means "stop protecting".
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .iran_ranges import default_data_dir

DEFAULTS: dict[str, object] = {
    # Iran pack is applied by default on first run (see apply.py).
    "iran_pack_enabled": True,
    # Close button minimises to the tray instead of quitting.
    "minimize_on_close": True,
    # Show the tray icon at all. Turning this off also turns off
    # minimise-on-close (there is nowhere to minimise to).
    "tray_enabled": True,
    # Start minimised to the tray (window hidden) on launch.
    "start_minimized": False,
    # Remove applied routes when the user chooses Exit from the tray.
    "remove_routes_on_exit": True,
    # Minutes between Iran-range update checks (RIPE publishes daily).
    "check_interval_minutes": 15,
}


def settings_path(base_dir: Path | None = None) -> Path:
    return (base_dir or default_data_dir()) / "settings.json"


class Settings:
    """Load/save settings, always returning a complete dict."""

    def __init__(self, path: Path | None = None):
        self.path = path or settings_path()
        self.values: dict[str, object] = dict(DEFAULTS)
        self.load()

    def load(self) -> dict[str, object]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for key, default in DEFAULTS.items():
                    if key in data and isinstance(data[key], type(default)):
                        self.values[key] = data[key]
        except (OSError, ValueError, TypeError):
            pass  # missing/corrupt file -> defaults, never crash
        return self.values

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.values, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def get(self, key: str) -> object:
        return self.values.get(key, DEFAULTS.get(key))

    def set(self, key: str, value: object) -> None:
        if key in DEFAULTS and isinstance(value, type(DEFAULTS[key])):
            self.values[key] = value
            self.save()
