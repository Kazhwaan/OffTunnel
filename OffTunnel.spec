# -*- mode: python ; coding: utf-8 -*-
# OffTunnel PyInstaller spec (v0.1.1).
#
# Use it instead of the long pyinstaller command line:
#   pyinstaller OffTunnel.spec
# build.ps1 uses the same flags. The important parts for v0.1.1:
#   * icon="assets/logo.ico"  — the exe shows the OffTunnel icon
#     in Explorer, the taskbar and the title bar (v0.1.0 had none).
#   * uac_admin=True           — the exe requests Administrator at
#     launch (requireAdministrator manifest). Without admin the app
#     cannot change Windows routes.
#   * datas includes data/ and assets/ so the Iran snapshot,
#     the domain catalog and the .ico travel with the exe.
# The GitHub workflow (.github/workflows/build-windows.yml) calls
# pyinstaller directly; it needs the same --icon / --uac-admin /
# --add-data flags to get these in the release exe (see BUILD_LOG.md).

a = Analysis(
    ['offtunnel.pyw'],
    pathex=[],
    binaries=[],
    datas=[('data', 'data'), ('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OffTunnel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/logo.ico',
    uac_admin=True,
)
