"""
Input utilities for keyboard and mouse control using the exact same approach as the original autofisher
"""
import time
import ctypes
import keyboard
import win32gui
import win32con
import win32api
from .win32_utils import force_focus_window

# Constants for input simulation
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

# Get user32 DLL for direct input
user32 = ctypes.WinDLL('user32', use_last_error=True)

# Input structures identical to the original autofisher.py
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

def send_key_press(key, target_window=None):
    """
    Send a key press using the original autofisher approach
    
    Args:
        key (str): The key to press
        target_window: Window handle to focus
    """
    try:
        # Get virtual key code based on the configured fishing key
        key = key.lower()
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
            print(f"Unknown key: {key}, falling back to 'f'")
            vk_code = 0x46  # Default to F
        
        # Calculate scan code for more reliable key identification
        scan_code = user32.MapVirtualKeyW(vk_code, 0)
        
        # Focus window for reliable key press detection
        if target_window:
            force_focus_window(target_window)
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
        
        return True
        
    except Exception as e:
        print(f"Error with key simulation: {e}")
        return False
        
def send_esc(target_window=None):
    """Send ESC key to the target window - identical to original implementation"""
    try:
        key = 'esc'
        vk_code = 0x1B  # VK_ESCAPE
        scan_code = user32.MapVirtualKeyW(vk_code, 0)
        
        # Focus window for reliable key press detection
        if target_window:
            force_focus_window(target_window)
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
        print(f"Error with ESC key simulation: {e}")
        return False 