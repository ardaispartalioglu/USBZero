# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['usbzero_en.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/usbzero_icon_blue_final_v3.ico', 'assets'),
        ('assets/flash-drive-blue-converted.png', 'assets')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='USBZero',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='assets/usbzero_icon_blue_final_v3.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='USBZero'
)
