"""
Windows utilities — ported from the working .prototype/autofisher.py
"""
import ctypes
import time
import keyboard
import win32gui
import win32con
import win32process
import win32api
import psutil

from utils.constants import GAME_WINDOW_NAMES, EXCLUDED_WINDOW_TITLES

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("ii", INPUT_UNION),
    ]


def force_focus_window(hwnd):
    """Force focus on a window (prototype implementation)."""
    try:
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.1)

        current_thread = kernel32.GetCurrentThreadId()
        target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)

        user32.AttachThreadInput(current_thread, target_thread, True)

        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )
        time.sleep(0.05)
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_NOTOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW,
        )

        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        user32.BringWindowToTop(hwnd)
        user32.SwitchToThisWindow(hwnd, True)

        user32.AttachThreadInput(current_thread, target_thread, False)

        keyboard.press_and_release("alt")
        time.sleep(0.05)
        user32.SetForegroundWindow(hwnd)

        return user32.GetForegroundWindow() == hwnd
    except Exception as e:
        print(f"Error forcing focus: {e}")
        return False


def find_play_together_window():
    """
    Find Play Together by process PID + EnumWindows (prototype logic).
    Returns (hwnd, pid) or (None, None).
    """
    name_variations = [n.lower() for n in GAME_WINDOW_NAMES]
    excluded = [e.lower() for e in EXCLUDED_WINDOW_TITLES]

    play_together_pid = None
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            process_name = proc.info["name"].lower()
            if any(v in process_name for v in name_variations):
                play_together_pid = proc.info["pid"]
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    found_hwnd = [None]

    def enum_window_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True

        window_text = win32gui.GetWindowText(hwnd).lower()
        if any(ex in window_text for ex in excluded):
            return True

        try:
            _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
            if play_together_pid and window_pid == play_together_pid:
                found_hwnd[0] = hwnd
                return False
        except Exception:
            pass

        if any(
            variation == window_text
            or window_text.startswith(f"{variation} ")
            or window_text.endswith(f" {variation}")
            or f" {variation} " in window_text
            for variation in name_variations
        ):
            found_hwnd[0] = hwnd
            return False

        return True

    try:
        win32gui.EnumWindows(enum_window_callback, None)
    except Exception as e:
        print(f"EnumWindows failed: {e}")
        return None, play_together_pid

    return found_hwnd[0], play_together_pid


def find_window_by_pattern(name_patterns=None):
    """Compatibility wrapper — returns HWND only."""
    hwnd, _ = find_play_together_window()
    return hwnd


def is_fullscreen_app_active(play_together_hwnd=None, exclude_hwnds=None):
    """Check if a borderless fullscreen app (not the game) is in the foreground."""
    exclude_hwnds = exclude_hwnds or []
    try:
        foreground_hwnd = user32.GetForegroundWindow()
        if not foreground_hwnd:
            return False

        if play_together_hwnd and foreground_hwnd == play_together_hwnd:
            return False

        if foreground_hwnd in exclude_hwnds:
            return False

        monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromWindow(foreground_hwnd))
        monitor_rect = monitor_info["Monitor"]
        window_rect = win32gui.GetWindowRect(foreground_hwnd)

        is_fullscreen = (
            window_rect[0] <= monitor_rect[0]
            and window_rect[1] <= monitor_rect[1]
            and window_rect[2] >= monitor_rect[2]
            and window_rect[3] >= monitor_rect[3]
        )

        style = win32gui.GetWindowLong(foreground_hwnd, win32con.GWL_STYLE)
        has_no_border = not (style & win32con.WS_BORDER or style & win32con.WS_DLGFRAME)

        return is_fullscreen and has_no_border
    except Exception:
        return False
