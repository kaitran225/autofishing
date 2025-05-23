"""
Windows implementation for screen capturing and region selection.
"""
import cv2
import numpy as np
import mss
import time
import os

class WindowsScreenCapturer:
    def __init__(self):
        self.exclamation_x = 960  # Center of screen horizontally for Windows
        self.exclamation_y = 540  # Center of screen vertically for Windows
        self.exclamation_width = 400  # Width of detection area
        self.exclamation_height = 300  # Height of detection area
        
        self.shadow_x = 960  # Center of screen horizontally for Windows
        self.shadow_y = 700  # Lower part of screen for fish shadows
        self.shadow_width = 600  # Width of detection area
        self.shadow_height = 200  # Height of detection area
        
        # For debugging
        self.debug_mode = False
        self.capture_dir = "captured_regions"
        if self.debug_mode:
            os.makedirs(self.capture_dir, exist_ok=True)
        
        # Initialize mss for screen capture
        self.sct = mss.mss()
    
    def save_debug_image(self, img, prefix="region"):
        """Save an image for debugging - only if debug mode is enabled"""
        if not self.debug_mode:
            return None
            
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{self.capture_dir}/{prefix}_{timestamp}.png"
        cv2.imwrite(filename, img)
        print(f"Saved debug image: {filename}")
        return filename
    
    def capture_screen_region(self, region):
        """Capture a specific region of the screen
        
        Args:
            region: Dict with keys 'left', 'top', 'width', 'height'
            
        Returns:
            numpy array: Captured image in BGR format
        """
        monitor = {
            "top": region["top"],
            "left": region["left"],
            "width": region["width"],
            "height": region["height"]
        }
        
        try:
            # Capture screen region
            screenshot = np.array(self.sct.grab(monitor))
            # Convert from BGRA to BGR
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            
            if self.debug_mode:
                self.save_debug_image(screenshot, "capture")
                
            return screenshot
        except Exception as e:
            print(f"Error capturing screen region: {e}")
            return None
    
    def get_screen_size(self):
        """Get the screen size of the primary monitor
        
        Returns:
            tuple: (width, height) of the primary monitor
        """
        monitor = self.sct.monitors[0]  # Primary monitor
        return monitor["width"], monitor["height"]
    
    def get_default_regions(self):
        """Get the default detection regions
        
        Returns:
            tuple: (exclamation_region, shadow_region) dicts
        """
        exclamation_region = {
            "top": self.exclamation_y - self.exclamation_height//2,
            "left": self.exclamation_x - self.exclamation_width//2,
            "width": self.exclamation_width,
            "height": self.exclamation_height
        }
        
        shadow_region = {
            "top": self.shadow_y - self.shadow_height//2,
            "left": self.shadow_x - self.shadow_width//2,
            "width": self.shadow_width,
            "height": self.shadow_height
        }
        
        return exclamation_region, shadow_region
    
    def interactive_region_setup(self):
        """Interactive setup to allow user to position detection regions"""
        print("\nInteractive Region Setup (Windows)")
        print("------------------------")
        print("This will help you position the detection regions correctly.")
        print("1. A window will open showing your screen")
        print("2. Click to position Exclamation Mark region")
        print("3. Then click to position Fish Shadow/Bait region")
        
        # Capture full screen as reference
        monitor = self.sct.monitors[0]  # Get primary monitor
        screen = np.array(self.sct.grab(monitor))
        screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
        
        # Resize for display if needed
        scale = 0.5
        screen = cv2.resize(screen, (0, 0), fx=scale, fy=scale)
        
        # Create a window and set mouse callback
        cv2.namedWindow("Region Setup")
        clicks = []
        
        def mouse_callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                clicks.append((x, y))
                
                if len(clicks) == 1:
                    # First click for Exclamation Mark region
                    self.exclamation_x = int(x / scale)
                    self.exclamation_y = int(y / scale)
                    print(f"Exclamation region center set to: ({self.exclamation_x}, {self.exclamation_y})")
                    
                    # Draw rectangle for exclamation region
                    cv2.rectangle(screen, 
                                (x - int(self.exclamation_width*scale/2), y - int(self.exclamation_height*scale/2)),
                                (x + int(self.exclamation_width*scale/2), y + int(self.exclamation_height*scale/2)),
                                (0, 255, 0), 2)
                    cv2.putText(screen, "Exclamation", (x - 40, y - int(self.exclamation_height*scale/2) - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    
                elif len(clicks) == 2:
                    # Second click for Fish Shadow region
                    self.shadow_x = int(x / scale)
                    self.shadow_y = int(y / scale)
                    print(f"Shadow region center set to: ({self.shadow_x}, {self.shadow_y})")
                    
                    # Draw rectangle for shadow region
                    cv2.rectangle(screen, 
                                (x - int(self.shadow_width*scale/2), y - int(self.shadow_height*scale/2)),
                                (x + int(self.shadow_width*scale/2), y + int(self.shadow_height*scale/2)),
                                (0, 0, 255), 2)
                    cv2.putText(screen, "Fish Shadow/Bait", (x - 60, y - int(self.shadow_height*scale/2) - 10),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                    
                    print("Regions set! Press any key to continue...")
        
        cv2.setMouseCallback("Region Setup", mouse_callback)
        
        # Add instructions to the image
        instructions = "Click to set Exclamation Mark region, then click to set Fish Shadow/Bait region"
        cv2.putText(screen, instructions, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # Wait for clicks
        while len(clicks) < 2:
            cv2.imshow("Region Setup", screen)
            if cv2.waitKey(100) != -1:
                break
        
        # Wait for key press to close
        cv2.imshow("Region Setup", screen)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        # Save the final regions image if in debug mode
        if self.debug_mode:
            self.save_debug_image(screen, "region_setup")
        
        # Create region monitors for usage
        exclamation_monitor = {
            "top": self.exclamation_y - self.exclamation_height//2,
            "left": self.exclamation_x - self.exclamation_width//2,
            "width": self.exclamation_width,
            "height": self.exclamation_height
        }
        
        shadow_monitor = {
            "top": self.shadow_y - self.shadow_height//2,
            "left": self.shadow_x - self.shadow_width//2,
            "width": self.shadow_width,
            "height": self.shadow_height
        }
        
        print("\nRegions set successfully:")
        print(f"Exclamation region: ({self.exclamation_x}, {self.exclamation_y}) - {self.exclamation_width}x{self.exclamation_height}")
        print(f"Shadow/Bait region: ({self.shadow_x}, {self.shadow_y}) - {self.shadow_width}x{self.shadow_height}")
        
        return exclamation_monitor, shadow_monitor 