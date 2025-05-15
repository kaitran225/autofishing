"""
macOS-specific adapters for screen capture, key sending, and window focus.
"""

from autofisher.os_adapters.macos.key_sender import MacOSKeySender
from autofisher.os_adapters.macos.window_focus import MacOSWindowFocus
from autofisher.os_adapters.macos.screen_capturer import MacOSScreenCapturer

__all__ = ['MacOSKeySender', 'MacOSWindowFocus', 'MacOSScreenCapturer'] 