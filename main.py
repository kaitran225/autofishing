#!/usr/bin/env python3
"""
AutoFisher Qt - Automatic Fishing Bot for Play Together
Ultra-Fast Detection Edition - Optimized for instant response
"""
import sys
from PyQt6.QtWidgets import QApplication
from ui.main_window import AutoFisherMainWindow
from utils.constants import VERSION, VERSION_NAME

def main():
    """Main application entry point"""
    # Create the application
    app = QApplication(sys.argv)
    
    # Create and show the main window
    main_window = AutoFisherMainWindow()
    main_window.show()
    
    # Log startup information
    print(f"Starting AutoFisher Qt v{VERSION} - {VERSION_NAME}")
    print("Ultra-Fast Detection enabled: Optimized for instant fish response")
    
    # Run the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 