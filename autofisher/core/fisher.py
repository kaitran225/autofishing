"""
Core fishing logic for AutoFisher.
"""
import time
from autofisher.core.detector import Detector


class Fisher:
    """Handles the core fishing logic and state machine."""
    
    def __init__(self, key_sender=None):
        # Detection module
        self.detector = Detector()
        
        # Key sender module (OS-specific)
        self.key_sender = key_sender
        
        # State variables
        self.waiting_for_fish = False
        self.in_action_sequence = False
        self.action_sequence_step = 0
        self.detection_count = 0
        
        # Configure fishing action sequence (can be customized)
        self.action_sequence = [
            {"action": "press_f", "delay": 0.0},   # Press F immediately
            {"action": "wait", "delay": 3.0},      # Wait 3 seconds
            {"action": "press_esc", "delay": 1.0}, # Press ESC, wait 1 second
            {"action": "wait", "delay": 1.0},      # Wait 1 more second
            {"action": "press_f", "delay": 1.0}    # Press F again, wait 1 second
        ]
        
        # Callback for status updates
        self.on_status_change = None
    
    def set_key_sender(self, key_sender):
        """Set the key sender module.
        
        Args:
            key_sender: OS-specific key sender module
        """
        self.key_sender = key_sender
    
    def set_status_callback(self, callback):
        """Set callback for status updates.
        
        Args:
            callback: Function to call with status updates
        """
        self.on_status_change = callback
    
    def update_status(self, status):
        """Update status and call the callback if set.
        
        Args:
            status: Status message string
        """
        if self.on_status_change:
            self.on_status_change(status)
    
    def process_frame(self, exclamation_frame, shadow_frame):
        """Process frames and handle fishing logic.
        
        Args:
            exclamation_frame: Frame from exclamation mark region
            shadow_frame: Frame from shadow region
            
        Returns:
            (exclamation_viz, shadow_viz, detection): Tuple of visualization frames and detection result
        """
        # Skip if in action sequence
        if self.in_action_sequence:
            self.process_action_sequence()
            # Return frames as-is during action sequence
            return exclamation_frame, shadow_frame, False
        
        # Detect exclamation mark
        exclamation_detected, exclamation_viz = self.detector.detect_exclamation_mark(exclamation_frame)
        
        # Only check for shadows if not already waiting for a fish
        if not self.waiting_for_fish:
            shadow_detected, shadow_viz, detection_type = self.detector.detect_fish_shadow(shadow_frame)
        else:
            shadow_detected, shadow_viz, detection_type = False, shadow_frame, "none"
        
        # Handle fishing logic
        if exclamation_detected:
            self.detection_count += 1
            self.waiting_for_fish = False
            self.update_status(f"Exclamation detected! (#{self.detection_count})")
            
            # Start action sequence
            self.in_action_sequence = True
            self.action_sequence_step = 0
            self.process_action_sequence()
            
            return exclamation_viz, shadow_viz, True
            
        elif shadow_detected and not self.waiting_for_fish:
            if detection_type == "shadow":
                self.waiting_for_fish = True
                self.update_status("Fish shadow detected! Waiting for bite...")
            
            return exclamation_viz, shadow_viz, False
        
        # No detection
        return exclamation_viz, shadow_viz, False
    
    def process_action_sequence(self):
        """Process the current step in the action sequence."""
        if not self.in_action_sequence or self.action_sequence_step >= len(self.action_sequence):
            self.in_action_sequence = False
            self.action_sequence_step = 0
            self.update_status("Watching for fish...")
            return
        
        # Get the current action
        action = self.action_sequence[self.action_sequence_step]
        
        # Execute the action based on type
        action_type = action["action"]
        
        if action_type == "press_f" and self.key_sender:
            self.key_sender.send_key('f')
            self.update_status("Pressing F")
        elif action_type == "press_esc" and self.key_sender:
            self.key_sender.send_key('esc')
            self.update_status("Pressing ESC")
        elif action_type == "wait":
            # Update status to show we're waiting
            self.update_status(f"Waiting {action['delay']}s")
        
        # Wait for the specified delay
        time.sleep(action["delay"])
        
        # Move to next step
        self.action_sequence_step += 1
        
        # If we've reached the end, exit the sequence
        if self.action_sequence_step >= len(self.action_sequence):
            self.in_action_sequence = False
            self.update_status("Fishing sequence complete. Watching for fish...")
    
    def reset(self):
        """Reset the fishing state."""
        self.waiting_for_fish = False
        self.in_action_sequence = False
        self.action_sequence_step = 0 