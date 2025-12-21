from PyInstaller.utils.hooks import copy_metadata

datas = []
# Textual needs its metadata to work inside an EXE
datas += copy_metadata('textual')
datas += copy_metadata('netwatchpy') 

block_cipher = None

a = Analysis(
    ['src/netwatch/tui.py'],  # Entry point
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['textual.drivers.windows_driver', 'textual.drivers.linux_driver'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='netwatch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)