import numpy as np
import keyboard
import time
import threading
import os
import win32gui
import win32con
import win32process
import win32api
import ctypes
import psutil
import matplotlib.pyplot as plt
import matplotlib.collections
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import queue
import datetime
from PIL import ImageGrab, Image
import cv2
import mss
import mss.tools

# For direct key simulation and window focus
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Special key constants
VK_F = 0x46  # Virtual key code for 'F'
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

# Window focus constants
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040

# Input type for SendInput
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort)
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("ii", INPUT_UNION)
    ]

# Helper functions for window focus and key press
def force_focus_window(hwnd):
    """Force focus on a window using multiple methods"""
    try:
        if not hwnd or not win32gui.IsWindow(hwnd):
            print("Invalid window handle")
            return False
            
        # Try to bring window to foreground
        if win32gui.IsIconic(hwnd):  # If minimized
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.1)
            
        # Get window thread process ID
        current_thread = kernel32.GetCurrentThreadId()
        target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
        
        # Attach threads to ensure focus change permission
        user32.AttachThreadInput(current_thread, target_thread, True)
        
        # Set the window position to top-most temporarily
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                             win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
        time.sleep(0.05)
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                             win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
        
        # Multiple focus attempts
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        user32.BringWindowToTop(hwnd)
        
        # Force active window
        user32.SwitchToThisWindow(hwnd, True)
        
        # Detach threads
        user32.AttachThreadInput(current_thread, target_thread, False)
        
        # Alt keypress can help with focus
        keyboard.press_and_release('alt')
        time.sleep(0.05)
        
        # One more foreground window attempt
        user32.SetForegroundWindow(hwnd)
        
        # Verify focus
        active_window = user32.GetForegroundWindow()
        result = (active_window == hwnd)
        print(f"Focus result: {result}, Active window: {win32gui.GetWindowText(active_window)}")
        return result
    except Exception as e:
        print(f"Error forcing focus: {e}")
        return False

# Use this function with key presses
def direct_key_press(key_char):
    """Press a key using multiple methods"""
    try:
        # First method - direct keyboard hook
        keyboard.press(key_char)
        time.sleep(0.05)
        keyboard.release(key_char)
        
        # Second method - Send virtual key code directly
        vk_code = ord(key_char.upper())
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
        print(f"Error with direct key press: {e}")
        return False

class PixelChangeDetector:
    def __init__(self, log_queue=None):
        self.THRESHOLD = 0.05  # Default threshold for pixel change
        self.is_running = False
        self.log_queue = log_queue
        self.gui = None
        
        # Screen capture region (required)
        self.region = None  # (left, top, right, bottom)
        
        # Advanced settings - always enabled
        self.high_performance_mode = True  # Use more resources for better reliability
        self.respect_fullscreen = True  # Don't interrupt fullscreen applications
        
        # Initialize visualization data
        self.current_frame = None
        self.previous_frame = None
        self.reference_frame = None
        self.reference_color_frame = None  # Store color reference frame
        self.diff_frame = None
        self.change_history = []
        self.color_frame = None
        
        # Last detection time for cooldown
        self.last_detection_time = 0
        self.detection_cooldown = 5.0  # Cooldown between detections (increased from 0.5 to 5.0)
        
        # Capture interval in seconds
        self.capture_interval = 0.05  # Capture interval
        self.max_fps = 30  # Maximum frames per second
        
        # Play Together window tracking
        self.play_together_window = None
        self.play_together_pid = None
        
        # Key settings
        self.fishing_key = "f"  # Default fishing key
        self.F_KEY = 0x46  # F key virtual key code (will be updated based on fishing_key)
        
        # Detection statistics
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
        
        # Detection thread reference
        self.detection_thread = None
        
        # Performance monitoring
        self.performance = {
            "avg_processing_time": 0.05,
            "processing_samples": 0,
            "cpu_usage": 0
        }
        
    def log(self, message):
        """Log a message to the queue if it exists"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted_message = f"[{timestamp}] {message}"
        if self.log_queue:
            self.log_queue.put(formatted_message)
        print(formatted_message)
        
    def reset_state(self):
        """Reset detector state to handle recovery"""
        self.current_frame = None
        self.previous_frame = None
        self.diff_frame = None
        # Don't reset reference_frame unless explicitly asked
        self.change_history = []
        self.last_detection_time = 0
        self.consecutive_failures = 0
        self.last_successful_capture = 0
        
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
            self.reset_state()
            
            # Try to recapture reference frame
            self.capture_reference()
            
            # Reset failure counter
            self.consecutive_failures = 0
            return True
            
        # Check if we haven't had a successful capture in a while
        if current_time - self.last_successful_capture > self.health_check_interval * 2:
            self.log("No successful captures detected, attempting recovery...")
            self.reset_state()
            self.capture_reference()
            return True
            
        return True
        
    def find_play_together_process(self):
        """Find Play Together process ID and window handle"""
        # List of possible name variations
        name_variations = [
            'play together',
            'playtogether',
            'play-together',
            'play_together',
            'playtogether.exe',
            'play together.exe', 
            'play together game',
            'playtogether game'
        ]
        
        # Explicitly exclude our own detector window
        excluded_titles = ['play together pixel change detector', 'pixel change detector']
        
        # Find process ID first
        found_pid = False
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                process_name = proc.info['name'].lower()
                if any(variation in process_name for variation in name_variations):
                    self.play_together_pid = proc.info['pid']
                    self.log(f"Found Play Together process: {process_name} (PID: {self.play_together_pid})")
                    found_pid = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        # Find window handle using EnumWindows
        def enum_window_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd).lower()
                
                # Skip our own detector window
                if any(excluded in window_text for excluded in excluded_titles):
                    return True
                
                try:
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    
                    # Check if window belongs to our process
                    if self.play_together_pid and found_pid == self.play_together_pid:
                        self.play_together_window = hwnd
                        self.log(f"Found Play Together window: {window_text} (HWND: {hwnd})")
                        return False
                except Exception:
                    pass
                    
                # Or check by window title - but be more strict about matching
                if any(variation == window_text or 
                       window_text.startswith(f"{variation} ") or
                       window_text.endswith(f" {variation}") or
                       f" {variation} " in window_text
                       for variation in name_variations):
                    self.play_together_window = hwnd
                    self.log(f"Found Play Together window by title: {window_text} (HWND: {hwnd})")
                    return False
            return True
            
        win32gui.EnumWindows(enum_window_callback, None)
        
        # If no Play Together window was found, log it clearly
        if not self.play_together_window:
            self.log("No Play Together window found. Please make sure the Play Together application is running.")
        
        return self.play_together_window is not None
            
    def focus_play_together_window(self):
        """Optimized window focus method"""
        if not self.play_together_window and not self.find_play_together_process():
            return False
                
        try:
            if not win32gui.IsWindow(self.play_together_window):
                if not self.find_play_together_process():
                    return False
                
            # Quick focus attempt using SetForegroundWindow
            user32.SetForegroundWindow(self.play_together_window)
            time.sleep(0.05)  # Reduced delay
            
            # Verify focus
            if user32.GetForegroundWindow() == self.play_together_window:
                return True
                
            # If quick focus failed, try enhanced method
            return force_focus_window(self.play_together_window)
            
        except Exception as e:
            self.log(f"Error focusing window: {e}")
            return False

    def is_fullscreen_app_active(self):
        """Check if any fullscreen application is currently active"""
        try:
            # Get foreground window
            foreground_hwnd = user32.GetForegroundWindow()
            if not foreground_hwnd:
                return False
                
            # Check if it's our own window or Play Together
            if foreground_hwnd == self.play_together_window:
                return False
                
            # Try to check if it's our GUI window
            if hasattr(self, 'gui') and self.gui and hasattr(self.gui, 'root'):
                if foreground_hwnd == self.gui.root.winfo_id():
                    return False
                
            # Get monitor info
            monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromWindow(foreground_hwnd))
            monitor_rect = monitor_info['Monitor']
            
            # Get window rect
            window_rect = win32gui.GetWindowRect(foreground_hwnd)
            
            # Check if window covers the entire monitor
            is_fullscreen = (
                window_rect[0] <= monitor_rect[0] and
                window_rect[1] <= monitor_rect[1] and
                window_rect[2] >= monitor_rect[2] and
                window_rect[3] >= monitor_rect[3]
            )
            
            # Additional check for borderless fullscreen
            style = win32gui.GetWindowLong(foreground_hwnd, win32con.GWL_STYLE)
            has_no_border = not (style & win32con.WS_BORDER or style & win32con.WS_DLGFRAME)
            
            # Get window title for logging
            if is_fullscreen and has_no_border:
                try:
                    window_title = win32gui.GetWindowText(foreground_hwnd)
                    if window_title:
                        self.log(f"Detected fullscreen app: {window_title[:30]}")
                except:
                    pass
                    
            return is_fullscreen and has_no_border
        except Exception as e:
            self.log(f"Error checking fullscreen status: {e}")
            return False

    def send_fishing_key(self):
        """Send the configured fishing key with focus mode"""
        try:
            # Update virtual key code based on the configured fishing key
            key = self.fishing_key.lower()
            vk_code = None
            
            # Handle special key names
            if key == "f":
                vk_code = 0x46  # VK_F
            elif key == "e":
                vk_code = 0x45  # VK_E
            elif key == "space":
                vk_code = 0x20  # VK_SPACE
            elif len(key) == 1:  # Single letter/number
                vk_code = ord(key.upper())
            else:
                self.log(f"Unknown key: {key}, falling back to 'f'")
                vk_code = 0x46  # Default to F
            
            # Calculate scan code for more reliable key identification
            scan_code = user32.MapVirtualKeyW(vk_code, 0)
            
            # Check for fullscreen applications if respect_fullscreen is enabled
            if self.respect_fullscreen and self.is_fullscreen_app_active():
                self.log("Fullscreen application detected - using ultra-minimal approach")
                # Use the most minimal approach possible - just a single message, no focus change
                try:
                    # Single quiet message
                    win32gui.PostMessage(self.play_together_window, win32con.WM_CHAR, ord(key.lower()), 0)
                    self.log("Sent quiet key message to avoid fullscreen interruption")
                    # Skip all other methods to ensure no interruption
                    return True
                except:
                    self.log("Couldn't send quiet key - skipping to avoid interruption")
                    # Don't try any other methods that might interrupt
                    return False
            
            # Focus window for reliable key press detection
            if user32.GetForegroundWindow() != self.play_together_window:
                self.focus_play_together_window()
                time.sleep(0.05)  # Reduced delay
            
            # Regular foreground mode
            # Create input structure
            kb_input = INPUT()
            kb_input.type = INPUT_KEYBOARD
            kb_input.ii.ki.wVk = vk_code
            kb_input.ii.ki.wScan = scan_code
            kb_input.ii.ki.dwFlags = 0
            kb_input.ii.ki.time = 0
            kb_input.ii.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
            
            # Press and release in quick succession
            user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
            time.sleep(0.01)  # Minimal delay
            kb_input.ii.ki.dwFlags = KEYEVENTF_KEYUP
            user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
            
            # Backup method - direct keyboard
            keyboard.press_and_release(key)
            
            # Update stats
            self.stats["total_detections"] += 1
            current_time = time.time()
            if self.stats["last_detection_time"] > 0:
                # Calculate interval since last detection
                interval = current_time - self.stats["last_detection_time"]
                # Update average detection interval using moving average
                if self.stats["avg_detection_interval"] == 0:
                    self.stats["avg_detection_interval"] = interval
                else:
                    self.stats["avg_detection_interval"] = (
                        0.8 * self.stats["avg_detection_interval"] + 0.2 * interval
                    )
            self.stats["last_detection_time"] = current_time
            
            return True
            
        except Exception as e:
            self.log(f"Error with key simulation: {e}")
            return False
            
    def send_f_key(self):
        """Legacy method for compatibility - redirects to send_fishing_key"""
        return self.send_fishing_key()

    def send_esc_key(self):
        """Optimized key press method for ESC key with focus mode"""
        try:
            key = 'esc'
            vk_code = 0x1B  # VK_ESCAPE
            scan_code = user32.MapVirtualKeyW(vk_code, 0)
            
            # Check for fullscreen applications if respect_fullscreen is enabled
            if self.respect_fullscreen and self.is_fullscreen_app_active():
                self.log("Fullscreen application detected - using ultra-minimal approach for ESC")
                # Use the most minimal approach possible for ESC - just a cancel message
                try:
                    # Send a cancel command instead of ESC key
                    win32gui.PostMessage(self.play_together_window, win32con.WM_SYSCOMMAND, win32con.SC_CLOSE, 0)
                    self.log("Sent quiet cancel message to avoid fullscreen interruption")
                    # Skip all other methods to ensure no interruption
                    return True
                except:
                    self.log("Couldn't send quiet cancel - skipping to avoid interruption")
                    # Don't try any other methods that might interrupt
                    return False
            
            # Focus window for reliable key press detection
            if user32.GetForegroundWindow() != self.play_together_window:
                self.focus_play_together_window()
                time.sleep(0.05)  # Reduced delay
            
            # Regular foreground mode
            # Create input structure
            kb_input = INPUT()
            kb_input.type = INPUT_KEYBOARD
            kb_input.ii.ki.wVk = vk_code
            kb_input.ii.ki.wScan = scan_code
            kb_input.ii.ki.dwFlags = 0
            kb_input.ii.ki.time = 0
            kb_input.ii.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
            
            # Press and release in quick succession
            user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
            time.sleep(0.01)  # Minimal delay
            kb_input.ii.ki.dwFlags = KEYEVENTF_KEYUP
            user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
            
            # Backup method - direct keyboard
            keyboard.press_and_release('esc')
            
            return True
            
        except Exception as e:
            self.log(f"Error with ESC key simulation: {e}")
            return False

    def capture_screen(self):
        """Capture the screen or region of interest using MSS for better multi-monitor support"""
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
                
            # Use mss library which has better performance and multi-monitor support
            with mss.mss() as sct:
                # Convert region format to mss format (left, top, width, height)
                mss_region = {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height
                }
                
                # Capture the region
                screenshot = sct.grab(mss_region)
                
                # Log first capture for debugging
                if not hasattr(self, 'first_capture_logged'):
                    self.log(f"First capture from region: ({left},{top}) to ({right},{bottom}), size: {width}x{height}")
                    monitor_info = f"Monitor info: {sct.monitors}"
                    self.log(monitor_info)
                    self.first_capture_logged = True
                
                # Convert to numpy array - sct.grab returns BGR
                frame = np.array(screenshot)
                
            # Validate frame
            if frame.size == 0:
                self.log("Error: Captured frame is empty")
                self.consecutive_failures += 1
                return None
                
            # Store color frame for visualization (convert BGR to RGB)
            if len(frame.shape) >= 3:
                self.color_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                # Keep original frame for color-based processing
            else:
                self.color_frame = None
                
            # For backward compatibility - don't convert to grayscale anymore
            # This keeps color information for better detection of pastel colors
            
            # Update health check variables
            self.last_successful_capture = time.time()
            self.consecutive_failures = 0
            return frame
            
        except Exception as e:
            self.log(f"Error capturing screen: {e}")
            self.consecutive_failures += 1
            return None
            
    def calculate_frame_difference(self, frame1, frame2):
        """Calculate the difference between two frames with improved color sensitivity"""
        if frame1 is None or frame2 is None:
            return None, 0
            
        # Ensure frames have same dimensions
        if frame1.shape != frame2.shape:
            # Resize to match
            frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
        
        # Apply slight blur to reduce noise sensitivity
        frame1_blurred = cv2.GaussianBlur(frame1, (5, 5), 0)
        frame2_blurred = cv2.GaussianBlur(frame2, (5, 5), 0)
        
        # For grayscale images
        if len(frame1.shape) < 3:
            # Calculate absolute difference
            diff_frame = cv2.absdiff(frame1_blurred, frame2_blurred)
        else:
            # For color images - convert to HSV for better color sensitivity
            frame1_hsv = cv2.cvtColor(frame1_blurred, cv2.COLOR_BGR2HSV)
            frame2_hsv = cv2.cvtColor(frame2_blurred, cv2.COLOR_BGR2HSV)
            
            # Calculate difference in HSV space (better for detecting pastel colors)
            h_diff = cv2.absdiff(frame1_hsv[:,:,0], frame2_hsv[:,:,0])
            s_diff = cv2.absdiff(frame1_hsv[:,:,1], frame2_hsv[:,:,1])
            v_diff = cv2.absdiff(frame1_hsv[:,:,2], frame2_hsv[:,:,2])
            
            # Weight hue differences more heavily for pastel colors
            h_weight = 2.0  # Increased weight for hue differences
            s_weight = 1.0
            v_weight = 1.0
            
            # Combine channels with weights
            diff_frame = cv2.addWeighted(h_diff, h_weight, s_diff, s_weight, 0)
            diff_frame = cv2.addWeighted(diff_frame, 1.0, v_diff, v_weight, 0)
        
        # Calculate percentage of pixels that changed significantly
        # Apply adaptive thresholding based on frame characteristics
        threshold = 20  # Lower threshold for more sensitivity
        
        # Apply morphological operations to highlight larger changes
        kernel = np.ones((3, 3), np.uint8)
        dilated_diff = cv2.dilate(diff_frame, kernel, iterations=1)
        
        # Count significant pixel changes
        changed_pixels = np.sum(dilated_diff > threshold)
        total_pixels = frame1.shape[0] * frame1.shape[1]
        change_percent = changed_pixels / total_pixels
        
        # For visualization, enhance the difference frame
        enhanced_diff = cv2.convertScaleAbs(dilated_diff, alpha=1.5)
        
        return enhanced_diff, change_percent
    
    def capture_reference(self):
        """Capture a reference frame for comparison"""
        frame = self.capture_screen()
        if frame is not None:
            self.reference_frame = frame
            self.log(f"Reference frame captured: {self.reference_frame.shape}")
            
            # If we have a color frame, store it for visualization
            if hasattr(self, 'color_frame') and self.color_frame is not None:
                self.reference_color_frame = self.color_frame.copy()
                
            return True
        else:
            self.log("Failed to capture reference frame")
            return False
            
    def validate_region(self):
        """Validate the selected region with a preview capture"""
        frame = self.capture_screen()
        if frame is not None:
            self.log(f"Region validation successful: captured {frame.shape}")
            return True
        else:
            self.log("Failed to validate region")
            return False
            
    def start_detection(self, thread_control=None):
        """Start detection with improved thread control"""
        if not self.find_play_together_process():
            self.log("Cannot start detection: Play Together window not found")
            return False
            
        self.is_running = True
        self.change_history = []
        
        # Capture initial frame as reference if none exists
        if self.reference_frame is None:
            self.capture_reference()
            
        self.previous_frame = self.reference_frame
        
        # Use thread control if provided
        self.thread_control = thread_control if thread_control else {
            "running": True,
            "paused": False,
            "stop_requested": False
        }
        
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        return True
        
    def stop_detection(self):
        """Stop detection cleanly"""
        self.is_running = False
        
    def _detection_loop(self):
        """Main detection loop with improved thread control and performance optimizations"""
        # Initialize frame skip counter for performance tuning
        frame_counter = 0
        fps_counter = 0
        fps_timer = time.time()
        last_fps_update = time.time()
        fps = 0
        
        # Load system resources
        cpu_load = psutil.cpu_percent(interval=0.1)
        
        # Adaptive performance based on system resources
        adaptive_interval = self.capture_interval
        
        self.log("Starting detection loop")
        
        while self.is_running and not self.thread_control.get("stop_requested", False):
            loop_start = time.time()
            try:
                # Check if paused
                if self.thread_control.get("paused", False):
                    time.sleep(0.1)
                    continue
                
                # Update FPS counter
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    fps = fps_counter
                    fps_counter = 0
                    fps_timer = time.time()
                    
                    # Update FPS in GUI every 5 seconds
                    if time.time() - last_fps_update >= 5.0:
                        if self.gui:
                            self.gui.root.after(0, lambda f=fps: self.gui.log(f"Processing at {f} FPS"))
                        last_fps_update = time.time()
                        
                        # Update CPU load
                        cpu_load = psutil.cpu_percent(interval=None)
                        
                        # Adjust capture interval based on CPU load
                        if cpu_load > 80:
                            adaptive_interval = max(0.05, self.capture_interval * 1.5)
                        elif cpu_load > 60:
                            adaptive_interval = self.capture_interval * 1.2
                        else:
                            adaptive_interval = self.capture_interval
                
                # Only perform health check every 10th frame
                if frame_counter % 10 == 0:
                    if not self.perform_health_check():
                        time.sleep(0.1)
                        continue
                
                # Capture current frame
                self.current_frame = self.capture_screen()
                
                if self.current_frame is None:
                    time.sleep(adaptive_interval)
                    continue
                    
                # Use reference frame if available, otherwise use previous frame
                compare_frame = self.reference_frame if self.reference_frame is not None else self.previous_frame
                
                if compare_frame is None:
                    self.capture_reference()
                    time.sleep(adaptive_interval)
                    continue
                
                # Calculate difference
                self.diff_frame, change_percent = self.calculate_frame_difference(self.current_frame, compare_frame)
                
                # Store in history (with downsampling for better performance)
                if frame_counter % 2 == 0:  # Only store every other frame
                    self.change_history.append(change_percent)
                    if len(self.change_history) > 1000:
                        self.change_history = self.change_history[-1000:]
                
                # Check for detection with cooldown
                current_time = time.time()
                if change_percent > self.THRESHOLD and (current_time - self.last_detection_time) > self.detection_cooldown:
                    change_percent_display = round(change_percent * 100, 2)
                    self.log(f"Major pixel change detected! Change: {change_percent_display}%")
                    self.last_detection_time = current_time
                    
                    # Update UI in the main thread
                    if self.gui:
                        self.gui.root.after(0, self.gui.increment_detection_count)
                    
                    # Enhanced detection handling
                    self._handle_detection()
                    
                    # Continue with next frame
                    continue
                
                # Store current frame as previous for next comparison if not using reference
                if self.reference_frame is None:
                    self.previous_frame = self.current_frame
                
                # Update frame counter
                frame_counter += 1
                
                # Calculate time spent in this iteration
                loop_time = time.time() - loop_start
                
                # Update performance metrics
                self.performance["processing_samples"] += 1
                if self.performance["processing_samples"] > 100:
                    self.performance["processing_samples"] = 1
                    
                # Update moving average of processing time
                alpha = 0.05  # Weight for new samples (lower = more stable average)
                self.performance["avg_processing_time"] = (1 - alpha) * self.performance["avg_processing_time"] + alpha * loop_time
                
                # Sleep to control capture rate, adjust based on processing time
                sleep_time = max(0, adaptive_interval - loop_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                self.log(f"Error in detection loop: {e}")
                self.consecutive_failures += 1
                time.sleep(0.05)  # Short delay on error
        
        # Thread is exiting
        self.log("Detection thread exiting")
        self.is_running = False
        
    def _handle_detection(self):
        """Handle detection event with optimized sequence"""
        try:
            # Handle key press with focus
            if self.focus_play_together_window():
                self.log(f"Pressing {self.fishing_key.upper()} key to catch fish...")
                self.send_fishing_key()
                time.sleep(0.2)
            else:
                self.log("Failed to focus window, skipping key press")
            
            # Pause detection based on the configured cooldown
            cooldown = self.detection_cooldown
            self.log(f"Pausing detection for {cooldown:.1f} seconds...")
            
            # Initial delay
            time.sleep(min(2.0, cooldown / 2))
            
            pause_start = time.time()
            
            # Wait additional time, checking for stop requests
            pause_end = pause_start + cooldown
            while time.time() < pause_end and self.is_running and not self.thread_control.get("stop_requested", False):
                remaining = int(pause_end - time.time())
                if self.gui:
                    self.gui.root.after(0, lambda r=remaining: self.gui.status_label.config(
                        text=f"System: monitor.paused ({r}s)",
                        style="Paused.Status.TLabel"
                    ))
                time.sleep(0.1)
            
            # Press ESC after pause
            if self.is_running and not self.thread_control.get("stop_requested", False):
                self.log("Pressing ESC key to exit fishing menu...")
                if self.focus_play_together_window():
                    self.send_esc_key()
                else:
                    self.log("Failed to focus window, skipping ESC key press")
            
            # Wait before casting again
            esc_end = time.time() + 2
            while time.time() < esc_end and self.is_running and not self.thread_control.get("stop_requested", False):
                time.sleep(0.1)
            
            # Cast fishing line again
            if self.is_running and not self.thread_control.get("stop_requested", False):
                self.log(f"Pressing {self.fishing_key.upper()} key to cast fishing line...")
                if self.focus_play_together_window():
                    self.send_fishing_key()
                    time.sleep(2)  # Wait for screen to update
                else:
                    self.log("Failed to focus window, skipping fishing cast")
                
                # Get a new reference frame
                self.capture_reference()
                self.log("New reference frame captured after casting")
            
            # Update status to running
            if self.gui and self.is_running and not self.thread_control.get("stop_requested", False):
                self.gui.root.after(0, lambda: self.gui.set_status_indicator("running"))
            
            # Pause a bit more to let the game stabilize
            stabilize_time = min(2.0, self.detection_cooldown * 0.2)
            time.sleep(stabilize_time)
        
        except Exception as e:
            self.log(f"Error handling detection: {e}")
            # Try to recover
            if self.gui:
                self.gui.root.after(0, lambda: self.gui.set_status_indicator("running"))

VERSION = "1.8.0"
VERSION_NAME = "Direct Control Edition"