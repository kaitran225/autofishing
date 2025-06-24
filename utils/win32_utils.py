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
    """Force focus a window using tiered approach - quick methods first, then heavy methods"""
    try:
        # Check if window exists
        if not hwnd or not win32gui.IsWindow(hwnd):
            print("Invalid window handle")
            return False
            
        # Method 1: Quick focus attempt using SetForegroundWindow
        current_hwnd = user32.GetForegroundWindow()
        if current_hwnd == hwnd:
            return True  # Already in focus
            
        # Try quick approach first
        result = user32.SetForegroundWindow(hwnd)
        time.sleep(0.05)  # Short delay
        
        # Verify quick focus worked
        if user32.GetForegroundWindow() == hwnd:
            return True
            
        # Method 2: Handle minimized windows
        if win32gui.IsIconic(hwnd):  # If minimized
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.1)
            
        # Method 3: Enhanced focus with thread attachment
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
        
        # Force active window (additional method from prototype)
        user32.SwitchToThisWindow(hwnd, True)
        
        # Detach threads
        user32.AttachThreadInput(current_thread, target_thread, False)
        
        # Method 4: ALT keypress can help with focus (from prototype)
        try:
            import keyboard
            keyboard.press_and_release('alt')
            time.sleep(0.05)
        except ImportError:
            # Fallback if keyboard module not available
            pass
        
        # Method 5: One more foreground window attempt
        user32.SetForegroundWindow(hwnd)
        
        # Final check if focus was achieved
        time.sleep(0.05)  # Short delay to let OS update window state
        focused_hwnd = user32.GetForegroundWindow()
        success = focused_hwnd == hwnd
        
        # Log result for debugging
        if success:
            print(f"Successfully focused window: {win32gui.GetWindowText(hwnd)}")
        else:
            print(f"Failed to focus window: {win32gui.GetWindowText(hwnd)}")
            print(f"Active window is: {win32gui.GetWindowText(focused_hwnd)}")
        
        return success
        
    except Exception as e:
        print(f"Error forcing focus: {e}")
        return False

def focus_window_tiered(hwnd):
    """
    Tiered window focus strategy - try force focus first (reliable), then quick method as backup
    This provides maximum reliability by using the most robust method first
    """
    if not hwnd or not win32gui.IsWindow(hwnd):
        return False
        
    try:
        # Method 1: Try force focus first (most reliable)
        if force_focus_window(hwnd):
            return True
            
        # Method 2: If force focus failed, try quick method as backup
        print("Force focus failed, trying quick focus as backup...")
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.05)
        
        # Verify quick focus
        if user32.GetForegroundWindow() == hwnd:
            print("Quick focus backup succeeded")
            return True
            
        print("Both force focus and quick focus failed")
        return False
        
    except Exception as e:
        print(f"Error in tiered focus: {e}")
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

def find_window_by_pattern(name_patterns, process_names=None):
    """
    Find a window by matching title patterns and optionally process names
    Enhanced version with better flexibility and process checking
    """
    result = [None]
    found_windows = []
    
    def enum_window_callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            window_text = win32gui.GetWindowText(hwnd).lower()
            
            # Skip empty titles and our own autofisher window
            if not window_text or 'autofisher' in window_text:
                return True
            
            # For debugging, store all visible window titles
            if window_text:  # Only include windows with titles
                found_windows.append((hwnd, window_text))
                
            # Check by exact match first - highest priority
            if any(window_text == pattern.lower() for pattern in name_patterns):
                print(f"Found exact window match: '{window_text}' (hwnd: {hwnd})")
                result[0] = hwnd
                return False
                
            # Check by start/end patterns - medium priority
            if any(window_text.startswith(pattern.lower()) or window_text.endswith(pattern.lower()) 
                   for pattern in name_patterns if len(pattern) > 5):  # Only match longer patterns
                print(f"Found partial window match: '{window_text}' (hwnd: {hwnd})")
                # Store but continue looking for better match
                if result[0] is None:
                    result[0] = hwnd
                    
            # Check by contains pattern - lowest priority
            if result[0] is None:
                if any(pattern.lower() in window_text for pattern in name_patterns if len(pattern) > 6):
                    print(f"Found window containing pattern: '{window_text}' (hwnd: {hwnd})")
                    result[0] = hwnd
                    
            # Additional process name checking if provided
            if process_names and result[0] is None:
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    process = psutil.Process(pid)
                    process_name = process.name().lower()
                    
                    if any(pname.lower() in process_name for pname in process_names):
                        print(f"Found window by process name: '{window_text}' (process: {process_name}, hwnd: {hwnd})")
                        result[0] = hwnd
                        return False
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
                    
        return True
        
    win32gui.EnumWindows(enum_window_callback, None)
    
    # If no matching window found, print all visible windows for debugging
    if result[0] is None:
        print(f"No matching window found for patterns: {name_patterns}")
        if process_names:
            print(f"Process names searched: {process_names}")
        print("Visible windows:")
        for hwnd, title in found_windows:
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid)
                process_name = process.name()
                print(f"- {hwnd}: '{title}' (process: {process_name})")
            except:
                print(f"- {hwnd}: '{title}'")
    else:
        # Check if the window is still valid
        try:
            if win32gui.IsWindow(result[0]):
                # Get window title for verification
                window_text = win32gui.GetWindowText(result[0])
                print(f"Selected window: '{window_text}' (hwnd: {result[0]})")
            else:
                print(f"Window {result[0]} is no longer valid")
                result[0] = None
        except Exception as e:
            print(f"Error verifying window: {e}")
            result[0] = None
    
    return result[0]

def is_fullscreen_app_active():
    """Check if any fullscreen application is active (except our app) - enhanced version"""
    try:
        # Get foreground window
        foreground_hwnd = user32.GetForegroundWindow()
        if not foreground_hwnd:
            return False
            
        # Skip if it's our window
        window_text = win32gui.GetWindowText(foreground_hwnd).lower()
        if 'autofisher' in window_text:
            return False
            
        # Get monitor info
        monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromWindow(foreground_hwnd))
        monitor_rect = monitor_info.get('Monitor')
        
        if not monitor_rect:
            return False
            
        # Get window rect
        window_rect = win32gui.GetWindowRect(foreground_hwnd)
        
        # Check if window covers the entire monitor
        is_fullscreen = (
            window_rect[0] <= monitor_rect[0] and
            window_rect[1] <= monitor_rect[1] and
            window_rect[2] >= monitor_rect[2] and
            window_rect[3] >= monitor_rect[3]
        )
        
        # Additional check for borderless fullscreen (from prototype)
        style = win32gui.GetWindowLong(foreground_hwnd, win32con.GWL_STYLE)
        has_no_border = not (style & win32con.WS_BORDER or style & win32con.WS_DLGFRAME)
        
        # Get window title for logging (from prototype)
        if is_fullscreen and has_no_border:
            try:
                window_title = win32gui.GetWindowText(foreground_hwnd)
                if window_title:
                    print(f"Detected fullscreen app: {window_title[:30]}")
            except:
                pass
                
        return is_fullscreen and has_no_border
    except Exception as e:
        print(f"Error checking fullscreen status: {e}")
        return False

def find_window_by_title_substring(title_substrings):
    """Find a window whose title contains any of the given substrings (case-insensitive)."""
    matches = []
    def enum_handler(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            window_text = win32gui.GetWindowText(hwnd)
            for substr in title_substrings:
                if substr.lower() in window_text.lower():
                    matches.append(hwnd)
                    break
    win32gui.EnumWindows(enum_handler, None)
    return matches[0] if matches else None 