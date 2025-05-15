"""
Windows-specific implementations for screen capture, key sending, and window focus.
"""
import time
import mss
import numpy as np
import cv2
import keyboard

# Try to import Windows-specific modules
try:
    import win32gui
    import win32con
    import win32process
    import win32api
    import ctypes
    WINDOWS_MODULES_AVAILABLE = True
except ImportError:
    WINDOWS_MODULES_AVAILABLE = False
    print("Warning: Windows-specific modules not available. Some features may not work.")


class WindowsScreenCapturer:
    """Windows implementation of screen capture functionality."""
    
    def __init__(self):
        """Initialize the screen capturer with mss."""
        self.sct = mss.mss()
    
    def capture_region(self, region):
        """Capture a specific region of the screen.
        
        Args:
            region: Dictionary with left, top, width, height
            
        Returns:
            Numpy array with captured image data
        """
        try:
            # Convert region to mss format
            monitor = {
                "left": region["left"],
                "top": region["top"],
                "width": region["width"],
                "height": region["height"]
            }
            
            # Capture the screen region
            sct_img = self.sct.grab(monitor)
            
            # Convert to numpy array in BGR format (for OpenCV)
            img = np.array(sct_img)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            print(f"Error capturing screen: {e}")
            return None
    
    def get_screen_size(self):
        """Get the screen size.
        
        Returns:
            Tuple of (width, height)
        """
        monitor = self.sct.monitors[0]  # Primary monitor
        return monitor["width"], monitor["height"]
    
    def close(self):
        """Clean up resources."""
        self.sct.close()


class WindowsKeySender:
    """Windows implementation of key sending functionality."""
    
    def __init__(self):
        """Initialize the key sender."""
        self.use_low_level = False
        
        if WINDOWS_MODULES_AVAILABLE:
            try:
                # Initialize user32 DLL for low-level keyboard input
                self.user32 = ctypes.WinDLL('user32', use_last_error=True)
                
                # Key constants
                self.VK_F = 0x46  # Virtual key code for 'F'
                self.VK_ESC = 0x1B  # Virtual key code for 'ESC'
                self.KEYEVENTF_KEYUP = 0x0002
                self.INPUT_KEYBOARD = 1
                
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
                        # Mouse and hardware input structures would go here
                    ]
                
                class INPUT(ctypes.Structure):
                    _fields_ = [
                        ("type", ctypes.c_ulong),
                        ("ui", INPUT_UNION),
                    ]
                
                self.KEYBDINPUT = KEYBDINPUT
                self.INPUT_UNION = INPUT_UNION
                self.INPUT = INPUT
                
                self.use_low_level = True
                print("Windows low-level key sender initialized")
            except Exception as e:
                print(f"Error initializing low-level key sender: {e}")
                self.use_low_level = False
    
    def send_key(self, key):
        """Send a key press to the active window.
        
        Args:
            key: The key to send (e.g., 'f', 'esc')
        """
        # Try low-level first for better game compatibility
        if self.use_low_level:
            try:
                self._send_key_low_level(key)
                return
            except Exception as e:
                print(f"Low-level key send failed: {e}")
                # Fall back to keyboard module
        
        # Use the keyboard module (more compatible but less reliable for games)
        keyboard.press_and_release(key)
    
    def _send_key_low_level(self, key):
        """Send a key using low-level Windows API for better game compatibility.
        
        Args:
            key: The key to send (e.g., 'f', 'esc')
        """
        if not self.use_low_level:
            return
        
        # Map key to virtual key code
        if key.lower() == 'f':
            vk = self.VK_F
        elif key.lower() == 'esc':
            vk = self.VK_ESC
        else:
            # More keys could be added here
            raise ValueError(f"Unsupported key: {key}")
        
        # Create input structure for key down
        extra = ctypes.pointer(ctypes.c_ulong(0))
        ii_ = self.INPUT_UNION()
        ii_.ki = self.KEYBDINPUT(vk, 0, 0, 0, extra)
        x = self.INPUT(self.INPUT_KEYBOARD, ii_)
        
        # Create input structure for key up
        ii2_ = self.INPUT_UNION()
        ii2_.ki = self.KEYBDINPUT(vk, 0, self.KEYEVENTF_KEYUP, 0, extra)
        x2 = self.INPUT(self.INPUT_KEYBOARD, ii2_)
        
        # Send key down and key up
        self.user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
        time.sleep(0.05)  # Short delay between down and up
        self.user32.SendInput(1, ctypes.byref(x2), ctypes.sizeof(x2))


class WindowsWindowFocus:
    """Windows implementation of window focus functionality."""
    
    def __init__(self):
        """Initialize the window focus handler."""
        self.game_window_title = "PLAY TOGETHER"
        self.game_hwnd = None
        
        if not WINDOWS_MODULES_AVAILABLE:
            print("Windows modules not available. Window focus features disabled.")
            return
        
        # Store module references
        self.win32gui = win32gui
        self.win32con = win32con
    
    def find_game_window(self):
        """Find the game window handle.
        
        Returns:
            Boolean indicating success or failure
        """
        if not WINDOWS_MODULES_AVAILABLE:
            return False
        
        def enum_windows_callback(hwnd, result):
            win_title = self.win32gui.GetWindowText(hwnd)
            if self.game_window_title.upper() in win_title.upper() and self.win32gui.IsWindowVisible(hwnd):
                result.append(hwnd)
            return True
        
        result = []
        try:
            self.win32gui.EnumWindows(enum_windows_callback, result)
            if result:
                self.game_hwnd = result[0]
                print(f"Found game window: {self.win32gui.GetWindowText(self.game_hwnd)}")
                return True
            else:
                print("Game window not found.")
                return False
        except Exception as e:
            print(f"Error finding game window: {e}")
            return False
    
    def focus_game_window(self):
        """Focus the game window.
        
        Returns:
            Boolean indicating success or failure
        """
        if not WINDOWS_MODULES_AVAILABLE or not self.game_hwnd:
            if self.find_game_window():
                pass  # Found window, continue
            else:
                return False  # Couldn't find window
        
        try:
            # Check if the window is minimized
            if self.win32gui.IsIconic(self.game_hwnd):
                # Restore the window
                self.win32gui.ShowWindow(self.game_hwnd, self.win32con.SW_RESTORE)
            
            # Bring to foreground
            self.win32gui.SetForegroundWindow(self.game_hwnd)
            
            # Give some time for window to gain focus
            time.sleep(0.1)
            
            return True
        except Exception as e:
            print(f"Error focusing game window: {e}")
            return False
    
    def is_game_window_focused(self):
        """Check if the game window is currently focused.
        
        Returns:
            Boolean indicating if game window is focused
        """
        if not WINDOWS_MODULES_AVAILABLE:
            return False
        
        try:
            foreground_hwnd = self.win32gui.GetForegroundWindow()
            if self.game_hwnd and foreground_hwnd == self.game_hwnd:
                return True
            return False
        except Exception as e:
            print(f"Error checking window focus: {e}")
            return False 