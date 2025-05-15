#!/usr/bin/env python3
"""
Build script for AutoFisher application
Builds both Mac and Windows versions depending on the platform
"""
import os
import sys
import platform
import subprocess
import shutil

def main():
    """Main build function"""
    system = platform.system().lower()
    
    # Make sure we have the correct icon format for each platform
    if system == 'windows' and not os.path.exists('autofisher/resources/app_icon.ico'):
        print("Converting PNG icon to ICO format for Windows...")
        try:
            subprocess.run([sys.executable, 'autofisher/utils/convert_icon.py'], check=True)
        except subprocess.CalledProcessError:
            print("Failed to convert icon. Make sure Pillow is installed and app_icon.png exists.")
            return False
    
    # Clean any previous build artifacts
    clean_build()
    
    # Build for the appropriate platform
    if system == 'darwin':
        return build_mac()
    elif system == 'windows':
        return build_windows()
    else:
        print(f"Unsupported platform: {platform.system()}")
        print("This build script only supports Windows and macOS.")
        return False

def clean_build():
    """Clean previous build artifacts"""
    print("Cleaning previous build artifacts...")
    
    # Clean directories
    for directory in ['build/temp', 'dist']:
        if os.path.exists(directory):
            print(f"Removing {directory}/ directory...")
            shutil.rmtree(directory)

def build_mac():
    """Build the macOS version"""
    print("Building macOS version...")
    
    try:
        # Make sure PyInstaller is installed
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
        
        # Build using the macOS spec file
        subprocess.run(['pyinstaller', 'build/autofishing_mac.spec'], check=True)
        
        print("\nBuild successful!")
        print("The macOS application is available at: dist/AutoFisher.app")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        return False

def build_windows():
    """Build the Windows version"""
    print("Building Windows version...")
    
    try:
        # Make sure PyInstaller is installed
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'], check=True)
        
        # Build using the Windows spec file
        subprocess.run(['pyinstaller', 'build/autofishing_windows.spec'], check=True)
        
        print("\nBuild successful!")
        print("The Windows application is available at: dist/AutoFisher_Windows.exe")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 