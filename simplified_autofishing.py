import sys
import time
import datetime
import numpy as np
import cv2
import mss
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, 
    QVBoxLayout, QHBoxLayout, QWidget, QSlider
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QPixmap, QImage
import subprocess

class PixelChangeDetector(QThread):
    """Thread to detect pixel changes in a screen region"""
    detection_signal = pyqtSignal()
    frame_update_signal = pyqtSignal(object, object, float)
    log_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        # Screen capture area
        self.monitor = {"top": 0, "left": 0, "width": 200, "height": 200}
        self.sct = mss.mss()
        
        # Detection parameters
        self.prev_frame = None
        self.color_frame = None
        self.diff_frame = None
        self.change_percent = 0
        self.threshold = 0.2  # Default 20% change threshold
        self.last_detection_time = 0
        self.detection_cooldown = 3.0  # seconds between detections
        
        # Enhanced bright detection
        self.enhanced_bright_detection = True
        
        # Loop control
        self.running = False
        self.paused = False
        
        # Action sequence
        self.in_action_sequence = False
        self.action_sequence_step = 0
        self.action_sequence = [
            {"action": "press_f", "delay": 0.0},   # Immediately press F
            {"action": "wait", "delay": 4.0},      # Wait to see if fish bites
            {"action": "press_esc", "delay": 1.5}, # Press ESC if no bite 
            {"action": "wait", "delay": 2.0},      # Wait before casting again
            {"action": "press_f", "delay": 2.0}    # Cast again
        ]
        
        # Game window details for focus
        self.game_process_name = ""
        self.game_window_name = ""
    
    def log(self, message):
        """Log a message"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_signal.emit(formatted_message)
    
    def set_capture_area(self, x, y, width, height):
        """Set the screen area to capture"""
        self.monitor = {"top": y, "left": x, "width": width, "height": height}
        self.log(f"Capture area set to: {self.monitor}")
    
    def set_threshold(self, threshold):
        """Set the detection threshold (0.0-1.0)"""
        self.threshold = threshold
        self.log(f"Detection threshold set to: {threshold:.1%}")
    
    def calculate_frame_difference(self, frame1, frame2):
        """Calculate the difference between two frames with improved handling for bright backgrounds"""
        if frame1 is None or frame2 is None:
            return None, 0
            
        # Ensure frames have same dimensions
        if frame1.shape != frame2.shape:
            frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]), interpolation=cv2.INTER_NEAREST)
            
        # Apply different methods based on bright background mode
        if self.enhanced_bright_detection:
            # Enhanced bright background method
            # Use absolute difference normalized by average brightness
            diff = cv2.absdiff(frame1, frame2)
            
            # Create a mask for bright areas
            bright_areas = cv2.threshold(frame1, 200, 255, cv2.THRESH_BINARY)[1]
            dark_areas = cv2.threshold(frame1, 50, 255, cv2.THRESH_BINARY_INV)[1]
            
            # Enhance differences in bright areas for better detection
            enhanced_diff = diff.copy()
            enhanced_diff = cv2.addWeighted(enhanced_diff, 2.0, bright_areas, 0.5, 0)
            enhanced_diff = cv2.addWeighted(enhanced_diff, 1.0, dark_areas, 0.2, 0)
            
            # Calculate change percentage with higher sensitivity
            total_pixels = frame1.shape[0] * frame1.shape[1]
            change_pixels = cv2.countNonZero(cv2.threshold(enhanced_diff, 25, 255, cv2.THRESH_BINARY)[1])
            change_percent = change_pixels / total_pixels
            
            return enhanced_diff, change_percent
        else:
            # Standard method
            diff = cv2.absdiff(frame1, frame2)
            binary = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)[1]
            total_pixels = frame1.shape[0] * frame1.shape[1]
            change_pixels = cv2.countNonZero(binary)
            change_percent = change_pixels / total_pixels
            
            return binary, change_percent
    
    def _send_f_key(self):
        """Send F key press using AppleScript with game focus"""
        try:
            # Simple F key press using AppleScript
            applescript = '''
            tell application "System Events"
                keystroke "f"
            end tell
            '''
            subprocess.run(["osascript", "-e", applescript])
            self.log("Sent F key press")
        except Exception as e:
            self.log(f"Error sending F key: {str(e)}")
    
    def _send_esc_key(self):
        """Send ESC key press using AppleScript"""
        try:
            applescript = '''
            tell application "System Events"
                key code 53  # ESC key
            end tell
            '''
            subprocess.run(["osascript", "-e", applescript])
            self.log("Sent ESC key press")
        except Exception as e:
            self.log(f"Error sending ESC key: {str(e)}")
    
    def _process_action_sequence(self):
        """Process the current step in the action sequence"""
        if not self.in_action_sequence or self.action_sequence_step >= len(self.action_sequence):
            self.in_action_sequence = False
            self.action_sequence_step = 0
            return
            
        # Get the current action
        action = self.action_sequence[self.action_sequence_step]
        action_type = action["action"]
        
        # Execute the action immediately
        if action_type == "press_f":
            self._send_f_key()
        elif action_type == "press_esc":
            self._send_esc_key()
        elif action_type == "wait":
            self.log(f"Waiting for {action['delay']} seconds")
        
        # Schedule the next action
        delay = action["delay"]
        self.log(f"Action sequence: {action_type} (Next in {delay}s)")
        
        # Move to next step after delay
        self.action_sequence_step += 1
        if self.action_sequence_step < len(self.action_sequence):
            # Schedule next action after delay
            QTimer.singleShot(int(delay * 1000), self._process_action_sequence)
        else:
            # End of sequence
            self.in_action_sequence = False
            self.action_sequence_step = 0
    
    def run(self):
        """Main detection loop"""
        self.log("Detection thread started")
        self.running = True
        
        while self.running:
            # Skip processing if paused
            if self.paused:
                time.sleep(0.1)
                continue
                
            # Capture screen
            screenshot = self.sct.grab(self.monitor)
            
            # Convert to numpy array
            frame = np.array(screenshot, dtype=np.uint8)
            
            # Store color frame for visualization
            self.color_frame = frame.copy()
            
            # Convert to grayscale for processing
            if len(frame.shape) > 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Skip if no previous frame
            if self.prev_frame is None:
                self.prev_frame = frame
                continue
            
            # Calculate difference
            self.diff_frame, self.change_percent = self.calculate_frame_difference(
                self.prev_frame, frame
            )
            
            # Update visualization
            self.frame_update_signal.emit(
                self.color_frame, 
                self.diff_frame,
                self.change_percent
            )
            
            # Current time in seconds
            current_time = time.time()
            
            # Check for detection with cooldown
            if (self.change_percent > self.threshold and 
                    (current_time - self.last_detection_time) > self.detection_cooldown):
                self.log(f"Change detected! {self.change_percent:.2%}")
                self.last_detection_time = current_time
                
                # Start the action sequence
                self.in_action_sequence = True
                self.action_sequence_step = 0
                
                # Execute first action immediately without delay
                self._process_action_sequence()
                
                # Emit signal to trigger UI update AFTER first action
                self.detection_signal.emit()
            
            # Store current frame as previous
            self.prev_frame = frame
            
            # Short sleep to reduce CPU usage
            time.sleep(0.05)
        
        self.log("Detection thread stopped")
    
    def stop(self):
        """Stop the detection thread"""
        self.running = False
        self.wait()
    
    def toggle_pause(self):
        """Pause/resume detection"""
        self.paused = not self.paused
        return self.paused


class MonitoringDisplay(QLabel):
    """Widget to display the monitoring area and results"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 250)
        
        # Colors
        self.colors = {
            'bg_dark': '#2C3639',     # Background
            'matcha': '#A0C49D',      # Accent
            'alert': '#F87474',       # Alert/Error
            'text': '#FFFFFF',        # Text
        }
        
        # Status display
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("No capture area selected")
        self.setStyleSheet(f"color: {self.colors['text']}; background-color: {self.colors['bg_dark']};")
        
        # Status label
        self.status_label = QLabel("Status: Stopped", self)
        self.status_label.setGeometry(10, 10, 150, 20)
        self.status_label.setStyleSheet(f"color: {self.colors['alert']}; background-color: transparent;")
        
        # Bright mode tracking
        self.bright_mode_enabled = True
        
    def update_display(self, color_frame, diff_frame, change_percent):
        """Update the display with current frames"""
        if color_frame is None:
            return
            
        try:
            # Create display frame
            display_frame = color_frame.copy()
            
            # Convert for Qt display
            if len(display_frame.shape) > 2:
                if display_frame.shape[2] == 4:  # BGRA
                    # Convert BGRA to RGB
                    display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGRA2RGB)
                else:
                    # Convert BGR to RGB
                    display_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            # Add difference overlay if available
            if diff_frame is not None:
                # Create a red mask for changed areas
                height, width = diff_frame.shape
                mask = np.zeros((height, width, 3), dtype=np.uint8)
                mask[:, :, 2] = diff_frame  # Red channel
                
                # Add text with change percentage
                percent_text = f"Change: {change_percent:.1%}"
                color = (0, 255, 0) if change_percent < 0.2 else (0, 0, 255)
                cv2.putText(display_frame, percent_text, (10, 30), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                
                # Add bright mode indicator if enabled
                if self.bright_mode_enabled:
                    cv2.putText(display_frame, "Bright Mode", (10, height - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                
                # Overlay the difference mask
                alpha = 0.5
                cv2.addWeighted(display_frame, 1-alpha, mask, alpha, 0, display_frame)
            
            # Convert to QImage and display
            h, w = display_frame.shape[:2]
            qimg = QImage(display_frame.data, w, h, display_frame.strides[0], QImage.Format.Format_RGB888)
            self.setPixmap(QPixmap.fromImage(qimg))
            
        except Exception as e:
            self.setText(f"Display error: {str(e)}")
    
    def set_status(self, status):
        """Update status display"""
        if status == "running":
            self.status_label.setText("Status: Running")
            self.status_label.setStyleSheet(f"color: {self.colors['matcha']};")
        elif status == "stopped":
            self.status_label.setText("Status: Stopped")
            self.status_label.setStyleSheet(f"color: {self.colors['alert']};")
        elif status == "paused":
            self.status_label.setText("Status: Paused")
            self.status_label.setStyleSheet(f"color: orange;")
    
    def set_bright_mode(self, enabled):
        """Set bright detection mode status"""
        self.bright_mode_enabled = enabled


class PixelChangeApp(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        
        # Setup UI
        self.setWindowTitle("AutoFishing")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: #2C3639; color: white;")
        
        # Create the detector thread
        self.detector = PixelChangeDetector()
        self.detector.detection_signal.connect(self.on_detection)
        self.detector.frame_update_signal.connect(self.update_visualization)
        self.detector.log_signal.connect(self.add_log)
        
        # Create main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create monitoring display
        self.monitor_display = MonitoringDisplay()
        main_layout.addWidget(self.monitor_display)
        
        # Control panel
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)
        main_layout.addWidget(control_panel)
        
        # Buttons
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_detection)
        control_layout.addWidget(self.start_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        control_layout.addWidget(self.pause_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)
        
        self.select_region_button = QPushButton("Select Region")
        self.select_region_button.clicked.connect(self.select_region)
        control_layout.addWidget(self.select_region_button)
        
        # Threshold slider
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Threshold:")
        threshold_layout.addWidget(threshold_label)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(1, 50)
        self.threshold_slider.setValue(20)  # Default 20%
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_value_label = QLabel("20%")
        threshold_layout.addWidget(self.threshold_value_label)
        main_layout.addLayout(threshold_layout)
        
        # Log area
        self.log_area = QLabel("Ready to start")
        self.log_area.setStyleSheet("background-color: #3F4E4F; padding: 10px;")
        self.log_area.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.log_area.setMinimumHeight(100)
        main_layout.addWidget(self.log_area)
        
        # Set initial state of bright detection in monitor display
        self.monitor_display.set_bright_mode(self.detector.enhanced_bright_detection)
    
    def update_threshold(self, value):
        """Update detection threshold from slider"""
        threshold = value / 100.0
        self.threshold_value_label.setText(f"{value}%")
        self.detector.set_threshold(threshold)
    
    def select_region(self):
        """Select region to monitor"""
        self.add_log("Click and drag to select a region to monitor")
        self.setWindowOpacity(0.3)
        QApplication.setOverrideCursor(Qt.CursorShape.CrossCursor)
        
        # Create a transparent fullscreen window for selection
        class SelectionWindow(QMainWindow):
            def __init__(self, parent=None):
                super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
                self.setGeometry(0, 0, 3000, 2000)  # Large enough for most screens
                self.setWindowOpacity(0.01)
                self.start_point = None
                self.end_point = None
                self.parent = parent
            
            def mousePressEvent(self, event):
                self.start_point = event.pos()
            
            def mouseReleaseEvent(self, event):
                self.end_point = event.pos()
                QApplication.restoreOverrideCursor()
                
                # Calculate selection rectangle
                x = min(self.start_point.x(), self.end_point.x())
                y = min(self.start_point.y(), self.end_point.y())
                width = abs(self.start_point.x() - self.end_point.x())
                height = abs(self.start_point.y() - self.end_point.y())
                
                # Update parent with selection
                if self.parent and width > 10 and height > 10:
                    self.parent.set_capture_area(x, y, width, height)
                
                self.close()
                self.parent.setWindowOpacity(1.0)
        
        self.selection_window = SelectionWindow(self)
        self.selection_window.show()
    
    def set_capture_area(self, x, y, width, height):
        """Set capture area from selection"""
        self.detector.set_capture_area(x, y, width, height)
        self.add_log(f"Selected region: x={x}, y={y}, width={width}, height={height}")
    
    def start_detection(self):
        """Start the detection thread"""
        self.detector.start()
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.monitor_display.set_status("running")
        self.add_log("Detection started")
    
    def stop_detection(self):
        """Stop the detection thread"""
        self.detector.stop()
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.monitor_display.set_status("stopped")
        self.add_log("Detection stopped")
    
    def toggle_pause(self):
        """Pause/resume detection"""
        paused = self.detector.toggle_pause()
        if paused:
            self.pause_button.setText("Resume")
            self.monitor_display.set_status("paused")
            self.add_log("Detection paused")
        else:
            self.pause_button.setText("Pause")
            self.monitor_display.set_status("running")
            self.add_log("Detection resumed")
    
    def on_detection(self):
        """Handle detection event"""
        self.add_log("Pixel change detected!")
    
    def update_visualization(self, color_frame=None, diff_frame=None, change_percent=0):
        """Update the visualization with current frames"""
        self.monitor_display.update_display(color_frame, diff_frame, change_percent)
    
    def add_log(self, message):
        """Add a message to the log area"""
        current_text = self.log_area.text()
        # Keep only the last 5 lines
        lines = current_text.split("<br>")
        if len(lines) > 5:
            lines = lines[-5:]
        lines.append(message)
        self.log_area.setText("<br>".join(lines))
    
    def closeEvent(self, event):
        """Handle window close event"""
        self.detector.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    window = PixelChangeApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    print("Starting AutoFishing app...")
    main() 