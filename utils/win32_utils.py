"""
Windows utilities for input simulation and window management
"""
import ctypes
import time
import win32gui
import win32con
import win32process
import win32api
import psutil

# Define Windows structures for input simulation
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
        ("union", INPUT_UNION)
    ]

# Load Windows DLLs
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Constants for Windows API
INPUT_KEYBOARD = 1
VK_F = 0x46  # F key
KEYEVENTF_KEYUP = 0x0002
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040

def force_focus_window(hwnd):
    """Force focus a window using multiple approaches"""
    try:
        # Check if window exists
        if not win32gui.IsWindow(hwnd):
            print("Window does not exist")
            return False
            
        # Method 1: Standard SetForegroundWindow
        current_hwnd = user32.GetForegroundWindow()
        if current_hwnd == hwnd:
            return True  # Already in focus
            
        # Try standard approach first
        result = user32.SetForegroundWindow(hwnd)
        
        # Method 2: Try AttachThreadInput approach
        if not result:
            foreground_thread = user32.GetWindowThreadProcessId(current_hwnd, None)
            target_thread = user32.GetWindowThreadProcessId(hwnd, None)
            
            if foreground_thread != target_thread:
                user32.AttachThreadInput(foreground_thread, target_thread, True)
                result = user32.SetForegroundWindow(hwnd)
                user32.AttachThreadInput(foreground_thread, target_thread, False)
        
        # Method 3: Try BringWindowToTop and show window
        if not result:
            user32.ShowWindow(hwnd, win32con.SW_RESTORE)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        
        # Method 4: Use SetWindowPos with TOPMOST flag
        if not result:
            user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
            )
            # Then set back to non-topmost to avoid staying always on top
            user32.SetWindowPos(
                hwnd,
                win32con.HWND_NOTOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
            )
        
        # Final check if focus was achieved
        time.sleep(0.05)  # Short delay to let OS update window state
        focused_hwnd = user32.GetForegroundWindow()
        success = focused_hwnd == hwnd
        
        return success
        
    except Exception as e:
        print(f"Error forcing focus: {e}")
        return False

def direct_key_press(key_char):
    """Press a key using multiple methods"""
    try:
        # Method 1: Use win32api key events
        vk_code = ord(key_char.upper())
        win32api.keybd_event(vk_code, 0, 0, 0)  # key down
        time.sleep(0.05)
        win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)  # key up
        
        # Method 2: Send message to active window
        active_window = user32.GetForegroundWindow()
        if active_window:
            win32gui.PostMessage(active_window, win32con.WM_KEYDOWN, vk_code, 0)
            time.sleep(0.05)
            win32gui.PostMessage(active_window, win32con.WM_KEYUP, vk_code, 0)
            
        return True
    except Exception as e:
        print(f"Error with direct key press: {e}")
        return False

def find_window_by_pattern(name_patterns):
    """Find a window by matching title patterns"""
    result = [None]
    
    def enum_window_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            window_text = win32gui.GetWindowText(hwnd).lower()
            
            # Skip autofisher window
            if 'autofisher' in window_text:
                return True
                
            # Check by window title
            if any(pattern in window_text for pattern in name_patterns):
                result[0] = hwnd
                return False
        return True
        
    win32gui.EnumWindows(enum_window_callback, None)
    return result[0]

def is_fullscreen_app_active():
    """Check if any fullscreen application is active (except our app)"""
    try:
        # Get foreground window
        foreground_hwnd = user32.GetForegroundWindow()
        if not foreground_hwnd:
            return False
            
        # Skip if it's our window
        window_text = win32gui.GetWindowText(foreground_hwnd).lower()
        if 'autofisher' in window_text:
            return False
            
        # Check if the window is full screen
        monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromWindow(foreground_hwnd))
        work_area = monitor_info.get('Work')
        monitor_area = monitor_info.get('Monitor')
        
        if not work_area or not monitor_area:
            return False
            
        # Get window rect
        window_rect = win32gui.GetWindowRect(foreground_hwnd)
        
        # Window is fullscreen if it covers the entire monitor
        is_same_size = (
            window_rect[0] <= monitor_area[0] and
            window_rect[1] <= monitor_area[1] and
            window_rect[2] >= monitor_area[2] and
            window_rect[3] >= monitor_area[3]
        )
        
        return is_same_size
    except Exception:
        return False 