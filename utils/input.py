"""
Input utilities for keyboard and mouse control
"""
import time
import keyboard
from .win32_utils import direct_key_press, force_focus_window

def send_key_press(key, target_window=None):
    """
    Send a key press to a target window, using multiple methods to ensure reliability
    
    Args:
        key (str): The key to press (single character or special key name)
        target_window (int, optional): Handle to target window. If provided, will focus first
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Focus window if provided
        if target_window:
            force_focus_window(target_window)
            time.sleep(0.05)  # Give focus time to take effect
        
        # Method 1: Use keyboard library
        keyboard.press_and_release(key)
        time.sleep(0.05)
        
        # Method 2: Use direct_key_press for single character keys
        if len(key) == 1:
            direct_key_press(key)
            
        return True
    except Exception as e:
        print(f"Error sending key {key}: {e}")
        return False
        
def send_esc(target_window=None):
    """Send ESC key to the target window"""
    try:
        # Focus window if provided
        if target_window:
            force_focus_window(target_window)
            time.sleep(0.05)
            
        # Send ESC key using multiple methods
        # Method 1: keyboard library
        keyboard.press_and_release('esc')
        time.sleep(0.05)
        
        # Method 2: Virtual key code
        from .win32_utils import win32api, win32con
        vk_code = 0x1B  # VK_ESCAPE
        win32api.keybd_event(vk_code, 0, 0, 0)  # key down
        time.sleep(0.05)
        win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)  # key up
        
        # Method 3: Send to window if provided
        if target_window:
            from .win32_utils import win32gui
            win32gui.PostMessage(target_window, win32con.WM_KEYDOWN, vk_code, 0)
            time.sleep(0.05)
            win32gui.PostMessage(target_window, win32con.WM_KEYUP, vk_code, 0)
            
        return True
    except Exception as e:
        print(f"Error sending ESC key: {e}")
        return False 