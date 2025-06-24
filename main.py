#!/usr/bin/env python3
"""
AutoFisher Qt - Automatic Fishing Bot for Play Together
Ultra-Fast Detection Edition - Optimized for instant response
"""
import sys
import time
import signal
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from ui.main_window import AutoFisherMainWindow
from utils.constants import VERSION, VERSION_NAME

def main():
    """Main application entry point"""
    # Create the application
    app = QApplication(sys.argv)
    
    # Create the main window configured for overlay-only mode
    main_window = AutoFisherMainWindow(overlay_only=True)
    
    # Set to use simple overlay
    main_window.use_full_overlay = False
    
    # Initialize and immediately switch to overlay mode
    main_window.show()
    main_window.hide()
    QTimer.singleShot(100, main_window.minimize_to_overlay)
    
    # Log startup information
    print(f"Starting AutoFisher Qt v{VERSION} - {VERSION_NAME}")
    print("Ultra-Fast Detection enabled: Optimized for instant fish response")
    
    # Handle graceful shutdown on SIGINT (Ctrl+C)
    def signal_handler(sig, frame):
        print("Shutting down gracefully...")
        # Stop any running detection
        if hasattr(main_window, 'detection_running') and main_window.detection_running:
            main_window.stop_detection()
        
        # Stop any running threads
        if hasattr(main_window, 'game_tracker') and main_window.game_tracker:
            main_window.game_tracker.stop()
            main_window.game_tracker.wait()
            
        # Close the window which will trigger proper cleanup
        main_window.close()
        app.quit()
        
    signal.signal(signal.SIGINT, signal_handler)
    
    # Set up a timer to process events and allow signals to be caught
    exit_timer = QTimer()
    exit_timer.timeout.connect(lambda: None)
    exit_timer.start(100)
    
    # Run the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 