"""
Dummy implementations for unsupported platforms.
These implementations provide fallback functionality that warns users about unsupported platforms.
"""

from autofisher.os_adapters.dummy.key_sender import DummyKeySender
from autofisher.os_adapters.dummy.window_focus import DummyWindowFocus
from autofisher.os_adapters.dummy.screen_capturer import DummyScreenCapturer

__all__ = ['DummyKeySender', 'DummyWindowFocus', 'DummyScreenCapturer'] 