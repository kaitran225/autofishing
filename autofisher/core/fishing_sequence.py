"""
Fishing sequence management for AutoFisher
"""
import time
import threading
from typing import Dict, List, Callable, Optional, Any


class FishingSequenceManager:
    """
    Manages the automated fishing sequence with customizable steps.
    
    This class handles the execution of the fishing action sequence,
    providing callbacks for UI updates and managing the state of the
    fishing process.
    """
    
    def __init__(self, key_sender=None):
        # Key sender module (from OS adapters)
        self.key_sender = key_sender
        
        # State variables
        self.is_running = False
        self.is_paused = False
        self.current_step = 0
        self.detection_count = 0
        self.sequence_thread = None
        
        # Action sequence configuration (customizable)
        self.action_sequence = [
            {"action": "press", "key": "f", "delay": 0.0},   # Cast fishing rod
            {"action": "wait", "delay": 3.0},                # Wait for fish
            {"action": "watch", "delay": 30.0},              # Watch for fish bite (max time)
            {"action": "press", "key": "f", "delay": 0.5},   # Hook the fish
            {"action": "wait", "delay": 3.0},                # Wait for fish catching
            {"action": "press", "key": "esc", "delay": 0.5}, # Close dialog
            {"action": "wait", "delay": 2.0},                # Wait to stabilize
        ]
        
        # Callbacks
        self.on_status_update = None
        self.on_sequence_complete = None
        self.on_step_complete = None
        
    def set_key_sender(self, key_sender):
        """Set the key sender module for the current platform"""
        self.key_sender = key_sender
        
    def set_status_callback(self, callback: Callable[[str], None]):
        """Set callback for status updates"""
        self.on_status_update = callback
        
    def set_sequence_complete_callback(self, callback: Callable[[], None]):
        """Set callback for when fishing sequence completes"""
        self.on_sequence_complete = callback
        
    def set_step_complete_callback(self, callback: Callable[[int], None]):
        """Set callback for when each step completes"""
        self.on_step_complete = callback
        
    def update_status(self, status: str):
        """Update status and call the callback if set"""
        if self.on_status_update:
            self.on_status_update(status)
            
    def update_action_sequence(self, sequence: List[Dict[str, Any]]):
        """Update the fishing action sequence"""
        if sequence:
            self.action_sequence = sequence
            
    def start_sequence(self, detected_type: str = "exclamation"):
        """
        Start the fishing sequence after detection
        
        Args:
            detected_type: Type of detection that triggered the sequence
                           ("exclamation" or "shadow")
        """
        if self.is_running:
            return
            
        self.is_running = True
        self.is_paused = False
        self.current_step = 0
        self.detection_count += 1
        
        self.update_status(f"Detection #{self.detection_count}: Starting fishing sequence")
        
        # Run the sequence in a separate thread
        self.sequence_thread = threading.Thread(target=self._sequence_loop)
        self.sequence_thread.daemon = True
        self.sequence_thread.start()
        
    def pause_sequence(self):
        """Pause the current fishing sequence"""
        self.is_paused = True
        self.update_status("Fishing sequence paused")
        
    def resume_sequence(self):
        """Resume the paused fishing sequence"""
        self.is_paused = False
        self.update_status("Fishing sequence resumed")
        
    def stop_sequence(self):
        """Stop the current fishing sequence"""
        self.is_running = False
        self.is_paused = False
        self.current_step = 0
        self.update_status("Fishing sequence stopped")
        
    def _sequence_loop(self):
        """Main loop for processing the fishing sequence"""
        while self.is_running and self.current_step < len(self.action_sequence):
            # Check for pause state
            if self.is_paused:
                time.sleep(0.1)
                continue
                
            # Get current action
            action = self.action_sequence[self.current_step]
            action_type = action["action"]
            
            # Process action based on type
            if action_type == "press" and self.key_sender:
                key = action.get("key", "")
                if key:
                    self.update_status(f"Pressing {key.upper()}")
                    self.key_sender.send_key(key)
            
            elif action_type == "wait":
                delay = action.get("delay", 1.0)
                self.update_status(f"Waiting {delay}s")
                time.sleep(delay)
                
            elif action_type == "watch":
                # This is a special case that should be interrupted by detection
                # For now, just implement as a maximum wait time
                max_delay = action.get("delay", 30.0)
                self.update_status(f"Watching for fish bite (max {max_delay}s)")
                time.sleep(0.5)  # Just a small delay for testing
            
            # Call step complete callback
            if self.on_step_complete:
                self.on_step_complete(self.current_step)
                
            # Move to next step (unless it's a watch action that should be
            # interrupted by detection)
            if action_type != "watch" or not self.is_running:
                self.current_step += 1
                
            # Add delay between actions
            delay = action.get("delay", 0.0)
            if delay > 0:
                time.sleep(delay)
                
        # Sequence completed or stopped
        self.is_running = False
        self.current_step = 0
        
        if self.on_sequence_complete:
            self.on_sequence_complete()
            
        self.update_status("Fishing sequence completed")
        
    def reset(self):
        """Reset the fishing sequence state"""
        self.is_running = False
        self.is_paused = False
        self.current_step = 0 