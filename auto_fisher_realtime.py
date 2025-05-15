import cv2
import numpy as np
import pyautogui
import time
import mss
import os
import platform
import datetime
import threading
import ctypes
import keyboard

# For Windows-specific functionality
if platform.system() == "Windows":
    import win32gui
    import win32con
    import win32process
    import win32api
    # For direct key simulation
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    # Key constants
    VK_F = 0x46  # Virtual key code for 'F'
    VK_ESC = 0x1B  # Virtual key code for 'ESC'
    KEYEVENTF_KEYUP = 0x0002
    INPUT_KEYBOARD = 1
    # Input type for SendInput
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
        ]
    class INPUT_UNION(ctypes.Union):
        _fields_ = [
            ("ki", KEYBDINPUT),
            # Other input types omitted for brevity
        ]
    class INPUT(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_ulong),
            ("ii", INPUT_UNION)
        ]


class AutoFisher:
    def __init__(self):
        # Detect OS
        self.os_type = platform.system()
        print(f"Detected OS: {self.os_type}")
        
        # Set up OS-specific parameters
        if self.os_type == "Windows":
            # Windows region parameters
            self.exclamation_x = 960  # Center of screen horizontally for Windows
            self.exclamation_y = 540  # Center of screen vertically for Windows
            self.exclamation_width = 400  # Width of detection area
            self.exclamation_height = 300  # Height of detection area
            
            # Fish shadow/bouncy bait region
            self.shadow_x = 960  # Center of screen horizontally for Windows
            self.shadow_y = 700  # Lower part of screen for fish shadows
            self.shadow_width = 600  # Width of detection area
            self.shadow_height = 200  # Height of detection area
        elif self.os_type == "Darwin":  # macOS
            # macOS region parameters
            self.exclamation_x = 960  # Center of screen horizontally for macOS
            self.exclamation_y = 500  # Center of screen vertically for macOS
            self.exclamation_width = 400  # Width of detection area
            self.exclamation_height = 300  # Height of detection area
            
            # Fish shadow/bouncy bait region
            self.shadow_x = 960  # Center of screen horizontally for macOS
            self.shadow_y = 650  # Lower part of screen for fish shadows
            self.shadow_width = 600  # Width of detection area
            self.shadow_height = 200  # Height of detection area
        else:  # Linux or other
            # Default parameters
            self.exclamation_x = 960
            self.exclamation_y = 540
            self.exclamation_width = 400
            self.exclamation_height = 300
            
            # Fish shadow/bouncy bait region
            self.shadow_x = 960
            self.shadow_y = 700
            self.shadow_width = 600
            self.shadow_height = 200
        
        # Detection parameters
        self.exclamation_threshold = 30  # Pixel change threshold for exclamation
        self.shadow_threshold = 20  # Shadow detection sensitivity
        self.bait_threshold = 25  # Bouncy bait detection sensitivity
        
        # Size parameters
        self.min_exclamation_area = 100
        self.max_exclamation_area = 800
        self.min_shadow_area = 500
        self.max_shadow_area = 5000
        
        # Last frames for comparison
        self.last_exclamation_frame = None
        self.last_shadow_frame = None
        self.reference_exclamation_frame = None
        self.reference_shadow_frame = None
        
        # Flag to control fishing loop
        self.is_running = False
        self.is_paused = False
        self.stop_requested = False
        
        # Game window tracking
        self.game_window = None
        self.game_window_title = "PLAY TOGETHER"
        
        # Create capture directory if debug mode enabled
        self.debug_mode = False  # Set to False to disable image saving
        if self.debug_mode:
            self.capture_dir = "captured_regions"
            os.makedirs(self.capture_dir, exist_ok=True)
        
        # Initialize screen capture - faster with reusable context
        self.sct = mss.mss()
        
        # Exclamation mark region
        self.exclamation_monitor = {
            "top": self.exclamation_y - self.exclamation_height//2,
            "left": self.exclamation_x - self.exclamation_width//2,
            "width": self.exclamation_width,
            "height": self.exclamation_height
        }
        
        # Fish shadow/bouncy bait region
        self.shadow_monitor = {
            "top": self.shadow_y - self.shadow_height//2,
            "left": self.shadow_x - self.shadow_width//2,
            "width": self.shadow_width,
            "height": self.shadow_height
        }
        
        # Detection counters and timing
        self.detection_count = 0
        self.last_detection_time = 0
        self.detection_cooldown = 1.0  # Seconds between detections
        
        # Health check variables
        self.last_successful_capture = 0
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        
        # Capture interval for optimized performance
        self.capture_interval = 0.03  # 30ms between captures (~33fps)
        
        # Action sequence control
        self.in_action_sequence = False
        self.action_sequence_step = 0
        
        # Action sequence (similar to the prototype implementations)
        self.action_sequence = [
            {"action": "press_f", "delay": 0.0},   # Press F immediately
            {"action": "wait", "delay": 3.0},      # Wait 3 seconds
            {"action": "press_esc", "delay": 1.0}, # Press ESC, wait 1 second
            {"action": "wait", "delay": 1.0},      # Wait 1 more second
            {"action": "press_f", "delay": 1.0}    # Press F again, wait 1 second
        ]
    
    def capture_screen(self, monitor):
        """Capture the current screen in the specified region - optimized for speed"""
        try:
            # Using reused mss context manager for better performance
            sct_img = self.sct.grab(monitor)
            
            # Use numpy array with zero copy when possible for speed
            img = np.array(sct_img)
            
            # Update health check variables
            self.last_successful_capture = time.time()
            self.consecutive_failures = 0
            
            # Convert BGRA to BGR (mss returns BGRA)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            print(f"Error capturing screen: {e}")
            self.consecutive_failures += 1
            return None
    
    def save_debug_image(self, img, prefix="region"):
        """Save an image for debugging - only if debug mode is enabled"""
        if not self.debug_mode:
            return None
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{self.capture_dir}/{prefix}_{timestamp}.png"
        cv2.imwrite(filename, img)
        print(f"Saved debug image: {filename}")
        return filename
    
    def detect_exclamation_mark(self, frame, last_frame=None):
        """Detect the exclamation mark using frame differencing and contour detection"""
        if last_frame is None:
            return False, frame
        
        # Convert to grayscale for faster processing
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_last_frame = cv2.cvtColor(last_frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate absolute difference to detect changes - fast operation
        frame_diff = cv2.absdiff(gray_frame, gray_last_frame)
        
        # Apply threshold to get binary image
        _, thresh = cv2.threshold(frame_diff, self.exclamation_threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours in the binary image
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by area and shape
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_exclamation_area < area < self.max_exclamation_area:
                # Additional verification - check for bright color (exclamation marks are usually bright)
                x, y, w, h = cv2.boundingRect(contour)
                roi = frame[y:y+h, x:x+w]
                
                # Check if there's a bright area that stands out
                hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                v_channel = hsv_roi[:, :, 2]  # Value channel (brightness)
                
                # If the region has high brightness, consider it an exclamation mark
                if np.mean(v_channel) > 160:
                    # Draw rectangle for debugging visualization
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    
                    # Save debug images if enabled
                    if self.debug_mode:
                        self.save_debug_image(roi, "exclamation_region")
                        self.save_debug_image(frame, "detection_frame_exclamation")
                    
                    return True, frame
        
        return False, frame
    
    def detect_fish_shadow(self, frame, last_frame=None):
        """Detect fish shadows and bouncy bait in water"""
        if last_frame is None:
            return False, frame, "none"
        
        # Convert to grayscale for faster processing
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_last_frame = cv2.cvtColor(last_frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate absolute difference to detect motion
        frame_diff = cv2.absdiff(gray_frame, gray_last_frame)
        
        # Apply threshold for motion detection
        _, thresh = cv2.threshold(frame_diff, self.shadow_threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours for motion - using EXTERNAL contours for speed
        motion_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # For fish shadow detection - look for darker regions
        # Apply blur for noise reduction - faster with smaller kernel
        blurred = cv2.GaussianBlur(gray_frame, (9, 9), 0)
        _, shadow_thresh = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours of shadow regions
        shadow_contours, _ = cv2.findContours(shadow_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Check for bouncy bait (usually has motion and specific size/shape)
        for contour in motion_contours:
            area = cv2.contourArea(contour)
            if 100 < area < 500:  # Bouncy bait is usually smaller than fish shadows
                x, y, w, h = cv2.boundingRect(contour)
                
                # Check if it's a bouncy motion (ratio of width/height)
                if 0.7 < w/h < 1.3:  # Approximately square/circular shape
                    # Draw rectangle for debugging visualization
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
                    cv2.putText(frame, "Bait", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    
                    # Save debug images if enabled
                    if self.debug_mode:
                        roi = frame[y:y+h, x:x+w]
                        self.save_debug_image(roi, "bait_region")
                        self.save_debug_image(frame, "detection_frame_bait")
                    
                    return True, frame, "bait"
        
        # Check for fish shadows (usually larger dark areas with some motion)
        for contour in shadow_contours:
            area = cv2.contourArea(contour)
            if self.min_shadow_area < area < self.max_shadow_area:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Calculate average darkness of the region
                roi = gray_frame[y:y+h, x:x+w]
                darkness = 255 - np.mean(roi)
                
                # If it's dark enough to be a shadow
                if darkness > 50:
                    # Draw rectangle for debugging visualization
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                    cv2.putText(frame, "Shadow", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                    
                    # Save debug images if enabled
                    if self.debug_mode:
                        roi = frame[y:y+h, x:x+w]
                        self.save_debug_image(roi, "shadow_region")
                        self.save_debug_image(frame, "detection_frame_shadow")
                    
                    return True, frame, "shadow"
        
        return False, frame, "none"
    
    def find_game_window(self):
        """Find the game window handle"""
        if self.os_type == "Windows":
            try:
                # Search for window by title
                self.game_window = win32gui.FindWindow(None, self.game_window_title)
                if not self.game_window:
                    # Try fuzzy match with partial title
                    def enum_windows_callback(hwnd, result):
                        if win32gui.IsWindowVisible(hwnd):
                            title = win32gui.GetWindowText(hwnd)
                            if "PLAY TOGETHER" in title.upper():
                                result.append(hwnd)
                                return False
                        return True
                    
                    result = []
                    win32gui.EnumWindows(enum_windows_callback, result)
                    if result:
                        self.game_window = result[0]
                
                if self.game_window:
                    print(f"Found game window: {win32gui.GetWindowText(self.game_window)}")
                    return True
                else:
                    print("Game window not found")
                    return False
            except Exception as e:
                print(f"Error finding game window: {e}")
                return False
        elif self.os_type == "Darwin":  # macOS
            # Use AppleScript to find window (simplified version)
            print("Mac game window focus will use keyboard.press directly")
            return True
        else:
            print("Window finding not implemented for this OS")
            return False
    
    def focus_game_window(self):
        """Focus the game window before sending keys"""
        if self.os_type == "Windows":
            try:
                if not self.game_window and not self.find_game_window():
                    return False
                
                # Check if window exists
                if not win32gui.IsWindow(self.game_window):
                    if not self.find_game_window():
                        return False
                
                # Try to focus window with multiple methods
                if win32gui.IsIconic(self.game_window):  # If minimized
                    win32gui.ShowWindow(self.game_window, win32con.SW_RESTORE)
                    time.sleep(0.1)
                
                # Set the window position to top-most temporarily
                win32gui.SetWindowPos(self.game_window, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                     win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
                time.sleep(0.05)
                win32gui.SetWindowPos(self.game_window, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                     win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
                
                # Multiple focus attempts
                user32.SetForegroundWindow(self.game_window)
                user32.SetFocus(self.game_window)
                user32.BringWindowToTop(self.game_window)
                
                # Force active window
                user32.SwitchToThisWindow(self.game_window, True)
                
                # Verify focus
                active_window = user32.GetForegroundWindow()
                result = (active_window == self.game_window)
                print(f"Focus result: {result}")
                return result
            except Exception as e:
                print(f"Error focusing window: {e}")
                return False
        else:
            # For macOS and others, we'll rely on keyboard.press working globally
            return True
    
    def send_key(self, key):
        """Send a key press to the game"""
        try:
            # Focus game window first if needed
            if self.os_type == "Windows":
                if not self.focus_game_window():
                    # Try once with more aggressive approach
                    time.sleep(0.5)
                    if not self.focus_game_window():
                        print("Failed to focus game window, attempting key press anyway")
                
                # Use SendInput for Windows (most reliable method)
                if key.lower() == 'f':
                    vk_code = VK_F
                elif key.lower() == 'esc':
                    vk_code = VK_ESC
                else:
                    vk_code = ord(key.upper())
                
                # Create input structure
                kb_input = INPUT()
                kb_input.type = INPUT_KEYBOARD
                kb_input.ii.ki.wVk = vk_code
                kb_input.ii.ki.wScan = 0
                kb_input.ii.ki.dwFlags = 0
                kb_input.ii.ki.time = 0
                kb_input.ii.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
                
                # Press key
                user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
                time.sleep(0.05)
                
                # Release key
                kb_input.ii.ki.dwFlags = KEYEVENTF_KEYUP
                user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
                
            # Also use the cross-platform method as backup
            keyboard.press_and_release(key)
            
            print(f"Sent {key} key")
            return True
        except Exception as e:
            print(f"Error sending key: {e}")
            return False
    
    def capture_reference_frames(self):
        """Capture reference frames for both regions"""
        exclamation_frame = self.capture_screen(self.exclamation_monitor)
        shadow_frame = self.capture_screen(self.shadow_monitor)
        
        if exclamation_frame is not None and shadow_frame is not None:
            self.reference_exclamation_frame = exclamation_frame
            self.reference_shadow_frame = shadow_frame
            print("Reference frames captured")
            return True
        else:
            print("Failed to capture reference frames")
            return False
    
    def perform_health_check(self):
        """Check detector health and attempt recovery if needed"""
        current_time = time.time()
        
        # Check if we've had too many consecutive failures
        if self.consecutive_failures >= self.max_consecutive_failures:
            print("Too many consecutive failures, attempting recovery...")
            
            # Reset state
            self.last_exclamation_frame = None
            self.last_shadow_frame = None
            
            # Try to recapture reference frames
            self.capture_reference_frames()
            
            # Reset failure counter
            self.consecutive_failures = 0
            
        # Check if we haven't had a successful capture in a while
        if self.last_successful_capture > 0 and (current_time - self.last_successful_capture) > 5.0:
            print("No successful captures detected, attempting recovery...")
            self.capture_reference_frames()
        
        return True
    
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
        
        if action_type == "press_f":
            print(f"Action sequence: Pressing F key")
            self.send_key('f')
        elif action_type == "press_esc":
            print(f"Action sequence: Pressing ESC key")
            self.send_key('esc')
        elif action_type == "wait":
            print(f"Action sequence: Waiting {action['delay']}s")
            # No actual action needed for wait
            pass
        
        # Wait for the specified delay
        time.sleep(action["delay"])
        
        # Move to next step
        self.action_sequence_step += 1
        
        # If we've reached the end, exit the sequence
        if self.action_sequence_step >= len(self.action_sequence):
            self.in_action_sequence = False
            print("Action sequence completed")
            
            # Take new reference frames after completing the sequence
            self.capture_reference_frames()
    
    def start_fishing(self):
        """Start the auto-fishing loop"""
        self.is_running = True
        self.is_paused = False
        self.stop_requested = False
        print("Auto-fishing started. Press 'q' to stop.")
        
        # Try to find game window
        self.find_game_window()
        
        # Capture initial frames
        self.last_exclamation_frame = self.capture_screen(self.exclamation_monitor)
        self.last_shadow_frame = self.capture_screen(self.shadow_monitor)
        
        # Capture reference frames
        self.capture_reference_frames()
        
        # Track state
        waiting_for_fish = False
        display_frame = None
        
        try:
            while self.is_running and not self.stop_requested:
                # Perform health check
                self.perform_health_check()
                
                # Handle action sequence if one is in progress
                if self.in_action_sequence:
                    self._process_action_sequence()
                    
                    # Show real-time display
                    if display_frame is not None:
                        cv2.imshow("Auto-fisher", display_frame)
                    
                    # Check for quit key
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                    
                    continue
                
                # Capture both regions - optimization: capture only what we need based on state
                exclamation_frame = self.capture_screen(self.exclamation_monitor)
                
                # Only capture shadow frame if we're not waiting for a fish
                if not waiting_for_fish:
                    shadow_frame = self.capture_screen(self.shadow_monitor)
                else:
                    shadow_frame = self.last_shadow_frame
                
                if exclamation_frame is None or shadow_frame is None:
                    time.sleep(self.capture_interval)
                    continue
                
                # Detect exclamation mark - only if we have reference frames
                if self.reference_exclamation_frame is not None:
                    exclamation_detected, exclamation_frame_viz = self.detect_exclamation_mark(
                        exclamation_frame, self.reference_exclamation_frame
                    )
                else:
                    exclamation_detected, exclamation_frame_viz = self.detect_exclamation_mark(
                        exclamation_frame, self.last_exclamation_frame
                    )
                
                # Detect fish shadow or bouncy bait if needed
                if not waiting_for_fish and self.reference_shadow_frame is not None:
                    shadow_detected, shadow_frame_viz, detection_type = self.detect_fish_shadow(
                        shadow_frame, self.reference_shadow_frame
                    )
                else:
                    shadow_detected = False
                    shadow_frame_viz = shadow_frame
                    detection_type = "none"
                
                # Update last frames
                self.last_exclamation_frame = exclamation_frame.copy()
                if not waiting_for_fish:
                    self.last_shadow_frame = shadow_frame.copy()
                
                # Logic for fishing
                current_time = time.time()
                if exclamation_detected and (current_time - self.last_detection_time) > self.detection_cooldown:
                    print("Exclamation mark detected!")
                    self.last_detection_time = current_time
                    self.detection_count += 1
                    waiting_for_fish = False
                    
                    # Start the action sequence
                    self.in_action_sequence = True
                    self.action_sequence_step = 0
                    # Execute first action immediately
                    self._process_action_sequence()
                    
                elif shadow_detected and not waiting_for_fish and (current_time - self.last_detection_time) > self.detection_cooldown:
                    if detection_type == "shadow":
                        print("Fish shadow detected!")
                        waiting_for_fish = True
                        # Move toward shadow position (click)
                        x = self.shadow_x
                        y = self.shadow_y
                        pyautogui.click(x, y)
                    elif detection_type == "bait":
                        print("Bouncy bait detected!")
                        # Optional: do something with bouncy bait detection
                
                # Display frames (debugging) - combine frames for visualization
                if exclamation_frame_viz is not None and shadow_frame_viz is not None:
                    # Resize for display
                    display_exclamation = cv2.resize(exclamation_frame_viz, (400, 300))
                    display_shadow = cv2.resize(shadow_frame_viz, (400, 300))
                    
                    # Combine frames horizontally
                    combined_frame = np.hstack((display_exclamation, display_shadow))
                    
                    # Add OS and region info text
                    cv2.putText(combined_frame, f"OS: {self.os_type} | Detections: {self.detection_count}", (10, 20), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(combined_frame, "Exclamation Mark", (10, 40), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    cv2.putText(combined_frame, "Fish Shadow/Bait", (410, 40), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    # Add status text
                    status = "WAITING FOR FISH" if waiting_for_fish else "SCANNING"
                    if self.in_action_sequence:
                        status = f"ACTION SEQUENCE ({self.action_sequence_step}/{len(self.action_sequence)})"
                    cv2.putText(combined_frame, status, (10, 290), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    
                    # Show the combined frame
                    cv2.imshow("Auto-fisher", combined_frame)
                    display_frame = combined_frame
                
                # Break on 'q' key
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
                # Control loop speed - but faster than original for better real-time detection
                time.sleep(self.capture_interval)
                
        except KeyboardInterrupt:
            print("Auto-fishing stopped by keyboard interrupt.")
        finally:
            self.stop_fishing()
    
    def stop_fishing(self):
        """Stop the auto-fishing loop"""
        self.is_running = False
        self.stop_requested = True
        cv2.destroyAllWindows()
        print("Auto-fishing stopped.")
    
    def interactive_region_setup(self):
        """Interactive setup to allow user to position detection regions"""
        print("\nInteractive Region Setup")
        print("------------------------")
        print("This will help you position the detection regions correctly.")
        print("1. A window will open showing your screen")
        print("2. Click to position Exclamation Mark region")
        print("3. Then click to position Fish Shadow/Bait region")
        
        # Capture full screen as reference
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # Get primary monitor
            screen = np.array(sct.grab(monitor))
            screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
            
            # Resize for display if needed
            scale = 0.5
            screen = cv2.resize(screen, (0, 0), fx=scale, fy=scale)
            
            # Create a window and set mouse callback
            cv2.namedWindow("Region Setup")
            clicks = []
            
            def mouse_callback(event, x, y, flags, param):
                if event == cv2.EVENT_LBUTTONDOWN:
                    clicks.append((x, y))
                    
                    if len(clicks) == 1:
                        # First click for Exclamation Mark region
                        self.exclamation_x = int(x / scale)
                        self.exclamation_y = int(y / scale)
                        print(f"Exclamation region center set to: ({self.exclamation_x}, {self.exclamation_y})")
                        
                        # Update exclamation monitor
                        self.exclamation_monitor = {
                            "top": self.exclamation_y - self.exclamation_height//2,
                            "left": self.exclamation_x - self.exclamation_width//2,
                            "width": self.exclamation_width,
                            "height": self.exclamation_height
                        }
                        
                        # Draw rectangle for exclamation region
                        cv2.rectangle(screen, 
                                     (x - int(self.exclamation_width*scale/2), y - int(self.exclamation_height*scale/2)),
                                     (x + int(self.exclamation_width*scale/2), y + int(self.exclamation_height*scale/2)),
                                     (0, 255, 0), 2)
                        cv2.putText(screen, "Exclamation", (x - 40, y - int(self.exclamation_height*scale/2) - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                        
                    elif len(clicks) == 2:
                        # Second click for Fish Shadow region
                        self.shadow_x = int(x / scale)
                        self.shadow_y = int(y / scale)
                        print(f"Shadow region center set to: ({self.shadow_x}, {self.shadow_y})")
                        
                        # Update shadow monitor
                        self.shadow_monitor = {
                            "top": self.shadow_y - self.shadow_height//2,
                            "left": self.shadow_x - self.shadow_width//2,
                            "width": self.shadow_width,
                            "height": self.shadow_height
                        }
                        
                        # Draw rectangle for shadow region
                        cv2.rectangle(screen, 
                                     (x - int(self.shadow_width*scale/2), y - int(self.shadow_height*scale/2)),
                                     (x + int(self.shadow_width*scale/2), y + int(self.shadow_height*scale/2)),
                                     (0, 0, 255), 2)
                        cv2.putText(screen, "Fish Shadow/Bait", (x - 60, y - int(self.shadow_height*scale/2) - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                        
                        print("Regions set! Press any key to continue...")
            
            cv2.setMouseCallback("Region Setup", mouse_callback)
            
            # Add instructions to the image
            instructions = "Click to set Exclamation Mark region, then click to set Fish Shadow/Bait region"
            cv2.putText(screen, instructions, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Wait for clicks
            while len(clicks) < 2:
                cv2.imshow("Region Setup", screen)
                if cv2.waitKey(100) != -1:
                    break
            
            # Wait for key press to close
            cv2.imshow("Region Setup", screen)
            cv2.waitKey(0)
            
            # Use destroyAllWindows instead of destroyWindow
            cv2.destroyAllWindows()
            
            # Save the final regions image if in debug mode
            if self.debug_mode:
                self.save_debug_image(screen, "region_setup")
            
            print("\nRegions set successfully:")
            print(f"Exclamation region: ({self.exclamation_x}, {self.exclamation_y}) - {self.exclamation_width}x{self.exclamation_height}")
            print(f"Shadow/Bait region: ({self.shadow_x}, {self.shadow_y}) - {self.shadow_width}x{self.shadow_height}")


if __name__ == "__main__":
    fisher = AutoFisher()
    
    # Interactive region setup
    print("Starting interactive region setup in 3 seconds...")
    print("Position the first region over where exclamation marks appear")
    print("Position the second region over where fish shadows and bait appear")
    time.sleep(3)
    fisher.interactive_region_setup()
    
    # Capture reference frames
    print("\nCapturing reference frames in 3 seconds...")
    print("Make sure no exclamation marks or fish shadows are visible")
    time.sleep(3)
    fisher.capture_reference_frames()
    
    # Start fishing
    print("\nStarting auto-fishing in 3 seconds...")
    print("Press 'q' to stop the program.")
    time.sleep(3)
    fisher.start_fishing() 