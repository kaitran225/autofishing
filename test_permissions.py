import sys
import time
import mss
import numpy as np
import cv2
from PIL import Image
import matplotlib.pyplot as plt
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Permissions")
        self.setGeometry(100, 100, 400, 300)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Status label
        self.status_label = QLabel("Ready to test")
        layout.addWidget(self.status_label)
        
        # Test screen capture button
        capture_button = QPushButton("Test Screen Capture")
        capture_button.clicked.connect(self.test_screen_capture)
        layout.addWidget(capture_button)
        
        # Test PyQt button
        pyqt_button = QPushButton("Test PyQt")
        pyqt_button.clicked.connect(self.test_pyqt)
        layout.addWidget(pyqt_button)
        
        # Test OpenCV button
        opencv_button = QPushButton("Test OpenCV")
        opencv_button.clicked.connect(self.test_opencv)
        layout.addWidget(opencv_button)
        
        # Test matplotlib button
        plt_button = QPushButton("Test Matplotlib")
        plt_button.clicked.connect(self.test_matplotlib)
        layout.addWidget(plt_button)
        
        # Exit button
        exit_button = QPushButton("Exit")
        exit_button.clicked.connect(self.close)
        layout.addWidget(exit_button)
    
    def test_screen_capture(self):
        try:
            # Try to capture screen
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                screenshot = sct.grab(monitor)
                
                # Convert to numpy array
                img = np.array(screenshot)
                
                # Show success
                self.status_label.setText(f"Screen capture successful! Size: {img.shape}")
                self.status_label.setStyleSheet("color: green;")
        except Exception as e:
            self.status_label.setText(f"Screen capture failed: {str(e)}")
            self.status_label.setStyleSheet("color: red;")
            
    def test_pyqt(self):
        try:
            # Simple PyQt test - change the window title
            self.setWindowTitle(f"PyQt Works! - {time.time()}")
            self.status_label.setText("PyQt test successful!")
            self.status_label.setStyleSheet("color: green;")
        except Exception as e:
            self.status_label.setText(f"PyQt test failed: {str(e)}")
            self.status_label.setStyleSheet("color: red;")
            
    def test_opencv(self):
        try:
            # Create a simple image with OpenCV
            img = np.zeros((100, 100, 3), dtype=np.uint8)
            img[:, :, 0] = 255  # Blue
            
            # Apply a blur
            blurred = cv2.GaussianBlur(img, (15, 15), 0)
            
            self.status_label.setText("OpenCV test successful!")
            self.status_label.setStyleSheet("color: green;")
        except Exception as e:
            self.status_label.setText(f"OpenCV test failed: {str(e)}")
            self.status_label.setStyleSheet("color: red;")
            
    def test_matplotlib(self):
        try:
            # Test matplotlib
            plt.figure(figsize=(3, 3))
            plt.plot([1, 2, 3, 4], [1, 4, 9, 16])
            plt.close()
            
            self.status_label.setText("Matplotlib test successful!")
            self.status_label.setStyleSheet("color: green;")
        except Exception as e:
            self.status_label.setText(f"Matplotlib test failed: {str(e)}")
            self.status_label.setStyleSheet("color: red;")
            
def main():
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    print("Starting test application...")
    main() 