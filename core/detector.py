"""
Core detection functionality for AutoFisher
"""
import time
import threading
import queue
import traceback
import numpy as np
import cv2
from PyQt6.QtCore import QObject, pyqtSignal
import datetime
import mss
import mss.tools
import psutil

from utils.constants import (
    DEFAULT_THRESHOLD, DEFAULT_DETECTION_COOLDOWN,
    DEFAULT_FISHING_KEY, DEFAULT_CAPTURE_INTERVAL,
    GAME_WINDOW_NAMES
)
from utils.win32_utils import find_window_by_pattern, is_fullscreen_app_active, force_focus_window
from utils.input import send_key_press, send_esc
from core.processing import capture_screen_region, calculate_frame_difference, enhance_visualization
from core.action_sequence import FishingActionSequence

class PixelChangeDetector(QObject):
    """Core detector for pixel changes in the game window with high reliability"""
    
    # Define signals
    detection_signal = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__()
        # Store parent for callbacks
        self.parent = parent
        
        # Initialize logging
        self.log_history = []
        
        # Initialize variables
        self.region = None
        self.reference_frame = None
        self.reference_color_frame = None
        self.previous_frame = None
        self.current_frame = None
        self.color_frame = None
        self.diff_frame = None
        
        # Play Together window handling
        self.play_together_window = None
        
        # Detection parameters
        self.THRESHOLD = DEFAULT_THRESHOLD
        self.detection_cooldown = DEFAULT_DETECTION_COOLDOWN
        self.last_detection_time = 0
        self.change_history = []
        self.fishing_key = DEFAULT_FISHING_KEY
        
        # Options - always enabled for max reliability
        self.high_performance_mode = True
        self.respect_fullscreen = True
        self.direct_control = True
        
        # Thread handling
        self.thread_control = {
            "detection_thread": None,
            "running": False,
            "paused": False,
            "stop_requested": False
        }
        self.running = False
        self.paused = False
        self.capture_interval = DEFAULT_CAPTURE_INTERVAL
        self.detection_thread = None
        
        # Initialize stats
        self.stats = {
            "total_detections": 0,
            "false_positives": 0,
            "session_start_time": time.time(),
            "last_detection_time": 0,
            "avg_detection_interval": 0
        }
        
        # Health check variables
        self.last_successful_capture = 0
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.health_check_interval = 5  # seconds
        self.last_health_check = 0
        
        # Performance metrics
        self.performance = {
            "avg_processing_time": 0.05,
            "processing_samples": 0,
            "fps": 0,
            "cpu_usage": 0
        }
        
        # Create action sequence handler
        self.action_sequence = FishingActionSequence(self)
        
        # Find Play Together window
        self.find_play_together_process()
        
        self.log("PixelChangeDetector initialized")
    
    def log(self, message):
        """Log a message to the parent application or print to console"""
        try:
            # Send to parent's log queue if available
            if self.parent:
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
        """Focus the Play Together window with high reliability"""
        if not self.play_together_window:
            self.find_play_together_process()
            if not self.play_together_window:
                self.log("Cannot focus window: Play Together window not found")
                return False
                
        # Try to focus the window using the enhanced method
        result = force_focus_window(self.play_together_window)
        if result:
            self.log("Successfully focused Play Together window")
        else:
            self.log("Failed to focus Play Together window")
            
        return result
    
    def capture_reference(self):
        """Capture a reference frame for comparison with high reliability"""
        if not self.region:
            self.log("No region selected. Please select a region first.")
            return False
        
        try:
            # Use MSS for better reliability
            with mss.mss() as sct:
                left, top, right, bottom = self.region
                width = right - left
                height = bottom - top
                
                # Convert region format to mss format
                mss_region = {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height
                }
                
                # Capture the region
                screenshot = sct.grab(mss_region)
                frame = np.array(screenshot)
                
                # Validate frame
                if frame.size == 0:
                    self.log("Error: Captured reference frame is empty")
                    self.consecutive_failures += 1
                    return False
                
                # Store color frame for visualization
                if len(frame.shape) >= 3:
                    self.color_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                    self.reference_color_frame = self.color_frame.copy()
                else:
                    self.color_frame = None
                    
                # Store the reference frame
                self.reference_frame = frame
                self.log(f"Reference frame captured: {self.reference_frame.shape}")
                
                # Reset health check variables
                self.last_successful_capture = time.time()
                self.consecutive_failures = 0
                return True
                
        except Exception as e:
            self.log(f"Error capturing reference frame: {e}")
            traceback.print_exc()
            self.consecutive_failures += 1
            return False
    
    def validate_region(self):
        """Validate the selected region with a preview capture"""
        try:
            if not self.region:
                self.log("No region selected")
                return False
                
            # Try to capture a frame from the region
            success = self.capture_reference()
            if success:
                self.log(f"Region validation successful")
                return True
            else:
                self.log("Failed to validate region")
                return False
                
        except Exception as e:
            self.log(f"Error validating region: {e}")
            return False
    
    def perform_health_check(self):
        """Check detector health and attempt recovery if needed"""
        current_time = time.time()
        
        # Only perform health check every health_check_interval seconds
        if current_time - self.last_health_check < self.health_check_interval:
            return True
            
        self.last_health_check = current_time
        
        # Check if we've had too many consecutive failures
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.log("Too many consecutive failures, attempting recovery...")
            # Reset state
            self.current_frame = None
            self.previous_frame = None
            self.diff_frame = None
            self.change_history = []
            self.last_detection_time = 0
            self.consecutive_failures = 0
            
            # Try to recapture reference frame
            self.capture_reference()
            return True
            
        # Check if we haven't had a successful capture in a while
        if current_time - self.last_successful_capture > self.health_check_interval * 2:
            self.log("No successful captures detected, attempting recovery...")
            self.capture_reference()
            return True
            
        return True
    
    def start_detection(self):
        """Start detection thread with robust thread control"""
        if not self.find_play_together_process():
            self.log("Cannot start detection: Play Together window not found")
            return False
            
        if not self.region:
            self.log("No region selected. Please select a region first.")
            return False
            
        # Reset the action sequence execution flag
        if hasattr(self, 'action_sequence'):
            self.action_sequence.is_executing = False
            
        self.running = True
        self.thread_control = {
            "running": True,
            "paused": False,
            "stop_requested": False
        }
        self.change_history = []
        self.stats["session_start_time"] = time.time()
        
        # Capture initial reference frame if none exists
        if self.reference_frame is None:
            self.capture_reference()
            
        self.previous_frame = self.reference_frame
        
        # Start detection thread
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        self.thread_control["detection_thread"] = self.detection_thread
        
        self.log("Detection thread started")
        return True
        
    def stop_detection(self):
        """Stop detection cleanly with proper thread management"""
        if not self.running:
            return
            
        # Check if action sequence is currently running
        if hasattr(self, 'action_sequence') and hasattr(self.action_sequence, 'is_executing') and self.action_sequence.is_executing:
            self.log("Action sequence is currently executing - waiting for completion before stopping")
            # Wait for action sequence to complete (max 10 seconds)
            wait_time = 0
            while self.action_sequence.is_executing and wait_time < 10:
                time.sleep(0.5)
                wait_time += 0.5
        
        # Signal thread to stop
        self.thread_control["stop_requested"] = True
        self.thread_control["running"] = False
        self.running = False
        
        # Wait for thread to finish (with timeout)
        if self.thread_control["detection_thread"] and self.thread_control["detection_thread"].is_alive():
            self.log("Waiting for detection thread to stop...")
            self.thread_control["detection_thread"].join(timeout=2.0)
            
        self.log("Detection stopped")
    
    def toggle_pause(self):
        """Pause or resume detection"""
        if not self.running:
            return
            
        if self.thread_control["paused"]:
            # Resume
            self.thread_control["paused"] = False
            self.paused = False
            self.log("Detection resumed")
        else:
            # Pause
            self.thread_control["paused"] = True
            self.paused = True
            self.log("Detection paused")
    
    def _detection_loop(self):
        """Main detection loop with ultra-fast response time"""
        frame_counter = 0
        fps_counter = 0
        fps_timer = time.time()
        fps = 0
        
        # For faster processing, reduce the interval
        self.capture_interval = 0.03  # ~33 FPS
        
        # Set a much faster adaptive interval
        adaptive_interval = self.capture_interval
        
        # Use a simpler approach for detection intensity
        detection_confidence = 0
        
        # Use MSS for screen capture
        with mss.mss() as sct:
            self.log("Starting ultra-fast detection loop")
            
            while self.thread_control["running"] and not self.thread_control["stop_requested"]:
                loop_start = time.time()
                try:
                    # Skip processing if paused
                    if self.thread_control["paused"]:
                        time.sleep(0.01)
                        continue
                    
                    # Skip processing if action sequence is running
                    if hasattr(self, 'action_sequence') and self.action_sequence.is_executing:
                        time.sleep(0.01)
                        continue
                    
                    # Periodically update FPS counter (less frequently)
                    fps_counter += 1
                    if time.time() - fps_timer >= 2.0:  # Update less frequently
                        fps = fps_counter / 2.0
                        fps_counter = 0
                        fps_timer = time.time()
                        self.performance["fps"] = fps
                        self.log(f"Detection running at {fps:.1f} FPS")
                    
                    # Ultra-fast screen capture using mss
                    if not self.region:
                        time.sleep(0.01)
                        continue
                        
                    left, top, right, bottom = self.region
                    width = right - left
                    height = bottom - top
                    
                    # Convert region format to mss format
                    mss_region = {
                        "left": left,
                        "top": top,
                        "width": width,
                        "height": height
                    }
                    
                    # Capture directly without any processing
                    screenshot = sct.grab(mss_region)
                    self.current_frame = np.array(screenshot)
                    
                    # Quick validation
                    if self.current_frame.size == 0:
                        continue
                        
                    # Store color frame only periodically (for UI)
                    if frame_counter % 5 == 0 and len(self.current_frame.shape) >= 3:
                        self.color_frame = cv2.cvtColor(self.current_frame, cv2.COLOR_BGRA2RGB)
                    
                    # Use reference frame for comparison
                    if self.reference_frame is None:
                        self.capture_reference()
                        continue
                    
                    # Calculate difference with ultra-fast algorithm
                    _, change_percent = self.calculate_frame_difference(self.current_frame, self.reference_frame)
                    
                    # Store in history less frequently
                    if frame_counter % 3 == 0:
                        self.change_history.append(change_percent)
                        if len(self.change_history) > 200:  # Keep a smaller history
                            self.change_history = self.change_history[-200:]
                    
                    # Time-based cooldown check
                    current_time = time.time()
                    cooldown_passed = (current_time - self.last_detection_time) > self.detection_cooldown
                    
                    # Fast detection logic
                    if change_percent > self.THRESHOLD and cooldown_passed:
                        # Immediate detection with high confidence
                        change_percent_display = round(change_percent * 100, 2)
                        self.log(f"Major pixel change detected! Change: {change_percent_display}%")
                        self.last_detection_time = current_time
                        
                        # Update stats
                        self.stats["total_detections"] += 1
                        if self.stats["last_detection_time"] > 0:
                            interval = current_time - self.stats["last_detection_time"]
                            self.stats["avg_detection_interval"] = interval if self.stats["avg_detection_interval"] == 0 else (
                                0.7 * self.stats["avg_detection_interval"] + 0.3 * interval
                            )
                        self.stats["last_detection_time"] = current_time
                        
                        # Emit detection signal for UI
                        self.detection_signal.emit()
                        
                        # Execute action sequence immediately
                        if self.action_sequence:
                            self.action_sequence.execute()
                    
                    # Update performance metrics
                    frame_counter += 1
                    loop_time = time.time() - loop_start
                    
                    # Ultra-minimal sleep interval
                    sleep_time = max(0.005, adaptive_interval - loop_time)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    
                except Exception as e:
                    self.log(f"Error in detection loop: {e}")
                    time.sleep(0.05)
            
            # Thread is exiting
            self.log("Detection thread exiting")
            self.running = False
    
    def capture_screen(self):
        """
        Capture the screen region for UI preview
        
        Returns:
            numpy.ndarray: The captured image in RGB format for display
        """
        try:
            if not self.region:
                self.log("No region selected. Please select a region first.")
                return None
                
            # Validate region size
            left, top, right, bottom = self.region
            width = right - left
            height = bottom - top
            
            if width < 10 or height < 10:
                self.log("Invalid region size detected. Please select a new region.")
                return None
                
            # Use MSS for better performance and multi-monitor support
            with mss.mss() as sct:
                # Convert region format to mss format
                mss_region = {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height
                }
                
                # Capture the region
                screenshot = sct.grab(mss_region)
                
                # Convert to numpy array (BGR)
                frame = np.array(screenshot)
                
                # Validate frame
                if frame.size == 0:
                    self.log("Error: Captured frame is empty")
                    return None
                
                # Store color frame for visualization (convert BGRA to RGB)
                if len(frame.shape) >= 3:
                    self.color_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                    return self.color_frame  # Return RGB for display
                else:
                    # For grayscale frames
                    return frame
                
        except Exception as e:
            self.log(f"Error capturing screen: {e}")
            traceback.print_exc()
            return None
    
    def calculate_frame_difference(self, frame1, frame2):
        """
        Calculate the difference between two frames with ultra-fast algorithm
        
        Args:
            frame1: Current frame
            frame2: Reference frame
            
        Returns:
            tuple: (diff_frame, change_percent)
        """
        if frame1 is None or frame2 is None:
            return None, 0
            
        try:
            # Ensure frames have same dimensions
            if frame1.shape != frame2.shape:
                # Resize to match - this should be rare
                frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
            
            # Fast approach:
            # 1. Downscale frames for faster processing
            small_frame1 = cv2.resize(frame1, (0, 0), fx=0.5, fy=0.5)
            small_frame2 = cv2.resize(frame2, (0, 0), fx=0.5, fy=0.5)
            
            # 2. Convert to grayscale if needed - faster than color processing
            if len(small_frame1.shape) == 3:
                gray1 = cv2.cvtColor(small_frame1, cv2.COLOR_BGR2GRAY)
                gray2 = cv2.cvtColor(small_frame2, cv2.COLOR_BGR2GRAY)
            else:
                gray1 = small_frame1
                gray2 = small_frame2
            
            # 3. Simple absolute difference - fastest approach
            diff_frame = cv2.absdiff(gray1, gray2)
            
            # 4. Calculate percentage of pixels that changed significantly
            # Using simplified thresholding with a fixed value
            threshold = 30  # Higher threshold value for clearer changes
            changed_pixels = np.sum(diff_frame > threshold)
            total_pixels = diff_frame.size
            change_percent = changed_pixels / total_pixels
            
            # 5. Store a visualization diff but don't waste time enhancing it
            if len(frame1.shape) == 3:
                # Get full resolution diff for visualization (but only if needed)
                self.diff_frame = cv2.absdiff(
                    cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY),
                    cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
                )
            else:
                self.diff_frame = cv2.absdiff(frame1, frame2)
            
            return diff_frame, change_percent
            
        except Exception as e:
            self.log(f"Error calculating frame difference: {e}")
            return None, 0 