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
    
    def execute(self):
        """
        Execute the full fishing action sequence
        
        Returns:
            bool: True if successful, False if error occurred
        """
        try:
            # STEP 1: Press fishing key to catch fish
            self.detector.log("STEP 1: Catching fish...")
            if not self._catch_fish():
                self.detector.log("Failed to catch fish - continuing sequence")
            
            # STEP 2: Wait for cooldown period
            cooldown = self.detector.detection_cooldown
            self.detector.log(f"STEP 2: Pausing for {cooldown:.1f} seconds...")
            self._wait_cooldown(cooldown)
            
            # STEP 3: Exit fishing menu with ESC key
            if self.detector.running and not self.detector.thread_control.get("stop_requested", False):
                self.detector.log("STEP 3: Exiting fishing menu...")
                if not self._exit_menu():
                    self.detector.log("Failed to exit menu - continuing sequence")
            
                # STEP 4: Wait briefly for menu to close
                self.detector.log("STEP 4: Waiting for menu to close...")
                self._wait_for_menu_close()
                
                # STEP 5: Cast fishing line again
                if self.detector.running and not self.detector.thread_control.get("stop_requested", False):
                    self.detector.log("STEP 5: Casting fishing line again...")
                    if not self._cast_fishing_line():
                        self.detector.log("Failed to cast fishing line")
                    
                    # STEP 6: Update reference frame
                    self.detector.log("STEP 6: Updating reference frame...")
                    self._update_reference()
            
            # STEP 7: Stabilization pause
            self.detector.log("STEP 7: Short stabilization pause...")
            self._stabilize()
            
            self.detector.log("Action sequence completed successfully")
            return True
            
        except Exception as e:
            self.detector.log(f"Error during action sequence: {e}")
            traceback.print_exc()
            self._attempt_recovery()
            return False
    
    def _catch_fish(self):
        """Press fishing key to catch fish"""
        success = False
        
        # Try up to 3 times to press fishing key
        for attempt in range(3):
            if self.detector.focus_play_together_window():
                self.detector.log(f"Pressing {self.detector.fishing_key.upper()} key to catch fish (attempt {attempt+1})")
                if send_key_press(self.detector.fishing_key, self.detector.play_together_window):
                    success = True
                    break
                time.sleep(0.2)
            else:
                self.detector.log(f"Failed to focus window, retrying ({attempt+1}/3)")
                time.sleep(0.1)
        
        return success
    
    def _wait_cooldown(self, cooldown):
        """Wait for the cooldown period"""
        pause_start = time.time()
        pause_end = pause_start + cooldown
        
        while (time.time() < pause_end and 
               self.detector.running and 
               not self.detector.thread_control.get("stop_requested", False)):
            time.sleep(0.1)
    
    def _exit_menu(self):
        """Exit fishing menu using ESC key"""
        success = False
        
        # Try up to 3 times to press ESC key
        for attempt in range(3):
            if self.detector.focus_play_together_window():
                self.detector.log(f"Pressing ESC key (attempt {attempt+1})")
                if send_esc(self.detector.play_together_window):
                    success = True
                    break
                time.sleep(0.2)
            else:
                self.detector.log(f"Failed to focus window for ESC key, retrying ({attempt+1}/3)")
                time.sleep(0.1)
        
        return success
    
    def _wait_for_menu_close(self):
        """Wait briefly for menu to close"""
        menu_close_time = 2.0  # Wait 2 seconds for menu to close
        menu_close_end = time.time() + menu_close_time
        
        while (time.time() < menu_close_end and 
               self.detector.running and 
               not self.detector.thread_control.get("stop_requested", False)):
            time.sleep(0.1)
    
    def _cast_fishing_line(self):
        """Cast fishing line again"""
        success = False
        
        # Try up to 3 times to cast fishing line
        for attempt in range(3):
            if self.detector.focus_play_together_window():
                self.detector.log(f"Casting fishing line with {self.detector.fishing_key.upper()} key (attempt {attempt+1})")
                if send_key_press(self.detector.fishing_key, self.detector.play_together_window):
                    success = True
                    break
                time.sleep(0.2)
            else:
                self.detector.log(f"Failed to focus window for casting, retrying ({attempt+1}/3)")
                time.sleep(0.1)
        
        # Wait for screen to update after casting
        if success:
            self.detector.log("Waiting for screen to update after casting...")
            time.sleep(2)
        
        return success
    
    def _update_reference(self):
        """Capture new reference frame"""
        try:
            self.detector.capture_reference()
            self.detector.log("New reference frame captured after casting")
            return True
        except Exception as e:
            self.detector.log(f"Error capturing reference frame: {e}")
            return False
    
    def _stabilize(self):
        """Pause to let the game stabilize"""
        stabilize_time = min(1.5, self.detector.detection_cooldown * 0.15)
        time.sleep(stabilize_time)
    
    def _attempt_recovery(self):
        """Try to recover after an error"""
        if self.detector.running and not self.detector.thread_control.get("stop_requested", False):
            # Try to capture new reference frame to recover
            try:
                self.detector.capture_reference()
                self.detector.log("Captured recovery reference frame")
            except Exception as e:
                self.detector.log(f"Failed to recover after error: {e}")
                pass 