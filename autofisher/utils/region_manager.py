"""
Region manager utility for capturing and managing screen regions.
"""
import cv2
import numpy as np
import platform
from autofisher.os_adapters import ScreenCapturer


class RegionManager:
    """Manages screen regions for fishing detection."""
    
    def __init__(self):
        """Initialize the region manager."""
        # Screen capturer
        self.screen_capturer = ScreenCapturer()
        
        # Region parameters - default values based on common screen setup
        screen_width, screen_height = self.screen_capturer.get_screen_size()
        
        # Default exclamation region (centered near top half)
        self.exclamation_region = {
            "left": screen_width // 2 - 200,
            "top": screen_height // 2 - 200,
            "width": 400,
            "height": 300
        }
        
        # Default shadow region (centered in bottom half)
        self.shadow_region = {
            "left": screen_width // 2 - 300,
            "top": screen_height // 2 + 100,
            "width": 600,
            "height": 200
        }
        
        # Reference frames
        self.exclamation_reference = None
        self.shadow_reference = None
    
    def get_exclamation_region(self):
        """Get the exclamation mark detection region.
        
        Returns:
            Dictionary with region parameters
        """
        return self.exclamation_region
    
    def get_shadow_region(self):
        """Get the shadow detection region.
        
        Returns:
            Dictionary with region parameters
        """
        return self.shadow_region
    
    def set_regions(self, exclamation_region, shadow_region):
        """Set both detection regions.
        
        Args:
            exclamation_region: Dictionary with left, top, width, height
            shadow_region: Dictionary with left, top, width, height
        """
        self.exclamation_region = exclamation_region
        self.shadow_region = shadow_region
        
        # Clear reference frames when regions change
        self.clear_reference_frames()
    
    def get_exclamation_reference(self):
        """Get the exclamation reference frame.
        
        Returns:
            Numpy array with reference frame or None
        """
        return self.exclamation_reference
    
    def get_shadow_reference(self):
        """Get the shadow reference frame.
        
        Returns:
            Numpy array with reference frame or None
        """
        return self.shadow_reference
    
    def has_reference_frames(self):
        """Check if reference frames are available.
        
        Returns:
            Boolean indicating if reference frames exist
        """
        return self.exclamation_reference is not None and self.shadow_reference is not None
    
    def clear_reference_frames(self):
        """Clear reference frames."""
        self.exclamation_reference = None
        self.shadow_reference = None
    
    def capture_reference_frames(self):
        """Capture reference frames for both regions.
        
        Returns:
            Boolean indicating success or failure
        """
        # Capture frames
        self.exclamation_reference = self.screen_capturer.capture_region(self.exclamation_region)
        self.shadow_reference = self.screen_capturer.capture_region(self.shadow_region)
        
        # Verify that both frames were captured successfully
        if self.exclamation_reference is not None and self.shadow_reference is not None:
            return True
        else:
            # Reset if capture failed
            self.clear_reference_frames()
            return False
    
    def interactive_region_setup(self):
        """Run interactive region setup.
        
        Returns:
            Boolean indicating success or failure
        """
        # Initial frames for both regions
        screen_width, screen_height = self.screen_capturer.get_screen_size()
        
        # Create window and instructions
        window_name = "Region Setup"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 800, 600)
        
        # Capture full screen for setup
        full_screen_region = {
            "left": 0,
            "top": 0,
            "width": screen_width,
            "height": screen_height
        }
        
        # Select exclamation region first
        exclamation_instructions = np.zeros((200, 800, 3), dtype=np.uint8)
        cv2.putText(exclamation_instructions, "SELECT EXCLAMATION MARK REGION", (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(exclamation_instructions, "Draw rectangle around the area where '!' appears", (50, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        cv2.putText(exclamation_instructions, "Press ENTER when done, ESC to cancel", (50, 150), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        
        cv2.imshow(window_name, exclamation_instructions)
        cv2.waitKey(2000)  # Show instructions for 2 seconds
        
        # Capture full screen
        full_frame = self.screen_capturer.capture_region(full_screen_region)
        if full_frame is None:
            cv2.destroyAllWindows()
            return False
        
        # Let user select exclamation region
        exclamation_rect = cv2.selectROI(window_name, full_frame, fromCenter=False, showCrosshair=True)
        if sum(exclamation_rect) == 0:  # User cancelled
            cv2.destroyAllWindows()
            return False
        
        # Update exclamation region
        self.exclamation_region = {
            "left": exclamation_rect[0],
            "top": exclamation_rect[1],
            "width": exclamation_rect[2],
            "height": exclamation_rect[3]
        }
        
        # Select shadow region next
        shadow_instructions = np.zeros((200, 800, 3), dtype=np.uint8)
        cv2.putText(shadow_instructions, "SELECT SHADOW/BAIT REGION", (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(shadow_instructions, "Draw rectangle around the area where fish shadows appear", (50, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        cv2.putText(shadow_instructions, "Press ENTER when done, ESC to cancel", (50, 150), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        
        cv2.imshow(window_name, shadow_instructions)
        cv2.waitKey(2000)  # Show instructions for 2 seconds
        
        # Use the same full frame
        shadow_rect = cv2.selectROI(window_name, full_frame, fromCenter=False, showCrosshair=True)
        if sum(shadow_rect) == 0:  # User cancelled
            cv2.destroyAllWindows()
            return False
        
        # Update shadow region
        self.shadow_region = {
            "left": shadow_rect[0],
            "top": shadow_rect[1],
            "width": shadow_rect[2],
            "height": shadow_rect[3]
        }
        
        # Clean up
        cv2.destroyAllWindows()
        
        # Clear reference frames
        self.clear_reference_frames()
        
        return True 