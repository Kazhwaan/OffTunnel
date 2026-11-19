"""tkinter GUI for OffTunnel (Windows 10/11; also opens in dry-run mode elsewhere).

v0.1.1 was redesigned for a normal user, not a developer — Javen
tested v0.1.0 and could not tell whether it worked. The Home tab is
the whole app in one glance:

  * A big status banner: **Protected** (green) or **Not protected**
    (red), verified against the live route table — never claimed
    from a log line.
  * Which VPN was detected, and whether the app is running as
    Administrator (with a one-click restart button when it is not).
  * One big primary button: **Protect Iran traffic**.
  * A **Test** button that checks a real Iranian site/IP, shows
    the route it takes, the ping, and a plain PASS / FAIL.

Other tabs hold the details: Rules (Iran pack + manual rules,
with the Iran CIDRs and site names visible in lists), Settings
(tray behaviour, update interval), Status & log (route table,
VPN notes, log).

``tkinter`` is imported lazily inside :func:`launch` so the rest of
the package (CLI, tests) works on machines without a display.
"""

from __future__ import annotations

import ipaddress
import json
import os
import threading
from pathlib import Path

from .admin import ensure_admin_or_warn, is_admin, relaunch_elevated
from .config import APP_NAME, APP_VERSION


def _resource_path(relative: str) -> Path:
    """File bundled with the app (PyInstaller) or in the source tree."""
    import sys

    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def _load_catalog() -> list[dict]:
    try:
        data = json.loads(_resource_path("data/catalog_ir.json").read_text(encoding="utf-8"))
        return list(data.get("domains", []))
    except Exception:
        return []


def launch(on_ready=None) -> None:
    """Open the GUI. ``on_ready(root)`` is a test hook: if given, it
    is called (on the GUI thread) once the window is built, before
    the main loop starts. Production callers pass nothing."""
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    from .apply import apply_all, effective_snapshot, load_applied, remove_all
    from .iran_ranges import load_snapshot, shipped_snapshot_path, snapshot_path
    from .routes import RouteExecutor, current_routes, find_regular_gateway
    from .rules import RuleStore, resolve_rule
    from .settings import Settings
    from .tray import TrayController, TrayIcon
    from .updater import check_once
    from .verify import check_target, public_ip, verify_applied
    from .vpn import (
        describe_interfaces,
        parse_ipconfig_interfaces,
        parse_route_print_interfaces,
        vpn_interface_ips,
    )

    settings = Settings()
    executor = RouteExecutor(dry_run=(os.name != "nt"))
    store = RuleStore()
    root = tk.Tk()
    root.title(f"{APP_NAME} {APP_VERSION}")
    root.geometry("780x680")
    root.minsize(700, 560)

    # --- app icon (embedded PNG, so it works even in a bare exe) ------
    try:
        from .icon import ICON_PNG_B64

        photo = tk.PhotoImage(data=ICON_PNG_B64)
        root.iconphoto(True, photo)
        root._icon_photo = photo  # keep a reference or Tk drops it
    except Exception:
        pass
    if os.name == "nt":
        try:
            ico = _resource_path("assets/logo.ico")
            if ico.exists():
                root.iconbitmap(str(ico))
        except Exception:
            pass

    log_box = None

    def log(msg: str) -> None:
        if log_box is not None:
            log_box.insert(tk.END, msg + "\n")
            log_box.see(tk.END)
        print(msg)

    # --- live system state ---------------------------------------------
    def read_system():
        """Gateway, VPN status, route table — fresh from Windows."""
        routes = current_routes()
        vpn_names: list[str] = []
        vpn_ips = []
        if os.name == "nt":
            import subprocess

            try:
                raw = subprocess.run(["route", "print", "-4"], capture_output=True, text=True).stdout
                vpn_names = parse_route_print_interfaces(raw)
            except Exception:
                raw = ""
            try:
                ipc = subprocess.run(["ipconfig"], capture_output=True, text=True).stdout
                vpn_ips = [ipaddress.IPv4Address(ip) for ip in vpn_interface_ips(parse_ipconfig_interfaces(ipc))]
            except Exception:
                vpn_ips = []
        vpn_status = describe_interfaces(vpn_names)
        gateway_route = find_regular_gateway(routes, vpn_ips) if routes else None
        gateway = str(gateway_route.gateway) if gateway_route else None
        return routes, gateway, vpn_status

    routes, gateway, vpn_status = read_system()
    admin_state = ensure_admin_or_warn()

    # --- tray ------------------------------------------------------------
    tray_controller = TrayController(
        tray_available=False,
        minimize_on_close=bool(settings.get("minimize_on_close")),
    )
    tray_icon: TrayIcon | None = None

    def show_window() -> None:
        tray_controller.on_tray_show()
        root.deiconify()
        root.lift()
        root.focus_force()

    def exit_app() -> None:
        """Tray Exit: remove routes if the setting says so, then quit."""
        if bool(settings.get("remove_routes_on_exit")) and gateway and admin_state == "admin":
            try:
                report = remove_all(executor, ipaddress.IPv4Address(gateway))
                log(f"Exit: removed {len(report.removed)} route(s).")
            except Exception as exc:  # noqa: BLE001 - exit must not hang
                log(f"Exit: could not remove routes: {exc}")
        if tray_icon is not None:
            tray_icon.remove()
        root.destroy()

    def on_close() -> None:
        action = tray_controller.on_close()
        if action == "minimize":
            root.withdraw()
            log("Minimised to the system tray — protection keeps running. Double-click the tray icon to bring OffTunnel back.")
        else:
            exit_app()

    root.protocol("WM_DELETE_WINDOW", on_close)

    if bool(settings.get("tray_enabled")):
        tray_icon = TrayIcon(
            on_show=lambda: root.after(0, show_window),
            on_apply=lambda: root.after(0, do_apply),
            on_exit=lambda: root.after(0, exit_app),
            tooltip=f"{APP_NAME} — VPN split tunneling",
        )
        tray_controller.tray_available = tray_icon.available
        if not tray_icon.available and os.name == "nt":
            log("System tray icon could not be created — closing the window will quit the app.")

    # --- notebook ---------------------------------------------------------
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    home_tab = ttk.Frame(notebook)
    rules_tab = ttk.Frame(notebook)
    settings_tab = ttk.Frame(notebook)
    status_tab = ttk.Frame(notebook)
    notebook.add(home_tab, text="Home")
    notebook.add(rules_tab, text="Rules")
    notebook.add(settings_tab, text="Settings")
    notebook.add(status_tab, text="Status & log")

    # === Home tab ==========================================================
    ttk.Label(home_tab, text="OffTunnel — local traffic goes off the VPN tunnel",
              font=("Segoe UI", 12, "bold")).pack(anchor=tk.W, padx=10, pady=(10, 2))
    ttk.Label(home_tab, text="Iranian sites and IPs go through your normal connection.\nEverything else stays on the VPN.",
              justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=2)

    banner = tk.Frame(home_tab, bg="#fde8e8", padx=10, pady=10)
    banner.pack(fill=tk.X, padx=10, pady=10)
    banner_text = tk.Label(banner, text="Checking…", font=("Segoe UI", 14, "bold"),
                           bg="#fde8e8", fg="#7a1f1f", justify=tk.LEFT)
    banner_text.pack(anchor=tk.W)
    banner_sub = tk.Label(banner, text="", bg="#fde8e8", fg="#7a1f1f", justify=tk.LEFT, wraplength=680)
    banner_sub.pack(anchor=tk.W)

    info_text = tk.StringVar()
    ttk.Label(home_tab, textvariable=info_text, justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=4)

    def refresh_home() -> None:
        nonlocal routes, gateway, vpn_status, admin_state
        routes, gateway, vpn_status = read_system()
        admin_state = ensure_admin_or_warn()
        snap = effective_snapshot()
        if snap:
            result = verify_applied(snap.networks, routes, gateway)
            total, applied = result["total"], result["applied"]
            if total and applied == total and not result["wrong_gateway"]:
                banner.configure(bg="#e6f4ea")
                banner_text.configure(text="✓ Protected", bg="#e6f4ea", fg="#14532d")
                banner_sub.configure(
                    text=f"All {total:,} Iran routes are in the Windows route table. Iranian traffic goes direct.",
                    bg="#e6f4ea", fg="#14532d")
            elif applied > 0:
                banner.configure(bg="#fef3c7")
                banner_text.configure(text="◐ Partly protected", bg="#fef3c7", fg="#713f12")
                banner_sub.configure(
                    text=f"Only {applied:,} of {total:,} Iran routes are applied ({result['missing']:,} missing). Click “Protect Iran traffic” again.",
                    bg="#fef3c7", fg="#713f12")
            else:
                banner.configure(bg="#fde8e8")
                banner_text.configure(text="✕ Not protected", bg="#fde8e8", fg="#7a1f1f")
                banner_sub.configure(
                    text="No Iran routes are applied yet. Click “Protect Iran traffic” below.",
                    bg="#fde8e8", fg="#7a1f1f")
        else:
            banner_text.configure(text="✕ Not protected")
            banner_sub.configure(text="No Iran snapshot found. Click “Protect Iran traffic” to load it.")
        vpn_line = (
            f"VPN detected: {', '.join(vpn_status.vpn_interfaces)}"
            if vpn_status.vpn_connected else "No VPN detected — connect your VPN first, then click Protect."
        )
        admin_line = (
            "Administrator: yes ✓" if admin_state == "admin"
            else "Administrator: NO — Apply will not work until you restart as Administrator."
            if admin_state == "not-admin" else "Administrator: not applicable (not Windows)"
        )
        info_text.set(
            f"{vpn_line}\n{admin_line}\nRegular gateway: {gateway or 'not found'}"
        )

    def do_apply() -> None:
        if admin_state == "not-admin":
            messagebox.showwarning(
                APP_NAME,
                "OffTunnel is not running as Administrator, so it cannot change Windows routes.\n\n"
                "Click “Restart as Administrator” on the Home tab, or right-click OffTunnel.exe and choose “Run as administrator”.",
            )
            return
        if not gateway:
            messagebox.showwarning(
                APP_NAME,
                "No regular gateway found.\n\nConnect to the internet first (your normal connection, not only the VPN), then click Protect again.",
            )
            return
        log("Applying protection (Iran pack + your rules)…")
        snap = effective_snapshot()

        def work():
            report = apply_all(executor, ipaddress.IPv4Address(gateway), snap, store)
            root.after(0, lambda: _after_apply(report))

        def _after_apply(report):
            if report.failed:
                messagebox.showwarning(
                    APP_NAME,
                    "Some routes could not be applied:\n" + "\n".join(report.failed[:5]) +
                    "\n\nTry restarting as Administrator and clicking Protect again.",
                )
                log("Apply finished with failures: " + "; ".join(report.failed[:5]))
            else:
                log(f"Applied {len(report.added)} route(s), removed {len(report.removed)}.")
            refresh_home()
            refresh_rules_list()

        threading.Thread(target=work, daemon=True).start()

    def do_remove_protection() -> None:
        if not gateway:
            return

        report = remove_all(executor, ipaddress.IPv4Address(gateway))
        log(f"Protection removed: {len(report.removed)} route(s) deleted.")
        if report.failed:
            messagebox.showwarning(APP_NAME, "Some routes could not be removed:\n" + "\n".join(report.failed[:5]))
        refresh_home()
        refresh_rules_list()

    def do_restart_admin() -> None:
        if relaunch_elevated():
            root.destroy()
        else:
            messagebox.showinfo(
                APP_NAME,
                "Could not restart as Administrator (the Windows prompt may have been cancelled).\n\n"
                "Right-click OffTunnel.exe and choose “Run as administrator” instead.",
            )

    btn_row = ttk.Frame(home_tab)
    btn_row.pack(anchor=tk.W, padx=10, pady=8)
    protect_btn = tk.Button(btn_row, text="Protect Iran traffic", command=do_apply,
                            font=("Segoe UI", 13, "bold"), bg="#00b39a", fg="white",
                            padx=18, pady=10)
    protect_btn.pack(side=tk.LEFT, padx=4)
    ttk.Button(btn_row, text="Remove protection", command=do_remove_protection).pack(side=tk.LEFT, padx=4)
    if admin_state == "not-admin":
        ttk.Button(btn_row, text="Restart as Administrator", command=do_restart_admin).pack(side=tk.LEFT, padx=4)

    ttk.Label(home_tab, text="What happens next:  1) OffTunnel adds the Iran routes  2) Iranian sites go direct  3) Everything else stays on the VPN",
              wraplength=700, justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=4)

    # --- Test / proof ------------------------------------------------------
    test_frame = ttk.LabelFrame(home_tab, text="Test — prove it works (no terminal needed)")
    test_frame.pack(fill=tk.X, padx=10, pady=10)
    test_row = ttk.Frame(test_frame)
    test_row.pack(fill=tk.X, padx=8, pady=6)
    ttk.Label(test_row, text="Test:").pack(side=tk.LEFT)
    test_entry = tk.Entry(test_row, width=28)
    test_entry.insert(0, "snapp.ir")
    test_entry.pack(side=tk.LEFT, padx=4)
    test_result = tk.Text(test_frame, height=6, wrap=tk.WORD)
    test_result.pack(fill=tk.X, padx=8, pady=6)
    test_result.insert(tk.END, "Click “Test now” to check a real Iranian site and IP.")
    test_result.configure(state=tk.DISABLED)

    def do_test() -> None:
        target = test_entry.get().strip() or "snapp.ir"
        test_result.configure(state=tk.NORMAL)
        test_result.delete("1.0", tk.END)
        test_result.insert(tk.END, f"Testing {target}…\n")
        test_result.configure(state=tk.DISABLED)

        def work():
            lines = []
            my_ip = public_ip()
            lines.append(f"Your public IP right now: {my_ip or 'unknown'}")
            lines.append("(That is your VPN IP when the VPN is on — other sites still use the VPN.)")
            snap = effective_snapshot()
            sample_ip = str(snap.networks[0].network_address + 1) if snap and snap.networks else "2.144.0.1"
            for item in (target, sample_ip):
                check = check_target(item, gateway)
                lines.append("")
                lines.append(check.message)
                lines.append("PASS — direct, off the VPN." if check.via == "direct" else "FAIL — not direct." if check.via == "vpn" else "Could not tell — check the route table on the Status tab.")
            root.after(0, lambda: _show_test("\n".join(lines)))

        def _show_test(text):
            test_result.configure(state=tk.NORMAL)
            test_result.delete("1.0", tk.END)
            test_result.insert(tk.END, text)
            test_result.configure(state=tk.DISABLED)
            log("Test finished.")

        threading.Thread(target=work, daemon=True).start()

    ttk.Button(test_row, text="Test now", command=do_test).pack(side=tk.LEFT, padx=4)

    # === Rules tab ==========================================================
    ttk.Label(rules_tab, text="Iran pack + your own rules. Everything listed here is what gets routed direct.",
              justify=tk.LEFT).pack(anchor=tk.W, padx=8, pady=6)

    iran_frame = ttk.LabelFrame(rules_tab, text="Iran pack (all Iran IP ranges)")
    iran_frame.pack(fill=tk.X, padx=8, pady=4)
    iran_row = ttk.Frame(iran_frame)
    iran_row.pack(fill=tk.X, padx=6, pady=4)
    ttk.Button(iran_row, text="Apply Iran pack", command=do_apply).pack(side=tk.LEFT, padx=4)
    ttk.Button(iran_row, text="Refresh ranges", command=lambda: threading.Thread(
        target=lambda: check_once(executor, gateway, log=log), daemon=True).start()).pack(side=tk.LEFT, padx=4)
    iran_count = tk.StringVar(value="")
    ttk.Label(iran_row, textvariable=iran_count).pack(side=tk.LEFT, padx=8)

    search_row = ttk.Frame(iran_frame)
    search_row.pack(fill=tk.X, padx=6, pady=2)
    ttk.Label(search_row, text="Search IP ranges:").pack(side=tk.LEFT)
    iran_search = tk.Entry(search_row, width=30)
    iran_search.pack(side=tk.LEFT, padx=4)
    iran_list = tk.Listbox(iran_frame, height=6)
    iran_list.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

    def refresh_iran_list(*_args) -> None:
        snap = effective_snapshot()
        query = iran_search.get().strip().lower()
        iran_list.delete(0, tk.END)
        if not snap:
            iran_count.set("No Iran snapshot loaded.")
            return
        shown = [str(n) for n in snap.networks if not query or query in str(n).lower()]
        iran_count.set(f"{len(snap.networks):,} Iran ranges ({snap.total_addresses:,} addresses) — showing {len(shown):,}")
        for item in shown[:2000]:
            iran_list.insert(tk.END, item)

    iran_search.bind("<KeyRelease>", refresh_iran_list)

    # --- catalog sites ------------------------------------------------------
    catalog = _load_catalog()
    cat_frame = ttk.LabelFrame(rules_tab, text="Iranian sites (hosted abroad — add as a domain rule)")
    cat_frame.pack(fill=tk.X, padx=8, pady=4)
    cat_list = tk.Listbox(cat_frame, height=3)
    cat_list.pack(fill=tk.X, padx=6, pady=4)
    for item in catalog:
        cat_list.insert(tk.END, f"{item.get('domain', '')} — {item.get('label', '')}")

    def do_add_catalog() -> None:
        sel = cat_list.curselection()
        if not sel:
            return
        domain = catalog[sel[0]].get("domain", "")
        try:
            rule = store.add("domain", domain)
            resolve_rule(rule)
            store.save()
            log(f"Added site rule: {domain} → {rule.resolved_ips}")
        except ValueError as exc:
            messagebox.showerror(APP_NAME, str(exc))
        refresh_rules_list()

    ttk.Button(cat_frame, text="Add selected site as a rule", command=do_add_catalog).pack(anchor=tk.W, padx=6, pady=4)

    # --- manual rules -------------------------------------------------------
    form = ttk.Frame(rules_tab)
    form.pack(fill=tk.X, padx=8, pady=4)
    kind_var = tk.StringVar(value="domain")
    ttk.OptionMenu(form, kind_var, "domain", "domain", "ip", "cidr").pack(side=tk.LEFT, padx=4)
    value_entry = tk.Entry(form, width=36)
    value_entry.pack(side=tk.LEFT, padx=4)
    ttk.Button(form, text="Add rule", command=lambda: do_add_rule()).pack(side=tk.LEFT, padx=4)
    ttk.Button(form, text="Apply Iran pack", command=do_apply).pack(side=tk.LEFT, padx=4)

    rules_list = tk.Listbox(rules_tab, height=4)
    rules_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

    def refresh_rules_list() -> None:
        rules_list.delete(0, tk.END)
        for r in store.rules:
            ips = f" → {', '.join(r.resolved_ips[:3])}" + ("…" if len(r.resolved_ips) > 3 else "")
            state = "" if r.enabled else " (off)"
            rules_list.insert(tk.END, f"{r.kind}: {r.value}{ips if r.resolved_ips else ''}{state}")
        refresh_iran_list()

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
        value_entry.delete(0, tk.END)
        refresh_rules_list()
        messagebox.showinfo(APP_NAME, f"Rule added: {rule.value}.\nClick “Protect Iran traffic” on the Home tab to route it.")

    def do_remove_rule() -> None:
        sel = rules_list.curselection()
        if not sel:
            return
        rule = store.rules[sel[0]]
        # Remove its routes first so a deleted rule stops routing.
        if gateway and admin_state == "admin":
            from .apply import load_applied
            from .rules import rule_networks

            state = load_applied()
            nets = [n for n in state.rules if n in rule_networks(rule)]
            for net in nets:
                executor.delete_route(net, ipaddress.IPv4Address(gateway))
            if nets:
                log(f"Removed {len(nets)} route(s) for {rule.value}.")
        store.remove(rule.kind, rule.value)
        log(f"Removed manual rule: {rule.kind} {rule.value}")
        refresh_rules_list()

    ttk.Button(rules_tab, text="Remove selected rule", command=do_remove_rule).pack(anchor=tk.W, padx=8, pady=4)
    refresh_rules_list()

    # === Settings tab =======================================================
    ttk.Label(settings_tab, text="Settings are saved automatically.",
              justify=tk.LEFT).pack(anchor=tk.W, padx=10, pady=8)

    def add_check(text: str, key: str, explain: str) -> None:
        var = tk.BooleanVar(value=bool(settings.get(key)))
        def on_change(*_args):
            settings.set(key, var.get())
            tray_controller.minimize_on_close = bool(settings.get("minimize_on_close"))
            log(f"Setting saved: {key} = {var.get()}")
        ttk.Checkbutton(settings_tab, text=text, variable=var, command=on_change).pack(anchor=tk.W, padx=10, pady=2)
        ttk.Label(settings_tab, text=explain, wraplength=680, justify=tk.LEFT).pack(anchor=tk.W, padx=28)

    add_check("Minimise to the system tray when I close the window",
              "minimize_on_close",
              "On: closing the window hides it in the tray and protection keeps running. Off: closing quits the app.")
    add_check("Show the tray icon", "tray_enabled",
              "Off: no tray icon, and closing the window always quits the app.")
    add_check("Start minimised to the tray", "start_minimized",
              "On: OffTunnel starts hidden in the tray. Double-click the tray icon to open it.")
    add_check("Remove the applied routes when I choose Exit from the tray",
              "remove_routes_on_exit",
              "On: Exit really stops the protection. Off: routes stay in Windows even after Exit.")
    add_check("Iran pack is on by default", "iran_pack_enabled",
              "The Iran pack is included every time you click Protect. Turn it off only if you want manual rules only.")

    interval_row = ttk.Frame(settings_tab)
    interval_row.pack(anchor=tk.W, padx=10, pady=8)
    ttk.Label(interval_row, text="Check for Iran range updates every (minutes):").pack(side=tk.LEFT)
    interval_var = tk.StringVar(value=str(settings.get("check_interval_minutes")))
    interval_entry = tk.Entry(interval_row, width=6, textvariable=interval_var)
    interval_entry.pack(side=tk.LEFT, padx=4)

    def save_interval(*_args) -> None:
        try:
            value = int(interval_var.get())
        except ValueError:
            return
        value = max(5, min(1440, value))
        settings.set("check_interval_minutes", value)
        log(f"Setting saved: check_interval_minutes = {value}")

    interval_entry.bind("<FocusOut>", save_interval)

    # === Status tab =========================================================
    status_text = tk.StringVar()
    ttk.Label(status_tab, textvariable=status_text, justify=tk.LEFT).pack(anchor=tk.W, padx=8, pady=8)
    for note in vpn_status.notes:
        ttk.Label(status_tab, text="• " + note, wraplength=680, justify=tk.LEFT).pack(anchor=tk.W, padx=8)

    def refresh_status_text() -> None:
        snap = effective_snapshot()
        applied = load_applied()
        snap_line = (
            f"Iran snapshot: {len(snap.networks):,} ranges" if snap else "Iran snapshot: none"
        )
        status_text.set(
            f"Platform: {'Windows' if os.name == 'nt' else 'non-Windows (dry-run mode)'}\n"
            f"Administrator: {admin_state}\n"
            f"Regular gateway: {gateway or 'not found'}\n"
            f"VPN connected: {vpn_status.vpn_connected} — {', '.join(vpn_status.vpn_interfaces) or 'none detected'}\n"
            f"Routes OffTunnel applied: {len(applied.all_networks)} "
            f"({len(applied.iran)} Iran, {len(applied.rules)} manual rules)\n"
            f"{snap_line}"
        )

    refresh_status_text()
    ttk.Button(status_tab, text="Verify now (re-check the route table)",
               command=lambda: (refresh_home(), refresh_status_text())).pack(anchor=tk.W, padx=8, pady=4)
    log_box = scrolledtext.ScrolledText(status_tab, height=12)
    log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
    log(f"{APP_NAME} {APP_VERSION} started. Dry-run={executor.dry_run}.")
    if executor.dry_run:
        log("Dry-run mode: route commands will be shown, not executed (no Windows routing table here).")
    if admin_state == "not-admin":
        log("Not running as Administrator — Apply will not work until you restart as Administrator.")

    refresh_home()
    if bool(settings.get("start_minimized")) and tray_controller.tray_available:
        root.withdraw()
        tray_controller.window_visible = False
        tray_controller.minimized_to_tray = True

    if on_ready is not None:
        root.after(100, lambda: on_ready(root))

    # Background updater (settings interval, only when admin on Windows).
    try:
        from .updater import Updater

        interval = int(settings.get("check_interval_minutes") or 15) * 60
        updater = Updater(executor, lambda: gateway, interval_seconds=interval, log=log)
        updater.start()
    except Exception as exc:  # noqa: BLE001 - updater must never kill the GUI
        log(f"Background updater could not start: {exc}")

    root.mainloop()
