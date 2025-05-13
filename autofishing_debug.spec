# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['debug_launcher.py'],  # Changed to use debug launcher as entry point
    pathex=[],
    binaries=[],
    datas=[
        ('mac_pixel_detector_simple.py', '.'),  # Include main script as data
    ],
    hiddenimports=[
        'PIL._tkinter_finder',
        'matplotlib.backends.backend_qtagg',
        'PyQt6.sip',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'cv2',
        'mss',
        'numpy',
        'PIL',
        'matplotlib',
        'threading',
        'queue',
        'datetime',
        'subprocess',
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
    name='AutoFishingDebug',
    debug=True,  # Enable debug mode
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Show console for debugging
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
    name='AutoFishingDebug',
)

app = BUNDLE(
    coll,
    name='AutoFishingDebug.app',
    icon='app_icon.icns',
    bundle_identifier='com.autofishing.debug',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'AutoFishingDebug',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Owner'
            }
        ],
        'NSHighResolutionCapable': True,
        'LSEnvironment': {
            'PYTHONIOENCODING': 'utf8',
            'PYTHONUNBUFFERED': '1',  # Ensure Python output is not buffered
        },
        'LSApplicationCategoryType': 'public.app-category.utilities',
        'NSCameraUsageDescription': 'This app uses screen recording to detect pixel changes in games.',
        'NSMicrophoneUsageDescription': 'This app does not use the microphone.',
        'NSScreenCaptureUsageDescription': 'This app needs to capture the screen to detect pixel changes.',
    }
) 