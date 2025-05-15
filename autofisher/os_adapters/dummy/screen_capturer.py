"""
Dummy screen capturer implementation for unsupported platforms.
"""
import numpy as np

class DummyScreenCapturer:
    def __init__(self):
        self.exclamation_width = 400
        self.exclamation_height = 300
        self.shadow_width = 600
        self.shadow_height = 200
        
        print("WARNING: Using dummy screen capturer implementation")
        print("This platform is not supported for screen capturing")
        print("Autofisher only fully supports Windows and macOS")
    
    def capture_screen_region(self, region):
        """Dummy implementation of capture_screen_region"""
        print(f"Dummy: Would capture screen region {region} if platform was supported")
        # Return a black image of the requested dimensions
        return np.zeros((region["height"], region["width"], 3), dtype=np.uint8)
    
    def get_screen_size(self):
        """Dummy implementation of get_screen_size"""
        print("Dummy: Would get screen size if platform was supported")
        return 1920, 1080  # Return a common screen resolution
    
    def get_default_regions(self):
        """Dummy implementation of get_default_regions"""
        print("Dummy: Would get default regions if platform was supported")
        # Return dummy regions in the center of the screen
        exclamation_region = {
            "top": 340,  # Roughly center of screen
            "left": 760,  # Roughly center of screen
            "width": self.exclamation_width,
            "height": self.exclamation_height
        }
        
        shadow_region = {
            "top": 600,  # Lower part of screen
            "left": 660,  # Roughly center of screen
            "width": self.shadow_width,
            "height": self.shadow_height
        }
        
        return exclamation_region, shadow_region
    
    def interactive_region_setup(self):
        """Dummy implementation of interactive_region_setup"""
        print("Dummy: Interactive region setup is not supported on this platform")
        return self.get_default_regions() 