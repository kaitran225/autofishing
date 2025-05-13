#!/usr/bin/env python3
import os
import platform
import sys
import subprocess

def main():
    """
    Main entry point for autofishing application.
    Detects the operating system and launches the appropriate version.
    """
    system = platform.system().lower()
    
    if system == 'darwin':
        print("Detected macOS - launching Mac version")
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'mac', 'mac_pixel_detector.py')
        subprocess.run([sys.executable, script_path])
    elif system == 'windows':
        print("Detected Windows - launching Windows version")
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'windows', 'pixel_change_trigger.py')
        subprocess.run([sys.executable, script_path])
    else:
        print(f"Unsupported operating system: {platform.system()}")
        print("This application only supports Windows and macOS.")
        sys.exit(1)

if __name__ == "__main__":
    main() 