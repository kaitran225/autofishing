# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['../autofishing.py'],
             pathex=[],
             binaries=[],
             datas=[
                 ('../autofisher/resources/app_icon.icns', 'autofisher/resources'),
                 ('../autofisher/resources', 'autofisher/resources')
             ],
             hiddenimports=[
                 'autofisher.ui',
                 'autofisher.backends.mac',
                 'autofisher.backends.factory',
                 'PyQt6',
                 'PyQt6.QtCore',
                 'PyQt6.QtGui',
                 'PyQt6.QtWidgets',
                 'matplotlib',
                 'mss',
                 'pyautogui'
             ],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=['_tkinter', 'Tkinter', 'enchant', 'win32com', 'win32api', 'win32gui', 'win32con', 'win32process'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='AutoFisher',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None)

coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='AutoFisher')
               
app = BUNDLE(coll,
             name='AutoFisher.app',
             icon='../autofisher/resources/app_icon.icns',
             bundle_identifier='com.autofisher',
             info_plist={
                'NSPrincipalClass': 'NSApplication',
                'NSAppleScriptEnabled': False,
                'CFBundleDisplayName': 'AutoFisher',
                'CFBundleShortVersionString': '1.0.0',
                'NSHighResolutionCapable': 'True',
                'NSRequiresAquaSystemAppearance': 'No',  # Allows dark mode support
                'LSBackgroundOnly': 'False',  # Allow app to appear in dock
                'CFBundleVersion': '1.0.0'
             }) 