"""
Action sequence handling for automatic fishing
"""
import time
import traceback
from utils.input import send_key_press, send_esc

class FishingActionSequence:
    """Manages the sequence of actions for fishing automation"""
    
    def __init__(self, detector):
        """
        Initialize with a reference to the detector
        
        Args:
            detector: PixelChangeDetector instance
        """
        self.detector = detector
        self.is_executing = False
    
    def execute(self):
        """
        Execute the fishing action sequence using the original timing from autofisher.py
        
        Returns:
            bool: True if successful, False if error occurred
        """
        try:
            # Set executing flag to prevent interruption
            self.is_executing = True
            
            # STEP 1: Press fishing key to catch fish (immediately)
            self._catch_fish_instant()
            self.detector.log(f"Pressing {self.detector.fishing_key.upper()} key to catch fish...")
            time.sleep(0.2)  # Same as original
            
            # STEP 2: Pause detection based on configured cooldown
            cooldown = self.detector.detection_cooldown
            self.detector.log(f"Pausing detection for {cooldown:.1f} seconds...")
            
            # Initial delay - same as original
            time.sleep(min(2.0, cooldown / 2))
            
            # Wait additional time, checking for stop requests
            pause_start = time.time()
            pause_end = pause_start + cooldown
            while (time.time() < pause_end and 
                   self.detector.running and 
                   not self.detector.thread_control.get("stop_requested", False)):
                time.sleep(0.1)  # Same as original
            
            # STEP 3: Press ESC to exit fishing menu
            self.detector.log("Pressing ESC key to exit fishing menu...")
            self._exit_menu_fast()
            
            # STEP 4: Wait before casting again - same as original
            esc_end = time.time() + 2
            while (time.time() < esc_end and 
                   self.detector.running and 
                   not self.detector.thread_control.get("stop_requested", False)):
                time.sleep(0.1)
            
            # STEP 5: Cast fishing line again
            self.detector.log(f"Pressing {self.detector.fishing_key.upper()} key to cast fishing line...")
            self._cast_fishing_line_fast()
            time.sleep(2)  # Wait for screen to update - same as original
            
            # STEP 6: Get new reference frame
            self.detector.log("New reference frame captured after casting")
            self._update_reference()
            
            # STEP 7: Stabilize before continuing detection
            stabilize_time = min(2.0, self.detector.detection_cooldown * 0.2)
            time.sleep(stabilize_time)
            
            self.is_executing = False
            return True
            
        except Exception as e:
            self.detector.log(f"Error during action sequence: {e}")
            traceback.print_exc()
            self._attempt_recovery()
            self.is_executing = False
            return False
    
    def _catch_fish_instant(self):
        """Press fishing key to catch fish - matching original method"""
        if self.detector.focus_play_together_window():
            send_key_press(self.detector.fishing_key, self.detector.play_together_window)
            return True
        else:
            self.detector.log("Failed to focus window, skipping key press")
            return False
    
    def _exit_menu_fast(self):
        """Exit fishing menu using ESC key - matching original but keeping speed"""
        if self.detector.focus_play_together_window():
            send_esc(self.detector.play_together_window)
        else:
            self.detector.log("Failed to focus window, skipping ESC key press")
    
    def _cast_fishing_line_fast(self):
        """Cast fishing line again - matching original method"""
        if self.detector.focus_play_together_window():
            send_key_press(self.detector.fishing_key, self.detector.play_together_window)
            return True
        else:
            self.detector.log("Failed to focus window, skipping fishing cast")
            return False
    
    def _wait_brief(self, duration):
        """Ultra-short wait that respects stop signals"""
        if duration <= 0.05:
            # For very short delays, just sleep directly
            time.sleep(duration)
            return
            
        # For longer delays, check interrupt flags
        end_time = time.time() + duration
        while (time.time() < end_time and 
               self.detector.running and 
               not self.detector.thread_control.get("stop_requested", False)):
            time.sleep(0.01)  # Much shorter sleep interval
    
    def _update_reference(self):
        """Capture new reference frame - critical step for detection"""
        try:
            # Explicitly force a new reference frame capture
            success = self.detector.capture_reference()
            if success:
                self.detector.log("New reference frame captured after casting")
                # Update detector's previous frame for consistency
                self.detector.previous_frame = self.detector.reference_frame
                return True
            else:
                self.detector.log("Failed to capture reference frame")
                return False
        except Exception as e:
            self.detector.log(f"Error capturing reference frame: {e}")
            return False
    
    def _attempt_recovery(self):
        """Try to recover after an error"""
        if self.detector.running and not self.detector.thread_control.get("stop_requested", False):
            # Try to capture new reference frame to recover
            try:
                self.detector.log("Attempting recovery by capturing new reference frame")
                self.detector.capture_reference()
                self.detector.log("Captured recovery reference frame")
                # Update detector's previous frame for consistency
                self.detector.previous_frame = self.detector.reference_frame
            except Exception as e:
                self.detector.log(f"Failed to recover after error: {e}") 