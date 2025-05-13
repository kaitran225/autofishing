import sys
import time
import os
import traceback

print("Starting minimal test application...")

try:
    print("Importing modules...")
    import numpy as np
    import cv2
    import mss
    from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
    from PyQt6.QtCore import Qt, QTimer
    
    print("All modules imported successfully")
    
    # Initialize QApplication
    print("Creating QApplication...")
    app = QApplication(sys.argv)
    
    # Create simple window
    print("Creating main window...")
    window = QMainWindow()
    window.setWindowTitle("AutoFishing Test")
    window.setGeometry(100, 100, 400, 300)
    
    # Create central widget
    central_widget = QWidget()
    window.setCentralWidget(central_widget)
    layout = QVBoxLayout(central_widget)
    
    # Add label
    label = QLabel("Testing screen capture in 3 seconds...")
    layout.addWidget(label)
    
    print("GUI created, showing window...")
    window.show()
    
    # Function to test screen capture
    def test_capture():
        try:
            print("Attempting screen capture...")
            with mss.mss() as sct:
                print("MSS initialized")
                monitor = sct.monitors[1]  # Primary monitor
                print(f"Monitor info: {monitor}")
                screenshot = sct.grab(monitor)
                print("Screenshot captured")
                
                # Convert to numpy array
                img = np.array(screenshot)
                print(f"Converted to numpy array, shape: {img.shape}")
                
                label.setText(f"Capture successful! Image shape: {img.shape}")
        except Exception as e:
            print(f"ERROR in screen capture: {str(e)}")
            print(traceback.format_exc())
            label.setText(f"Error: {str(e)}")
    
    # Schedule the test after 3 seconds
    print("Scheduling screen capture test...")
    QTimer.singleShot(3000, test_capture)
    
    print("Entering Qt event loop...")
    sys.exit(app.exec())
    
except Exception as e:
    print(f"ERROR: {str(e)}")
    print(traceback.format_exc()) 