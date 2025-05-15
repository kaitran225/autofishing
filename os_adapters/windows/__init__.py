"""
Windows-specific adapters for screen capture, key sending, and window focus.
"""

from autofisher.os_adapters.windows.key_sender import WindowsKeySender
from autofisher.os_adapters.windows.window_focus import WindowsWindowFocus
from autofisher.os_adapters.windows.screen_capturer import WindowsScreenCapturer

__all__ = ['WindowsKeySender', 'WindowsWindowFocus', 'WindowsScreenCapturer'] 