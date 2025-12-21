import sys
import os
from PyInstaller.utils.hooks import copy_metadata, collect_data_files

datas = []

# COLLECT METADATA & RESOURCES
datas += copy_metadata('textual')
datas += copy_metadata('netwatchpy')
datas += copy_metadata('desktop_notifier')
# This collects the icons/assets for notifications
datas += collect_data_files('desktop_notifier')

# DEFINE HIDDEN IMPORTS
hidden_imports = [
    'textual.widgets._tab_pane',
    'textual.widgets._tabbed_content',
    'textual.widgets._data_table',
    'desktop_notifier.resources',
]

# OS-SPECIFIC DRIVERS
if sys.platform.startswith('win'):
    hidden_imports.append('textual.drivers.windows_driver')
elif sys.platform.startswith('linux'):
    hidden_imports.append('textual.drivers.linux_driver')
elif sys.platform.startswith('darwin'):
    hidden_imports.append('textual.drivers.macos_driver')

block_cipher = None

a = Analysis(
    ['entry_point.py'],
    pathex=['src'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
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