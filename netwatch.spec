import sys
from PyInstaller.utils.hooks import copy_metadata, collect_data_files

datas = []

# COLLECT METADATA & RESOURCES
# Textual needs metadata for version info
datas += copy_metadata('textual')
# Netwatch needs its own metadata
datas += copy_metadata('netwatchpy')
# Desktop Notifier needs metadata AND actual data files (icons, resources)
datas += copy_metadata('desktop_notifier')
datas += collect_data_files('desktop_notifier')

# DEFINE HIDDEN IMPORTS
hidden_imports = [
    # Textual Widgets (loaded dynamically, missed by PyInstaller)
    'textual.widgets._tab_pane',
    'textual.widgets._tabbed_content',
    'textual.widgets._data_table',
    
    # Desktop Notifier Resources (loaded dynamically)
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
    ['src/netwatch/tui.py'],
    pathex=[],
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