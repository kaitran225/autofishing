"""
OS-specific adapters for screen capture, key sending, and window focus.
"""
import platform

# Import and export the right classes based on platform
system = platform.system()

if system == "Windows":
    from autofisher.os_adapters.windows import (
        WindowsScreenCapturer,
        WindowsKeySender,
        WindowsWindowFocus
    )
    
    # Export as platform-neutral names
    ScreenCapturer = WindowsScreenCapturer
    KeySender = WindowsKeySender
    WindowFocus = WindowsWindowFocus
    
elif system == "Darwin":  # macOS
    from autofisher.os_adapters.macos import (
        MacOSScreenCapturer,
        MacOSKeySender,
        MacOSWindowFocus
    )
    
    # Export as platform-neutral names
    ScreenCapturer = MacOSScreenCapturer
    KeySender = MacOSKeySender
    WindowFocus = MacOSWindowFocus
    
else:
    # Fallback to dummy implementations
    from autofisher.os_adapters.dummy import (
        DummyScreenCapturer as ScreenCapturer,
        DummyKeySender as KeySender,
        DummyWindowFocus as WindowFocus
    )
    
    print(f"Warning: Unsupported OS '{system}'. Using dummy implementations.") 