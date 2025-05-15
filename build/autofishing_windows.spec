# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(['../autofishing.py'],
             pathex=[],
             binaries=[],
             datas=[
                ('../autofisher/resources', 'autofisher/resources')
             ],
             hiddenimports=[
                'autofisher.ui',
                'autofisher.backends.windows',
                'autofisher.backends.factory',
                'PyQt6',
                'PyQt6.QtCore',
                'PyQt6.QtGui',
                'PyQt6.QtWidgets',
                'matplotlib',
                'win32api',
                'win32gui',
                'win32con',
                'win32process',
                'keyboard'
             ],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=['_tkinter', 'Tkinter', 'enchant', 'pyautogui', 'AppKit', 'Cocoa', 'PyObjCTools'],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='AutoFisher_Windows',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None,
          icon='../autofisher/resources/app_icon.ico' if os.path.exists('../autofisher/resources/app_icon.ico') else None,
          version='file_version_info.txt') 