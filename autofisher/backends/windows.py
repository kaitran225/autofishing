"""
Windows-specific implementation of the pixel change detector
"""
import threading
import time
import win32gui
import win32con
import win32process
import win32api
import ctypes
import keyboard
from PIL import ImageGrab
import cv2
import numpy as np

from autofisher.core.detector import PixelChangeDetector

# For direct key simulation and window focus
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Special key constants
VK_F = 0x46  # Virtual key code for 'F'
VK_ESC = 0x1B  # Virtual key code for 'ESC'
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

class WindowsPixelDetector(PixelChangeDetector):
    """Windows implementation of the pixel change detector"""
    
    def __init__(self):
        super().__init__()
        
        # Game window info for focusing
        self.game_process_name = ""
        self.game_window_name = "PLAY TOGETHER"
        self.game_hwnd = None
        
        # Standard action sequence
        self.action_sequence = [
            {"action": "press_f", "delay": 0.0},
            {"action": "wait", "delay": 4.0},
            {"action": "press_esc", "delay": 1.5},
            {"action": "wait", "delay": 2.0},
            {"action": "press_f", "delay": 2.0}
        ]
        
    def find_game_window(self):
        """Find the game window"""
        self.log("Searching for game window...")
        
        def enum_window_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if self.game_window_name.lower() in window_title.lower():
                    self.game_hwnd = hwnd
                    self.log(f"Found game window: {window_title}")
                    return False  # Stop enumeration
            return True
        
        win32gui.EnumWindows(enum_window_callback, None)
        
        if not self.game_hwnd:
            self.log("Game window not found")
            return False
            
        return True
        
    def focus_game_window(self):
        """Focus the game window"""
        if not self.game_hwnd or not win32gui.IsWindow(self.game_hwnd):
            if not self.find_game_window():
                return False
                
        try:
            # Try to bring window to foreground
            if win32gui.IsIconic(self.game_hwnd):  # If minimized
                win32gui.ShowWindow(self.game_hwnd, win32con.SW_RESTORE)
                time.sleep(0.1)
                
            # Get window thread process ID
            current_thread = kernel32.GetCurrentThreadId()
            target_thread, _ = win32process.GetWindowThreadProcessId(self.game_hwnd)
            
            # Attach threads to ensure focus change permission
            user32.AttachThreadInput(current_thread, target_thread, True)
            
            # Set the window position to top-most temporarily
            win32gui.SetWindowPos(self.game_hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                 win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
            time.sleep(0.05)
            win32gui.SetWindowPos(self.game_hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                                 win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
            
            # Multiple focus attempts
            user32.SetForegroundWindow(self.game_hwnd)
            user32.SetFocus(self.game_hwnd)
            user32.BringWindowToTop(self.game_hwnd)
            
            # Force active window
            user32.SwitchToThisWindow(self.game_hwnd, True)
            
            # Detach threads
            user32.AttachThreadInput(current_thread, target_thread, False)
            
            # Alt keypress can help with focus
            keyboard.press_and_release('alt')
            time.sleep(0.05)
            
            # One more foreground window attempt
            user32.SetForegroundWindow(self.game_hwnd)
            
            return True
        except Exception as e:
            self.log(f"Error forcing focus: {e}")
            return False
    
    def _send_key(self, key):
        """Send a key press"""
        if key.lower() == 'f':
            vk_code = VK_F
        elif key.lower() == 'esc':
            vk_code = VK_ESC
        else:
            vk_code = ord(key.upper())
            
        try:
            # First method - direct keyboard hook
            keyboard.press(key)
            time.sleep(0.05)
            keyboard.release(key)
            
            # Second method - Send virtual key code directly
            win32api.keybd_event(vk_code, 0, 0, 0)  # key down
            time.sleep(0.05)
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)  # key up
            
            # Third method - PostMessage to active window
            active_window = user32.GetForegroundWindow()
            if active_window:
                win32gui.PostMessage(active_window, win32con.WM_KEYDOWN, vk_code, 0)
                time.sleep(0.05)
                win32gui.PostMessage(active_window, win32con.WM_KEYUP, vk_code, 0)
                
            return True
        except Exception as e:
            self.log(f"Error with key press: {e}")
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
            
            # Capture screenshot using PIL
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            
            # Convert to numpy array
            frame = np.array(screenshot)
            
            # Store color frame for visualization
            self.color_frame = frame.copy()
            
            # Convert to grayscale for processing
            if len(frame.shape) > 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                
            # Apply Gaussian blur to reduce noise if enabled
            if self.apply_blur and self.blur_kernel_size > 0:
                frame = cv2.GaussianBlur(frame, (self.blur_kernel_size, self.blur_kernel_size), 0)
            
            return frame
                
        except Exception as e:
            self.log(f"Error capturing screen: {e}")
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
            time.sleep(0.01)
            
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