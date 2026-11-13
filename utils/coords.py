"""
Screen coordinate helpers — physical pixels for Win32/MSS, client-area relative tracking.
"""
from typing import Optional, Tuple

try:
    import win32gui
except ImportError:
    win32gui = None

# (left, top, right, bottom) in physical screen pixels
ScreenRect = Tuple[int, int, int, int]
# offset within game client area
ClientOffset = Tuple[int, int]


def get_client_area_screen_rect(hwnd) -> Optional[ScreenRect]:
    """Game client area in physical screen coordinates (for MSS capture)."""
    if not hwnd or not win32gui or not win32gui.IsWindow(hwnd):
        return None
    try:
        cl, ct, cr, cb = win32gui.GetClientRect(hwnd)
        left, top = win32gui.ClientToScreen(hwnd, (cl, ct))
        right, bottom = win32gui.ClientToScreen(hwnd, (cr, cb))
        return int(left), int(top), int(right), int(bottom)
    except Exception:
        return None


def get_cursor_physical() -> Tuple[int, int]:
    """Current cursor position in physical screen pixels."""
    try:
        import win32api

        return win32api.GetCursorPos()
    except Exception:
        from PyQt6.QtGui import QCursor

        p = QCursor.pos()
        return p.x(), p.y()


def clamp_region_to_rect(
    left: int, top: int, width: int, height: int, bounds: ScreenRect
) -> ScreenRect:
    """Clamp a width×height box centered near (left,top) inside bounds."""
    b_left, b_top, b_right, b_bottom = bounds
    max_w = b_right - b_left
    max_h = b_bottom - b_top
    w = min(width, max_w)
    h = min(height, max_h)
    left = max(b_left, min(left, b_right - w))
    top = max(b_top, min(top, b_bottom - h))
    return left, top, left + w, top + h


def region_from_client_offset(
    hwnd, rel_left: int, rel_top: int, width: int, height: int
) -> Optional[ScreenRect]:
    """Rebuild absolute MSS region from client-relative offset."""
    client = get_client_area_screen_rect(hwnd)
    if not client:
        return None
    c_left, c_top, _, _ = client
    left = c_left + rel_left
    top = c_top + rel_top
    return left, top, left + width, top + height


def offset_in_client(hwnd, abs_left: int, abs_top: int) -> Optional[ClientOffset]:
    """Physical screen point → offset from client top-left."""
    client = get_client_area_screen_rect(hwnd)
    if not client:
        return None
    return abs_left - client[0], abs_top - client[1]
