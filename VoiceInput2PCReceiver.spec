# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['receiver_app.py'],
    pathex=[],
    binaries=[('vendor/tailcat/windows/tailcat.exe', 'tailcat')],
    datas=[],
    hiddenimports=['pystray._win32', 'qrcode'],
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
    [],
    exclude_binaries=True,
    name='VoiceInput2PCReceiver',
    version='windows_version_info.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='VoiceInput2PCReceiver',
)
