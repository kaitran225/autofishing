"""
macOS-specific implementation of the pixel change detector
"""
import threading
import time
import subprocess
import mss
import pyautogui
import cv2
import numpy as np

from autofisher.core.detector import PixelChangeDetector

class MacPixelDetector(PixelChangeDetector):
    """macOS implementation of the pixel change detector"""
    
    def __init__(self):
        super().__init__()
        
        # Game window info for focusing
        self.game_process_name = ""
        self.game_window_name = "PLAY TOGETHER"
        
        # Standard action sequence with appropriate timings for macOS
        self.action_sequence = [
            {"action": "press_f", "delay": 0.0},
            {"action": "wait", "delay": 4.0},
            {"action": "press_esc", "delay": 1.5},
            {"action": "wait", "delay": 2.0},
            {"action": "press_f", "delay": 2.0}
        ]
        
        # Use mss for faster screen capture
        self.sct = mss.mss()
        
        # Performance metrics
        self.capture_interval = 0.01  # 10ms between captures (100fps)
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.last_successful_capture = 0
        
    def focus_game_window(self):
        """Focus the game window using AppleScript"""
        try:
            # AppleScript to focus on window containing "PLAY TOGETHER" in its title
            script = f'''
            tell application "System Events"
                set frontApp to first application process whose frontmost is true
                set frontAppName to name of frontApp
                
                # Try to find our target app
                repeat with thisProcess in application processes
                    set thisName to name of thisProcess
                    repeat with thisWindow in windows of thisProcess
                        if name of thisWindow contains "{self.game_window_name}" then
                            set frontmost of thisProcess to true
                            perform action "AXRaise" of thisWindow
                            # If we found it, consider it a success
                            return "Window focused"
                        end if
                    end repeat
                end repeat
                # If we get here, we didn't find it
                return "Window not found"
            end tell
            '''
            
            # Run the AppleScript
            proc = subprocess.Popen(['osascript', '-e', script], 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE)
            result, error = proc.communicate()
            
            if error:
                self.log(f"Error focusing window: {error.decode('utf-8')}")
                return False
                
            return "Window focused" in result.decode('utf-8')
        except Exception as e:
            self.log(f"Error focusing window: {e}")
            return False
    
    def _send_key(self, key):
        """Send a key press using pyautogui"""
        try:
            # Focus game window first
            self.focus_game_window()
            
            # Send key press - pyautogui handles this for Mac
            pyautogui.press(key)
            return True
        except Exception as e:
            self.log(f"Error sending key {key}: {e}")
            return False
            
    def capture_screen(self):
        """Capture the defined region of the screen"""
        try:
            if not self.region:
                self.log("No region selected")
                return None
                
            left, top, right, bottom = self.region
            width = right - left
            height = bottom - top
            
            # Using mss for faster capture
            monitor = {"top": top, "left": left, "width": width, "height": height}
            screenshot = self.sct.grab(monitor)
            
            # Use numpy array with zero copy when possible
            frame = np.array(screenshot, dtype=np.uint8)
            
            # Store color frame for visualization
            self.color_frame = frame.copy()
            
            # Convert to grayscale for processing
            if len(frame.shape) > 2:
                if frame.shape[2] == 4:  # BGRA format from mss
                    frame = np.dot(frame[..., :3], [0.114, 0.587, 0.299])
                else:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                
                # Ensure uint8 type
                frame = frame.astype(np.uint8)
            
            # Apply Gaussian blur to reduce noise if enabled
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
            
    def capture_reference(self):
        """Capture a reference frame"""
        self.log("Capturing reference frame...")
        self.reference_frame = self.capture_screen()
        if self.reference_frame is not None:
            self.log("Reference frame captured successfully")
            if self.on_frame_updated:
                self.on_frame_updated()
        else:
            self.log("Failed to capture reference frame")
            
    def start_detection(self):
        """Start the detection process"""
        if self.is_running:
            self.log("Detection already running")
            return
            
        self.log("Starting detection...")
        self.is_running = True
        self.is_paused = False
        
        # Start detection thread
        self.stop_requested = False
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
    def stop_detection(self):
        """Stop the detection process"""
        if not self.is_running:
            return
            
        self.log("Stopping detection...")
        self.stop_requested = True
        self.is_running = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=1.0)
            
    def _detection_loop(self):
        """Main detection loop"""
        self.log("Detection loop started")
        
        cooldown_threshold = 0.5  # seconds between detections
        detection_count = 0
        
        while not self.stop_requested:
            if self.is_paused:
                time.sleep(0.1)
                continue
                
            # Process action sequence if active
            if self.in_action_sequence:
                self._process_action_sequence()
                continue
                
            # Capture current frame
            self.current_frame = self.capture_screen()
            
            if self.current_frame is None:
                time.sleep(0.1)
                continue
                
            # Set reference frame if not set
            if self.reference_frame is None:
                self.reference_frame = self.current_frame
                continue
                
            # Calculate difference from reference frame
            self.diff_frame, change_percent = self.calculate_frame_difference(
                self.current_frame, self.reference_frame)
                
            # Update frame in the UI
            if self.on_frame_updated:
                self.on_frame_updated()
                
            # Check for significant change
            current_time = time.time()
            if (change_percent > self.THRESHOLD and 
                (current_time - self.last_detection_time) > cooldown_threshold):
                    
                # Record detection
                self.last_detection_time = current_time
                self.change_history.append((current_time, change_percent))
                
                # Trim history if too long
                if len(self.change_history) > 100:
                    self.change_history = self.change_history[-100:]
                    
                self.log(f"Change detected: {change_percent:.2%}")
                detection_count += 1
                
                # Start action sequence
                self.in_action_sequence = True
                self.action_sequence_step = 0
                self._process_action_sequence()
                
                # Trigger detection callback
                if self.on_detection:
                    self.on_detection()
                    
            # Set previous frame
            self.previous_frame = self.current_frame
            
            # Short sleep to avoid overloading CPU
            time.sleep(self.capture_interval)
            
        self.log("Detection loop stopped")
        
    def _process_action_sequence(self):
        """Process the action sequence for fishing"""
        if not self.in_action_sequence or self.action_sequence_step >= len(self.action_sequence):
            self.in_action_sequence = False
            self.action_sequence_step = 0
            return
            
        # Get current step
        step = self.action_sequence[self.action_sequence_step]
        action = step["action"]
        delay = step["delay"]
        
        # Process based on action type
        if action == "press_f":
            self.log("Sending F key...")
            self.focus_game_window()
            self._send_key("f")
        elif action == "press_esc":
            self.log("Sending ESC key...")
            self.focus_game_window()
            self._send_key("esc")
        elif action == "wait":
            self.log(f"Waiting {delay} seconds...")
            # Wait is handled below by the sleep
            
        # Move to next step
        self.action_sequence_step += 1
        
        # Sleep for the specified delay
        time.sleep(delay) 