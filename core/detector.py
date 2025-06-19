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
            
        # Set both instance and thread control flags
        self.running = True
        self.paused = False
        self.thread_control = {
            "running": True,
            "paused": False,
            "stop_requested": False,
            "detection_thread": None,  # Will be set after thread creation
            "warmup_period": True,     # Flag to indicate warmup period
            "needs_reference": True    # Flag to indicate we need a new reference frame after warmup
        }
        self.change_history = []
        self.stats["session_start_time"] = time.time()
        
        # Initial reference frame for starting (will be replaced after warmup)
        self.capture_reference()
        self.previous_frame = self.reference_frame
        
        # Start detection thread
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        self.thread_control["detection_thread"] = self.detection_thread
        
        self.log("Detection thread started")
        self.log("Warming up for 2 seconds...")
        
        # Schedule warmup period reset after 2 seconds
        def reset_warmup():
            time.sleep(2.0)  # 2 second warmup
            if self.running and hasattr(self, 'thread_control'):
                # We'll capture a fresh reference frame before enabling detection
                self.thread_control["warmup_period"] = False
                self.log("Warmup complete - capturing fresh reference frame...")
                
        # Start warmup thread
        warmup_thread = threading.Thread(target=reset_warmup)
        warmup_thread.daemon = True
        warmup_thread.start()
        
        return True
        
    def stop_detection(self):
        """Stop detection with proper resource cleanup"""
        self.log("Stopping detection...")
        
        # Set both instance and thread control flags
        self.running = False
        self.paused = False
        
        # Stop the action sequence if running
        if hasattr(self, 'action_sequence') and self.action_sequence.is_executing:
            self.log("Terminating action sequence...")
            self.action_sequence.terminate()
        
        # Set thread control flags to ensure clean shutdown
        if hasattr(self, 'thread_control'):
            self.thread_control["running"] = False
            self.thread_control["paused"] = False
            self.thread_control["stop_requested"] = True
            self.thread_control["warmup_period"] = False
        
        # Clean up MSS instance if it exists
        if hasattr(self, 'mss_instance') and self.mss_instance:
            try:
                self.mss_instance.close()
            except Exception:
                pass
            self.mss_instance = None
        
        # Wait for detection thread to terminate with a short timeout
        if hasattr(self, 'detection_thread') and self.detection_thread and self.detection_thread.is_alive():
            try:
                # Don't try to join the current thread
                if self.detection_thread != threading.current_thread():
                    self.detection_thread.join(timeout=1.0)
                    if self.detection_thread.is_alive():
                        self.log("Warning: Detection thread didn't terminate within timeout")
            except Exception:
                pass
        
        # Clean up remaining resources
        self.previous_frame = None
        self.current_frame = None
        self.diff_frame = None
        # Keep reference_frame for next start
        
        self.log("Detection stopped")
    
    def toggle_pause(self):
        """Pause or resume detection"""
        if not self.running:
            return
            
        # Toggle the paused state in both instance and thread control
        if self.thread_control["paused"]:
            # Resume detection
            self.thread_control["paused"] = False
            self.paused = False
            self.log("Detection resumed")
        else:
            # Pause detection
            self.thread_control["paused"] = True
            self.paused = True
            self.log("Detection paused")
    
    def _detection_loop(self):
        """Main detection loop with enhanced detection algorithm and safe resource handling"""
        # Initialize counters and variables
        frame_counter = 0
        fps_counter = 0
        fps_timer = time.time()
        fps = 0
        
        # For faster processing, maintain high frame rate
        self.capture_interval = 0.03  # ~33 FPS
        
        # Set adaptive interval
        adaptive_interval = self.capture_interval
        
        # Store mss instance as instance variable for safe cleanup
        self.mss_instance = None
        
        try:
            # Pre-define region parameters
            if not self.region:
                self.log("No region selected for detection")
                return
                
            left, top, right, bottom = self.region
            width = right - left
            height = bottom - top
            
            # Prepare MSS region format once
            mss_region = {
                "left": left,
                "top": top,
                "width": width,
                "height": height
            }
            
            # Create MSS instance with safe handling
            self.mss_instance = mss.mss()
            
            self.log("Starting enhanced detection loop")
            self.log("Using HSV color detection with multi-frame confidence building")
            
            # Main detection loop with proper exception handling
            while self.thread_control["running"] and not self.thread_control["stop_requested"]:
                try:
                    loop_start = time.time()
                    
                    # Check for stop request first thing in each loop
                    if self.thread_control["stop_requested"]:
                        break
                        
                    # Skip processing if paused
                    if self.thread_control["paused"]:
                        time.sleep(0.01)
                        continue
                    
                    # Skip processing if action sequence is running
                    if hasattr(self, 'action_sequence') and self.action_sequence.is_executing:
                        time.sleep(0.01)
                        continue
                    
                    # Periodically update FPS counter
                    fps_counter += 1
                    if time.time() - fps_timer >= 2.0:
                        fps = fps_counter / 2.0
                        fps_counter = 0
                        fps_timer = time.time()
                        self.performance["fps"] = fps
                        self.log(f"Detection running at {fps:.1f} FPS")
                    
                    # Capture directly without any processing
                    screenshot = self.mss_instance.grab(mss_region)
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
                    
                    # Calculate difference with enhanced HSV algorithm
                    # This is the key improvement - uses the original autofisher's color-based detection
                    _, change_percent = self.calculate_frame_difference(self.current_frame, self.reference_frame)
                    
                    # Store in history less frequently
                    if frame_counter % 3 == 0:
                        self.change_history.append(change_percent)
                        if len(self.change_history) > 200:  # Keep a smaller history
                            self.change_history = self.change_history[-200:]
                    
                    # Time-based cooldown check
                    current_time = time.time()
                    cooldown_passed = (current_time - self.last_detection_time) > self.detection_cooldown
                    
                    # Enhanced detection logic from original autofisher.py 
                    # Using detection intensity that builds up over multiple frames
                    if not hasattr(self, 'detection_intensity'):
                        self.detection_intensity = 0
                        
                    # Check if we're in warmup period - skip detection if we are
                    if self.thread_control.get("warmup_period", False):
                        # During warmup, just gather data but don't trigger detections
                        self.detection_intensity = 0  # Reset intensity during warmup
                        continue
                    
                    # Check if we need a fresh reference frame after warmup
                    if self.thread_control.get("needs_reference", False):
                        # Capture a fresh reference frame now that warmup is complete
                        self.reference_frame = self.current_frame.copy()
                        if len(self.current_frame.shape) >= 3:
                            self.reference_color_frame = self.color_frame.copy() if self.color_frame is not None else None
                        self.change_history = []  # Clear history with new reference
                        self.detection_intensity = 0  # Reset intensity
                        self.thread_control["needs_reference"] = False  # Clear flag
                        self.log("Fresh reference frame captured - detection active")
                        continue  # Skip one frame after capturing reference
                        
                    # Implement a confidence system for detections
                    if change_percent > self.THRESHOLD * 1.5:
                        # Strong change - count as 2 points (exactly as in original)
                        self.detection_intensity += 2
                    elif change_percent > self.THRESHOLD:
                        # Regular change - count as 1 point
                        self.detection_intensity += 1
                    else:
                        # No change - decrease intensity
                        self.detection_intensity = max(0, self.detection_intensity - 0.5)
                    
                    # Detect when intensity threshold reached and cooldown passed
                    if self.detection_intensity >= 3 and cooldown_passed:
                        # We have enough confidence in the detection
                        confidence = min(10, int(self.detection_intensity * 10 / 6))  # Scale to 1-10
                        change_percent_display = round(change_percent * 100, 2)
                        self.log(f"Major pixel change detected! Change: {change_percent_display}% (Confidence: {confidence}/10)")
                        self.last_detection_time = current_time
                        self.detection_intensity = 0  # Reset intensity after detection
                        
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
                    # Don't break the loop on error, just slow down
                    time.sleep(0.05)
            
            # Thread is exiting
            self.log("Detection thread exiting")
            self.running = False
            
        except Exception as e:
            self.log(f"Critical error in detection thread: {e}")
        finally:
            # Always clean up resources to prevent crashes
            try:
                if self.mss_instance:
                    self.mss_instance.close()
                    self.mss_instance = None
            except Exception as e:
                self.log(f"Error closing MSS: {e}")
            
            # Make sure we reset state flags
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
        Calculate the difference between two frames with enhanced detection from original autofisher.py
        
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
            
            # For color images - use HSV for better fishing detection (from original)
            if len(frame1.shape) == 3:
                # Apply slight blur to reduce noise sensitivity
                frame1_blurred = cv2.GaussianBlur(frame1, (5, 5), 0)
                frame2_blurred = cv2.GaussianBlur(frame2, (5, 5), 0)
                
                # Convert to HSV for better color sensitivity - especially for pastel colors
                # This was a key improvement in the original autofisher for detecting subtle changes
                frame1_hsv = cv2.cvtColor(frame1_blurred, cv2.COLOR_BGR2HSV)
                frame2_hsv = cv2.cvtColor(frame2_blurred, cv2.COLOR_BGR2HSV)
                
                # Calculate difference in HSV space with channel weighting from original
                h_diff = cv2.absdiff(frame1_hsv[:,:,0], frame2_hsv[:,:,0])
                s_diff = cv2.absdiff(frame1_hsv[:,:,1], frame2_hsv[:,:,1])
                v_diff = cv2.absdiff(frame1_hsv[:,:,2], frame2_hsv[:,:,2])
                
                # Weight hue differences more heavily for pastel colors (from original)
                h_weight = 2.0  # Increased weight for hue differences
                s_weight = 1.0
                v_weight = 1.0
                
                # Combine channels with weights
                diff_frame = cv2.addWeighted(h_diff, h_weight, s_diff, s_weight, 0)
                diff_frame = cv2.addWeighted(diff_frame, 1.0, v_diff, v_weight, 0)
                
                # Apply morphological operations to highlight larger changes
                kernel = np.ones((3, 3), np.uint8)
                dilated_diff = cv2.dilate(diff_frame, kernel, iterations=1)
                
                # Calculate percentage of pixels that changed significantly
                threshold = 20  # Lower threshold for more sensitivity (from original)
                changed_pixels = np.sum(dilated_diff > threshold)
                total_pixels = diff_frame.shape[0] * diff_frame.shape[1]
                change_percent = changed_pixels / total_pixels
                
                # For visualization, enhance the difference frame
                enhanced_diff = cv2.convertScaleAbs(dilated_diff, alpha=1.5)
                self.diff_frame = enhanced_diff
                
                return enhanced_diff, change_percent
                
            else:
                # Fast grayscale approach for non-color frames
                gray1 = cv2.GaussianBlur(frame1, (5, 5), 0)
                gray2 = cv2.GaussianBlur(frame2, (5, 5), 0)
                diff_frame = cv2.absdiff(gray1, gray2)
                
                # Apply morphological operations
                kernel = np.ones((3, 3), np.uint8)
                dilated_diff = cv2.dilate(diff_frame, kernel, iterations=1)
                
                # Calculate percentage of changed pixels
                threshold = 20
                changed_pixels = np.sum(dilated_diff > threshold)
                total_pixels = diff_frame.size
                change_percent = changed_pixels / total_pixels
                
                self.diff_frame = dilated_diff
                return dilated_diff, change_percent
            
        except Exception as e:
            self.log(f"Error calculating frame difference: {e}")
            return None, 0 