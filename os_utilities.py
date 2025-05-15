import platform
import os
import cv2
import numpy as np
import mss
import time

class OSUtilities:
    def __init__(self):
        # Detect OS
        self.os_type = platform.system()
        print(f"Detected OS: {self.os_type}")
        
        # Import OS-specific modules on initialization
        if self.os_type == "Windows":
            try:
                import win32gui
                import win32con
                import win32process
                import win32api
                import ctypes
                self.win32gui = win32gui
                self.win32con = win32con
                self.win32process = win32process
                self.win32api = win32api
                self.ctypes = ctypes
                self.user32 = ctypes.WinDLL('user32', use_last_error=True)
                self.kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
                self.win_modules_loaded = True
            except ImportError:
                print("Warning: Windows modules could not be imported")
                self.win_modules_loaded = False
        elif self.os_type == "Darwin":  # macOS
            try:
                # Import any macOS-specific modules here if needed
                self.mac_modules_loaded = True
            except ImportError:
                print("Warning: macOS modules could not be imported")
                self.mac_modules_loaded = False
    
    def get_default_regions(self):
        """Get default region parameters based on OS"""
        if self.os_type == "Windows":
            # Windows region parameters
            exclamation_region = {
                "x": 960,  # Center of screen horizontally for Windows
                "y": 540,  # Center of screen vertically for Windows
                "width": 400,  # Width of detection area
                "height": 300  # Height of detection area
            }
            
            shadow_region = {
                "x": 960,  # Center of screen horizontally for Windows
                "y": 700,  # Lower part of screen for fish shadows
                "width": 600,  # Width of detection area
                "height": 200  # Height of detection area
            }
        elif self.os_type == "Darwin":  # macOS
            # macOS region parameters
            exclamation_region = {
                "x": 960,  # Center of screen horizontally for macOS
                "y": 500,  # Center of screen vertically for macOS
                "width": 400,  # Width of detection area
                "height": 300  # Height of detection area
            }
            
            shadow_region = {
                "x": 960,  # Center of screen horizontally for macOS
                "y": 650,  # Lower part of screen for fish shadows
                "width": 600,  # Width of detection area
                "height": 200  # Height of detection area
            }
        else:  # Linux or other
            # Default parameters
            exclamation_region = {
                "x": 960,
                "y": 540,
                "width": 400,
                "height": 300
            }
            
            shadow_region = {
                "x": 960,
                "y": 700,
                "width": 600,
                "height": 200
            }
        
        return exclamation_region, shadow_region
    
    def create_monitor_dict(self, region):
        """Create an mss monitor dictionary from region parameters"""
        monitor = {
            "top": region["y"] - region["height"]//2,
            "left": region["x"] - region["width"]//2,
            "width": region["width"],
            "height": region["height"]
        }
        return monitor
    
    def capture_screen(self, sct, monitor):
        """Capture screen region with error handling"""
        try:
            # Use the provided mss context
            sct_img = sct.grab(monitor)
            
            # Use numpy array with zero copy when possible for speed
            img = np.array(sct_img)
            
            # Convert BGRA to BGR (mss returns BGRA)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            print(f"Error capturing screen: {e}")
            return None
    
    def get_game_window_title(self):
        """Get the game window title based on OS"""
        return "PLAY TOGETHER"
    
    def is_windows(self):
        """Check if the OS is Windows"""
        return self.os_type == "Windows"
    
    def is_macos(self):
        """Check if the OS is macOS"""
        return self.os_type == "Darwin"
    
    def get_os_name(self):
        """Get a user-friendly OS name"""
        if self.os_type == "Windows":
            return "Windows"
        elif self.os_type == "Darwin":
            return "macOS"
        elif self.os_type == "Linux":
            return "Linux"
        else:
            return self.os_type

if __name__ == "__main__":
    # Test the OS utilities
    os_utils = OSUtilities()
    print(f"OS detected: {os_utils.get_os_name()}")
    exclamation_region, shadow_region = os_utils.get_default_regions()
    print(f"Default exclamation region: {exclamation_region}")
    print(f"Default shadow region: {shadow_region}")
    
    # Create monitor dicts
    exclamation_monitor = os_utils.create_monitor_dict(exclamation_region)
    shadow_monitor = os_utils.create_monitor_dict(shadow_region)
    print(f"Exclamation monitor: {exclamation_monitor}")
    print(f"Shadow monitor: {shadow_monitor}")
    
    # Test screen capture
    with mss.mss() as sct:
        print("Capturing screen region...")
        img = os_utils.capture_screen(sct, exclamation_monitor)
        if img is not None:
            print(f"Capture successful. Image shape: {img.shape}")
        else:
            print("Capture failed.") 