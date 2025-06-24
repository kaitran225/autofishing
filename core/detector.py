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
import win32gui
import copy
from typing import Dict, List, Tuple, Optional
import imutils

from utils.constants import (
    DEFAULT_THRESHOLD, DEFAULT_DETECTION_COOLDOWN,
    DEFAULT_FISHING_KEY, DEFAULT_CAPTURE_INTERVAL,
    GAME_WINDOW_NAMES, DEFAULT_DETECTION_ZONES,
    ERROR_HANDLING_CONFIG, PERFORMANCE_CONFIG, UI_CONFIG
)
from utils.win32_utils import find_window_by_pattern, is_fullscreen_app_active, force_focus_window, focus_window_tiered, find_window_by_title_substring
from utils.input import send_key_press, send_esc
from core.processing import capture_screen_region, calculate_frame_difference, enhance_visualization
from core.action_sequence import FishingActionSequence

class DetectionZone:
    """Represents a single detection zone with its own configuration and state"""
    
    def __init__(self, zone_id: str, config: dict, region: Optional[Tuple[int, int, int, int]] = None):
        self.zone_id = zone_id
        self.name = config.get("name", zone_id)
        self.description = config.get("description", "")
        self.enabled = config.get("enabled", True)
        self.sensitivity = config.get("sensitivity", 1.0)
        self.threshold = config.get("threshold", 0.045)
        self.cooldown = config.get("cooldown", 5.0)
        self.priority = config.get("priority", 1)
        
        # Zone state
        self.region = region  # (left, top, right, bottom)
        self.reference_frame = None
        self.current_frame = None
        self.last_detection_time = 0
        self.detection_count = 0
        self.false_positive_count = 0
        
        # Performance tracking
        self.avg_processing_time = 0.05
        self.processing_samples = 0
        
        # Error tracking
        self.consecutive_failures = 0
        self.last_successful_capture = 0
        
    def update_config(self, config: dict):
        """Update zone configuration"""
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)
                
    def is_ready_for_detection(self, current_time: float) -> bool:
        """Check if zone is ready for detection (cooldown passed)"""
        return current_time - self.last_detection_time >= self.cooldown
        
    def record_detection(self, current_time: float, was_false_positive: bool = False):
        """Record a detection event"""
        self.last_detection_time = current_time
        self.detection_count += 1
        if was_false_positive:
            self.false_positive_count += 1
            
    def get_accuracy(self) -> float:
        """Calculate detection accuracy"""
        if self.detection_count == 0:
            return 0.0
        return (self.detection_count - self.false_positive_count) / self.detection_count
        
    def reset_stats(self):
        """Reset zone statistics"""
        self.detection_count = 0
        self.false_positive_count = 0
        self.consecutive_failures = 0

class MultiZoneDetector(QObject):
    """Enhanced detector with multi-zone detection, error handling, and performance optimizations"""
    
    # Define signals
    detection_signal = pyqtSignal(str)  # Emits zone_id
    zone_status_signal = pyqtSignal(str, str)  # Emits zone_id, status
    performance_signal = pyqtSignal(dict)  # Emits performance metrics
    error_signal = pyqtSignal(str, str)  # Emits error_type, error_message
    
    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        
        # Initialize logging
        self.log_history = []
        
        # Multi-zone detection
        self.zones: Dict[str, DetectionZone] = {}
        self.initialize_zones()
        
        # Play Together window handling
        self.play_together_window = None
        
        # Error handling and recovery
        self.error_config = ERROR_HANDLING_CONFIG
        self.retry_count = 0
        self.last_error_time = 0
        self.auto_recovery_enabled = self.error_config["auto_recovery_enabled"]
        
        # Performance optimization
        self.performance_config = PERFORMANCE_CONFIG
        self.adaptive_interval = DEFAULT_CAPTURE_INTERVAL
        self.frame_history = []
        self.last_memory_cleanup = time.time()
        
        # Thread handling
        self.thread_control = {
            "detection_thread": None,
            "running": False,
            "paused": False,
            "stop_requested": False
        }
        self.running = False
        self.paused = False
        
        # Create action sequence handler
        self.action_sequence = FishingActionSequence(self)
        
        # Find Play Together window
        self.find_play_together_process()
        
        self.log("MultiZoneDetector initialized with enhanced features")
        
    def initialize_zones(self):
        """Initialize all detection zones with default configurations"""
        for zone_id, config in DEFAULT_DETECTION_ZONES.items():
            self.zones[zone_id] = DetectionZone(zone_id, config)
        self.log(f"Initialized {len(self.zones)} detection zones")
        
    def set_zone_region(self, zone_id: str, region: Tuple[int, int, int, int]):
        """Set the region for a specific detection zone"""
        if zone_id in self.zones:
            self.zones[zone_id].region = region
            self.log(f"Set region for {zone_id}: {region}")
        else:
            self.log(f"Warning: Zone {zone_id} not found")
            
    def enable_zone(self, zone_id: str, enabled: bool = True):
        """Enable or disable a detection zone"""
        if zone_id in self.zones:
            self.zones[zone_id].enabled = enabled
            status = "enabled" if enabled else "disabled"
            self.log(f"Zone {zone_id} {status}")
            self.zone_status_signal.emit(zone_id, status)
        else:
            self.log(f"Warning: Zone {zone_id} not found")
            
    def update_zone_config(self, zone_id: str, config: dict):
        """Update configuration for a specific zone"""
        if zone_id in self.zones:
            self.zones[zone_id].update_config(config)
            self.log(f"Updated config for zone {zone_id}")
        else:
            self.log(f"Warning: Zone {zone_id} not found")
            
    def get_zone_stats(self) -> Dict[str, dict]:
        """Get statistics for all zones"""
        stats = {}
        for zone_id, zone in self.zones.items():
            stats[zone_id] = {
                "name": zone.name,
                "enabled": zone.enabled,
                "detection_count": zone.detection_count,
                "false_positive_count": zone.false_positive_count,
                "accuracy": zone.get_accuracy(),
                "avg_processing_time": zone.avg_processing_time,
                "consecutive_failures": zone.consecutive_failures
            }
        return stats
        
    def reset_all_zone_stats(self):
        """Reset statistics for all zones"""
        for zone in self.zones.values():
            zone.reset_stats()
        self.log("Reset statistics for all zones")
        
    def log(self, message):
        """Enhanced logging with error handling"""
        try:
            # Send to parent's log queue if available
            if self.parent:
                self.parent.log(message)
            else:
                # Otherwise print to console
                print(f"[MultiZoneDetector] {message}")
                
            # Add to local log history
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.log_history.append(f"[{timestamp}] {message}")
            while len(self.log_history) > 100:  # Limit history size
                self.log_history.pop(0)
        except Exception as e:
            # Emergency fallback
            print(f"[ERROR] Failed to log message: {e}")
            print(f"[DEBUG] Original message: {message}")
            
    def handle_error(self, error_type: str, error_message: str, zone_id: str = None):
        """Enhanced error handling with recovery mechanisms"""
        current_time = time.time()
        
        # Log the error
        self.log(f"Error ({error_type}): {error_message}")
        if zone_id:
            self.log(f"Zone affected: {zone_id}")
            
        # Emit error signal
        self.error_signal.emit(error_type, error_message)
        
        # Update error tracking
        self.last_error_time = current_time
        self.retry_count += 1
        
        # Zone-specific error handling
        if zone_id and zone_id in self.zones:
            zone = self.zones[zone_id]
            zone.consecutive_failures += 1
            
            # Disable zone if too many consecutive failures
            if zone.consecutive_failures >= self.error_config["max_consecutive_failures"]:
                self.log(f"Disabling zone {zone_id} due to consecutive failures")
                zone.enabled = False
                self.zone_status_signal.emit(zone_id, "disabled")
                
        # Auto-recovery logic
        if self.auto_recovery_enabled and self.retry_count <= self.error_config["max_retries"]:
            self.log(f"Attempting auto-recovery (attempt {self.retry_count})")
            time.sleep(self.error_config["retry_delay"])
        else:
            self.log("Max retries reached, stopping detection")
            self.stop_detection()
            
    def find_play_together_process(self):
        """Find the Play Together window handle by robust title search"""
        try:
            hwnd = find_window_by_title_substring(GAME_WINDOW_NAMES)
            if hwnd:
                self.play_together_window = hwnd
                self.log(f"Found Play Together window: Handle {hwnd}")
            else:
                self.play_together_window = None
                self.log("Play Together window not found")
        except Exception as e:
            self.log(f"Error finding Play Together window: {e}")
            
    def get_game_window_handle(self):
        """Get the Play Together window handle for overlay positioning"""
        try:
            import win32gui
            
            # If we already have a handle, validate it first
            if self.play_together_window:
                if win32gui.IsWindow(self.play_together_window):
                    return self.play_together_window
                else:
                    # Handle is no longer valid
                    self.play_together_window = None
            
            # Try to find it again
            self.find_play_together_process()
            
            # Validate the found handle
            if self.play_together_window and win32gui.IsWindow(self.play_together_window):
                return self.play_together_window
            else:
                return None
                
        except Exception as e:
            self.log(f"Error getting game window handle: {e}")
            return None
            
    def focus_play_together_window(self):
        """Focus the Play Together window using tiered approach with error handling"""
        if not self.play_together_window and not self.find_play_together_process():
            return False
                
        try:
            if not win32gui.IsWindow(self.play_together_window):
                if not self.find_play_together_process():
                    return False
                
            # Use tiered focus approach
            result = focus_window_tiered(self.play_together_window)
            
            if result:
                self.log("Successfully focused Play Together window")
            else:
                self.log("Failed to focus Play Together window")
                
            return result
            
        except Exception as e:
            self.handle_error("window_focus", f"Error focusing window: {e}")
            return False
    
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
        """Start multi-zone detection with enhanced error handling"""
        if self.running:
            self.log("Detection already running")
            return
            
        if not self.play_together_window:
            self.find_play_together_process()
            if not self.play_together_window:
                self.log("Cannot start detection: Play Together window not found")
                return
                
        # Check if any zones are configured
        enabled_zones = [z for z in self.zones.values() if z.enabled and z.region]
        if not enabled_zones:
            self.log("Cannot start detection: No enabled zones with regions configured")
            return
            
        self.log(f"Starting detection with {len(enabled_zones)} enabled zones")
        
        # Reset error tracking
        self.retry_count = 0
        self.last_error_time = 0
        
        # Start detection thread
        self.thread_control["running"] = True
        self.thread_control["stop_requested"] = False
        self.running = True
        
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        
        self.log("Detection started successfully")
        
    def stop_detection(self):
        """Stop detection with proper cleanup"""
        self.log("Stopping detection...")
        
        self.thread_control["stop_requested"] = True
        self.thread_control["running"] = False
        self.running = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2.0)
            
        # Cleanup resources
        self._cleanup_resources()
        
        self.log("Detection stopped")
        
    def toggle_pause(self):
        """Pause or resume detection"""
        if not self.running:
            return
            
        self.thread_control["paused"] = not self.thread_control["paused"]
        self.paused = self.thread_control["paused"]
        
        status = "paused" if self.paused else "resumed"
        self.log(f"Detection {status}")
        
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

    def capture_zone_frame(self, zone_id: str) -> Optional[np.ndarray]:
        """Capture frame for a specific detection zone with error handling"""
        if zone_id not in self.zones:
            return None
            
        zone = self.zones[zone_id]
        if not zone.region:
            return None
            
        try:
            left, top, right, bottom = zone.region
            width = right - left
            height = bottom - top
            
            if width < 10 or height < 10:
                self.handle_error("invalid_region", f"Zone {zone_id} has invalid region size", zone_id)
                return None
                
            # Use MSS for better performance
            with mss.mss() as sct:
                mss_region = {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height
                }
                
                screenshot = sct.grab(mss_region)
                frame = np.array(screenshot)
                
                if frame.size == 0:
                    self.handle_error("empty_frame", f"Zone {zone_id} captured empty frame", zone_id)
                    return None
                    
                # Convert BGRA to BGR for OpenCV
                if len(frame.shape) >= 3:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    
                zone.last_successful_capture = time.time()
                zone.consecutive_failures = 0
                return frame
                
        except Exception as e:
            self.handle_error("capture_error", f"Failed to capture zone {zone_id}: {e}", zone_id)
            return None
            
    def detect_shadow_movement(self, frame1: np.ndarray, frame2: np.ndarray) -> Tuple[float, int]:
        """
        Detect fish shadow movement using techniques from the prototype
        Returns: (change_percent, shadow_size)
        """
        try:
            if frame1 is None or frame2 is None:
                return 0.0, 0
                
            # Ensure frames have same dimensions
            if frame1.shape != frame2.shape:
                frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
                
            # Convert to grayscale for shadow detection
            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            
            # Calculate average brightness to determine threshold (from prototype)
            avg1 = cv2.mean(gray1)[0]
            avg2 = cv2.mean(gray2)[0]
            avg = (avg1 + avg2) / 2
            
            # Adaptive thresholding based on brightness (from prototype)
            if avg > 140 and avg < 155:
                threshold_val = 90
            elif avg >= 155:
                threshold_val = 100
            elif avg > 57 and avg < 90:
                threshold_val = 50
            elif avg > 90 and avg < 140:
                threshold_val = 65
            else:
                threshold_val = 30
                
            # Create binary images
            _, thresh1 = cv2.threshold(gray1, threshold_val, 255, cv2.THRESH_BINARY_INV)
            _, thresh2 = cv2.threshold(gray2, threshold_val, 255, cv2.THRESH_BINARY_INV)
            
            # Edge detection and morphological operations (from prototype)
            edged1 = cv2.Canny(thresh1, 10, 100)
            edged1 = cv2.dilate(edged1, None, iterations=1)
            edged1 = cv2.erode(edged1, None, iterations=1)
            
            edged2 = cv2.Canny(thresh2, 10, 100)
            edged2 = cv2.dilate(edged2, None, iterations=1)
            edged2 = cv2.erode(edged2, None, iterations=1)
            
            # Find contours
            cnts1 = cv2.findContours(edged1.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts1 = imutils.grab_contours(cnts1)
            cnts1 = [x for x in cnts1 if cv2.contourArea(x) > 300]
            
            cnts2 = cv2.findContours(edged2.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts2 = imutils.grab_contours(cnts2)
            cnts2 = [x for x in cnts2 if cv2.contourArea(x) > 300]
            
            # Calculate shadow size and movement
            size1 = self._get_shadow_size(cnts1)
            size2 = self._get_shadow_size(cnts2)
            
            # Calculate change percentage
            diff = cv2.absdiff(edged1, edged2)
            change_percent = np.sum(diff > 0) / diff.size
            
            return change_percent, max(size1, size2)
            
        except Exception as e:
            self.log(f"Error in shadow detection: {e}")
            return 0.0, 0
            
    def _get_shadow_size(self, contours) -> int:
        """Determine shadow size based on contour area (from prototype)"""
        if not contours:
            return 0
            
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 300 < area < 420:
                return 1
            elif 700 < area < 1100:
                return 2
            elif 1300 < area < 2100:
                return 3
            elif area > 2100:
                return 4
        return 0
        
    def detect_text_changes(self, frame1: np.ndarray, frame2: np.ndarray) -> float:
        """Detect text changes for fish name detection zone"""
        try:
            if frame1 is None or frame2 is None:
                return 0.0
                
            # Ensure frames have same dimensions
            if frame1.shape != frame2.shape:
                frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
                
            # Convert to grayscale for text detection
            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            
            # Apply slight blur to reduce noise
            gray1 = cv2.GaussianBlur(gray1, (3, 3), 0)
            gray2 = cv2.GaussianBlur(gray2, (3, 3), 0)
            
            # Calculate difference with higher sensitivity for text
            diff = cv2.absdiff(gray1, gray2)
            
            # Apply threshold to highlight text changes
            _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
            
            # Calculate change percentage
            change_percent = np.sum(thresh > 0) / thresh.size
            
            return change_percent
            
        except Exception as e:
            self.log(f"Error in text detection: {e}")
            return 0.0
            
    def detect_rod_movement(self, frame1: np.ndarray, frame2: np.ndarray) -> float:
        """Detect fishing rod movement/state changes"""
        try:
            if frame1 is None or frame2 is None:
                return 0.0
                
            # Ensure frames have same dimensions
            if frame1.shape != frame2.shape:
                frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
                
            # Convert to HSV for better color-based detection
            hsv1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2HSV)
            hsv2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2HSV)
            
            # Focus on saturation and value channels for rod detection
            s_diff = cv2.absdiff(hsv1[:,:,1], hsv2[:,:,1])
            v_diff = cv2.absdiff(hsv1[:,:,2], hsv2[:,:,2])
            
            # Combine differences with weights
            diff = cv2.addWeighted(s_diff, 0.6, v_diff, 0.4, 0)
            
            # Apply morphological operations to reduce noise
            kernel = np.ones((3, 3), np.uint8)
            diff = cv2.morphologyEx(diff, cv2.MORPH_OPEN, kernel)
            
            # Calculate change percentage
            change_percent = np.sum(diff > 20) / diff.size
            
            return change_percent
            
        except Exception as e:
            self.log(f"Error in rod detection: {e}")
            return 0.0
            
    def process_zone(self, zone_id: str, current_time: float) -> bool:
        """Process a single detection zone and return True if detection occurred"""
        zone = self.zones[zone_id]
        
        if not zone.enabled or not zone.region:
            return False
            
        if not zone.is_ready_for_detection(current_time):
            return False
            
        # Capture current frame
        current_frame = self.capture_zone_frame(zone_id)
        if current_frame is None:
            return False
            
        # Set reference frame if not set
        if zone.reference_frame is None:
            zone.reference_frame = current_frame.copy()
            return False
            
        # Process based on zone type
        start_time = time.time()
        detection_occurred = False
        
        try:
            if zone_id == "bounce_shadow":
                # Shadow detection with size analysis
                change_percent, shadow_size = self.detect_shadow_movement(
                    zone.reference_frame, current_frame
                )
                threshold = zone.threshold * zone.sensitivity
                detection_occurred = change_percent > threshold and shadow_size > 0
                
            elif zone_id == "fish_name":
                # Text change detection
                change_percent = self.detect_text_changes(
                    zone.reference_frame, current_frame
                )
                threshold = zone.threshold * zone.sensitivity
                detection_occurred = change_percent > threshold
                
            elif zone_id == "fishing_rod":
                # Rod movement detection
                change_percent = self.detect_rod_movement(
                    zone.reference_frame, current_frame
                )
                threshold = zone.threshold * zone.sensitivity
                detection_occurred = change_percent > threshold
                
            else:  # main_fishing or default
                # Standard frame difference detection
                diff_frame, change_percent = calculate_frame_difference(
                    zone.reference_frame, current_frame, 
                    fast_mode=self.performance_config["enable_fast_mode"]
                )
                threshold = zone.threshold * zone.sensitivity
                detection_occurred = change_percent > threshold
                
            # Update performance metrics
            processing_time = time.time() - start_time
            zone.avg_processing_time = (
                (zone.avg_processing_time * zone.processing_samples + processing_time) /
                (zone.processing_samples + 1)
            )
            zone.processing_samples += 1
            
            # Record detection
            if detection_occurred:
                zone.record_detection(current_time)
                self.log(f"Detection in {zone_id}: {change_percent:.4f} > {threshold:.4f}")
                
            # Update current frame
            zone.current_frame = current_frame.copy()
            
        except Exception as e:
            self.handle_error("zone_processing", f"Error processing zone {zone_id}: {e}", zone_id)
            return False
            
        return detection_occurred
        
    def _cleanup_resources(self):
        """Clean up resources to prevent memory leaks"""
        try:
            # Clear frame history
            self.frame_history.clear()
            
            # Clear zone frames
            for zone in self.zones.values():
                zone.reference_frame = None
                zone.current_frame = None
                
            # Force garbage collection
            import gc
            gc.collect()
            
        except Exception as e:
            self.log(f"Error during cleanup: {e}")
            
    def _detection_loop(self):
        """Main detection loop with multi-zone processing and error handling"""
        self.log("Detection loop started")
        
        try:
            # Initialize MSS instance
            mss_instance = mss.mss()
            
            # Performance tracking
            frame_counter = 0
            last_performance_update = time.time()
            
            while self.thread_control["running"] and not self.thread_control["stop_requested"]:
                try:
                    loop_start = time.time()
                    current_time = time.time()
                    
                    # Check for fullscreen apps
                    if is_fullscreen_app_active():
                        time.sleep(0.1)
                        continue
                        
                    # Process each enabled zone
                    detections = []
                    for zone_id, zone in self.zones.items():
                        if zone.enabled and zone.region:
                            if self.process_zone(zone_id, current_time):
                                detections.append(zone_id)
                                
                    # Handle detections
                    if detections:
                        # Prioritize detections by zone priority
                        detections.sort(key=lambda z: self.zones[z].priority)
                        primary_detection = detections[0]
                        
                        self.log(f"Detection triggered by {primary_detection}")
                        self.detection_signal.emit(primary_detection)
                        
                        # Execute action sequence
                        if self.action_sequence:
                            self.action_sequence.execute()
                            
                    # Update performance metrics
                    frame_counter += 1
                    if current_time - last_performance_update >= 1.0:
                        fps = frame_counter / (current_time - last_performance_update)
                        self.performance_signal.emit({
                            "fps": fps,
                            "frame_counter": frame_counter,
                            "active_zones": len([z for z in self.zones.values() if z.enabled])
                        })
                        frame_counter = 0
                        last_performance_update = current_time
                        
                    # Adaptive interval adjustment
                    if self.performance_config["adaptive_capture_interval"]:
                        self._adjust_capture_interval()
                        
                    # Memory cleanup
                    if current_time - self.last_memory_cleanup >= self.performance_config["memory_cleanup_interval"]:
                        self._cleanup_resources()
                        self.last_memory_cleanup = current_time
                        
                    # Sleep with adaptive timing
                    loop_time = time.time() - loop_start
                    sleep_time = max(0.001, self.adaptive_interval - loop_time)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        
                except Exception as e:
                    self.handle_error("detection_loop", f"Error in detection loop: {e}")
                    time.sleep(0.1)  # Brief pause before retry
                    
        except Exception as e:
            self.handle_error("critical_error", f"Critical error in detection thread: {e}")
        finally:
            # Cleanup
            try:
                if 'mss_instance' in locals():
                    mss_instance.close()
            except Exception as e:
                self.log(f"Error closing MSS: {e}")
                
            self.running = False
            self.log("Detection loop ended")
            
    def _adjust_capture_interval(self):
        """Adjust capture interval based on system performance"""
        try:
            # Get CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Adjust interval based on CPU usage
            if cpu_percent > 80:
                self.adaptive_interval = min(
                    self.adaptive_interval * 1.1,
                    self.performance_config["max_capture_interval"]
                )
            elif cpu_percent < 50:
                self.adaptive_interval = max(
                    self.adaptive_interval * 0.9,
                    self.performance_config["min_capture_interval"]
                )
                
        except Exception as e:
            self.log(f"Error adjusting capture interval: {e}")
            
    def get_performance_metrics(self) -> dict:
        """Get comprehensive performance metrics"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            zone_stats = self.get_zone_stats()
            total_detections = sum(stats["detection_count"] for stats in zone_stats.values())
            total_accuracy = sum(stats["accuracy"] for stats in zone_stats.values()) / len(zone_stats) if zone_stats else 0
            
            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory.percent,
                "adaptive_interval": self.adaptive_interval,
                "total_detections": total_detections,
                "average_accuracy": total_accuracy,
                "active_zones": len([z for z in self.zones.values() if z.enabled]),
                "zone_stats": zone_stats,
                "error_count": self.retry_count,
                "last_error_time": self.last_error_time
            }
        except Exception as e:
            self.log(f"Error getting performance metrics: {e}")
            return {}

# Keep the original PixelChangeDetector for backward compatibility
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