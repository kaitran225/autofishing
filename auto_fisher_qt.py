import sys
import threading
import time
import platform
import os
import cv2
import numpy as np
import mss
from PIL import Image
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QPushButton, QSlider, QGroupBox, QMessageBox,
                           QFrame, QSplitter)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject

# Import OS-specific modules
if platform.system() == "Windows":
    from region_selector_win import RegionSelectorWin as RegionSelector
    from game_focus_win import GameFocusWin as GameFocus
    from key_sender_win import KeySenderWin as KeySender
elif platform.system() == "Darwin":  # macOS
    from region_selector_mac import RegionSelectorMac as RegionSelector
    from game_focus_mac import GameFocusMac as GameFocus
    from key_sender_mac import KeySenderMac as KeySender
else:
    print("Unsupported OS")
    # Use Windows as fallback
    from region_selector_win import RegionSelectorWin as RegionSelector
    from game_focus_win import GameFocusWin as GameFocus
    from key_sender_win import KeySenderWin as KeySender

# Import utility module
from os_utilities import OSUtilities

# Worker class for running the fishing process in a separate thread
class FishingWorker(QObject):
    """Worker thread for fishing operations"""
    error_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    detection_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.is_running = False
        self.is_paused = False
        self.in_action_sequence = False
        self.action_sequence_step = 0
    
    def start_fishing(self):
        """Start the fishing process"""
        self.is_running = True
        self.is_paused = False
        
        # Try to find game window
        self.parent.game_focus.find_game_window()
        
        # Set up initial frames only when actually starting fishing
        try:
            # Capture initial frames
            self.parent.last_exclamation_frame = self.parent.os_utils.capture_screen(self.parent.sct, self.parent.exclamation_monitor)
            self.parent.last_shadow_frame = self.parent.os_utils.capture_screen(self.parent.sct, self.parent.shadow_monitor)
            
            # Check if we got valid frames
            if self.parent.last_exclamation_frame is None or self.parent.last_shadow_frame is None:
                self.error_signal.emit("Failed to capture screen regions. Please check your region setup.")
                self.finished_signal.emit()
                return
            
            # If references don't exist, use first captures
            if self.parent.reference_exclamation_frame is None:
                self.parent.reference_exclamation_frame = self.parent.last_exclamation_frame.copy()
            if self.parent.reference_shadow_frame is None:
                self.parent.reference_shadow_frame = self.parent.last_shadow_frame.copy()
            
            # State variables
            waiting_for_fish = False
            
            self.status_signal.emit("Started fishing")
            
            while self.is_running:
                # Check if paused
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                
                # Handle action sequence if one is in progress
                if self.in_action_sequence:
                    self._process_action_sequence()
                    time.sleep(0.05)
                    continue
                
                # Capture frames
                exclamation_frame = self.parent.os_utils.capture_screen(self.parent.sct, self.parent.exclamation_monitor)
                
                # Only capture shadow frame if we're not waiting for a fish (optimization)
                if not waiting_for_fish:
                    shadow_frame = self.parent.os_utils.capture_screen(self.parent.sct, self.parent.shadow_monitor)
                else:
                    shadow_frame = self.parent.last_shadow_frame
                
                if exclamation_frame is None or shadow_frame is None:
                    time.sleep(0.05)
                    continue
                
                # Detect exclamation mark
                exclamation_detected, exclamation_frame_viz = self.parent.detect_exclamation_mark(
                    exclamation_frame, self.parent.reference_exclamation_frame
                )
                
                # Detect fish shadow or bouncy bait if needed
                if not waiting_for_fish:
                    shadow_detected, shadow_frame_viz, detection_type = self.parent.detect_fish_shadow(
                        shadow_frame, self.parent.reference_shadow_frame
                    )
                else:
                    shadow_detected = False
                    shadow_frame_viz = shadow_frame
                    detection_type = "none"
                
                # Update last frames
                self.parent.last_exclamation_frame = exclamation_frame.copy()
                if not waiting_for_fish:
                    self.parent.last_shadow_frame = shadow_frame.copy()
                
                # Logic for fishing
                current_time = time.time()
                if exclamation_detected and (current_time - self.parent.last_detection_time) > self.parent.detection_cooldown:
                    self.parent.last_detection_time = current_time
                    self.parent.detection_count += 1
                    waiting_for_fish = False
                    
                    # Update UI using signals
                    self.detection_signal.emit(self.parent.detection_count)
                    self.status_signal.emit("Exclamation detected!")
                    
                    # Start the action sequence
                    self.in_action_sequence = True
                    self.action_sequence_step = 0
                    # Execute first action immediately
                    self._process_action_sequence()
                    
                elif shadow_detected and not waiting_for_fish and (current_time - self.parent.last_detection_time) > self.parent.detection_cooldown:
                    if detection_type == "shadow":
                        waiting_for_fish = True
                        self.status_signal.emit("Fish shadow detected!")
                
                # Control loop speed - sleep to reduce CPU usage
                time.sleep(0.03)
                
        except Exception as e:
            self.error_signal.emit(f"Fishing error: {str(e)}")
        finally:
            # Make sure flags are reset
            self.is_running = False
            self.in_action_sequence = False
            self.finished_signal.emit()

    def _process_action_sequence(self):
        """Process the current step in the action sequence"""
        if not self.in_action_sequence or self.action_sequence_step >= len(self.parent.action_sequence):
            self.in_action_sequence = False
            self.action_sequence_step = 0
            return
        
        # Get the current action
        action = self.parent.action_sequence[self.action_sequence_step]
        
        # Execute the action based on type
        action_type = action["action"]
        
        if action_type == "press_f":
            self.parent.key_sender.send_key('f')
            self.status_signal.emit("Pressing F")
        elif action_type == "press_esc":
            self.parent.key_sender.send_key('esc')
            self.status_signal.emit("Pressing ESC")
        elif action_type == "wait":
            # Update status to show we're waiting
            self.status_signal.emit(f"Waiting {action['delay']}s")
        
        # Wait for the specified delay
        time.sleep(action["delay"])
        
        # Move to next step
        self.action_sequence_step += 1
        
        # If we've reached the end, exit the sequence
        if self.action_sequence_step >= len(self.parent.action_sequence):
            self.in_action_sequence = False
            self.status_signal.emit("Running")
    
    def stop(self):
        """Stop the fishing process"""
        self.is_running = False
        self.is_paused = False
    
    def pause(self):
        """Pause the fishing process"""
        self.is_paused = True
    
    def resume(self):
        """Resume the fishing process"""
        self.is_paused = False


class AutoFisherQt(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("Auto Fisher (PyQt)")
        self.setGeometry(100, 100, 900, 600)
        self.setMinimumSize(800, 600)
        
        # Platform detection
        self.os_utils = OSUtilities()
        self.os_name = self.os_utils.get_os_name()
        
        # Initialize OS-specific modules
        self.region_selector = RegionSelector()
        self.game_focus = GameFocus()
        self.key_sender = KeySender()
        
        # Region parameters
        exclamation_region, shadow_region = self.os_utils.get_default_regions()
        self.exclamation_monitor = self.os_utils.create_monitor_dict(exclamation_region)
        self.shadow_monitor = self.os_utils.create_monitor_dict(shadow_region)
        
        # Status variables
        self.is_running = False
        self.is_paused = False
        self.detection_count = 0
        self.last_detection_time = 0
        self.detection_cooldown = 1.0  # Seconds between detections
        
        # Reference frames
        self.reference_exclamation_frame = None
        self.reference_shadow_frame = None
        self.last_exclamation_frame = None
        self.last_shadow_frame = None
        
        # Detection parameters
        self.exclamation_threshold = 30  # Pixel change threshold
        self.shadow_threshold = 20
        self.bait_threshold = 25
        self.min_exclamation_area = 100
        self.max_exclamation_area = 800
        self.min_shadow_area = 500
        self.max_shadow_area = 5000
        
        # Action sequence for fishing
        self.action_sequence = [
            {"action": "press_f", "delay": 0.0},   # Press F immediately
            {"action": "wait", "delay": 3.0},      # Wait 3 seconds
            {"action": "press_esc", "delay": 1.0}, # Press ESC, wait 1 second
            {"action": "wait", "delay": 1.0},      # Wait 1 more second
            {"action": "press_f", "delay": 1.0}    # Press F again, wait 1 second
        ]
        
        # Create the screen capture context
        self.sct = mss.mss()
        
        # Set up worker thread - but don't start the thread until needed
        self.fishing_thread = None
        self.fishing_worker = None
        
        # Build UI
        self.init_ui()
        
        # Start preview timer
        self.preview_timer = QTimer(self)
        self.preview_timer.timeout.connect(self.update_preview)
        self.preview_timer.start(100)  # Update every 100ms
        
        # Try to get initial frames for preview
        try:
            self.capture_blank_frames()
        except Exception as e:
            print(f"Could not capture initial frames: {e}")
    
    def capture_blank_frames(self):
        """Capture blank frames just for preview"""
        # Create blank black images for preview until actual frames are captured
        self.last_exclamation_frame = np.zeros((300, 400, 3), dtype=np.uint8)
        cv2.putText(self.last_exclamation_frame, "Exclamation Region", (80, 150), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        self.last_shadow_frame = np.zeros((300, 400, 3), dtype=np.uint8)
        cv2.putText(self.last_shadow_frame, "Shadow Region", (100, 150), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    def init_ui(self):
        """Initialize the user interface"""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Control panel (left side)
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        splitter.addWidget(control_panel)
        
        # Preview panel (right side)
        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        splitter.addWidget(preview_panel)
        
        # Set initial splitter sizes (30% controls, 70% preview)
        splitter.setSizes([300, 700])
        
        # ===== Control Panel =====
        # OS Detection
        os_label = QLabel(f"Detected OS: {self.os_name}")
        os_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        control_layout.addWidget(os_label)
        
        # Buttons section
        # Region setup
        self.region_button = QPushButton("Setup Detection Regions")
        self.region_button.clicked.connect(self.setup_regions)
        control_layout.addWidget(self.region_button)
        
        # Capture reference frames
        self.reference_button = QPushButton("Capture Reference Frames")
        self.reference_button.clicked.connect(self.capture_reference_frames)
        control_layout.addWidget(self.reference_button)
        
        # Start/Stop button
        self.start_stop_button = QPushButton("Start Fishing")
        self.start_stop_button.clicked.connect(self.toggle_fishing)
        control_layout.addWidget(self.start_stop_button)
        
        # Pause/Resume button
        self.pause_resume_button = QPushButton("Pause")
        self.pause_resume_button.clicked.connect(self.toggle_pause)
        self.pause_resume_button.setEnabled(False)
        control_layout.addWidget(self.pause_resume_button)
        
        # Status section
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("font-size: 11px;")
        status_layout.addWidget(self.status_label)
        
        self.detection_label = QLabel("Detections: 0")
        self.detection_label.setStyleSheet("font-size: 11px;")
        status_layout.addWidget(self.detection_label)
        
        control_layout.addWidget(status_group)
        
        # Parameters section
        param_group = QGroupBox("Detection Parameters")
        param_layout = QVBoxLayout(param_group)
        
        # Exclamation threshold
        param_layout.addWidget(QLabel("Exclamation Threshold:"))
        self.exclamation_slider = QSlider(Qt.Horizontal)
        self.exclamation_slider.setRange(5, 50)
        self.exclamation_slider.setValue(self.exclamation_threshold)
        self.exclamation_slider.valueChanged.connect(lambda v: self.update_parameter('exclamation_threshold', v))
        param_layout.addWidget(self.exclamation_slider)
        
        # Shadow threshold
        param_layout.addWidget(QLabel("Shadow Threshold:"))
        self.shadow_slider = QSlider(Qt.Horizontal)
        self.shadow_slider.setRange(5, 50)
        self.shadow_slider.setValue(self.shadow_threshold)
        self.shadow_slider.valueChanged.connect(lambda v: self.update_parameter('shadow_threshold', v))
        param_layout.addWidget(self.shadow_slider)
        
        control_layout.addWidget(param_group)
        
        # Add stretch to push controls to the top
        control_layout.addStretch(1)
        
        # ===== Preview Panel =====
        # Preview image
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_label.setFrameShape(QFrame.StyledPanel)
        self.preview_label.setStyleSheet("background-color: #222222;")
        preview_layout.addWidget(self.preview_label)
        
        # Information text
        info_text = """
        <h3>How to use:</h3>
        <ol>
            <li>Click "Setup Detection Regions" to position detection areas</li>
            <li>Click "Capture Reference Frames" when no fish or markers are visible</li>
            <li>Click "Start Fishing" to begin auto-fishing</li>
        </ol>
        
        <h3>Tips:</h3>
        <ul>
            <li>Position the exclamation region where '!' marks appear</li>
            <li>Position the shadow region where fish shadows are visible</li>
            <li>Adjust thresholds if detection is too sensitive or not sensitive enough</li>
        </ul>
        """
        info_label = QLabel()
        info_label.setText(info_text)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-size: 11px;")
        preview_layout.addWidget(info_label)
        
        # Status bar
        self.statusBar().showMessage(f"Auto Fisher ready - {self.os_name}")
    
    def update_parameter(self, param_name, value):
        """Update a detection parameter"""
        if hasattr(self, param_name):
            setattr(self, param_name, int(value))
    
    def setup_regions(self):
        """Run the interactive region setup"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "Stop fishing before setting up regions")
            return
        
        self.hide()  # Hide main window
        
        try:
            # Run the region selector
            exclamation_monitor, shadow_monitor = self.region_selector.interactive_region_setup()
            
            # Update monitors
            self.exclamation_monitor = exclamation_monitor
            self.shadow_monitor = shadow_monitor
            
            # Reset reference frames
            self.reference_exclamation_frame = None
            self.reference_shadow_frame = None
            
            QMessageBox.information(self, "Success", "Regions set successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error setting up regions: {e}")
        finally:
            self.show()  # Show main window again
    
    def capture_reference_frames(self):
        """Capture reference frames for both regions"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "Stop fishing before capturing reference frames")
            return
        
        try:
            # Capture frames
            self.reference_exclamation_frame = self.os_utils.capture_screen(self.sct, self.exclamation_monitor)
            self.reference_shadow_frame = self.os_utils.capture_screen(self.sct, self.shadow_monitor)
            
            if self.reference_exclamation_frame is not None and self.reference_shadow_frame is not None:
                # Also update last frames for preview
                self.last_exclamation_frame = self.reference_exclamation_frame.copy()
                self.last_shadow_frame = self.reference_shadow_frame.copy()
                
                QMessageBox.information(self, "Success", "Reference frames captured successfully")
                self.status_label.setText("Reference frames ready")
            else:
                QMessageBox.critical(self, "Error", "Failed to capture reference frames")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error capturing reference frames: {e}")
    
    def setup_worker_thread(self):
        """Set up the worker thread properly"""
        # Clean up existing thread if any
        if self.fishing_thread is not None:
            self.fishing_thread.quit()
            self.fishing_thread.wait()
        
        # Create and set up thread
        self.fishing_thread = QThread()
        self.fishing_worker = FishingWorker(self)
        self.fishing_worker.moveToThread(self.fishing_thread)
        
        # Connect signals
        self.fishing_worker.error_signal.connect(self.show_error)
        self.fishing_worker.status_signal.connect(self.update_status)
        self.fishing_worker.detection_signal.connect(self.update_detection_count)
        self.fishing_worker.finished_signal.connect(self.fishing_stopped)
        
        self.fishing_thread.started.connect(self.fishing_worker.start_fishing)
        
        # Start thread
        self.fishing_thread.start()
    
    def toggle_fishing(self):
        """Start or stop the fishing process"""
        if not self.is_running:
            # Check if reference frames exist
            if self.reference_exclamation_frame is None or self.reference_shadow_frame is None:
                result = QMessageBox.question(self, "Warning", 
                         "Reference frames have not been captured. This is recommended for best results.\n\nCapture reference frames now?",
                         QMessageBox.Yes | QMessageBox.No)
                if result == QMessageBox.Yes:
                    self.capture_reference_frames()
                    return
            
            # Start fishing in worker thread
            self.is_running = True
            self.is_paused = False
            
            # Set up the worker thread
            self.setup_worker_thread()
            
            self.start_stop_button.setText("Stop Fishing")
            self.pause_resume_button.setEnabled(True)
            self.status_label.setText("Running")
            self.statusBar().showMessage("Fishing started")
        else:
            # Stop fishing
            if self.fishing_worker:
                self.fishing_worker.stop()
            self.start_stop_button.setText("Starting Fishing")
            self.pause_resume_button.setEnabled(False)
            self.pause_resume_button.setText("Pause")
            self.status_label.setText("Stopping...")
            self.statusBar().showMessage("Fishing stopping...")
    
    def fishing_stopped(self):
        """Called when fishing has stopped"""
        self.is_running = False
        self.is_paused = False
        self.start_stop_button.setText("Start Fishing")
        self.pause_resume_button.setEnabled(False)
        self.pause_resume_button.setText("Pause")
        self.status_label.setText("Stopped")
        self.statusBar().showMessage("Fishing stopped")
    
    def toggle_pause(self):
        """Pause or resume the fishing process"""
        if not self.is_running or not self.fishing_worker:
            return
        
        if not self.is_paused:
            self.is_paused = True
            self.fishing_worker.pause()
            self.pause_resume_button.setText("Resume")
            self.status_label.setText("Paused")
            self.statusBar().showMessage("Fishing paused")
        else:
            self.is_paused = False
            self.fishing_worker.resume()
            self.pause_resume_button.setText("Pause")
            self.status_label.setText("Running")
            self.statusBar().showMessage("Fishing resumed")
    
    def update_status(self, status):
        """Update the status label"""
        self.status_label.setText(status)
    
    def update_detection_count(self, count):
        """Update the detection count label"""
        self.detection_count = count
        self.detection_label.setText(f"Detections: {count}")
    
    def show_error(self, error_message):
        """Show error message"""
        QMessageBox.critical(self, "Error", error_message)
    
    def update_preview(self):
        """Update the preview image"""
        try:
            # Check if frames exist
            if self.last_exclamation_frame is not None and self.last_shadow_frame is not None:
                # Resize for display
                ex_height, ex_width = self.last_exclamation_frame.shape[:2]
                sh_height, sh_width = self.last_shadow_frame.shape[:2]
                
                # Calculate scaling to fit within preview area
                preview_width = 400  # Width for each preview image
                
                ex_scale = preview_width / ex_width
                sh_scale = preview_width / sh_width
                
                ex_display = cv2.resize(self.last_exclamation_frame, (preview_width, int(ex_height * ex_scale)))
                sh_display = cv2.resize(self.last_shadow_frame, (preview_width, int(sh_height * sh_scale)))
                
                # Add labels
                cv2.putText(ex_display, "Exclamation Region", (10, 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(sh_display, "Shadow/Bait Region", (10, 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Add status
                status = "RUNNING" if self.is_running and not self.is_paused else "PAUSED" if self.is_paused else "IDLE"
                
                if self.fishing_worker and self.fishing_worker.in_action_sequence:
                    status = f"ACTION ({self.fishing_worker.action_sequence_step+1}/{len(self.action_sequence)})"
                
                cv2.putText(ex_display, status, (10, ex_display.shape[0]-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                
                # Combine horizontally
                combined = np.hstack((ex_display, sh_display))
                
                # Convert BGR to RGB for PyQt
                rgb_image = cv2.cvtColor(combined, cv2.COLOR_BGR2RGB)
                
                # Convert to QImage and then to QPixmap
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qt_image)
                
                # Update label
                self.preview_label.setPixmap(pixmap)
                self.preview_label.setAlignment(Qt.AlignCenter)
            else:
                # If frames don't exist yet, create a blank image
                self.capture_blank_frames()
                
                # Convert to QImage
                frame = np.hstack((self.last_exclamation_frame, self.last_shadow_frame))
                rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb_image.shape
                bytes_per_line = ch * w
                qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qt_image)
                
                # Update label
                self.preview_label.setPixmap(pixmap)
                self.preview_label.setAlignment(Qt.AlignCenter)
        except Exception as e:
            print(f"Error updating preview: {e}")
    
    def detect_exclamation_mark(self, frame, reference_frame):
        """Detect the exclamation mark using frame differencing and contour detection"""
        if reference_frame is None:
            return False, frame
        
        # Convert to grayscale for faster processing
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_reference = cv2.cvtColor(reference_frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate absolute difference to detect changes
        frame_diff = cv2.absdiff(gray_frame, gray_reference)
        
        # Apply threshold to get binary image
        _, thresh = cv2.threshold(frame_diff, self.exclamation_threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours in the binary image
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by area and shape
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_exclamation_area < area < self.max_exclamation_area:
                # Additional verification - check for bright color (exclamation marks are usually bright)
                x, y, w, h = cv2.boundingRect(contour)
                roi = frame[y:y+h, x:x+w]
                
                # Check if there's a bright area that stands out
                hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                v_channel = hsv_roi[:, :, 2]  # Value channel (brightness)
                
                # If the region has high brightness, consider it an exclamation mark
                if np.mean(v_channel) > 160:
                    # Draw rectangle for visualization
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, "!", (x+w//2-5, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    return True, frame
        
        return False, frame
    
    def detect_fish_shadow(self, frame, reference_frame):
        """Detect fish shadows and bouncy bait in water"""
        if reference_frame is None:
            return False, frame, "none"
        
        # Convert to grayscale for faster processing
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_reference = cv2.cvtColor(reference_frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate absolute difference to detect motion
        frame_diff = cv2.absdiff(gray_frame, gray_reference)
        
        # Apply threshold for motion detection
        _, thresh = cv2.threshold(frame_diff, self.shadow_threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours for motion
        motion_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # For fish shadow detection - look for darker regions
        # Apply blur for noise reduction
        blurred = cv2.GaussianBlur(gray_frame, (9, 9), 0)
        _, shadow_thresh = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours of shadow regions
        shadow_contours, _ = cv2.findContours(shadow_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Check for bouncy bait (usually has motion and specific size/shape)
        for contour in motion_contours:
            area = cv2.contourArea(contour)
            if 100 < area < 500:  # Bouncy bait is usually smaller than fish shadows
                x, y, w, h = cv2.boundingRect(contour)
                
                # Check if it's a bouncy motion (ratio of width/height)
                if 0.7 < w/h < 1.3:  # Approximately square/circular shape
                    # Draw rectangle for visualization
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
                    cv2.putText(frame, "Bait", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    return True, frame, "bait"
        
        # Check for fish shadows (usually larger dark areas with some motion)
        for contour in shadow_contours:
            area = cv2.contourArea(contour)
            if self.min_shadow_area < area < self.max_shadow_area:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Calculate average darkness of the region
                roi = gray_frame[y:y+h, x:x+w]
                darkness = 255 - np.mean(roi)
                
                # If it's dark enough to be a shadow
                if darkness > 50:
                    # Draw rectangle for visualization
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                    cv2.putText(frame, "Shadow", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                    return True, frame, "shadow"
        
        return False, frame, "none"
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop fishing thread if running
        if self.is_running and self.fishing_worker:
            self.fishing_worker.stop()
        
        # Stop the thread
        if self.fishing_thread:
            self.fishing_thread.quit()
            self.fishing_thread.wait()
        
        # Close mss context
        self.sct.close()
        
        event.accept()


# Main application entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Set application style to be consistent across platforms
    app.setStyle("Fusion")
    
    # Apply stylesheet for a modern look
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #f0f0f0;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #cccccc;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px;
        }
        QPushButton {
            background-color: #2a82da;
            color: white;
            border: none;
            border-radius: 3px;
            padding: 6px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #3a92ea;
        }
        QPushButton:pressed {
            background-color: #1a72ca;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            color: #888888;
        }
        QSlider::groove:horizontal {
            border: 1px solid #bbb;
            background: white;
            height: 10px;
            border-radius: 4px;
        }
        QSlider::handle:horizontal {
            background: #2a82da;
            border: 1px solid #5c5c5c;
            width: 18px;
            margin: -2px 0;
            border-radius: 3px;
        }
    """)
    
    window = AutoFisherQt()
    window.show()
    sys.exit(app.exec_()) 