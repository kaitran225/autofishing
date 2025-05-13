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
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
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
        
        # Updated action sequence with consistent delay times for each action type
        self.action_sequence = [
            {"action": "press_f", "delay": 2.0},
            {"action": "wait", "delay": 3.0},
            {"action": "press_esc", "delay": 1.0},
            {"action": "wait", "delay": 1.0},
            {"action": "press_f", "delay": 1.0}
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
        """Calculate the difference between two frames with improved noise handling and performance"""
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
            
        # Calculate absolute difference
        diff_frame = cv2.absdiff(frame1, frame2)
        
        # Apply threshold to create binary difference mask - helps ignore minor noise
        threshold_value = 30  # Threshold for significant change
        _, thresholded_diff = cv2.threshold(diff_frame, threshold_value, 255, cv2.THRESH_BINARY)
        
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
        
        # Always clear and recapture the reference frame when starting
        self.reference_frame = None
        self.log("Capturing new reference frame...")
        if not self.capture_reference():
            self.log("Failed to capture reference frame. Please check region selection.")
            self.is_running = False
            return
            
        self.previous_frame = self.reference_frame
        
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
                    
                    # Emit signal to trigger UI update
                    self.detection_signal.emit()
                    
                    # Execute first action immediately
                    self._process_action_sequence()
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
        
        # Execute the action
        if action["action"] == "press_f":
            self.log(f"Action sequence: Pressing F key")
            self._send_f_key()
        elif action["action"] == "press_esc":
            self.log(f"Action sequence: Pressing ESC key")
            self._send_esc_key()
        elif action["action"] == "wait":
            self.log(f"Action sequence: Waiting {action['delay']}s")
            # No actual action needed for wait
            pass
        
        # Schedule the next action after the delay
        time.sleep(action["delay"])
        
        # Move to next step
        self.action_sequence_step += 1
        
        # If we've reached the end, exit the sequence
        if self.action_sequence_step >= len(self.action_sequence):
            self.in_action_sequence = False
            self.log("Action sequence completed")
            
            # Take a new reference frame after completing the sequence
            self.capture_reference()
            
    def _send_f_key(self):
        """Send F key press using AppleScript"""
        try:
            script = '''
            tell application "System Events"
                key code 3 -- "f" key
            end tell
            '''
            subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
            return True
        except Exception as e:
            self.log(f"Error sending F key: {e}")
            return False
            
    def _send_esc_key(self):
        """Send ESC key press using AppleScript"""
        try:
            script = '''
            tell application "System Events"
                key code 53  -- ESC key code
            end tell
            '''
            subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
            return True
        except Exception as e:
            self.log(f"Error sending ESC key: {e}")
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
        
        # Modern macOS theme colors
        self.colors = {
            'bg_overlay': QColor(25, 25, 25, 150),     # Dark background with transparency
            'bg_medium': QColor(53, 54, 57, 220),      # Medium background with transparency
            'accent_blue': QColor(10, 132, 255, 255),  # macOS blue accent
            'accent_blue_light': QColor(50, 172, 255, 200), # Lighter blue
            'accent_green': QColor(48, 209, 88, 255),  # macOS green
            'text': QColor(255, 255, 255, 255),        # White text
            'border': QColor(90, 90, 95, 180)          # Border color with transparency
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
        """Initialize the UI components with modern macOS theme"""
        # Add label with instructions
        self.instructions = QLabel("Click and drag to move selection box. Release to place. (ESC to cancel)", self)
        self.instructions.setStyleSheet("""
            color: white; 
            background-color: rgba(53, 54, 57, 220); 
            padding: 12px;
            border-radius: 10px;
            font-family: Helvetica, Arial, sans-serif;
            font-weight: 500;
            font-size: 13px;
        """)
        self.instructions.setGeometry(
            (self.screen_width - 500) // 2,  # Center horizontally
            30,  # Position from top
            500,  # Width
            40   # Height
        )
        self.instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add "Position on PLAY TOGETHER" button
        self.play_together_button = QPushButton("Position on PLAY TOGETHER", self)
        self.play_together_button.setStyleSheet("""
            background-color: rgba(10, 132, 255, 220); 
            color: white; 
            border: none; 
            padding: 10px 16px;
            border-radius: 10px;
            font-family: Helvetica, Arial, sans-serif;
            font-weight: 500;
            font-size: 13px;
        """)
        self.play_together_button.setGeometry(self.screen_width - 250, 70, 220, 40)
        self.play_together_button.clicked.connect(self.position_on_play_together)
        
        # Show button only if PLAY TOGETHER window was found
        self.play_together_button.setVisible(self.play_together_rect is not None)
        
    def find_play_together_window(self):
        """Try to find the PLAY TOGETHER game window using AppleScript"""
        try:
            # AppleScript to find windows with PLAY TOGETHER in the title
            script = '''
            tell application "System Events"
                set allWindows to {}
                repeat with proc in processes
                    repeat with w in windows of proc
                        if name of w contains "PLAY TOGETHER" or name of w contains "Play Together" or name of w contains "play together" then
                            set winPos to position of w
                            set winSize to size of w
                            return {item 1 of winPos, item 2 of winPos, item 1 of winSize, item 2 of winSize}
                        end if
                    end repeat
                end repeat
                return ""
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=False)
            if result.stdout.strip():
                try:
                    # Parse the result into left, top, width, height
                    values = [int(x) for x in result.stdout.strip().split(", ")]
                    if len(values) == 4:
                        left, top, width, height = values
                        self.play_together_rect = QRect(left, top, width, height)
                        return True
                except Exception as e:
                    print(f"Error parsing window dimensions: {e}")
                    
            # Alternative approach if the above fails - try to find by window title
            script2 = '''
            tell application "System Events"
                set windowNames to {}
                repeat with proc in processes
                    repeat with w in windows of proc
                        set windowNames to windowNames & name of w
                    end repeat
                end repeat
                return windowNames
            end tell
            '''
            
            result2 = subprocess.run(['osascript', '-e', script2], capture_output=True, text=True, check=False)
            print(f"Window titles: {result2.stdout}")
            
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
        """Draw the selection overlay with modern macOS theme"""
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
            painter.fillRect(target_rect, QColor(25, 25, 25, 100))  # Dark overlay
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
            painter.fillRect(play_together_highlight, QColor(10, 132, 255, 30))  # Blue highlight
            painter.setPen(QPen(self.colors['accent_blue'], 2, Qt.PenStyle.DashLine))
            painter.drawRect(play_together_highlight)
            
            # Display a label identifying the window
            game_label_rect = QRect(
                self.play_together_rect.left(), 
                self.play_together_rect.top() - 30,
                self.play_together_rect.width(), 
                30
            )
            painter.fillRect(game_label_rect, QColor(53, 54, 57, 220))  # Dark background
            painter.setPen(self.colors['accent_blue'])
            painter.setFont(QFont("Helvetica", 10, QFont.Weight.Medium))
            painter.drawText(game_label_rect, Qt.AlignmentFlag.AlignCenter, "PLAY TOGETHER WINDOW")
        
        # Draw dimmed rectangle around the selection area to highlight it
        # Create four rectangles to cover all areas except the selection
        # Top area
        painter.fillRect(
            QRect(0, 0, self.screen_width, self.box_rect.top()),
            QColor(25, 25, 25, 150)  # Dark with transparency
        )
        # Bottom area
        painter.fillRect(
            QRect(0, self.box_rect.bottom() + 1, self.screen_width, self.screen_height - self.box_rect.bottom() - 1),
            QColor(25, 25, 25, 150)
        )
        # Left area
        painter.fillRect(
            QRect(0, self.box_rect.top(), self.box_rect.left(), self.box_rect.height()),
            QColor(25, 25, 25, 150)
        )
        # Right area
        painter.fillRect(
            QRect(self.box_rect.right() + 1, self.box_rect.top(), 
                  self.screen_width - self.box_rect.right() - 1, self.box_rect.height()),
            QColor(25, 25, 25, 150)
        )
        
        # Draw crosshairs - blue accent
        painter.setPen(QPen(self.colors['accent_blue'], 1, Qt.PenStyle.DashLine))
        painter.drawLine(0, self.mouse_pos.y(), self.screen_width, self.mouse_pos.y())
        painter.drawLine(self.mouse_pos.x(), 0, self.mouse_pos.x(), self.screen_height)
        
        # Ensure box stays within screen bounds
        self.constrain_box_to_screen()
        
        # Draw selection box border - blue accent
        outer_pen = QPen(self.colors['accent_blue'], 2)
        painter.setPen(outer_pen)
        painter.drawRoundedRect(self.box_rect, 10, 10)  # Rounded corners
        
        # Add a second, inner border for better visibility
        inner_rect = QRect(
            self.box_rect.left() + 3, 
            self.box_rect.top() + 3, 
            self.box_rect.width() - 6, 
            self.box_rect.height() - 6
        )
        painter.setPen(QPen(self.colors['accent_blue_light'], 1))
        painter.drawRoundedRect(inner_rect, 8, 8)  # Rounded corners
        
        # Draw semi-transparent fill
        painter.fillRect(self.box_rect, QColor(10, 132, 255, 15))  # Very light blue
        
        # Draw grid lines
        painter.setPen(QPen(self.colors['accent_blue_light'], 1, Qt.PenStyle.DashLine))
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
        
        # Draw coordinates with macOS-style pill background
        coord_text = f"Position: ({self.box_rect.left()},{self.box_rect.top()}) • Size: {self.box_width}×{self.box_height}"
        text_width = 400
        text_height = 30
        
        # Create pill background
        coord_rect = QRect(
            (self.screen_width - text_width) // 2,
            self.screen_height - 50, 
            text_width, 
            text_height
        )
        
        # Draw background pill
        path = QPainterPath()
        path.addRoundedRect(QRectF(coord_rect), 15, 15)
        painter.fillPath(path, QColor(53, 54, 57, 220))  # Dark background
        
        # Draw text
        painter.setPen(self.colors['text'])
        painter.setFont(QFont("Helvetica", 11, QFont.Weight.Medium))
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
            'bg_dark': '#2C3639',      # Deep charcoal background
            'bg_wood': '#3F4E4F',      # Wood tone
            'grid': '#555555',         # Grid color
            'matcha': '#A0C49D',       # Medium matcha
            'matcha_light': '#DAE5D0', # Light matcha
            'alert': '#F87474',        # Soft red
            'text': '#FFFFFF',         # White text
            'text_dim': '#DCD7C9',     # Dim text
        }
        
        # Create figure and axes with matcha wood theme
        self.fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        self.fig.set_facecolor(self.colors['bg_wood'])
        self.ax.set_facecolor(self.colors['bg_wood'])
        
        # Initialize with empty data
        self.x_data = np.arange(100)
        self.y_data = np.zeros(100)
        
        # Create the plot with matcha colors
        self.activity_line, = self.ax.plot(self.x_data, self.y_data, color=self.colors['matcha'], linewidth=1.5)
        self.threshold_line = self.ax.axhline(y=0.05, color=self.colors['alert'], linestyle='--', alpha=0.7, linewidth=1)
        
        # Configure appearance for matcha wood theme
        self.ax.set_xlim(0, 99)
        self.ax.set_ylim(0, 1)
        self.ax.set_xticks([])
        
        # Add subtle grid lines
        self.ax.grid(True, alpha=0.15, color=self.colors['grid'])
        
        # Set text styling - using standard fonts that matplotlib supports
        self.ax.set_title("Activity Timeline", color=self.colors['matcha_light'], fontsize=11, 
                         fontweight='medium')
        
        # Set text color for axis labels and ticks
        self.ax.tick_params(axis='y', colors=self.colors['text_dim'], labelsize=9)
        self.ax.yaxis.label.set_color(self.colors['text'])
        
        # Remove spines
        for spine in self.ax.spines.values():
            spine.set_color(self.colors['grid'])
            spine.set_linewidth(0.5)
        
        # Initialize the canvas
        super().__init__(self.fig)
        self.setParent(parent)
        
        # Set up a tight layout
        self.fig.tight_layout(pad=1.2)
        
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
        
        # Update title with threshold value in minimal format - using standard fonts
        self.ax.set_title(f"Activity Timeline [threshold: {threshold:.2f}]", 
                        color=self.colors['matcha_light'], fontsize=11, 
                        fontweight='medium')
        
        # Redraw the canvas
        self.draw()


class MonitoringDisplay(QWidget):
    """Widget for displaying the captured region and difference visualization"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 250)
        
        # Define colors
        self.colors = {
            'bg_dark': '#2C3639',      # Deep charcoal background
            'bg_wood': '#3F4E4F',      # Wood tone
            'matcha': '#A0C49D',       # Medium matcha
            'matcha_light': '#DAE5D0', # Light matcha
            'matcha_dark': '#7D8F69',  # Dark matcha
            'alert': '#F87474',        # Soft red
            'warning': '#F9B572',      # Soft orange
            'text': '#FFFFFF',         # White text
        }
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)  # Reduced spacing for slimmer appearance
        
        # Image display label with rounded corners
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(f"""
            background-color: {self.colors['bg_wood']}; 
            border: none; 
            border-radius: 10px;
            padding: 4px;
        """)
        layout.addWidget(self.image_label)
        
        # Status indicators in a ultra-slim frame
        status_frame = QFrame()
        status_frame.setMaximumHeight(28)  # Make it slimmer
        status_frame.setStyleSheet(f"""
            background-color: {self.colors['bg_wood']};
            border-radius: 6px;
            padding: 0px;
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 2, 8, 2)  # Very slim padding
        status_layout.setSpacing(6)
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.status_label)
        
        self.change_label = QLabel("Change: 0.00%")
        self.change_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.change_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addWidget(status_frame)
        
        # Pre-allocate reusable image buffers for performance
        self._last_pixmap = None
        self._last_display_time = 0
        self._display_throttle_ms = 16.67  # ~60fps
        
    def update_display(self, color_frame, diff_frame, change_percent):
        """Update the display with improved rendering to reduce noise - optimized for performance"""
        if color_frame is None:
            return
            
        # Throttle updates for better performance, but with higher frame rate
        current_time = time.time() * 1000  # Convert to ms
        if current_time - self._last_display_time < self._display_throttle_ms:
            return
            
        self._last_display_time = current_time
            
        try:
            # Create a clean copy for display - optimize by avoiding unnecessary copies
            display_frame = color_frame

            if diff_frame is not None:
                # Apply a more selective highlighting approach
                # Convert diff_frame to 3 channel if it's grayscale
                if len(diff_frame.shape) == 2:
                    # Create a colored mask for changes - using blue for visibility (macOS style)
                    # Optimized version with fewer operations
                    change_indices = diff_frame > 0
                    if np.any(change_indices):
                        # Only modify pixels that actually changed - create a copy only when needed
                        if id(display_frame) == id(color_frame):
                            display_frame = color_frame.copy()
                        # Use matcha green for highlights
                        display_frame[change_indices, 0] = 157   # B value (in BGR)
                        display_frame[change_indices, 1] = 196   # G value
                        display_frame[change_indices, 2] = 160   # R value
            
            # Convert BGR to RGB for proper display
            display_frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            # Convert to QImage for display - avoid memory copies when possible
            height, width, channels = display_frame_rgb.shape
            bytes_per_line = channels * width
            
            q_img = QImage(display_frame_rgb.data, width, height, 
                          bytes_per_line, QImage.Format.Format_RGB888)
            
            # Scale image to fit label while maintaining aspect ratio
            pixmap = QPixmap.fromImage(q_img)
            
            # Only rescale if the size changed
            if (self._last_pixmap is None or 
                self.image_label.width() != self._last_pixmap.width() or 
                self.image_label.height() != self._last_pixmap.height()):
                
                scaled_pixmap = pixmap.scaled(
                    self.image_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation  # Use smooth transformation for better quality
                )
                self._last_pixmap = scaled_pixmap
            else:
                # Use cached pixmap size
                scaled_pixmap = pixmap.scaled(
                    self._last_pixmap.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._last_pixmap = scaled_pixmap
                
            self.image_label.setPixmap(self._last_pixmap)
            
            # Update change percentage display
            self.change_label.setText(f"Change: {change_percent:.2%}")
            
        except Exception as e:
            print(f"Error updating display: {e}")
    
    def set_status(self, status):
        """Update the status display with Matcha Wood theme colors"""
        if status == "running":
            self.status_label.setText("Status: Running")
            self.status_label.setStyleSheet(f"color: {self.colors['matcha']}; font-weight: 500; font-size: 12px;")
        elif status == "stopped":
            self.status_label.setText("Status: Stopped")
            self.status_label.setStyleSheet(f"color: {self.colors['alert']}; font-weight: 500; font-size: 12px;")
        elif status == "paused":
            self.status_label.setText("Status: Paused")
            self.status_label.setStyleSheet(f"color: {self.colors['warning']}; font-weight: 500; font-size: 12px;")
        elif status == "action_sequence":
            self.status_label.setText("Status: Action Sequence")
            self.status_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        else:
            self.status_label.setText(f"Status: {status}")
            self.status_label.setStyleSheet(f"color: {self.colors['text']}; font-weight: 500; font-size: 12px;")


class PixelChangeApp(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pixel Change Detector")
        self.setMinimumSize(800, 550)  # More compact minimum size
        
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
            'bg_dark': '#2C3639',      # Deep charcoal for background
            'bg_wood': '#3F4E4F',      # Darker wood tone
            'bg_light': '#A27B5C',     # Light wood accent
            'bg_control': '#A27B5C',   # Wood tone for controls
            
            # Text colors
            'text': '#FFFFFF',         # White text
            'text_dim': '#DCD7C9',     # Soft beige for secondary text
            'text_secondary': '#C8B6A6', # Muted wood tone for tertiary text
            'text_dark': '#2C3639',    # Dark text for light backgrounds
            
            # Accent colors - Matcha and wood tones
            'matcha': '#A0C49D',       # Medium matcha green
            'matcha_light': '#DAE5D0',  # Light matcha
            'matcha_dark': '#7D8F69',   # Dark matcha
            'wood_accent': '#C8B6A6',   # Light wood accent
            
            # Status colors
            'success': '#A0C49D',      # Success - matcha green
            'alert': '#F87474',        # Error - soft red
            'warning': '#F9B572',      # Warning - soft orange
            'border': '#454649',       # Border color
        }
        
    def _init_ui(self):
        """Initialize the user interface - Matcha Wood theme"""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        
        # Set application-wide stylesheet - Matcha Wood theme
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ 
                background-color: {self.colors['bg_dark']}; 
                color: {self.colors['text']}; 
                font-family: Helvetica, Arial, sans-serif;
            }}
            
            QGroupBox {{ 
                background-color: {self.colors['bg_wood']}; 
                color: {self.colors['text_dim']}; 
                border: none;
                border-radius: 10px; 
                margin-top: 1.2em;
                font-weight: 500;
                font-size: 13px;
            }}
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                left: 12px; 
                padding: 0 8px 0 8px;
                color: {self.colors['matcha_light']};
            }}
            
            QLabel {{ 
                color: {self.colors['text']}; 
                font-size: 13px;
                background: transparent;
            }}
            
            QPushButton {{ 
                background-color: {self.colors['bg_wood']}; 
                color: {self.colors['text']}; 
                border: none; 
                padding: 8px 16px; 
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
                min-height: 28px;
                margin: 2px;
            }}
            QPushButton:hover {{ 
                background-color: {self.colors['matcha_dark']}; 
            }}
            QPushButton:pressed {{ 
                background-color: {self.colors['matcha']}; 
                color: {self.colors['text_dark']};
            }}
            QPushButton:disabled {{ 
                color: {self.colors['text_secondary']}; 
                background-color: {self.colors['bg_wood']};
                opacity: 0.8;
            }}
            
            QTextEdit {{ 
                background-color: {self.colors['bg_wood']}; 
                color: {self.colors['text']}; 
                border: none; 
                border-radius: 8px;
                font-family: 'Menlo', 'Monaco', monospace;
                font-size: 12px;
                padding: 6px;
                selection-background-color: {self.colors['matcha']};
            }}
            
            QSlider::groove:horizontal {{
                border: none;
                height: 4px;
                background: {self.colors['bg_dark']};
                margin: 0px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {self.colors['matcha']};
                border: none;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {self.colors['matcha_light']};
            }}
            
            QCheckBox {{
                color: {self.colors['text']};
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: none;
                background-color: {self.colors['bg_dark']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors['matcha']};
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNCIgaGVpZ2h0PSIxNCIgdmlld0JveD0iMCAwIDE0IDE0Ij48cGF0aCBmaWxsPSIjRkZGRkZGIiBkPSJNNS43MzMgMTBMMTIgMy43MzMgMTAuMjY3IDIgNS43MzMgNi41MzMgMy43MzMgNC41MzMgMiA2LjI2N3oiLz48L3N2Zz4=);
            }}
        """)
        
        # Create left panel (controls) with macOS spacing
        left_panel = QWidget()
        left_panel.setFixedWidth(280)  # Slightly wider for better readability
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)  # Standard macOS spacing
        main_layout.addWidget(left_panel)
        
        # Create right panel (visualization)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)  # Standard macOS spacing
        main_layout.addWidget(right_panel)
        
        # === LEFT PANEL COMPONENTS ===
        
        # 1. Settings group - macOS style
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        settings_layout.setSpacing(12)
        left_layout.addWidget(settings_group)
        
        # Threshold control
        threshold_layout = QHBoxLayout()
        threshold_layout.setSpacing(10)
        threshold_label = QLabel("Threshold:")
        threshold_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        threshold_layout.addWidget(threshold_label)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(1, 50)  # 0.01 to 0.50
        self.threshold_slider.setValue(5)      # Default 0.05
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_value_label = QLabel("0.05")
        self.threshold_value_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        threshold_layout.addWidget(self.threshold_value_label)
        settings_layout.addLayout(threshold_layout)
        
        # Region size control
        size_layout = QHBoxLayout()
        size_layout.setSpacing(10)
        size_label = QLabel("Region Size:")
        size_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        size_layout.addWidget(size_label)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(20, 200)  # 20 to 200 pixels
        self.size_slider.setValue(50)      # Default 100
        self.size_slider.valueChanged.connect(self.update_size_label)
        size_layout.addWidget(self.size_slider)
        
        self.size_value_label = QLabel("50")
        self.size_value_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        size_layout.addWidget(self.size_value_label)
        settings_layout.addLayout(size_layout)
        
        # Add noise reduction controls
        settings_layout.addSpacing(4)
        
        # Noise reduction settings
        noise_layout = QHBoxLayout()
        noise_layout.setSpacing(10)
        noise_label = QLabel("Noise Reduction:")
        noise_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        noise_layout.addWidget(noise_label)
        
        self.noise_checkbox = QCheckBox("On")
        self.noise_checkbox.setChecked(True)
        self.noise_checkbox.toggled.connect(self.toggle_noise_reduction)
        noise_layout.addWidget(self.noise_checkbox)
        
        settings_layout.addLayout(noise_layout)
        
        # 2. Monitoring group - macOS style
        monitoring_group = QGroupBox("Monitoring")
        monitoring_layout = QVBoxLayout(monitoring_group)
        monitoring_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        monitoring_layout.setSpacing(12)
        left_layout.addWidget(monitoring_group)
        
        # Region selection button
        self.region_button = QPushButton("Select Region")
        self.region_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['matcha_dark']};
                color: {self.colors['text']};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {self.colors['matcha']};
            }}
        """)
        self.region_button.clicked.connect(self.select_region)
        monitoring_layout.addWidget(self.region_button)
        
        # Region info display
        region_info_layout = QHBoxLayout()
        region_info_layout.setSpacing(8)
        status_label = QLabel("Status:")
        status_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        region_info_layout.addWidget(status_label)
        
        self.region_info_label = QLabel("No region selected")
        region_info_layout.addWidget(self.region_info_label)
        monitoring_layout.addLayout(region_info_layout)
        
        # 3. Control group - macOS style
        control_group = QGroupBox("Control")
        control_layout = QVBoxLayout(control_group)
        control_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        control_layout.setSpacing(12)
        left_layout.addWidget(control_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        self.start_button = QPushButton("Start")
        self.start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['matcha']};
                color: {self.colors['text_dark']};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self.colors['matcha_light']};
            }}
        """)
        self.start_button.clicked.connect(self.start_detection)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['alert']};
                color: #FFFFFF;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #FF8A8A;
            }}
        """)
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['warning']};
                color: {self.colors['text_dark']};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #FFCA85;
            }}
        """)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        button_layout.addWidget(self.pause_button)
        
        control_layout.addLayout(button_layout)
        
        # Second row of buttons
        button_layout2 = QHBoxLayout()
        button_layout2.setSpacing(8)
        
        self.reference_button = QPushButton("Capture Reference")
        self.reference_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_light']};
                color: {self.colors['text']};
            }}
            QPushButton:hover {{
                background-color: {self.colors['wood_accent']};
                color: {self.colors['text_dark']};
            }}
        """)
        self.reference_button.clicked.connect(self.capture_reference)
        button_layout2.addWidget(self.reference_button)
        
        self.clear_button = QPushButton("Clear Logs")
        self.clear_button.clicked.connect(self.clear_logs)
        button_layout2.addWidget(self.clear_button)
        
        control_layout.addLayout(button_layout2)
        
        # 4. Log display - macOS style
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        log_layout.setSpacing(8)
        left_layout.addWidget(log_group, stretch=1)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        
        # === RIGHT PANEL COMPONENTS ===
        
        # 1. Monitoring display with matcha wood theme
        monitor_group = QGroupBox("Live Monitor")
        monitor_layout = QVBoxLayout(monitor_group)
        monitor_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        monitor_layout.setSpacing(8)
        
        self.monitor_display = MonitoringDisplay()
        self.monitor_display.setStyleSheet(f"""
            QLabel {{ 
                background-color: {self.colors['bg_wood']}; 
                border: none; 
                border-radius: 8px;
            }}
        """)
        monitor_layout.addWidget(self.monitor_display)
        right_layout.addWidget(monitor_group, stretch=3)
        
        # 2. Timeline plot in its own group
        timeline_group = QGroupBox("Activity Timeline")
        timeline_layout = QVBoxLayout(timeline_group)
        timeline_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        
        self.timeline_plot = TimelinePlot(width=5, height=1.5)
        timeline_layout.addWidget(self.timeline_plot)
        
        right_layout.addWidget(timeline_group, stretch=1)
        
        # 3. Status and count display
        status_frame = QFrame()
        status_frame.setMaximumHeight(28)  # Keep it slim
        status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors['bg_wood']};
                border-radius: 6px;
                padding: 0px;
            }}
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 2, 8, 2)  # Very slim padding
        status_layout.setSpacing(8)
        
        self.status_label = QLabel("Status: Waiting")
        self.status_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.status_label)
        
        self.count_label = QLabel("Detections: 0")
        self.count_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.count_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        right_layout.addWidget(status_frame)
        
        # Add a welcome log message
        self.add_log("Pixel Change Detector initialized")
        self.add_log("macOS Modern UI Theme")
        self.add_log("Click 'Select Region' to begin")
    
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
        selection_dialog = RegionSelectionOverlay(None, region_size)
        selection_dialog.region_selected.connect(self.set_region)
        
        # Force the selection dialog to stay on top
        selection_dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        
        # Show dialog and make it active - fullscreen
        selection_dialog.showFullScreen()
        selection_dialog.activateWindow()
        selection_dialog.raise_()
        
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
        
        result = selection_dialog.exec()
        
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
        self.status_label.setStyleSheet(f"color: {self.colors['matcha']}; font-weight: 500; font-size: 12px;")
    
    def stop_detection(self):
        """Stop the detection process"""
        self.detector.stop_detection()
        
        # Update UI
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.monitor_display.set_status("stopped")
        self.status_label.setText("Status: Stopped")
        self.status_label.setStyleSheet(f"color: {self.colors['alert']}; font-weight: 500; font-size: 12px;")
    
    def toggle_pause(self):
        """Pause or resume detection"""
        self.detector.toggle_pause()
        
        if self.detector.is_paused:
            self.pause_button.setText("Resume")
            self.monitor_display.set_status("paused")
            self.status_label.setText("Status: Paused")
            self.status_label.setStyleSheet(f"color: {self.colors['warning']}; font-weight: 500; font-size: 12px;")
        else:
            self.pause_button.setText("Pause")
            self.monitor_display.set_status("running")
            self.status_label.setText("Status: Running")
            self.status_label.setStyleSheet(f"color: {self.colors['matcha']}; font-weight: 500; font-size: 12px;")
    
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
        self.status_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        
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
                self.status_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        except Exception as e:
            print(f"Error updating visualization: {e}")
            # Don't stop the application on visualization errors
    
    def toggle_noise_reduction(self, checked):
        """Toggle noise reduction processing"""
        if self.detector:
            self.detector.apply_blur = checked
            self.add_log(f"Noise reduction {'enabled' if checked else 'disabled'}")


def main():
    app = QApplication(sys.argv)
    window = PixelChangeApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()