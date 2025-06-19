"""
Core detection and action functionality for AutoFisher
"""
import time
import threading
import queue
import traceback
import numpy as np
import cv2
from PyQt6.QtCore import QObject, pyqtSignal
import keyboard
import mss
import pyautogui
import logging

from utils.constants import (
    DEFAULT_THRESHOLD, DEFAULT_DETECTION_COOLDOWN,
    DEFAULT_FISHING_KEY, DEFAULT_CAPTURE_INTERVAL, 
    DEFAULT_HIGH_PERFORMANCE, DEFAULT_RESPECT_FULLSCREEN,
    DEFAULT_DIRECT_CONTROL, GAME_WINDOW_NAMES
)
from utils.win32_utils import find_window_by_pattern, is_fullscreen_app_active
from utils.input import send_key_press, send_esc
from core.processing import capture_screen_region, calculate_frame_difference

class PixelChangeDetector(QObject):
    """Core detector for pixel changes in the game window"""
    
    # Define signals
    detection_signal = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__()
        # Store parent for callbacks
        self.parent = parent
        
        # Initialize logging
        self.log_history = []  # Store log messages locally
        
        # Initialize variables
        self.region = None
        self.reference_frame = None
        self.previous_frame = None
        self.current_frame = None
        self.color_frame = None  # For visualization
        self.diff_frame = None
        
        # Play Together window handling
        self.play_together_window = None
        
        # Detection parameters
        self.THRESHOLD = DEFAULT_THRESHOLD
        self.detection_cooldown = DEFAULT_DETECTION_COOLDOWN
        self.last_detection_time = 0
        self.change_history = []
        self.fishing_key = DEFAULT_FISHING_KEY
        
        # Options
        self.high_performance_mode = DEFAULT_HIGH_PERFORMANCE
        self.respect_fullscreen = DEFAULT_RESPECT_FULLSCREEN
        self.direct_control = DEFAULT_DIRECT_CONTROL
        
        # Thread handling
        self.thread_control = {"stop_requested": False}
        self.running = False
        self.paused = False
        self.capture_interval = DEFAULT_CAPTURE_INTERVAL
        
        # Initialize stats
        self.stats = {
            "total_detections": 0,
            "last_detection_time": 0,
            "avg_detection_interval": 0
        }
        
        # Find Play Together window
        self.find_play_together_process()
        
        # Set up performance metrics
        self.performance = {
            "fps": 0,
            "processing_samples": 0
        }
        
        # Log initialization
        self.log("PixelChangeDetector initialized")
        
        # Create a logger
        self.logger = logging.getLogger("PixelChangeDetector")
        self.logger.setLevel(logging.DEBUG)
        
        # Create console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(ch)
    
    def log(self, message):
        """Log a message to the parent application or print to console"""
        try:
            # Send to parent's log queue if available
            if self.parent:
                # Make sure we're using the parent's log method
                self.parent.log(message)
            else:
                # Otherwise print to console
                print(f"[Detector] {message}")
                
            # Add to local log history
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.log_history.append(f"[{timestamp}] {message}")
            while len(self.log_history) > 100:  # Limit history size
                self.log_history.pop(0)
        except Exception as e:
            # Emergency fallback
            print(f"[ERROR] Failed to log message: {e}")
            print(f"[DEBUG] Original message: {message}")
    
    def find_play_together_process(self):
        """Find Play Together window handle"""
        self.play_together_window = find_window_by_pattern(GAME_WINDOW_NAMES)
        
        if self.play_together_window:
            self.log(f"Found Play Together window: {self.play_together_window}")
            return True
        else:
            self.log("No Play Together window found. Please make sure the game is running.")
            return False
            
    def focus_play_together_window(self):
        """Focus the Play Together window"""
        from utils.win32_utils import force_focus_window
        
        if not self.play_together_window:
            self.find_play_together_process()
            if not self.play_together_window:
                self.log("Cannot focus window: Play Together window not found")
                return False
                
        # Try to focus the window
        result = force_focus_window(self.play_together_window)
        if result:
            self.log("Successfully focused Play Together window")
        else:
            self.log("Failed to focus Play Together window")
            
        return result
    
    def capture_reference(self):
        """Capture a reference frame for comparison"""
        frame, color_frame = capture_screen_region(self.region)
        if frame is not None:
            self.reference_frame = frame
            self.color_frame = color_frame
            self.log(f"Reference frame captured: {self.reference_frame.shape}")
            return True
        else:
            self.log("Failed to capture reference frame")
            return False
    
    def capture_screen(self):
        """
        Capture the screen region with minimal processing for raw preview
        
        Returns:
            numpy.ndarray: The captured image in RGB format
        """
        try:
            if not self.region:
                print("No region selected. Please select a region first.")
                return None
                
            # Validate region size
            left, top, right, bottom = self.region
            width = right - left
            height = bottom - top
            
            if width < 10 or height < 10:
                print("Invalid region size detected. Please select a new region.")
                return None
                
            # Use mss library which has better performance and multi-monitor support
            with mss.mss() as sct:
                # Convert region format to mss format (left, top, width, height)
                mss_region = {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height
                }
                
                # Capture the region
                screenshot = sct.grab(mss_region)
                
                # Convert to numpy array - sct.grab returns BGRA
                frame = np.array(screenshot)
                
            # Validate frame
            if frame.size == 0:
                print("Error: Captured frame is empty")
                self.consecutive_failures += 1
                return None
                
            # Store color frame for visualization (convert BGRA to RGB)
            if len(frame.shape) >= 3:
                self.color_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                # Return the raw RGB frame
                return self.color_frame
            else:
                self.color_frame = None
                # Return the raw frame as is
                return frame
            
        except Exception as e:
            print(f"Error capturing screen: {e}")
            import traceback
            traceback.print_exc()
            self.consecutive_failures += 1
            return None
    
    def validate_region(self):
        """Validate the selected region with a preview capture"""
        frame, _ = capture_screen_region(self.region)
        if frame is not None:
            self.log(f"Region validation successful: captured {frame.shape}")
            return True
        else:
            self.log("Failed to validate region")
            return False
    
    def start_detection(self):
        """Start detection thread"""
        if not self.find_play_together_process():
            self.log("Cannot start detection: Play Together window not found")
            return False
            
        self.running = True
        self.paused = False
        self.change_history = []
        
        # Capture initial frame as reference if none exists
        if self.reference_frame is None:
            self.capture_reference()
            
        self.previous_frame = self.reference_frame
        
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        return True
    
    def stop_detection(self):
        """Stop detection thread"""
        self.running = False
        
    def _detection_loop(self):
        """Main detection loop"""
        self.log("Starting detection loop")
        
        # Initialize performance tracking
        frame_counter = 0
        fps_counter = 0
        fps_timer = time.time()
        
        # Track consecutive detections to filter false positives
        detection_intensity = 0  # Used to track detection confidence
        
        while self.running:
            try:
                # Check if paused
                if self.paused:
                    time.sleep(0.1)
                    continue
                    
                # Check if we should respect fullscreen apps
                if self.respect_fullscreen and is_fullscreen_app_active():
                    time.sleep(0.5)  # Sleep longer when fullscreen app is active
                    continue
                    
                # Capture current frame
                self.current_frame = self.capture_screen()
                
                if self.current_frame is None:
                    time.sleep(0.1)
                    continue
                    
                # Use reference frame if available, otherwise use previous frame
                compare_frame = self.reference_frame if self.reference_frame is not None else self.previous_frame
                
                if compare_frame is None:
                    self.capture_reference()
                    time.sleep(0.1)
                    continue
                
                # Calculate difference
                self.diff_frame, change_percent = self.calculate_frame_difference(
                    self.current_frame, compare_frame
                )
                
                # Store in history
                self.change_history.append(change_percent)
                if len(self.change_history) > 100:
                    self.change_history = self.change_history[-100:]
                
                # Check for detection with cooldown
                current_time = time.time()
                cooldown_passed = (current_time - self.last_detection_time) > self.detection_cooldown
                
                # Calculate triggering threshold with hysteresis
                # Use higher threshold for isolated frames to avoid false positives
                # Use lower threshold for consecutive detections
                trigger_threshold = self.THRESHOLD * (1.0 - min(detection_intensity / 10.0, 0.5))
                
                if change_percent > trigger_threshold:
                    # Increase detection confidence
                    detection_intensity = min(detection_intensity + 1, 10)
                    
                    # Check if we should trigger action sequence
                    if detection_intensity >= 3 and cooldown_passed:  # Require at least 3 consecutive detections
                        change_percent_display = round(change_percent * 100, 2)
                        self.log(f"Major pixel change detected! Change: {change_percent_display}% (Confidence: {detection_intensity}/10)")
                        self.last_detection_time = current_time
                        
                        # Reset detection intensity after triggering
                        detection_intensity = 0
                        
                        # Update stats
                        self.stats["total_detections"] += 1
                        
                        # Calculate interval since last detection
                        if self.stats["last_detection_time"] > 0:
                            interval = current_time - self.stats["last_detection_time"]
                            # Update average detection interval using moving average
                            if self.stats["avg_detection_interval"] == 0:
                                self.stats["avg_detection_interval"] = interval
                            else:
                                self.stats["avg_detection_interval"] = (
                                    0.8 * self.stats["avg_detection_interval"] + 0.2 * interval
                                )
                        self.stats["last_detection_time"] = current_time
                        
                        # Emit the detection signal
                        self.detection_signal.emit()
                        
                        # Handle the detection with fishing sequence
                        self._handle_detection()
                else:
                    # Gradually decrease detection confidence
                    detection_intensity = max(detection_intensity - 0.5, 0)
                    
                # Store current frame as previous for next comparison if not using reference
                if self.reference_frame is None:
                    self.previous_frame = self.current_frame
                
                # Update performance metrics
                frame_counter += 1
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    fps = fps_counter
                    fps_counter = 0
                    fps_timer = time.time()
                    
                    # Update performance metrics
                    self.performance["fps"] = fps
                    self.performance["processing_samples"] += 1
                    if self.performance["processing_samples"] > 100:
                        self.performance["processing_samples"] = 1
                
                # Sleep to control capture rate - use adaptive timing based on performance
                sleep_time = max(0.01, self.capture_interval)  # Minimum 10ms sleep
                time.sleep(sleep_time)
                
            except Exception as e:
                self.log(f"Error in detection loop: {e}")
                traceback.print_exc()
                time.sleep(0.1)  # Short delay on error
                # Reset detection intensity on errors
                detection_intensity = 0
        
        # Thread is exiting
        self.log("Detection thread exiting")
        self.running = False
        
    def _handle_detection(self):
        """Handle detection event with optimized sequence"""
        try:
            # STEP 1: Press fishing key to catch fish
            self.log("STEP 1: Catching fish...")
            success = False
            
            # Try up to 3 times to press fishing key
            for attempt in range(3):
                if self.focus_play_together_window():
                    self.log(f"Pressing {self.fishing_key.upper()} key to catch fish (attempt {attempt+1})")
                    if send_key_press(self.fishing_key, self.play_together_window):
                        success = True
                        break
                    time.sleep(0.2)
                else:
                    self.log(f"Failed to focus window, retrying ({attempt+1}/3)")
                    time.sleep(0.1)
            
            if not success:
                self.log("Failed to send fishing key after multiple attempts")
            
            # STEP 2: Wait for cooldown period
            cooldown = self.detection_cooldown
            self.log(f"STEP 2: Pausing for {cooldown:.1f} seconds...")
            
            # Wait for cooldown period
            pause_start = time.time()
            pause_end = pause_start + cooldown
            
            while time.time() < pause_end and self.running and not self.thread_control.get("stop_requested", False):
                time.sleep(0.1)
            
            # STEP 3: Exit fishing menu with ESC key
            if self.running and not self.thread_control.get("stop_requested", False):
                self.log("STEP 3: Exiting fishing menu...")
                success = False
                
                # Try up to 3 times to press ESC key
                for attempt in range(3):
                    if self.focus_play_together_window():
                        self.log(f"Pressing ESC key (attempt {attempt+1})")
                        if send_esc(self.play_together_window):
                            success = True
                            break
                        time.sleep(0.2)
                    else:
                        self.log(f"Failed to focus window for ESC key, retrying ({attempt+1}/3)")
                        time.sleep(0.1)
                
                if not success:
                    self.log("Failed to send ESC key after multiple attempts")
            
            # STEP 4: Wait briefly for menu to close
            self.log("STEP 4: Waiting for menu to close...")
            menu_close_time = 2.0  # Wait 2 seconds for menu to close
            menu_close_end = time.time() + menu_close_time
            
            while time.time() < menu_close_end and self.running and not self.thread_control.get("stop_requested", False):
                time.sleep(0.1)
            
            # STEP 5: Cast fishing line again
            if self.running and not self.thread_control.get("stop_requested", False):
                self.log("STEP 5: Casting fishing line again...")
                success = False
                
                # Try up to 3 times to cast fishing line
                for attempt in range(3):
                    if self.focus_play_together_window():
                        self.log(f"Casting fishing line with {self.fishing_key.upper()} key (attempt {attempt+1})")
                        if send_key_press(self.fishing_key, self.play_together_window):
                            success = True
                            break
                        time.sleep(0.2)
                    else:
                        self.log(f"Failed to focus window for casting, retrying ({attempt+1}/3)")
                        time.sleep(0.1)
                
                if not success:
                    self.log("Failed to cast fishing line after multiple attempts")
                
                # Wait for screen to update after casting
                self.log("Waiting for screen to update after casting...")
                time.sleep(2)
                
                # Capture new reference frame
                self.log("Capturing new reference frame...")
                self.capture_reference()
                self.log("New reference frame captured after casting")
            
            # STEP 6: Resume monitoring
            self.log("STEP 6: Resuming monitoring...")
            
            # STEP 7: Stabilization pause
            self.log("STEP 7: Short stabilization pause...")
            stabilize_time = min(1.5, self.detection_cooldown * 0.15)
            time.sleep(stabilize_time)
            
            self.log("Action sequence completed successfully")
            
        except Exception as e:
            self.log(f"Error during action sequence: {e}")
            traceback.print_exc()
            # Try to recover by capturing new reference
            if self.running and not self.thread_control.get("stop_requested", False):
                # Try to capture new reference frame to recover
                try:
                    self.capture_reference()
                    self.log("Captured recovery reference frame")
                except:
                    pass 
    
    def calculate_frame_difference(self, frame1, frame2):
        """
        Calculate the difference between two frames with minimal processing
        
        Args:
            frame1: First frame
            frame2: Second frame
            
        Returns:
            tuple: (diff_frame, change_percent)
        """
        if frame1 is None or frame2 is None:
            return None, 0
            
        try:
            # Ensure frames have same dimensions
            if frame1.shape != frame2.shape:
                # Resize to match
                frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
            
            # Apply slight blur to reduce noise sensitivity
            frame1_blurred = cv2.GaussianBlur(frame1, (5, 5), 0)
            frame2_blurred = cv2.GaussianBlur(frame2, (5, 5), 0)
            
            # For color images - use direct absolute difference
            if len(frame1.shape) == 3:
                # Calculate absolute difference directly
                diff_frame = cv2.absdiff(frame1_blurred, frame2_blurred)
                
                # Convert to grayscale for threshold calculation
                diff_gray = cv2.cvtColor(diff_frame, cv2.COLOR_RGB2GRAY)
                
                # Calculate percentage of pixels that changed significantly
                threshold = 20  # Lower threshold for more sensitivity
                changed_pixels = np.sum(diff_gray > threshold)
                total_pixels = diff_gray.shape[0] * diff_gray.shape[1]
                change_percent = changed_pixels / total_pixels
                
                # Return the raw difference frame and change percentage
                return diff_frame, change_percent
            else:
                # For grayscale images
                diff_frame = cv2.absdiff(frame1_blurred, frame2_blurred)
                
                # Calculate percentage of changed pixels
                threshold = 20
                changed_pixels = np.sum(diff_frame > threshold)
                total_pixels = diff_frame.shape[0] * diff_frame.shape[1]
                change_percent = changed_pixels / total_pixels
                
                return diff_frame, change_percent
                
        except Exception as e:
            print(f"Error calculating frame difference: {e}")
            import traceback
            traceback.print_exc()
            return None, 0 