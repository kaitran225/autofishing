#!/usr/bin/env python3
import platform
import sys

def main():
    """
    Main entry point for autofishing application.
    Detects the operating system and launches the appropriate version.
    """
    system = platform.system().lower()
    
    # Import common UI module
    try:
        from autofisher.ui import AutoFisherApp
        
        # Start the application with platform-specific backend
        app = AutoFisherApp()
        app.run()
    except ImportError as e:
        # Fallback to legacy platform-specific launchers
        print(f"Cross-platform UI not available: {e}")
        print(f"Falling back to platform-specific version")
        
        if system == 'darwin':
            print("Detected macOS - launching Mac version")
            from src.mac.mac_pixel_detector import main as mac_main
            mac_main()
        elif system == 'windows':
            print("Detected Windows - launching Windows version")
            from src.windows.pixel_change_trigger import main as win_main
            win_main()
        else:
            print(f"Unsupported operating system: {platform.system()}")
            print("This application only supports Windows and macOS.")
            sys.exit(1)

if __name__ == "__main__":
    main() 