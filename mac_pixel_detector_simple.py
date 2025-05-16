import sys
import time
import threading
import queue
import datetime
import numpy as np
import pyautogui
import mss
import cv2  # For efficient image processing
from PIL import Image
import matplotlib.pyplot as plt
import subprocess  # For running AppleScript to focus on windows
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSlider, QFrame, QSplitter, QTextEdit,
    QGroupBox, QMessageBox, QDialog, QDialogButtonBox, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect, QPoint, QSize, QThread, QObject, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QImage, QFont, QPainterPath
import os


class PixelChangeDetector(QObject):
    """Core detector class for monitoring pixel changes in a screen region"""
    detection_signal = pyqtSignal()
    log_signal = pyqtSignal(str)
    frame_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.THRESHOLD = 0.05  # Default threshold for pixel change detection
        self.is_running = False
        self.is_paused = False
        
        # Screen capture region
        self.region = None  # (left, top, right, bottom)
        
        # Game window info for focusing
        self.game_process_name = ""
        self.game_window_name = "PLAY TOGETHER"
        
        # Frames for comparison
        self.current_frame = None
        self.previous_frame = None
        self.reference_frame = None
        self.diff_frame = None
        self.color_frame = None
        
        # Change history
        self.change_history = []
        
        # Last detection time for cooldown
        self.last_detection_time = 0
        self.detection_cooldown = 0.5  # Seconds between detections
        
        # Thread control
        self.detection_thread = None
        self.stop_requested = False
        
        # Noise reduction parameters
        self.apply_blur = True
        self.blur_kernel_size = 3
        
        # Bright background detection
        self.enhanced_bright_detection = True  # Enable enhanced detection for bright backgrounds
        
        # Performance optimization - faster capture rate
        self.capture_interval = 0.01  # 10ms between captures (100fps) - decreased from 0.05
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.last_successful_capture = 0
        
        # Optimization: Use mss context manager only once
        self.sct = mss.mss()
        
        # Action sequence control with standardized delay times
        self.in_action_sequence = False
        self.action_sequence_step = 0
        
        # Template images for repair dialog and button detection
        self.repair_dialog_template = None
        self.repair_button_template = None
        
        # Template matching thresholds
        self.template_match_threshold = 0.7
        
        # Path to template images - will be loaded when needed
        self.repair_dialog_path = "repair.png"
        self.repair_button_path = "button.png"
        
        # Updated action sequence with repair detection and button clicking
        self.action_sequence = [
            {"action": "press_f", "delay": 0.0},
            {"action": "wait", "delay": 6.0},
            {"action": "press_esc", "delay": 2.0},
            {"action": "wait", "delay": 2.0},
            {"action": "press_f", "delay": 0.5},  # Wait 0.5s after pressing F
            {"action": "check_repair_dialog", "delay": 0.0},  # Check for repair dialog
            {"action": "click_repair_button", "delay": 0.5},  # Click repair button if found
            {"action": "press_esc", "delay": 1.0},  # Press ESC and wait 1s
            {"action": "press_f", "delay": 1.0}    # Final F press to end sequence
        ]
        
    def log(self, message):
        """Log a message"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_signal.emit(formatted_message)
        
    def perform_health_check(self):
        """Check detector health and attempt recovery if needed"""
        current_time = time.time()
        
        # Check if we've had too many consecutive failures
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.log("Too many consecutive failures, attempting recovery...")
            # Reset state
            self.current_frame = None
            self.diff_frame = None
            
            # Try to recapture reference frame
            self.capture_reference()
            
            # Reset failure counter
            self.consecutive_failures = 0
            
        # Check if we haven't had a successful capture in a while
        if self.last_successful_capture > 0 and (current_time - self.last_successful_capture) > 5.0:
            self.log("No successful captures detected, attempting recovery...")
            self.capture_reference()
            
        return True
        
    def load_template_images(self):
        """Load template images for repair dialog and button detection"""
        try:
            # Check if template files exist with absolute paths
            repair_dialog_abs_path = os.path.abspath(self.repair_dialog_path)
            repair_button_abs_path = os.path.abspath(self.repair_button_path)
            
            self.log(f"Looking for repair dialog template at: {repair_dialog_abs_path}")
            self.log(f"Looking for repair button template at: {repair_button_abs_path}")
            
            if os.path.exists(repair_dialog_abs_path):
                self.repair_dialog_template = cv2.imread(repair_dialog_abs_path)
                if self.repair_dialog_template is None:
                    self.log(f"Error: Failed to load repair dialog template despite file existing")
                else:
                    self.log(f"Loaded repair dialog template: {repair_dialog_abs_path}")
                    self.log(f"Template size: {self.repair_dialog_template.shape}")
            else:
                self.log(f"Warning: Repair dialog template not found at {repair_dialog_abs_path}")
                
            if os.path.exists(repair_button_abs_path):
                self.repair_button_template = cv2.imread(repair_button_abs_path)
                if self.repair_button_template is None:
                    self.log(f"Error: Failed to load repair button template despite file existing")
                else:
                    self.log(f"Loaded repair button template: {repair_button_abs_path}")
                    self.log(f"Template size: {self.repair_button_template.shape}")
            else:
                self.log(f"Warning: Repair button template not found at {repair_button_abs_path}")
                
            # Lower the matching threshold for more permissive matching
            self.template_match_threshold = 0.5
            self.log(f"Repair template matching threshold set to: {self.template_match_threshold}")
                
            return self.repair_dialog_template is not None and self.repair_button_template is not None
                
        except Exception as e:
            self.log(f"Error loading template images: {e}")
            import traceback
            self.log(traceback.format_exc())
            return False
    
    def capture_screen(self):
        """Capture the defined region of the screen with optimized performance"""
        try:
            if not self.region:
                self.log("No region selected")
                return None
                
            left, top, right, bottom = self.region
            width = right - left
            height = bottom - top
            
            # Using reused mss context manager for better performance
            monitor = {"top": top, "left": left, "width": width, "height": height}
            screenshot = self.sct.grab(monitor)
            
            # Use numpy array with zero copy when possible
            frame = np.array(screenshot, dtype=np.uint8)
            
            # Store color frame for visualization
            self.color_frame = frame.copy()
            
            # Convert to grayscale for processing - more efficient conversion
            if len(frame.shape) > 2:
                if frame.shape[2] == 4:  # BGRA format from mss
                    # Faster grayscale conversion using weighted sum
                    frame = np.dot(frame[..., :3], [0.114, 0.587, 0.299])
                else:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Ensure uint8 type
                frame = frame.astype(np.uint8)
            
            # Apply Gaussian blur to reduce noise if enabled - use small kernel for speed
            if self.apply_blur and self.blur_kernel_size > 0:
                frame = cv2.GaussianBlur(frame, (self.blur_kernel_size, self.blur_kernel_size), 0)
            
            # Update health check variables
            self.last_successful_capture = time.time()
            self.consecutive_failures = 0
            
            return frame
                
        except Exception as e:
            self.log(f"Error capturing screen: {e}")
            self.consecutive_failures += 1
            return None
            
    def calculate_frame_difference(self, frame1, frame2):
        """Calculate the difference between two frames with improved handling for bright backgrounds"""
        if frame1 is None or frame2 is None:
            return None, 0
            
        # Ensure frames have same dimensions
        if frame1.shape != frame2.shape:
            # Resize to match - use faster INTER_NEAREST for performance
            frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]), interpolation=cv2.INTER_NEAREST)
            
        # Ensure both frames are grayscale for accurate comparison
        if len(frame1.shape) == 3 and len(frame2.shape) == 2:
            # Convert frame1 to grayscale
            frame1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        elif len(frame1.shape) == 2 and len(frame2.shape) == 3:
            # Convert frame2 to grayscale
            frame2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        elif len(frame1.shape) == 3 and len(frame2.shape) == 3:
            # Convert both to grayscale
            frame1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            frame2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            
        # Base threshold value
        threshold_base = 30  # Default threshold for significant change
        
        if self.enhanced_bright_detection:
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to improve contrast
            # This helps with detecting changes in bright backgrounds
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            frame1_eq = clahe.apply(frame1)
            frame2_eq = clahe.apply(frame2)
                
            # Calculate absolute difference from contrast-enhanced images
            diff_frame = cv2.absdiff(frame1_eq, frame2_eq)
            
            # Identify bright areas
            bright_mask = frame1 > 180
            
            # Apply the adaptive threshold to get binary difference
            _, thresholded_diff = cv2.threshold(diff_frame, threshold_base, 255, cv2.THRESH_BINARY)
            
            # Additional processing for bright regions to enhance sensitivity
            if np.any(bright_mask):
                # Apply a more sensitive threshold to bright areas
                bright_diff = cv2.bitwise_and(diff_frame, diff_frame, mask=bright_mask.astype(np.uint8) * 255)
                _, bright_thresh = cv2.threshold(bright_diff, threshold_base // 2, 255, cv2.THRESH_BINARY)
                
                # Combine normal threshold with enhanced bright area threshold
                thresholded_diff = cv2.bitwise_or(thresholded_diff, bright_thresh)
        else:
            # Standard detection method
            diff_frame = cv2.absdiff(frame1, frame2)
            _, thresholded_diff = cv2.threshold(diff_frame, threshold_base, 255, cv2.THRESH_BINARY)
        
        # Optional: use morphological operations to reduce noise further
        # Using smaller kernel and simpler operation for better performance
        kernel = np.ones((2, 2), np.uint8)
        thresholded_diff = cv2.morphologyEx(thresholded_diff, cv2.MORPH_OPEN, kernel)
        
        # Calculate percentage efficiently by counting non-zero pixels
        non_zero_pixels = cv2.countNonZero(thresholded_diff)
        total_pixels = frame1.size  # More efficient than shape[0] * shape[1]
        change_percent = non_zero_pixels / total_pixels
        
        # Store the thresholded difference for visualization
        self.diff_frame = thresholded_diff
        
        return thresholded_diff, change_percent
        
    def capture_reference(self):
        """Capture a reference frame"""
        if self.region:
            success = self.capture_screen() is not None
            if success:
                self.reference_frame = self.color_frame
                self.log("Reference frame captured")
                return True
        else:
            self.log("You must select a region first")
            return False
    
    def start_detection(self):
        """Start the detection process"""
        if not self.region:
            self.log("You must select a region first")
            return
            
        # Set running state
        self.is_running = True
        self.is_paused = False
        self.stop_requested = False
        self.change_history = []
        self.consecutive_failures = 0
        self.last_successful_capture = 0
        self.in_action_sequence = False
        self.action_sequence_step = 0
        
        # Try to find the game window if we don't have its info yet
        if not self.game_process_name or not self.game_window_name:
            self.find_game_window()
        
        # Always clear and recapture the reference frame when starting
        self.reference_frame = None
        self.log("Capturing new reference frame...")
        if not self.capture_reference():
            self.log("Failed to capture reference frame. Please check region selection.")
            self.is_running = False
            return
            
        self.previous_frame = self.reference_frame
        
        # Load template images if not already loaded
        if self.repair_dialog_template is None or self.repair_button_template is None:
            self.load_template_images()
        
        # Start detection thread
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        self.log("Detection started")
        
    def stop_detection(self):
        """Stop the detection process"""
        self.stop_requested = True
        self.is_running = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=1.0)
            
        # Reset state
        self.is_running = False
        self.is_paused = False
        self.stop_requested = False
        self.change_history = []
        self.consecutive_failures = 0
        self.last_successful_capture = 0
        self.in_action_sequence = False
        self.action_sequence_step = 0
            
        self.log("Detection stopped")
    
    def toggle_pause(self):
        """Pause or resume detection"""
        self.is_paused = not self.is_paused
        
        if self.is_paused:
            self.log("Detection paused")
        else:
            self.log("Detection resumed")
            
    def _detection_loop(self):
        """Main detection loop with the action sequence from pixel_change_trigger.py"""
        # Initialize local variables for performance
        local_threshold = self.THRESHOLD
        local_interval = self.capture_interval
        
        while self.is_running and not self.stop_requested:
            try:
                # Skip if paused
                if self.is_paused:
                    time.sleep(local_interval * 2)
                    continue
                
                # Perform health check periodically
                self.perform_health_check()
                
                # Handle action sequence if one is in progress
                if self.in_action_sequence:
                    self._process_action_sequence()
                    continue
                    
                # Capture current frame
                self.current_frame = self.capture_screen()
                
                if self.current_frame is None:
                    time.sleep(local_interval)
                    continue
                    
                # Determine which frame to compare against
                compare_frame = self.reference_frame if self.reference_frame is not None else self.previous_frame
                
                if compare_frame is None:
                    self.capture_reference()
                    time.sleep(local_interval)
                    continue
                
                # Calculate difference
                self.diff_frame, change_percent = self.calculate_frame_difference(
                    self.current_frame, compare_frame
                )
                
                # Store in history
                self.change_history.append(change_percent)
                if len(self.change_history) > 100:
                    self.change_history = self.change_history[-100:]
                    
                # Emit signal for UI update - increased to 30fps (33ms) for more responsive display
                current_time = time.time()
                if not hasattr(self, '_last_ui_update') or (current_time - getattr(self, '_last_ui_update', 0)) > 0.033:
                    self.frame_updated.emit()
                    self._last_ui_update = current_time
                
                # Check for detection with cooldown
                if (change_percent > local_threshold and 
                        (current_time - self.last_detection_time) > self.detection_cooldown):
                    self.log(f"Change detected! {change_percent:.2%}")
                    self.last_detection_time = current_time
                    
                    # Start the action sequence
                    self.in_action_sequence = True
                    self.action_sequence_step = 0
                    
                    # Execute first action immediately without delay
                    self._process_action_sequence()
                    
                    # Emit signal to trigger UI update AFTER first action is already processed
                    self.detection_signal.emit()
                    
                    continue
                
                # Store current frame as previous for next comparison
                self.previous_frame = self.current_frame
                
                # Control capture rate - faster loop for better responsiveness
                time.sleep(local_interval)
                
            except Exception as e:
                self.log(f"Error in detection loop: {e}")
                self.consecutive_failures += 1
                time.sleep(local_interval)
                
        # Cleanup when loop exits
        self.log("Detection thread exiting")
        
    def _process_action_sequence(self):
        """Process the current step in the action sequence"""
        if not self.in_action_sequence or self.action_sequence_step >= len(self.action_sequence):
            self.in_action_sequence = False
            self.action_sequence_step = 0
            return
            
        # Get the current action
        action = self.action_sequence[self.action_sequence_step]
        
        # Execute the action based on type
        action_type = action["action"]
        
        # Special case for first F key press (step 0) - execute immediately with high priority
        if self.action_sequence_step == 0 and action_type == "press_f":
            self.log(f"Action sequence: Pressing F key (IMMEDIATE)")
            # Execute F key press with high priority
            self._send_f_key()
        else:
            # Normal action execution
            if action_type == "press_f":
                self.log(f"Action sequence: Pressing F key")
                self._send_f_key()
            elif action_type == "press_esc":
                self.log(f"Action sequence: Pressing ESC key")
                self._send_esc_key()
            elif action_type == "wait":
                self.log(f"Action sequence: Waiting {action['delay']}s")
                # No actual action needed for wait
                pass
            elif action_type == "check_repair_dialog":
                self.log(f"Action sequence: Checking for repair dialog")
                if not self._check_repair_dialog():
                    # Skip repair button click if no dialog found
                    self.log("No repair dialog found, skipping repair button click")
                    self.action_sequence_step += 1
            elif action_type == "click_repair_button":
                self.log(f"Action sequence: Clicking repair button")
                self._click_repair_button()
        
        # Wait for the specified delay AFTER executing the action
        time.sleep(action["delay"])
        
        # Move to next step
        self.action_sequence_step += 1
        
        # If we've reached the end, exit the sequence
        if self.action_sequence_step >= len(self.action_sequence):
            self.in_action_sequence = False
            self.log("Action sequence completed")
            
            # Take a new reference frame after completing the sequence
            self.capture_reference()
            
    def _check_repair_dialog(self):
        """Check if the repair dialog is present in the current screen"""
        # Make sure we have the template loaded
        if self.repair_dialog_template is None:
            success = self.load_template_images()
            if not success or self.repair_dialog_template is None:
                self.log("Error: Repair dialog template not loaded")
                return False
                
        try:
            # Capture the current screen
            screen_frame = self.capture_screen()
            if self.color_frame is None:
                self.log("Error: Failed to capture screen for repair dialog check")
                return False
                
            # Get a copy of the current color frame for debugging and visualization
            display_frame = self.color_frame.copy()
            
            # Convert template to grayscale if needed
            if len(self.repair_dialog_template.shape) == 3 and self.repair_dialog_template.shape[2] == 3:
                template_gray = cv2.cvtColor(self.repair_dialog_template, cv2.COLOR_BGR2GRAY)
            else:
                template_gray = self.repair_dialog_template
                
            # Convert screen to grayscale
            if len(self.color_frame.shape) == 3 and self.color_frame.shape[2] == 3:
                screen_gray = cv2.cvtColor(self.color_frame, cv2.COLOR_BGR2GRAY)
            else:
                screen_gray = self.color_frame
                
            # Log template and screen dimensions for debugging
            self.log(f"Repair dialog template dimensions: {template_gray.shape}")
            self.log(f"Screen dimensions: {screen_gray.shape}")
            
            # Check if the screen is big enough for the template
            if (screen_gray.shape[0] < template_gray.shape[0] or 
                screen_gray.shape[1] < template_gray.shape[1]):
                self.log("Error: Screen is smaller than template, cannot perform matching")
                return False
                
            # Perform template matching
            self.log("Performing template matching for repair dialog...")
            result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            self.log(f"Repair dialog match confidence: {max_val:.2f}")
            
            # Draw rectangle around match on debug frame
            top_left = max_loc
            bottom_right = (top_left[0] + template_gray.shape[1], top_left[1] + template_gray.shape[0])
            cv2.rectangle(display_frame, top_left, bottom_right, (0, 255, 0), 2)
            
            # Save debug image if confidence is above a minimum threshold
            if max_val > 0.3:
                debug_path = "repair_dialog_match.png"
                cv2.imwrite(debug_path, display_frame)
                self.log(f"Saved debug image to: {debug_path}")
            
            # If the match is good enough, return the position
            if max_val >= self.template_match_threshold:
                self.log(f"Repair dialog found at {max_loc} with confidence {max_val:.2f}")
                # Store the dialog position for later use
                self.repair_dialog_position = max_loc
                self.repair_dialog_size = (template_gray.shape[1], template_gray.shape[0])
                return True
            
            return False
            
        except Exception as e:
            self.log(f"Error checking for repair dialog: {e}")
            import traceback
            self.log(traceback.format_exc())
            return False
    
    def _click_repair_button(self):
        """Find and click the repair button in the dialog"""
        try:
            # Check if we have already found the repair dialog
            if not hasattr(self, 'repair_dialog_position'):
                self.log("No repair dialog position found, checking again")
                if not self._check_repair_dialog():
                    self.log("Could not find repair dialog for button click")
                    return False
                    
            # Make sure we have the template loaded
            if self.repair_button_template is None:
                success = self.load_template_images()
                if not success or self.repair_button_template is None:
                    self.log("Error: Repair button template not loaded")
                    return False
            
            # Capture the current screen
            self.capture_screen()
            if self.color_frame is None:
                self.log("Error: Failed to capture screen for repair button check")
                return False
                
            # Get a copy of the current color frame for debugging
            display_frame = self.color_frame.copy()
            
            # ======== COLOR-BASED DETECTION ========
            # Try color-based detection for blue/green button first
            self.log("Attempting color-based detection for blue/green button...")
            
            # Convert to HSV for better color detection
            hsv_frame = cv2.cvtColor(self.color_frame, cv2.COLOR_BGR2HSV)
            
            # Define color ranges for blue with hint of green (teal/cyan range)
            # Lower and upper bounds for blue-green colors in HSV
            lower_blue_green = np.array([80, 50, 50])   # Cyan/teal lower bound
            upper_blue_green = np.array([110, 255, 255]) # Cyan/teal upper bound
            
            # Create a mask for the blue-green color
            blue_green_mask = cv2.inRange(hsv_frame, lower_blue_green, upper_blue_green)
            
            # Also try a more pure blue range as backup
            lower_blue = np.array([100, 50, 50])
            upper_blue = np.array([130, 255, 255])
            blue_mask = cv2.inRange(hsv_frame, lower_blue, upper_blue)
            
            # Combine masks
            combined_mask = cv2.bitwise_or(blue_green_mask, blue_mask)
            
            # Clean up mask with morphological operations
            kernel = np.ones((5, 5), np.uint8)
            clean_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
            clean_mask = cv2.morphologyEx(clean_mask, cv2.MORPH_OPEN, kernel)
            
            # Find contours of potential button areas
            contours, hierarchy = cv2.findContours(clean_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Debug - save color mask
            color_mask_path = "button_color_mask.png"
            cv2.imwrite(color_mask_path, clean_mask)
            self.log(f"Saved color mask to: {color_mask_path}")
            
            # Initialize variables for button detection
            button_center = None
            button_rect = None
            largest_area = 0
            
            # Process contours, looking for button-like shapes
            self.log(f"Found {len(contours)} potential button contours")
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # Log contour area for debugging
                self.log(f"Contour area: {area}")
                
                # Filter out very small contours
                if area < 200:  # Minimum area threshold
                    continue
                    
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter based on aspect ratio - buttons are usually wider than tall
                aspect_ratio = float(w) / h
                self.log(f"Contour aspect ratio: {aspect_ratio:.2f}")
                
                if 1.5 < aspect_ratio < 5.0:  # Typical button aspect ratio
                    # Draw contour and rectangle on debug image
                    cv2.drawContours(display_frame, [contour], -1, (0, 255, 255), 2)
                    cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    
                    # Compute center
                    center_x = x + w // 2
                    center_y = y + h // 2
                    
                    # Check for text or dollar sign - money buttons often have dollar signs or text
                    roi = self.color_frame[y:y+h, x:x+w]
                    
                    # Convert to grayscale for template matching
                    if roi.size > 0:  # Ensure ROI is not empty
                        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                        
                        # Simple check for brightness variation that might indicate text
                        stddev = np.std(roi_gray)
                        self.log(f"ROI standard deviation: {stddev:.2f}")
                        
                        # Higher stddev indicates more variation, likely text
                        if stddev > 15:  # Adjust this threshold based on testing
                            cv2.putText(display_frame, f"Button? {area:.0f}", (x, y-5), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                            
                            # If this is the largest valid button so far, save it
                            if area > largest_area:
                                largest_area = area
                                button_center = (center_x, center_y)
                                button_rect = (x, y, w, h)
            
            # If we found a button using color detection
            if button_center is not None:
                self.log(f"Found button using color detection at {button_center}")
                
                # Draw a crosshair at button center
                cv2.drawMarker(display_frame, button_center, (255, 0, 0), 
                              cv2.MARKER_CROSS, 20, 3)
                
                # Save button detection image
                button_detect_path = "button_color_detection.png"
                cv2.imwrite(button_detect_path, display_frame)
                self.log(f"Saved color detection image to: {button_detect_path}")
                
                # Adjust for the region offset if we're not capturing full screen
                click_x, click_y = button_center
                if self.region:
                    left, top, _, _ = self.region
                    click_x += left
                    click_y += top
                
                self.log(f"Clicking button from color detection at ({click_x}, {click_y})")
                
                # Use AppleScript to click the button
                click_script = f'''
                tell application "System Events"
                    set frontmost of process "{self.game_process_name}" to true
                    click at {{{click_x}, {click_y}}}
                end tell
                '''
                
                subprocess.run(['osascript', '-e', click_script], check=True, capture_output=True)
                self.log("Clicked repair button (color detection)")
                
                # Save a verification image after clicking
                time.sleep(0.5)  # Brief pause to let UI update
                self.capture_screen()
                if self.color_frame is not None:
                    verify_path = "after_button_click_color.png"
                    cv2.imwrite(verify_path, self.color_frame)
                    self.log(f"Saved verification image to: {verify_path}")
                
                return True
            
            # ======== TEMPLATE MATCHING (FALLBACK) ========
            # If color detection failed, fall back to template matching
            self.log("Color detection didn't find a button, falling back to template matching...")
                
            # Convert template to grayscale if needed
            if len(self.repair_button_template.shape) == 3 and self.repair_button_template.shape[2] == 3:
                button_gray = cv2.cvtColor(self.repair_button_template, cv2.COLOR_BGR2GRAY)
            else:
                button_gray = self.repair_button_template
                
            # Convert screen to grayscale
            if len(self.color_frame.shape) == 3 and self.color_frame.shape[2] == 3:
                screen_gray = cv2.cvtColor(self.color_frame, cv2.COLOR_BGR2GRAY)
            else:
                screen_gray = self.color_frame
                
            # Log dimensions
            self.log(f"Repair button template dimensions: {button_gray.shape}")
            self.log(f"Screen dimensions: {screen_gray.shape}")
            
            # Check if we should limit the search to just the dialog area
            if hasattr(self, 'repair_dialog_position') and hasattr(self, 'repair_dialog_size'):
                # Restrict search to the area of the dialog plus a margin
                dialog_x, dialog_y = self.repair_dialog_position
                dialog_w, dialog_h = self.repair_dialog_size
                margin = 50  # pixels margin around dialog
                
                # Ensure we don't go out of bounds
                roi_x = max(0, dialog_x - margin)
                roi_y = max(0, dialog_y - margin)
                roi_w = min(screen_gray.shape[1] - roi_x, dialog_w + 2*margin)
                roi_h = min(screen_gray.shape[0] - roi_y, dialog_h + 2*margin)
                
                # Extract region of interest
                screen_roi = screen_gray[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
                self.log(f"Using ROI for button detection: x={roi_x}, y={roi_y}, w={roi_w}, h={roi_h}")
                
                # Ensure ROI is big enough for template matching
                if (screen_roi.shape[0] < button_gray.shape[0] or 
                    screen_roi.shape[1] < button_gray.shape[1]):
                    self.log("ROI is too small for button template, using full screen")
                    screen_roi = screen_gray
                    roi_x, roi_y = 0, 0
                else:
                    # Draw ROI on debug image
                    cv2.rectangle(display_frame, (roi_x, roi_y), 
                                 (roi_x + roi_w, roi_y + roi_h), (0, 0, 255), 2)
            else:
                # Use the full screen
                screen_roi = screen_gray
                roi_x, roi_y = 0, 0
                
            # Try multiple template matching methods for better results
            methods = [
                (cv2.TM_CCOEFF_NORMED, "CCOEFF_NORMED"),
                (cv2.TM_CCORR_NORMED, "CCORR_NORMED"),
                (cv2.TM_SQDIFF_NORMED, "SQDIFF_NORMED")
            ]
            
            best_max_val = 0
            best_max_loc = None
            best_method = None
            
            for method, method_name in methods:
                # Perform template matching
                self.log(f"Trying button match with method: {method_name}")
                result = cv2.matchTemplate(screen_roi, button_gray, method)
                
                # For SQDIFF, best match is minimum; for others, it's maximum
                if method == cv2.TM_SQDIFF_NORMED:
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    curr_val = 1.0 - min_val  # Convert to a score where higher is better
                    curr_loc = min_loc
                else:
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    curr_val = max_val
                    curr_loc = max_loc
                    
                self.log(f"Method {method_name} confidence: {curr_val:.2f}")
                
                # Keep track of best result
                if curr_val > best_max_val:
                    best_max_val = curr_val
                    best_max_loc = curr_loc
                    best_method = method_name
            
            # Now use the best result
            if best_max_loc is not None:
                # Adjust for ROI offset
                max_loc = (best_max_loc[0] + roi_x, best_max_loc[1] + roi_y)
                max_val = best_max_val
                self.log(f"Best button match: method={best_method}, confidence={max_val:.2f}, loc={max_loc}")
                
                # Draw match on debug image
                top_left = max_loc
                bottom_right = (top_left[0] + button_gray.shape[1], top_left[1] + button_gray.shape[0])
                cv2.rectangle(display_frame, top_left, bottom_right, (255, 0, 0), 2)
                
                # Save debug image
                debug_path = "repair_button_match.png"
                cv2.imwrite(debug_path, display_frame)
                self.log(f"Saved button match debug image to: {debug_path}")
            else:
                self.log("No button match found")
                return False
            
            # If the match is good enough, click the button
            if max_val >= self.template_match_threshold:
                # Calculate button center position
                button_x = max_loc[0] + button_gray.shape[1] // 2
                button_y = max_loc[1] + button_gray.shape[0] // 2
                
                # Adjust for the region offset
                if self.region:
                    left, top, _, _ = self.region
                    button_x += left
                    button_y += top
                
                self.log(f"Clicking repair button at ({button_x}, {button_y})")
                
                # Use AppleScript to click the button
                click_script = f'''
                tell application "System Events"
                    set frontmost of process "{self.game_process_name}" to true
                    click at {{{button_x}, {button_y}}}
                end tell
                '''
                
                subprocess.run(['osascript', '-e', click_script], check=True, capture_output=True)
                self.log("Clicked repair button")
                
                # Save a verification image after clicking
                time.sleep(0.5)  # Brief pause to let UI update
                self.capture_screen()
                if self.color_frame is not None:
                    verify_path = "after_button_click.png"
                    cv2.imwrite(verify_path, self.color_frame)
                    self.log(f"Saved verification image to: {verify_path}")
                
                return True
            else:
                self.log(f"Button match confidence {max_val:.2f} below threshold {self.template_match_threshold}")
                return False
                
        except Exception as e:
            self.log(f"Error clicking repair button: {e}")
            import traceback
            self.log(traceback.format_exc())
            return False
            
    def _send_f_key(self):
        """Send F key press using AppleScript with game focus"""
        try:
            # Create a more targeted focus script if we have window details
            if self.game_process_name and self.game_window_name:
                # Integrated focus and keypress in a single AppleScript for maximum responsiveness
                focus_key_script = f'''
                tell application "System Events"
                    tell process "{self.game_process_name}"
                        set frontmost to true
                        tell window "{self.game_window_name}"
                            perform action "AXRaise"
                        end tell
                        # Immediate key press after focus, no delay
                        key code 3 # "f" key
                    end tell
                end tell
                '''
            else:
                # Fallback with integrated focus and key press
                focus_key_script = '''
                tell application "System Events"
                    # Try to find and focus on the game window
                    set targetFound to false
                    repeat with proc in application processes
                        if exists (windows of proc) then
                            repeat with w in windows of proc
                                if name of w contains "PLAY TOGETHER" or name of w contains "Play Together" then
                                    set frontmost of proc to true
                                    perform action "AXRaise" of w
                                    set targetFound to true
                                    exit repeat
                                end if
                            end repeat
                        end if
                        if targetFound then
                            # Immediate key press after focus found
                            key code 3 # "f" key
                            exit repeat
                        end if
                    end repeat
                    
                    # If no specific window found, just send the key anyway
                    if not targetFound then
                        key code 3 # "f" key
                    end if
                end tell
                '''
                
            # Execute the integrated focus+key script as a single operation
            subprocess.run(['osascript', '-e', focus_key_script], check=True, capture_output=True)
            self.log("F key sent to game (instant)")
            return True
        except Exception as e:
            self.log(f"Error sending F key: {e}")
            return False
            
    def _send_esc_key(self):
        """Send ESC key press using AppleScript with game focus"""
        try:
            # Create a more targeted focus script if we have window details
            if self.game_process_name and self.game_window_name:
                focus_script = f'''
                tell application "System Events"
                    tell process "{self.game_process_name}"
                        set frontmost to true
                        tell window "{self.game_window_name}"
                            perform action "AXRaise"
                        end tell
                    end tell
                    delay 0.2
                end tell
                '''
            else:
                # Fallback to generic window search
                focus_script = '''
                tell application "System Events"
                    set frontApp to first application process whose frontmost is true
                    set frontAppName to name of frontApp
                    
                    # Try to find and focus on the game window
                    set targetApp to "PLAY TOGETHER"
                    
                    # Look for window with PLAY TOGETHER in the title
                    repeat with proc in application processes
                        if exists (windows of proc) then
                            repeat with w in windows of proc
                                if name of w contains "PLAY TOGETHER" or name of w contains "Play Together" then
                                    set frontmost of proc to true
                                    perform action "AXRaise" of w
                                    delay 0.2
                                    exit repeat
                                end if
                            end repeat
                        end if
                    end repeat
                end tell
                '''
                
            # Execute the focus script
            subprocess.run(['osascript', '-e', focus_script], check=True, capture_output=True)
            self.log("Focused on game window")
            
            # Now send the ESC key
            key_script = '''
            tell application "System Events"
                key code 53  -- ESC key code
            end tell
            '''
            subprocess.run(['osascript', '-e', key_script], check=True, capture_output=True)
            self.log("ESC key sent to game")
            return True
        except Exception as e:
            self.log(f"Error sending ESC key: {e}")
            return False

    def find_game_window(self):
        """Try to find the game window"""
        try:
            # AppleScript to find windows with PLAY TOGETHER in the title
            script = '''
            tell application "System Events"
                set windowInfo to {}
                repeat with proc in application processes
                    set procName to name of proc
                    repeat with w in windows of proc
                        if name of w contains "PLAY TOGETHER" or name of w contains "Play Together" or name of w contains "play together" then
                            set winName to name of w
                            return {procName, winName}
                        end if
                    end repeat
                end repeat
                return ""
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=False)
            output = result.stdout.strip()
            
            if output:
                values = output.split(", ")
                if len(values) >= 2:
                    self.game_process_name = values[0]
                    self.game_window_name = values[1]
                    self.log(f"Found game window: {self.game_window_name} ({self.game_process_name})")
                    return True
                    
            self.log("Game window not found. Will use generic search during keystroke sending.")
            return False
            
        except Exception as e:
            self.log(f"Error finding game window: {e}")
            return False


class RegionSelectionOverlay(QDialog):
    """Overlay for selecting a screen region"""
    region_selected = pyqtSignal(tuple)
    
    def __init__(self, parent=None, default_size=100):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        
        # Force this window to be on top of all others
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        
        # Get screen information - full desktop size
        self.get_full_screen_dimensions()
        
        # Capture the current screen before showing the selection overlay
        self.background_pixmap = self.capture_screen_background()
        
        # Box dimensions (1.5:1 ratio)
        self.box_height = default_size
        self.box_width = int(default_size * 1.5)
        
        # For tracking mouse position
        self.mouse_pos = QPoint(self.screen_width // 2, self.screen_height // 2)
        
        # For drag and drop functionality
        self.is_dragging = False
        self.box_rect = QRect(
            self.mouse_pos.x() - self.box_width // 2,
            self.mouse_pos.y() - self.box_height // 2,
            self.box_width,
            self.box_height
        )
        
        # Matcha wood theme colors
        self.colors = {
            'bg_overlay': QColor(44, 36, 23, 150),     # Dark oak wood with transparency
            'bg_medium': QColor(67, 52, 31, 220),      # Medium oak wood with transparency
            'accent_green': QColor(141, 195, 112, 255), # Matcha green
            'accent_green_light': QColor(167, 207, 144, 200), # Light matcha green
            'accent_dark': QColor(93, 112, 82, 255),   # Dark grass green
            'text': QColor(248, 244, 227, 255),        # Cream text
            'border': QColor(94, 73, 41, 180)          # Oak border color with transparency
        }
        
        # For finding "PLAY TOGETHER" window
        self.play_together_rect = None
        self.find_play_together_window()
        
        # Initialize UI
        self._init_ui()
        
        # Ensure window is activated properly
        self.activateWindow()
        self.raise_()
        
    def get_full_screen_dimensions(self):
        """Get the full screen dimensions of the entire desktop"""
        # Get primary screen geometry
        primary_screen = QApplication.primaryScreen()
        self.screen_geometry = primary_screen.geometry()
        self.screen_width = self.screen_geometry.width()
        self.screen_height = self.screen_geometry.height()
        
        # Handle high DPI screens
        self.device_pixel_ratio = primary_screen.devicePixelRatio()
        
        # For macOS, try to get the full desktop size using mss directly
        try:
            with mss.mss() as sct:
                # Get monitor information for the primary display
                monitor_info = sct.monitors[1]  # 0 is all monitors combined, 1 is the primary
                
                # Store the native screen resolution
                self.full_width = monitor_info["width"]
                self.full_height = monitor_info["height"]
                
                # Debug output
                print(f"Qt Screen geometry: {self.screen_width}x{self.screen_height}")
                print(f"MSS Monitor size: {self.full_width}x{self.full_height}")
                print(f"Device pixel ratio: {self.device_pixel_ratio}")
                
                # Update screen size based on what we found
                if self.full_width > self.screen_width or self.full_height > self.screen_height:
                    # Use the larger dimensions for fullscreen capture
                    self.screen_width = self.full_width
                    self.screen_height = self.full_height
                    print(f"Using full screen size: {self.screen_width}x{self.screen_height}")
        except Exception as e:
            print(f"Error getting full screen dimensions: {e}")
            # Fallback to Qt screen geometry if mss fails
            self.full_width = self.screen_width
            self.full_height = self.screen_height
        
        # Set the window size to match the full screen
        self.setGeometry(0, 0, self.screen_width, self.screen_height)
        
    def capture_screen_background(self):
        """Capture the entire screen to use as background"""
        try:
            # Give a small delay to ensure any other windows are properly hidden
            time.sleep(0.3)
            
            # Capture the entire screen using MSS
            with mss.mss() as sct:
                # Capture the primary monitor at full resolution
                monitor_idx = 1  # Primary monitor
                monitor = sct.monitors[monitor_idx]
                
                # Ensure we get the full monitor, not just the application window
                screenshot = sct.grab(monitor)
                
                # Convert to numpy array
                img_array = np.array(screenshot)
                
                # Convert from BGRA to RGB for proper display
                if img_array.shape[2] == 4:  # If it has an alpha channel
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_BGRA2RGB)
                else:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
                
                # Get the dimensions of the captured image
                height, width, channels = img_array.shape
                print(f"Captured image dimensions: {width}x{height}")
                
                # Scale if the captured size doesn't match our window size
                if width != self.screen_width or height != self.screen_height:
                    img_array = cv2.resize(img_array, (self.screen_width, self.screen_height))
                    print(f"Resized image to: {self.screen_width}x{self.screen_height}")
                
                # Convert to QImage
                height, width, channels = img_array.shape
                bytes_per_line = channels * width
                
                q_img = QImage(img_array.data, width, height, 
                               bytes_per_line, QImage.Format.Format_RGB888)
                
                # Convert to QPixmap for drawing
                pixmap = QPixmap.fromImage(q_img)
                
                # Debug
                print(f"Final pixmap dimensions: {pixmap.width()}x{pixmap.height()}")
                
                return pixmap
        except Exception as e:
            print(f"Error capturing screen background: {e}")
            return None
    
    def _init_ui(self):
        """Initialize the UI components with matcha wood theme"""
        # Add label with instructions - more compact
        self.instructions = QLabel("Click and drag to move selection box. Release to place. (ESC to cancel)", self)
        self.instructions.setStyleSheet("""
            color: #F8F4E3; 
            background-color: rgba(67, 52, 31, 220); 
            padding: 8px;
            border-radius: 8px;
            font-family: Helvetica, Arial, sans-serif;
            font-weight: 500;
            font-size: 12px;
        """)
        self.instructions.setGeometry(
            (self.screen_width - 480) // 2,  # Center horizontally
            25,  # Position from top
            480,  # Width
            32   # Height
        )
        self.instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add "Position on PLAY TOGETHER" button - more compact
        self.play_together_button = QPushButton("Position on PLAY TOGETHER", self)
        self.play_together_button.setStyleSheet("""
            background-color: rgba(141, 195, 112, 220); 
            color: #2C2417; 
            border: none; 
            padding: 6px 12px;
            border-radius: 8px;
            font-family: Helvetica, Arial, sans-serif;
            font-weight: 600;
            font-size: 12px;
        """)
        self.play_together_button.setGeometry(self.screen_width - 220, 65, 200, 30)
        self.play_together_button.clicked.connect(self.position_on_play_together)
        
        # Show button only if PLAY TOGETHER window was found
        self.play_together_button.setVisible(self.play_together_rect is not None)
        
    def find_play_together_window(self):
        """Try to find the PLAY TOGETHER game window using AppleScript"""
        try:
            # AppleScript to find windows with PLAY TOGETHER in the title and get more details
            script = '''
            tell application "System Events"
                set windowInfo to {}
                repeat with proc in application processes
                    set procName to name of proc
                    repeat with w in windows of proc
                        if name of w contains "PLAY TOGETHER" or name of w contains "Play Together" or name of w contains "play together" then
                            set winPos to position of w
                            set winSize to size of w
                            set winName to name of w
                            return {item 1 of winPos, item 2 of winPos, item 1 of winSize, item 2 of winSize, procName, winName}
                        end if
                    end repeat
                end repeat
                return ""
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=False)
            if result.stdout.strip():
                try:
                    # Parse the result: left, top, width, height, process name, window name
                    values = result.stdout.strip().split(", ")
                    if len(values) >= 4:
                        left = int(values[0])
                        top = int(values[1])
                        width = int(values[2])
                        height = int(values[3])
                        
                        # Store process name and window name if available
                        self.play_together_proc = values[4] if len(values) > 4 else ""
                        self.play_together_name = values[5] if len(values) > 5 else "PLAY TOGETHER"
                        
                        self.play_together_rect = QRect(left, top, width, height)
                        print(f"Found game window: {self.play_together_name} ({self.play_together_proc}) at {left},{top} size {width}x{height}")
                        return True
                except Exception as e:
                    print(f"Error parsing window dimensions: {e}")
                    
            # Alternative approach - try to list all windows for debugging
            script2 = '''
            tell application "System Events"
                set allWindows to {}
                repeat with proc in application processes
                    set procName to name of proc
                    repeat with w in windows of proc
                        set winName to name of w
                        set entry to procName & ": " & winName
                        set allWindows to allWindows & entry & return
                    end repeat
                end repeat
                return allWindows
            end tell
            '''
            
            result2 = subprocess.run(['osascript', '-e', script2], capture_output=True, text=True, check=False)
            print(f"Available windows: {result2.stdout}")
            
            return False
        except Exception as e:
            print(f"Error finding PLAY TOGETHER window: {e}")
            return False
    
    def position_on_play_together(self):
        """Position the selection box centered on the PLAY TOGETHER window"""
        if self.play_together_rect is not None:
            # Center the box on the game window
            center_x = self.play_together_rect.left() + self.play_together_rect.width() // 2
            center_y = self.play_together_rect.top() + self.play_together_rect.height() // 2
            
            # Position the box
            self.box_rect.moveCenter(QPoint(center_x, center_y))
            
            # Ensure box stays within screen bounds
            self.constrain_box_to_screen()
            
            # Update the display
            self.update()
            
    def showEvent(self, event):
        """Ensure window is on top when shown"""
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        
        # Use Apple Script to ensure window focus (for macOS)
        try:
            script = '''
            tell application "System Events" 
                set frontmost of every process whose unix id is %d to true
            end tell
            ''' % os.getpid()
            subprocess.run(['osascript', '-e', script], check=True)
        except Exception as e:
            print(f"Error focusing window: {e}")
        
    def paintEvent(self, event):
        """Draw the selection overlay with matcha wood theme"""
        painter = QPainter(self)
        
        # Set up rendering hints for better quality
        painter.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | 
                             QPainter.RenderHint.Antialiasing)
        
        # Draw the captured screen background
        if hasattr(self, 'background_pixmap') and self.background_pixmap is not None:
            target_rect = self.rect()
            painter.drawPixmap(target_rect, self.background_pixmap, 
                             QRect(0, 0, self.background_pixmap.width(), self.background_pixmap.height()))
            
            # Apply a slight darkening overlay
            painter.fillRect(target_rect, QColor(44, 36, 23, 100))  # Dark oak overlay
        else:
            # Fallback to a semi-transparent background if no screenshot
            painter.fillRect(self.rect(), self.colors['bg_overlay'])
        
        # Highlight PLAY TOGETHER window if found
        if self.play_together_rect is not None:
            play_together_highlight = QRect(
                self.play_together_rect.left(),
                self.play_together_rect.top(),
                self.play_together_rect.width(),
                self.play_together_rect.height()
            )
            painter.fillRect(play_together_highlight, QColor(141, 195, 112, 30))  # Light matcha highlight
            painter.setPen(QPen(self.colors['accent_green'], 1, Qt.PenStyle.DashLine))
            painter.drawRect(play_together_highlight)
            
            # Display a label identifying the window - more compact
            game_label_rect = QRect(
                self.play_together_rect.left(), 
                self.play_together_rect.top() - 24,
                self.play_together_rect.width(), 
                24
            )
            painter.fillRect(game_label_rect, QColor(67, 52, 31, 220))  # Oak background
            painter.setPen(self.colors['accent_green'])
            painter.setFont(QFont("Helvetica", 9, QFont.Weight.Medium))
            painter.drawText(game_label_rect, Qt.AlignmentFlag.AlignCenter, "PLAY TOGETHER WINDOW")
        
        # Draw dimmed rectangle around the selection area to highlight it
        # Create four rectangles to cover all areas except the selection
        # Top area
        painter.fillRect(
            QRect(0, 0, self.screen_width, self.box_rect.top()),
            QColor(44, 36, 23, 150)  # Dark oak with transparency
        )
        # Bottom area
        painter.fillRect(
            QRect(0, self.box_rect.bottom() + 1, self.screen_width, self.screen_height - self.box_rect.bottom() - 1),
            QColor(44, 36, 23, 150)
        )
        # Left area
        painter.fillRect(
            QRect(0, self.box_rect.top(), self.box_rect.left(), self.box_rect.height()),
            QColor(44, 36, 23, 150)
        )
        # Right area
        painter.fillRect(
            QRect(self.box_rect.right() + 1, self.box_rect.top(), 
                  self.screen_width - self.box_rect.right() - 1, self.box_rect.height()),
            QColor(44, 36, 23, 150)
        )
        
        # Draw crosshairs - matcha green - thinner line
        painter.setPen(QPen(self.colors['accent_green'], 1, Qt.PenStyle.DotLine))
        painter.drawLine(0, self.mouse_pos.y(), self.screen_width, self.mouse_pos.y())
        painter.drawLine(self.mouse_pos.x(), 0, self.mouse_pos.x(), self.screen_height)
        
        # Ensure box stays within screen bounds
        self.constrain_box_to_screen()
        
        # Draw selection box border - matcha green - thinner line
        outer_pen = QPen(self.colors['accent_green'], 1.5)
        painter.setPen(outer_pen)
        painter.drawRoundedRect(self.box_rect, 8, 8)  # Smaller rounded corners
        
        # Add a second, inner border for better visibility - thinner
        inner_rect = QRect(
            self.box_rect.left() + 2, 
            self.box_rect.top() + 2, 
            self.box_rect.width() - 4, 
            self.box_rect.height() - 4
        )
        painter.setPen(QPen(self.colors['accent_green_light'], 1))
        painter.drawRoundedRect(inner_rect, 6, 6)  # Smaller rounded corners
        
        # Draw semi-transparent fill
        painter.fillRect(self.box_rect, QColor(141, 195, 112, 15))  # Very light matcha green
        
        # Draw grid lines - thinner
        painter.setPen(QPen(self.colors['accent_green_light'], 0.5, Qt.PenStyle.DashLine))
        # Vertical grid lines
        cell_width = self.box_width // 3
        for i in range(1, 3):
            painter.drawLine(
                self.box_rect.left() + i * cell_width, self.box_rect.top(),
                self.box_rect.left() + i * cell_width, self.box_rect.bottom()
            )
        # Horizontal grid lines
        cell_height = self.box_height // 3
        for i in range(1, 3):
            painter.drawLine(
                self.box_rect.left(), self.box_rect.top() + i * cell_height,
                self.box_rect.right(), self.box_rect.top() + i * cell_height
            )
        
        # Draw coordinates with oak-style pill background - more compact
        coord_text = f"Position: ({self.box_rect.left()},{self.box_rect.top()}) • Size: {self.box_width}×{self.box_height}"
        text_width = 360
        text_height = 24
        
        # Create pill background
        coord_rect = QRect(
            (self.screen_width - text_width) // 2,
            self.screen_height - 40, 
            text_width, 
            text_height
        )
        
        # Draw background pill
        path = QPainterPath()
        path.addRoundedRect(QRectF(coord_rect), 12, 12)
        painter.fillPath(path, QColor(67, 52, 31, 220))  # Oak background
        
        # Draw text - smaller font
        painter.setPen(self.colors['text'])
        painter.setFont(QFont("Helvetica", 10, QFont.Weight.Medium))
        painter.drawText(
            coord_rect, 
            Qt.AlignmentFlag.AlignCenter, 
            coord_text
        )
        
    def mouseMoveEvent(self, event):
        """Track mouse movement for dragging or positioning the box"""
        self.mouse_pos = event.pos()
        
        if self.is_dragging:
            # Move the box with the mouse
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()
            
            self.box_rect.moveTopLeft(self.box_start_pos + QPoint(dx, dy))
        else:
            # Center box on cursor when not dragging
            self.box_rect = QRect(
                self.mouse_pos.x() - self.box_width // 2,
                self.mouse_pos.y() - self.box_height // 2,
                self.box_width,
                self.box_height
            )
            
        self.update()  # Redraw
        
    def mousePressEvent(self, event):
        """Start dragging when mouse pressed"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is inside box
            if self.box_rect.contains(event.pos()):
                self.is_dragging = True
                self.drag_start_pos = event.pos()
                self.box_start_pos = self.box_rect.topLeft()
            else:
                # Center box on click position
                self.box_rect = QRect(
                    event.pos().x() - self.box_width // 2,
                    event.pos().y() - self.box_height // 2,
                    self.box_width,
                    self.box_height
                )
                self.is_dragging = True
                self.drag_start_pos = event.pos()
                self.box_start_pos = self.box_rect.topLeft()
                
            self.update()  # Redraw
            
    def mouseReleaseEvent(self, event):
        """Finalize selection on mouse release"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            
            # Constrain box to screen before finalizing
            self.constrain_box_to_screen()
            
            # Get the exact coordinates from the box
            left = self.box_rect.left()
            top = self.box_rect.top()
            right = self.box_rect.right() + 1  # +1 because right/bottom are inclusive
            bottom = self.box_rect.bottom() + 1
            
            # Ensure coordinates are within screen bounds and have correct dimensions
            if left < 0: left = 0
            if top < 0: top = 0
            if right > self.screen_width: right = self.screen_width
            if bottom > self.screen_height: bottom = self.screen_height
            
            # Debug output
            print(f"Selected region: ({left}, {top}, {right}, {bottom})")
            print(f"Dimensions: {right-left}x{bottom-top}")
            
            # Emit signal with selected region
            region = (left, top, right, bottom)
            self.region_selected.emit(region)
            self.accept()
    
    def constrain_box_to_screen(self):
        """Ensure the box stays within screen bounds"""
        # Get current position
        left = self.box_rect.left()
        top = self.box_rect.top()
        
        # Adjust for screen boundaries
        if left < 0:
            left = 0
        elif left + self.box_width > self.screen_width:
            left = self.screen_width - self.box_width
            
        if top < 0:
            top = 0
        elif top + self.box_height > self.screen_height:
            top = self.screen_height - self.box_height
            
        # Update rectangle position
        self.box_rect = QRect(left, top, self.box_width, self.box_height)
            
    def keyPressEvent(self, event):
        """Handle key presses"""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()


class TimelinePlot(FigureCanvas):
    """Timeline plot for visualizing change history"""
    def __init__(self, parent=None, width=6, height=1, dpi=100):
        # Define matcha wood theme colors for plot
        self.colors = {
            'bg_dark': '#2C2417',      # Dark oak wood background
            'bg_card': '#43341F',      # Medium oak wood background
            'grid': '#5E4929',         # Grid color - oak with more contrast
            'accent': '#8DC370',       # Matcha green accent
            'accent_light': '#A7CF90', # Light matcha green
            'alert': '#D95F4E',        # Error - burnt sienna
            'text': '#F8F4E3',         # Cream text
            'text_dim': '#E6DFC8',     # Light cream text
        }
        
        # Create figure and axes with modern dark theme
        self.fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        self.fig.set_facecolor(self.colors['bg_dark'])
        self.ax.set_facecolor(self.colors['bg_dark'])
        
        # Initialize with empty data
        self.x_data = np.arange(100)
        self.y_data = np.zeros(100)
        
        # Create the plot with teal accent colors
        self.activity_line, = self.ax.plot(self.x_data, self.y_data, color=self.colors['accent'], linewidth=1.5)
        self.threshold_line = self.ax.axhline(y=0.05, color=self.colors['alert'], linestyle='--', alpha=0.8, linewidth=1)
        
        # Configure appearance for modern dark theme
        self.ax.set_xlim(0, 99)
        self.ax.set_ylim(0, 1)
        self.ax.set_xticks([])
        
        # Add subtle grid lines
        self.ax.grid(True, alpha=0.2, color=self.colors['grid'])
        
        # Set text styling with smaller font - using standard fonts that matplotlib supports
        self.ax.set_title("Activity Timeline", color=self.colors['accent_light'], fontsize=10, 
                         fontweight='medium')
        
        # Set text color for axis labels and ticks - smaller font
        self.ax.tick_params(axis='y', colors=self.colors['text_dim'], labelsize=8)
        self.ax.yaxis.label.set_color(self.colors['text'])
        
        # Remove spines
        for spine in self.ax.spines.values():
            spine.set_color(self.colors['grid'])
            spine.set_linewidth(0.5)
        
        # Initialize the canvas
        super().__init__(self.fig)
        self.setParent(parent)
        
        # Set up a tight layout with smaller padding
        self.fig.tight_layout(pad=0.8)
        
    def update_plot(self, history, threshold):
        """Update the plot with new data"""
        if not history:
            return
            
        # Create data array, padded with zeros if necessary
        data = history[-100:].copy()
        if len(data) < 100:
            data = [0] * (100 - len(data)) + data
            
        # Update the plot
        self.activity_line.set_ydata(data)
        self.threshold_line.set_ydata([threshold, threshold])
        
        # Update title with threshold value in minimal format - smaller font
        self.ax.set_title(f"Activity [threshold: {threshold:.2f}]", 
                        color=self.colors['accent_light'], fontsize=9, 
                        fontweight='medium')
        
        # Redraw the canvas
        self.draw()


class MonitoringDisplay(QWidget):
    """Widget for displaying the captured region and difference visualization"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(380, 230)  # Even smaller minimum size
        
        # Define colors - use the matcha wood theme
        self.colors = {
            'bg_dark': '#2C2417',      # Dark oak wood for background
            'bg_card': '#43341F',      # Medium oak wood for cards/controls
            'accent': '#8DC370',       # Matcha green accent
            'accent_light': '#A7CF90',  # Light matcha green
            'accent_dark': '#6B9E4F',   # Dark matcha green
            'alert': '#D95F4E',        # Error - burnt sienna
            'warning': '#E6A948',      # Warning - golden oak
            'text': '#F8F4E3',         # Cream text
            'text_dim': '#E6DFC8',     # Light cream text
        }
        
        # Initialize bright mode tracking
        self.bright_mode_enabled = True
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)  # Further reduced spacing
        
        # Image display label with rounded corners
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(f"""
            background-color: {self.colors['bg_card']}; 
            border: none; 
            border-radius: 8px;
            padding: 4px;
        """)
        layout.addWidget(self.image_label)
        
        # Status indicators in a slim frame
        status_frame = QFrame()
        status_frame.setMaximumHeight(28)  # Even smaller height
        status_frame.setStyleSheet(f"""
            background-color: {self.colors['bg_card']};
            border-radius: 6px;
            padding: 0px;
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 2, 8, 2)  # Further reduced padding
        status_layout.setSpacing(6)  # Reduced spacing
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet(f"color: {self.colors['accent_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.status_label)
        
        self.change_label = QLabel("Change: 0.00%")
        self.change_label.setStyleSheet(f"color: {self.colors['accent_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.change_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addWidget(status_frame)
        
        # Pre-allocate reusable image buffers for performance
        self._last_pixmap = None
        self._last_display_time = 0
        self._display_throttle_ms = 16.67  # ~60fps
        
    def set_status(self, status):
        """Update the status display with Modern Dark theme colors"""
        if status == "running":
            self.status_label.setText("Status: Running")
            self.status_label.setStyleSheet(f"color: {self.colors['accent']}; font-weight: 500; font-size: 14px;")
        elif status == "stopped":
            self.status_label.setText("Status: Stopped")
            self.status_label.setStyleSheet(f"color: {self.colors['alert']}; font-weight: 500; font-size: 14px;")
        elif status == "paused":
            self.status_label.setText("Status: Paused")
            self.status_label.setStyleSheet(f"color: {self.colors['warning']}; font-weight: 500; font-size: 14px;")
        elif status == "action_sequence":
            self.status_label.setText("Status: Action Sequence")
            self.status_label.setStyleSheet(f"color: {self.colors['primary_light']}; font-weight: 500; font-size: 14px;")
        else:
            self.status_label.setText(f"Status: {status}")
            self.status_label.setStyleSheet(f"color: {self.colors['text']}; font-weight: 500; font-size: 14px;")
            
    def set_bright_mode(self, enabled):
        """Set whether bright detection mode is enabled"""
        self.bright_mode_enabled = enabled


class PixelChangeApp(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pixel Change Detector")
        self.setMinimumSize(780, 520)  # Even more compact minimum size
        
        # Initialize detector
        self.detector = PixelChangeDetector()
        self.detector.log_signal.connect(self.add_log)
        self.detector.frame_updated.connect(self.update_visualization)
        self.detector.detection_signal.connect(self.handle_detection)
        
        # Define color scheme first
        self._define_colors()
        
        # Create UI
        self._init_ui()
        
        # Detection counter
        self.detection_count = 0
        
    def _define_colors(self):
        """Define the color scheme for the application - Matcha Wood Theme"""
        # Define color scheme - Matcha Wood Theme
        self.colors = {
            # Base colors
            'bg_dark': '#2C2417',      # Dark oak wood for background
            'bg_panel': '#372D1C',     # Slightly lighter oak wood for panels
            'bg_card': '#43341F',      # Medium oak wood for cards/controls
            'bg_accent': '#4E3C22',    # Lighter oak wood for accents
            
            # Text colors
            'text': '#F8F4E3',         # Cream text
            'text_dim': '#E6DFC8',     # Light cream for secondary text
            'text_muted': '#BDB59A',   # Muted cream for tertiary text
            'text_dark': '#2C2417',    # Dark text for light backgrounds
            
            # Accent colors
            'primary': '#8DC370',      # Matcha green primary
            'primary_light': '#A7CF90', # Light matcha green
            'primary_dark': '#6B9E4F',  # Dark matcha green
            'secondary': '#5D7052',    # Dark grass green secondary accent
            'highlight': '#B9C784',    # Light grass green highlight
            
            # Status colors
            'success': '#8DC370',      # Success - matcha green
            'alert': '#D95F4E',        # Error - burnt sienna 
            'warning': '#E6A948',      # Warning - golden oak
            'border': '#43341F',       # Border color - medium oak
        }
        
    def _init_ui(self):
        """Initialize the user interface - Modern Dark theme"""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)  # Even smaller margins
        main_layout.setSpacing(6)  # Reduced spacing further
        
        # Set application-wide stylesheet - Modern Dark theme with smaller fonts
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ 
                background-color: {self.colors['bg_dark']}; 
                color: {self.colors['text']}; 
                font-family: 'SF Pro Display', 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            }}
            
            QGroupBox {{ 
                background-color: {self.colors['bg_panel']}; 
                color: {self.colors['text_dim']}; 
                border: none;
                border-radius: 8px; 
                margin-top: 1.2em;
                font-weight: 500;
                font-size: 13px;
                padding: 4px;
            }}
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                left: 8px; 
                padding: 0 6px;
                color: {self.colors['primary_light']};
            }}
            
            QPushButton {{ 
                background-color: {self.colors['bg_card']}; 
                color: {self.colors['text']}; 
                border: none; 
                padding: 4px 10px; 
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                min-height: 24px;
                margin: 1px;
            }}
            QPushButton:hover {{ 
                background-color: {self.colors['primary_dark']}; 
            }}
            QPushButton:pressed {{ 
                background-color: {self.colors['primary']}; 
                color: {self.colors['text']};
            }}
            QPushButton:disabled {{ 
                color: {self.colors['text_muted']}; 
                background-color: {self.colors['bg_card']};
                opacity: 0.8;
            }}
        """)
        
        # Create a container that will resize with window
        self.container = QWidget()
        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        main_layout.addWidget(self.container)
        
        # Create a splitter for the main panels
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        container_layout.addWidget(self.main_splitter)
        
        # Create left panel (controls)
        self.left_panel = QWidget()
        self.left_panel.setFixedWidth(320)  # Even narrower left panel
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.setSpacing(8)  # Reduced spacing further
        self.main_splitter.addWidget(self.left_panel)
        
        # Create right panel (visualization)
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(8)  # Reduced spacing
        self.main_splitter.addWidget(self.right_panel)
        
        # Create a persistent button frame that stays visible when right panel is collapsed
        self.persistent_button_frame = QFrame()
        self.persistent_button_frame.setFixedWidth(36)  # Slimmer button
        self.persistent_button_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors['bg_dark']};
                border: none;
                padding: 0px;
            }}
        """)
        persistent_layout = QVBoxLayout(self.persistent_button_frame)
        persistent_layout.setContentsMargins(0, 0, 0, 0)
        persistent_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Create expand button for collapsed state
        self.expand_button = QPushButton("▶")
        self.expand_button.setFixedSize(36, 80)  # Smaller button
        self.expand_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['primary_dark']};
                color: {self.colors['text']};
                border-radius: 0px 6px 6px 0px;
                padding: 2px;
                font-size: 14px;
                font-weight: bold;
                margin: 0px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['primary']};
            }}
        """)
        self.expand_button.clicked.connect(self.expand_right_panel)
        persistent_layout.addWidget(self.expand_button)
        persistent_layout.addStretch()
        
        # Initially hide the expand button
        self.expand_button.hide()
        
        # Don't add this to main layout yet - will add only when needed
        self.persistent_button_widget = self.persistent_button_frame
        
        # Add "Controls" header to left panel
        header_font = QFont()
        header_font.setPointSize(14)  # Even smaller font
        header_font.setBold(True)
        
        left_header = QLabel("Controls")
        left_header.setFont(header_font)
        left_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        left_header.setStyleSheet(f"color: {self.colors['primary_light']}; margin-bottom: 2px; padding-left: 2px;")
        left_layout.addWidget(left_header)
        
        # Create toggle button
        self.toggle_button = QPushButton("◀ Hide")
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_card']};
                border-radius: 4px;
                padding: 3px 6px;
                font-size: 11px;
                max-width: 60px;
                margin-left: auto;
            }}
            QPushButton:hover {{
                background-color: {self.colors['primary_dark']};
            }}
        """)
        self.toggle_button.clicked.connect(self.toggle_right_panel)
        
        # Add "View" header to right panel with collapse button
        right_header = QLabel("Monitoring View")
        right_header.setFont(header_font)
        right_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        right_header.setStyleSheet(f"color: {self.colors['primary_light']}; margin-bottom: 2px; padding-left: 2px;")
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(right_header)
        header_layout.addStretch()
        header_layout.addWidget(self.toggle_button)
        right_layout.addLayout(header_layout)
        
        # Store the original sizes for later restoration
        self.original_sizes = [320, 440]  # Default sizes for left and right panels
        self.right_panel_collapsed = False
        
        # === LEFT PANEL COMPONENTS ===
        
        # 1. Settings group - more compact style
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(12, 20, 12, 12)  # Further reduced padding
        settings_layout.setSpacing(10)  # Further reduced spacing
        left_layout.addWidget(settings_group)
        
        # Threshold control - using grid layout for better alignment
        settings_grid = QGridLayout()
        settings_grid.setColumnStretch(1, 1)  # Make slider column stretch
        settings_grid.setVerticalSpacing(10)  # Reduced spacing between rows
        settings_grid.setHorizontalSpacing(8)  # Reduced spacing between columns
        
        threshold_label = QLabel("Threshold:")
        threshold_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-size: 12px;")
        threshold_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        settings_grid.addWidget(threshold_label, 0, 0)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setFixedHeight(28)  # Shorter slider
        self.threshold_slider.setRange(1, 50)  # 0.01 to 0.50
        self.threshold_slider.setValue(5)      # Default 0.05
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        settings_grid.addWidget(self.threshold_slider, 0, 1)
        
        self.threshold_value_label = QLabel("0.05")
        self.threshold_value_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-size: 12px;")
        self.threshold_value_label.setFixedWidth(36) # Narrower fixed width
        self.threshold_value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        settings_grid.addWidget(self.threshold_value_label, 0, 2)
        
        # Region size control
        size_label = QLabel("Region Size:")
        size_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-size: 12px;")
        size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        settings_grid.addWidget(size_label, 1, 0)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setFixedHeight(28)  # Shorter slider
        self.size_slider.setRange(20, 200)  # 20 to 200 pixels
        self.size_slider.setValue(50)      # Default 100
        self.size_slider.valueChanged.connect(self.update_size_label)
        settings_grid.addWidget(self.size_slider, 1, 1)
        
        self.size_value_label = QLabel("50")
        self.size_value_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-size: 12px;")
        self.size_value_label.setFixedWidth(36) # Narrower fixed width
        self.size_value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        settings_grid.addWidget(self.size_value_label, 1, 2)
        
        settings_layout.addLayout(settings_grid)
        
        # Compact settings layout with checkboxes in horizontal arrangement
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(24)  # Reduced spacing between checkboxes
        checkbox_layout.setContentsMargins(0, 6, 0, 0)  # Less top margin
        
        # Noise reduction checkbox - more compact
        self.noise_checkbox = QCheckBox("Noise Reduction")
        self.noise_checkbox.setStyleSheet("font-size: 12px;")
        self.noise_checkbox.setChecked(True)
        self.noise_checkbox.toggled.connect(self.toggle_noise_reduction)
        checkbox_layout.addWidget(self.noise_checkbox)
        
        # Bright background detection checkbox - more compact
        self.bright_checkbox = QCheckBox("Bright Detection")
        self.bright_checkbox.setStyleSheet("font-size: 12px;")
        self.bright_checkbox.setChecked(True)
        self.bright_checkbox.toggled.connect(self.toggle_bright_detection)
        checkbox_layout.addWidget(self.bright_checkbox)
        
        settings_layout.addLayout(checkbox_layout)
        
        # 2. Monitoring group - more compact style
        monitoring_group = QGroupBox("Monitoring")
        monitoring_layout = QVBoxLayout(monitoring_group)
        monitoring_layout.setContentsMargins(12, 20, 12, 12)  # Further reduced padding
        monitoring_layout.setSpacing(8)  # Further reduced spacing
        left_layout.addWidget(monitoring_group)
        
        # Region selection button
        self.region_button = QPushButton("Select Region")
        self.region_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['primary_dark']};
                color: {self.colors['text']};
                font-weight: 600;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['primary']};
            }}
        """)
        self.region_button.setMinimumHeight(28)  # Shorter height
        self.region_button.clicked.connect(self.select_region)
        monitoring_layout.addWidget(self.region_button)
        
        # Region info display
        region_info_layout = QHBoxLayout()
        region_info_layout.setSpacing(6)  # Further reduced spacing
        region_info_layout.setContentsMargins(2, 2, 2, 2)  # Further reduced padding
        status_label = QLabel("Status:")
        status_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-size: 12px;")
        region_info_layout.addWidget(status_label)
        
        self.region_info_label = QLabel("No region selected")
        self.region_info_label.setStyleSheet("font-size: 12px;")
        region_info_layout.addWidget(self.region_info_label)
        monitoring_layout.addLayout(region_info_layout)
        
        # 3. Control group - more compact style
        control_group = QGroupBox("Control")
        control_layout = QVBoxLayout(control_group)
        control_layout.setContentsMargins(12, 20, 12, 12)  # Further reduced padding
        control_layout.setSpacing(8)  # Further reduced spacing
        left_layout.addWidget(control_group)
        
        # Control buttons - more compact
        button_layout = QHBoxLayout()
        button_layout.setSpacing(6)  # Further reduced spacing
        
        self.start_button = QPushButton("Start")
        self.start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['success']};
                color: {self.colors['text']};
                font-weight: 600;
                font-size: 13px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background-color: #34D399;
            }}
        """)
        self.start_button.setMinimumHeight(28)  # Shorter height
        self.start_button.clicked.connect(self.start_detection)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['alert']};
                color: #FFFFFF;
                font-weight: 600;
                font-size: 13px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background-color: #F87171;
            }}
        """)
        self.stop_button.setMinimumHeight(28)  # Shorter height
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['warning']};
                color: {self.colors['text']};
                font-weight: 600;
                font-size: 13px;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background-color: #FBBF24;
            }}
        """)
        self.pause_button.setMinimumHeight(28)  # Shorter height
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        button_layout.addWidget(self.pause_button)
        
        control_layout.addLayout(button_layout)
        
        # Second row of buttons - more compact
        button_layout2 = QHBoxLayout()
        button_layout2.setSpacing(6)  # Further reduced spacing
        
        self.reference_button = QPushButton("Capture Reference")
        self.reference_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['highlight']};
                color: {self.colors['text']};
                font-size: 12px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: #94A3B8;
            }}
        """)
        self.reference_button.setMinimumHeight(26)  # Shorter height
        self.reference_button.clicked.connect(self.capture_reference)
        button_layout2.addWidget(self.reference_button)
        
        self.clear_button = QPushButton("Clear Logs")
        self.clear_button.setMinimumHeight(26)  # Shorter height
        self.clear_button.setStyleSheet(f"""
            font-size: 12px; 
            padding: 4px 8px;
            background-color: {self.colors['bg_accent']};
        """)
        self.clear_button.clicked.connect(self.clear_logs)
        button_layout2.addWidget(self.clear_button)
        
        control_layout.addLayout(button_layout2)
        
        # 4. Log display - more compact style
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(12, 20, 12, 12)  # Further reduced padding
        log_layout.setSpacing(6)
        left_layout.addWidget(log_group, stretch=1)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMinimumHeight(100)  # Shorter minimum height
        self.log_display.setStyleSheet("font-size: 11px;")  # Smaller font for logs
        log_layout.addWidget(self.log_display)
        
        # === RIGHT PANEL COMPONENTS ===
        
        # 1. Monitoring display with more compact theme
        monitor_group = QGroupBox("Live Monitor")
        monitor_layout = QVBoxLayout(monitor_group)
        monitor_layout.setContentsMargins(12, 20, 12, 12)  # Further reduced padding
        monitor_layout.setSpacing(6)
        
        self.monitor_display = MonitoringDisplay()
        self.monitor_display.setStyleSheet(f"""
            QLabel {{ 
                background-color: {self.colors['bg_card']}; 
                border: none; 
                border-radius: 8px;
                font-size: 12px;
            }}
        """)
        monitor_layout.addWidget(self.monitor_display)
        right_layout.addWidget(monitor_group, stretch=3)
        
        # 2. Timeline plot in its own group - more compact
        timeline_group = QGroupBox("Activity Timeline")
        timeline_layout = QVBoxLayout(timeline_group)
        timeline_layout.setContentsMargins(12, 20, 12, 12)  # Further reduced padding
        
        self.timeline_plot = TimelinePlot(width=5, height=1.5)  # Shorter height
        timeline_layout.addWidget(self.timeline_plot)
        
        right_layout.addWidget(timeline_group, stretch=1)
        
        # 3. Status and count display - more compact
        status_frame = QFrame()
        status_frame.setMinimumHeight(28)  # Shorter height
        status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors['bg_card']};
                border-radius: 6px;
                padding: 0px;
            }}
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 3, 10, 3)  # Further reduced padding
        status_layout.setSpacing(6)
        
        self.status_label = QLabel("Status: Waiting")
        self.status_label.setStyleSheet(f"color: {self.colors['primary_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.status_label)
        
        self.count_label = QLabel("Detections: 0")
        self.count_label.setStyleSheet(f"color: {self.colors['primary_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.count_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        right_layout.addWidget(status_frame)
        
        # Add a welcome log message
        self.add_log("Pixel Change Detector initialized")
        self.add_log("macOS Modern UI Theme")
        self.add_log("Click 'Select Region' to begin")
        
        # Set initial state of bright detection in monitor display
        self.monitor_display.set_bright_mode(self.detector.enhanced_bright_detection)
    
    def toggle_right_panel(self):
        """Toggle the right panel between collapsed and expanded states"""
        if self.right_panel_collapsed:
            self.expand_right_panel()
        else:
            # Save current sizes before collapsing
            self.original_sizes = self.main_splitter.sizes()
            
            # Hide the right panel
            self.right_panel.hide()
            
            # Show the expand button by adding it to the layout
            container_layout = self.container.layout()
            container_layout.addWidget(self.persistent_button_frame)
            self.expand_button.show()
            
            # Resize the window to be more compact
            current_width = self.width()
            new_width = self.left_panel.width() + 70  # Left panel + margins + expand button
            self.resize(new_width, self.height())
            
            # Update toggle button
            self.toggle_button.setText("▶ Show View")
            
            # Update state
            self.right_panel_collapsed = True
    
    def expand_right_panel(self):
        """Expand the previously collapsed right panel"""
        # Show the right panel
        self.right_panel.show()
        
        # Remove and hide the expand button
        self.persistent_button_frame.setParent(None)
        self.expand_button.hide()
        
        # Restore original window size
        self.resize(880, self.height())
        
        # Restore original panel sizes after a short delay to ensure layout is updated
        QTimer.singleShot(100, lambda: self.main_splitter.setSizes(self.original_sizes))
        
        # Update toggle button text
        self.toggle_button.setText("◀ Hide View")
        
        # Update state
        self.right_panel_collapsed = False
    
    def update_threshold(self):
        """Update threshold value from slider"""
        value = self.threshold_slider.value() / 100.0
        self.threshold_value_label.setText(f"{value:.2f}")
        
        if self.detector:
            self.detector.THRESHOLD = value
            
            # Update the threshold line in the timeline plot
            self.timeline_plot.threshold_line.set_ydata([value, value])
            self.timeline_plot.draw()
    
    def update_size_label(self):
        """Update size value label from slider"""
        value = self.size_slider.value()
        self.size_value_label.setText(str(value))
    
    def select_region(self):
        """Open region selection overlay"""
        # Hide main window to ensure it's not in the screenshot
        self.hide()
        
        # Delay to ensure the main window disappears before capturing screen
        # Longer delay for more reliable fullscreen capture
        time.sleep(0.5)
        
        # Make sure all Qt events are processed before taking the screenshot
        QApplication.processEvents()
        
        # Create and show region selection dialog
        region_size = self.size_slider.value()
        self.selection_dialog = RegionSelectionOverlay(None, region_size)
        self.selection_dialog.region_selected.connect(self.set_region)
        
        # Force the selection dialog to stay on top
        self.selection_dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        
        # Show dialog and make it active - fullscreen
        self.selection_dialog.showFullScreen()
        self.selection_dialog.activateWindow()
        self.selection_dialog.raise_()
        
        # Use Apple Script to ensure window focus and bring to front (for macOS)
        try:
            script = '''
            tell application "System Events" 
                set frontmost of every process whose unix id is %d to true
            end tell
            ''' % os.getpid()
            subprocess.run(['osascript', '-e', script], check=True)
        except Exception as e:
            print(f"Error focusing window: {e}")
        
        result = self.selection_dialog.exec()
        
        if result == QDialog.DialogCode.Rejected:
            self.add_log("Region selection canceled")
            
        # Show main window again
        self.show()
        self.activateWindow()
        self.raise_()
    
    def set_region(self, region):
        """Set the selected region"""
        # Ensure region coordinates are valid integers
        left, top, right, bottom = [int(coord) for coord in region]
        
        # Calculate dimensions for display
        width = right - left
        height = bottom - top
        
        # Validate the region
        if width <= 0 or height <= 0:
            self.add_log(f"Invalid region dimensions: {width}x{height}")
            return
            
        # Set the region in the detector
        self.detector.region = (left, top, right, bottom)
        
        # Share game window info if available
        if hasattr(self.selection_dialog, 'play_together_proc') and self.selection_dialog.play_together_proc:
            self.detector.game_process_name = self.selection_dialog.play_together_proc
            self.add_log(f"Game process identified: {self.detector.game_process_name}")
            
        if hasattr(self.selection_dialog, 'play_together_name') and self.selection_dialog.play_together_name:
            self.detector.game_window_name = self.selection_dialog.play_together_name
            self.add_log(f"Game window identified: {self.detector.game_window_name}")
        
        # Update UI
        self.region_info_label.setText(f"region({left},{top},{width}×{height})")
        self.add_log(f"Region selected: ({left},{top}) {width}×{height}")
        
        # Capture a reference frame if detector is initialized
        if self.detector and not self.detector.is_running:
            self.capture_reference()
            self.add_log("Initial reference frame captured")
    
    def start_detection(self):
        """Start the detection process"""
        if not self.detector.region:
            self.add_log("You must select a region first")
            return
            
        # Update threshold from UI
        self.detector.THRESHOLD = self.threshold_slider.value() / 100.0
        
        # Always clear and recapture the reference frame when starting
        self.detector.reference_frame = None
        self.add_log("Capturing new reference frame...")
        if not self.detector.capture_reference():
            self.add_log("Failed to capture reference frame. Please check region selection.")
            return
        
        # Start detection
        self.detector.start_detection()
        
        # Update UI
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.monitor_display.set_status("running")
        self.status_label.setText("Status: Running")
        self.status_label.setStyleSheet(f"color: {self.colors['success']}; font-weight: 500; font-size: 14px;")
    
    def stop_detection(self):
        """Stop the detection process"""
        self.detector.stop_detection()
        
        # Update UI
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.monitor_display.set_status("stopped")
        self.status_label.setText("Status: Stopped")
        self.status_label.setStyleSheet(f"color: {self.colors['alert']}; font-weight: 500; font-size: 14px;")
    
    def toggle_pause(self):
        """Pause or resume detection"""
        self.detector.toggle_pause()
        
        if self.detector.is_paused:
            self.pause_button.setText("Resume")
            self.monitor_display.set_status("paused")
            self.status_label.setText("Status: Paused")
            self.status_label.setStyleSheet(f"color: {self.colors['warning']}; font-weight: 500; font-size: 14px;")
        else:
            self.pause_button.setText("Pause")
            self.monitor_display.set_status("running")
            self.status_label.setText("Status: Running")
            self.status_label.setStyleSheet(f"color: {self.colors['success']}; font-weight: 500; font-size: 14px;")
            
    def capture_reference(self):
        """Capture a reference frame"""
        if self.detector.region:
            success = self.detector.capture_reference()
            if success:
                self.add_log("Reference frame captured")
        else:
            self.add_log("You must select a region first")
    
    def add_log(self, message):
        """Add message to log display"""
        self.log_display.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_logs(self):
        """Clear log display"""
        self.log_display.clear()
    
    def handle_detection(self):
        """Handle a detection event"""
        # Increment detection counter
        self.detection_count += 1
        self.count_label.setText(f"Detections: {self.detection_count}")
        
        # Update status to show action sequence
        self.monitor_display.set_status("action_sequence")
        self.status_label.setText("Status: Action Sequence")
        self.status_label.setStyleSheet(f"color: {self.colors['primary_light']}; font-weight: 500; font-size: 14px;")
        
        # Add a log message
        self.add_log(f"Detection #{self.detection_count} - executing action sequence")
        
        # Note: The actual key presses are handled by the detector's action sequence
        
    def update_visualization(self):
        """Update visualization components"""
        if not self.detector:
            return
            
        try:
            # Get latest data from detector
            current_frame = self.detector.color_frame
            diff_frame = self.detector.diff_frame
            
            # Calculate current change percentage
            current_change = self.detector.change_history[-1] if self.detector.change_history else 0
            
            # Update display components
            self.monitor_display.update_display(current_frame, diff_frame, current_change)
            self.timeline_plot.update_plot(self.detector.change_history, self.detector.THRESHOLD)
            
            # Update status if in action sequence
            if self.detector.in_action_sequence:
                step = self.detector.action_sequence_step
                total_steps = len(self.detector.action_sequence)
                self.status_label.setText(f"Status: Action Sequence ({step}/{total_steps})")
                self.status_label.setStyleSheet(f"color: {self.colors['primary_light']}; font-weight: 500; font-size: 12px;")
        except Exception as e:
            print(f"Error updating visualization: {e}")
            # Don't stop the application on visualization errors
    
    def toggle_noise_reduction(self, checked):
        """Toggle noise reduction processing"""
        if self.detector:
            self.detector.apply_blur = checked
            self.add_log(f"Noise reduction {'enabled' if checked else 'disabled'}")
    
    def toggle_bright_detection(self, checked):
        """Toggle enhanced bright detection"""
        if self.detector:
            self.detector.enhanced_bright_detection = checked
            self.monitor_display.set_bright_mode(checked)
            self.add_log(f"Enhanced bright detection {'enabled' if checked else 'disabled'}")
            
            # Update visualization to show the indicator immediately
            self.update_visualization()


def main():
    app = QApplication(sys.argv)
    window = PixelChangeApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()