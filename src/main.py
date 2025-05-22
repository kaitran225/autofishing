#!/usr/bin/env python3
import sys
from PyQt6.QtWidgets import QApplication, QMessageBox
from src.ui.main_window import PixelChangeApp
from src.utils.permissions import request_screen_recording_permission, check_screen_recording_permission

def main():
    """Main entry point for the application"""
    app = QApplication(sys.argv)
    
    # First try to explicitly request permission (will trigger dialog if needed)
    request_screen_recording_permission()
    
    # Then check if we have permission
    has_permission = check_screen_recording_permission()
    
    window = PixelChangeApp()
    window.show()
    
    # Show permission warning if needed
    if not has_permission:
        QMessageBox.warning(
            None,
            "Screen Recording Permission Required",
            "This application requires screen recording permission to function properly.\n\n"
            "Please grant permission in System Settings > Privacy & Security > Screen Recording.\n\n"
            "You may need to restart the application after granting permission."
        )
        window.add_log("WARNING: Screen recording permission not detected")
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 