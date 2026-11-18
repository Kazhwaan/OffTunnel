"""tkinter GUI for OffTunnel (Windows 10/11; also opens in dry-run mode elsewhere).

``tkinter`` is imported lazily inside :func:`launch` so the rest of
the package (CLI, tests) works on machines without a display.

Tabs:
  * **Iran pack** — enable/disable the default Iran ranges, show how
    many merged CIDRs / addresses are applied, last update, and the
    Apply / Refresh buttons.
  * **Manual rules** — add a domain, IP or CIDR (like DirectLane's
    domain list), resolve / refresh it, remove it.
  * **Status & log** — VPN interfaces detected, regular gateway,
    and a scrolling log. On non-Windows, or without admin rights,
    the app says so plainly and runs in dry-run mode instead of
    pretending routes were applied.
"""

from __future__ import annotations

import os
import threading

from .config import APP_NAME, APP_VERSION


def launch() -> None:
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    from .iran_ranges import load_snapshot, shipped_snapshot_path, snapshot_path
    from .routes import RouteExecutor, current_routes, find_regular_gateway
    from .rules import RuleStore, resolve_rule
    from .updater import check_once
    from .vpn import describe_interfaces, parse_route_print_interfaces

    executor = RouteExecutor(dry_run=(os.name != "nt"))
    store = RuleStore()
    root = tk.Tk()
    root.title(f"{APP_NAME} {APP_VERSION} — Windows VPN split tunneling")
    root.geometry("720x520")

    log_box = None  # created below; log() closes over it

    def log(msg: str) -> None:
        if log_box is not None:
            log_box.insert(tk.END, msg + "\n")
            log_box.see(tk.END)
        print(msg)

    # --- status ---------------------------------------------------------
    if os.name == "nt":
        import ctypes

        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    else:
        is_admin = False
    routes = current_routes()
    gateway_route = find_regular_gateway(routes) if routes else None
    gateway = str(gateway_route.gateway) if gateway_route else None

    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    iran_tab = ttk.Frame(notebook)
    rules_tab = ttk.Frame(notebook)
    status_tab = ttk.Frame(notebook)
    notebook.add(iran_tab, text="Iran pack")
    notebook.add(rules_tab, text="Manual rules")
    notebook.add(status_tab, text="Status & log")

    # --- Iran tab -------------------------------------------------------
    snap = load_snapshot(snapshot_path()) or load_snapshot(shipped_snapshot_path())
    iran_info = (
        f"{len(snap.networks):,} merged CIDRs, {snap.total_addresses:,} addresses"
        if snap
        else "No Iran snapshot loaded yet — click Refresh to fetch from RIPE."
    )
    ttk.Label(
        iran_tab,
        text="Default: all Iran IPv4 ranges go via your regular connection,\n"
        "the VPN stays on for everything else.",
        justify=tk.LEFT,
    ).pack(anchor=tk.W, padx=8, pady=8)
    iran_label = ttk.Label(iran_tab, text=iran_info, justify=tk.LEFT)
    iran_label.pack(anchor=tk.W, padx=8, pady=4)

    def do_apply() -> None:
        if not gateway:
            messagebox.showwarning(
                APP_NAME, "No regular gateway found. Connect to the internet (without VPN) first, or check Status."
            )
            return
        if os.name == "nt" and not is_admin:
            messagebox.showwarning(
                APP_NAME, "Run OffTunnel as Administrator to change Windows routes."
            )
            return
        log(f"Applying Iran pack via gateway {gateway} (dry-run={executor.dry_run}) …")
        threading.Thread(target=lambda: check_once(executor, gateway, log=log), daemon=True).start()

    def do_refresh() -> None:
        log("Refreshing Iran ranges from RIPE (hash check first) …")
        threading.Thread(target=lambda: check_once(executor, gateway, log=log), daemon=True).start()

    btn_row = ttk.Frame(iran_tab)
    btn_row.pack(anchor=tk.W, padx=8, pady=8)
    ttk.Button(btn_row, text="Apply Iran pack", command=do_apply).pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_row, text="Refresh ranges", command=do_refresh).pack(side=tk.LEFT, padx=4)

    # --- Manual rules tab ----------------------------------------------
    ttk.Label(
        rules_tab,
        text="Add a domain (its current IPs are resolved by DNS), a single IP, or a CIDR.\n"
        "Use this for Iranian sites hosted abroad (e.g. on Cloudflare) —\nthe Iran pack alone cannot catch those.",
        justify=tk.LEFT,
    ).pack(anchor=tk.W, padx=8, pady=8)
    form = ttk.Frame(rules_tab)
    form.pack(fill=tk.X, padx=8, pady=4)
    kind_var = tk.StringVar(value="domain")
    ttk.OptionMenu(form, kind_var, "domain", "domain", "ip", "cidr").pack(side=tk.LEFT, padx=4)
    value_entry = tk.Entry(form, width=40)
    value_entry.pack(side=tk.LEFT, padx=4)

    rules_list = tk.Listbox(rules_tab, height=10)
    rules_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    def refresh_list() -> None:
        rules_list.delete(0, tk.END)
        for r in store.rules:
            ips = f" → {', '.join(r.resolved_ips[:3])}" + ("…" if len(r.resolved_ips) > 3 else "")
            rules_list.insert(tk.END, f"{r.kind}: {r.value}{ips if r.resolved_ips else ''}")

    def do_add_rule() -> None:
        value = value_entry.get().strip()
        if not value:
            return
        try:
            rule = store.add(kind_var.get(), value)
            resolve_rule(rule)
            store.save()
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return
        log(f"Added manual rule: {rule.kind} {rule.value} → {rule.resolved_ips}")
        refresh_list()

    def do_remove_rule() -> None:
        sel = rules_list.curselection()
        if not sel:
            return
        rule = store.rules[sel[0]]
        store.remove(rule.kind, rule.value)
        log(f"Removed manual rule: {rule.kind} {rule.value}")
        refresh_list()

    ttk.Button(form, text="Add", command=do_add_rule).pack(side=tk.LEFT, padx=4)
    ttk.Button(rules_tab, text="Remove selected", command=do_remove_rule).pack(anchor=tk.W, padx=8, pady=4)
    refresh_list()

    # --- Status tab -----------------------------------------------------
    if os.name == "nt":
        import subprocess

        raw = subprocess.run(["route", "print", "-4"], capture_output=True, text=True).stdout
        vpn_status = describe_interfaces(parse_route_print_interfaces(raw))
    else:
        vpn_status = describe_interfaces([])
    status_text = (
        f"Platform: {'Windows' if os.name == 'nt' else 'non-Windows (dry-run mode)'}\n"
        f"Administrator: {is_admin}\n"
        f"Regular gateway: {gateway or 'not found'}\n"
        f"VPN connected: {vpn_status.vpn_connected} — {', '.join(vpn_status.vpn_interfaces) or 'none detected'}\n"
    )
    ttk.Label(status_tab, text=status_text, justify=tk.LEFT).pack(anchor=tk.W, padx=8, pady=8)
    for note in vpn_status.notes:
        ttk.Label(status_tab, text="• " + note, wraplength=680, justify=tk.LEFT).pack(anchor=tk.W, padx=8)
    log_box = scrolledtext.ScrolledText(status_tab, height=12)
    log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    log(f"{APP_NAME} {APP_VERSION} started. Dry-run={executor.dry_run}.")
    if executor.dry_run:
        log("Dry-run mode: route commands will be shown, not executed (no Windows routing table here).")

    root.mainloop()
