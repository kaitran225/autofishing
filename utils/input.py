"""
Keyboard input — prototype send_fishing_key / send_esc behavior.
"""
import time
import ctypes
import keyboard
import win32gui
import win32con

from utils.win32_utils import (
    INPUT,
    INPUT_KEYBOARD,
    KEYEVENTF_KEYUP,
    user32,
    force_focus_window,
    is_fullscreen_app_active,
)


def _vk_for_key(key):
    key = key.lower()
    if key == "f":
        return 0x46
    if key == "e":
        return 0x45
    if key == "space":
        return 0x20
    if len(key) == 1:
        return ord(key.upper())
    return 0x46


def send_key_press(key, target_window=None, respect_fullscreen=True, exclude_hwnds=None):
    """Press fishing/action key using prototype SendInput + keyboard fallback."""
    try:
        key = key.lower()
        vk_code = _vk_for_key(key)
        scan_code = user32.MapVirtualKeyW(vk_code, 0)

        if respect_fullscreen and is_fullscreen_app_active(
            play_together_hwnd=target_window, exclude_hwnds=exclude_hwnds or []
        ):
            if target_window:
                try:
                    win32gui.PostMessage(
                        target_window, win32con.WM_CHAR, ord(key.lower()), 0
                    )
                    return True
                except Exception:
                    return False
            return False

        if target_window and user32.GetForegroundWindow() != target_window:
            force_focus_window(target_window)
            time.sleep(0.05)

        kb_input = INPUT()
        kb_input.type = INPUT_KEYBOARD
        kb_input.ii.ki.wVk = vk_code
        kb_input.ii.ki.wScan = scan_code
        kb_input.ii.ki.dwFlags = 0
        kb_input.ii.ki.time = 0
        kb_input.ii.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

        user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
        time.sleep(0.01)
        kb_input.ii.ki.dwFlags = KEYEVENTF_KEYUP
        user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))

        keyboard.press_and_release(key)
        return True
    except Exception as e:
        print(f"Error with key simulation: {e}")
        return False


def send_esc(target_window=None, respect_fullscreen=True, exclude_hwnds=None):
    """Press ESC using prototype behavior."""
    try:
        vk_code = 0x1B
        scan_code = user32.MapVirtualKeyW(vk_code, 0)

        if respect_fullscreen and is_fullscreen_app_active(
            play_together_hwnd=target_window, exclude_hwnds=exclude_hwnds or []
        ):
            if target_window:
                try:
                    win32gui.PostMessage(
                        target_window, win32con.WM_SYSCOMMAND, win32con.SC_CLOSE, 0
                    )
                    return True
                except Exception:
                    return False
            return False

        if target_window and user32.GetForegroundWindow() != target_window:
            force_focus_window(target_window)
            time.sleep(0.05)

        kb_input = INPUT()
        kb_input.type = INPUT_KEYBOARD
        kb_input.ii.ki.wVk = vk_code
        kb_input.ii.ki.wScan = scan_code
        kb_input.ii.ki.dwFlags = 0
        kb_input.ii.ki.time = 0
        kb_input.ii.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

        user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
        time.sleep(0.01)
        kb_input.ii.ki.dwFlags = KEYEVENTF_KEYUP
        user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))

        keyboard.press_and_release("esc")
        return True
    except Exception as e:
        print(f"Error with ESC key simulation: {e}")
        return False
