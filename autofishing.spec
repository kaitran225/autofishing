# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['mac_pixel_detector_simple.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PIL._tkinter_finder',
        'matplotlib.backends.backend_qtagg',
        'PyQt6.sip'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure, 
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoFishing',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app_icon.icns',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AutoFishing',
)

app = BUNDLE(
    coll,
    name='AutoFishing.app',
    icon='app_icon.icns',
    bundle_identifier='com.autofishing.app',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'AutoFishing',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Owner'
            }
        ],
        'NSHighResolutionCapable': True,
        'LSEnvironment': {
            'PYTHONIOENCODING': 'utf8'
        },
        'LSApplicationCategoryType': 'public.app-category.utilities',
        'NSCameraUsageDescription': 'This app uses screen recording to detect pixel changes in games.',
        'NSMicrophoneUsageDescription': 'This app does not use the microphone.',
    }
) 