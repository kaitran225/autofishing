import time
import threading
import queue
import datetime
import numpy as np
import cv2
import mss
import subprocess
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject

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
        
        # Updated action sequence with longer delays for better detection on bright backgrounds
        self.action_sequence = [
            {"action": "press_f", "delay": 0.0},
            {"action": "wait", "delay": 4.0},  # Increased from 3.0 to 4.0
            {"action": "press_esc", "delay": 1.5},  # Increased from 1.0 to 1.5
            {"action": "wait", "delay": 2.0},  # Increased from 1.0 to 2.0
            {"action": "press_f", "delay": 2.0}   # Increased from 1.0 to 2.0
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