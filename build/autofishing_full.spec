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
        'PyQt6.sip',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'cv2',
        'mss',
        'numpy',
        'PIL',
        'matplotlib',
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
    console=True,  # Enable console for debugging
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
        'NSAppleScriptEnabled': True,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'AutoFishing',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Owner'
            }
        ],
        'NSHighResolutionCapable': True,
        'LSUIElement': False,
        'LSEnvironment': {
            'PYTHONIOENCODING': 'utf8',
            'PYTHONOPTIMIZE': '0',
            'PYTHONDONTWRITEBYTECODE': '1',
        },
        'LSApplicationCategoryType': 'public.app-category.utilities',
        # macOS permission descriptions
        'NSCameraUsageDescription': 'This app uses screen recording for game automation.',
        'NSMicrophoneUsageDescription': 'This app does not use the microphone.',
        'NSAppleEventsUsageDescription': 'This app uses AppleScript to send keyboard commands.',
        'NSScreenCaptureUsageDescription': 'This app needs screen recording permission to detect changes in the game.',
    }
) 