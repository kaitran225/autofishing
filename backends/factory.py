"""
Factory for creating the appropriate platform-specific detector
"""
import platform

def create_detector():
    """Create the appropriate detector implementation for the current platform"""
    system = platform.system().lower()
    
    if system == 'darwin':
        from autofisher.backends.mac import MacPixelDetector
        return MacPixelDetector()
    elif system == 'windows':
        from autofisher.backends.windows import WindowsPixelDetector
        return WindowsPixelDetector()
    else:
        raise NotImplementedError(f"Unsupported platform: {platform.system()}") 