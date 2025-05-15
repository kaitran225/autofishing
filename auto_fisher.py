import cv2
import numpy as np
import pyautogui
import time
import mss
import os
import platform
import datetime
import threading

class AutoFisher:
    def __init__(self):
        # Detect OS
        self.os_type = platform.system()
        print(f"Detected OS: {self.os_type}")
        
        # Set up OS-specific parameters
        if self.os_type == "Windows":
            # Windows region parameters
            self.exclamation_x = 960  # Center of screen horizontally for Windows
            self.exclamation_y = 540  # Center of screen vertically for Windows
            self.exclamation_width = 400  # Width of detection area
            self.exclamation_height = 300  # Height of detection area
            
            # Fish shadow/bouncy bait region
            self.shadow_x = 960  # Center of screen horizontally for Windows
            self.shadow_y = 700  # Lower part of screen for fish shadows
            self.shadow_width = 600  # Width of detection area
            self.shadow_height = 200  # Height of detection area
        elif self.os_type == "Darwin":  # macOS
            # macOS region parameters (may need adjustment for Retina displays)
            self.exclamation_x = 960  # Center of screen horizontally for macOS
            self.exclamation_y = 500  # Center of screen vertically for macOS
            self.exclamation_width = 400  # Width of detection area
            self.exclamation_height = 300  # Height of detection area
            
            # Fish shadow/bouncy bait region
            self.shadow_x = 960  # Center of screen horizontally for macOS
            self.shadow_y = 650  # Lower part of screen for fish shadows
            self.shadow_width = 600  # Width of detection area
            self.shadow_height = 200  # Height of detection area
        else:  # Linux or other
            # Default parameters
            self.exclamation_x = 960
            self.exclamation_y = 540
            self.exclamation_width = 400
            self.exclamation_height = 300
            
            # Fish shadow/bouncy bait region
            self.shadow_x = 960
            self.shadow_y = 700
            self.shadow_width = 600
            self.shadow_height = 200
        
        # Detection parameters
        self.exclamation_threshold = 30  # Pixel change threshold for exclamation
        self.shadow_threshold = 20  # Shadow detection sensitivity
        self.bait_threshold = 25  # Bouncy bait detection sensitivity
        
        # Size parameters
        self.min_exclamation_area = 100
        self.max_exclamation_area = 800
        self.min_shadow_area = 500
        self.max_shadow_area = 5000
        
        # Last frames for comparison
        self.last_exclamation_frame = None
        self.last_shadow_frame = None
        
        # Flag to control fishing loop
        self.is_running = False
        
        # Create capture directory
        self.capture_dir = "captured_regions"
        os.makedirs(self.capture_dir, exist_ok=True)
        
        # Initialize screen capture
        self.sct = mss.mss()
        
        # Exclamation mark region
        self.exclamation_monitor = {
            "top": self.exclamation_y - self.exclamation_height//2,
            "left": self.exclamation_x - self.exclamation_width//2,
            "width": self.exclamation_width,
            "height": self.exclamation_height
        }
        
        # Fish shadow/bouncy bait region
        self.shadow_monitor = {
            "top": self.shadow_y - self.shadow_height//2,
            "left": self.shadow_x - self.shadow_width//2,
            "width": self.shadow_width,
            "height": self.shadow_height
        }
    
    def capture_screen(self, monitor):
        """Capture the current screen in the specified region"""
        sct_img = self.sct.grab(monitor)
        img = np.array(sct_img)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    
    def save_raw_image(self, img, prefix="region"):
        """Save a raw image to the capture directory"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{self.capture_dir}/{prefix}_{timestamp}.png"
        cv2.imwrite(filename, img)
        print(f"Saved raw image: {filename}")
        return filename
    
    def detect_exclamation_mark(self, frame, last_frame=None):
        """Detect the exclamation mark using frame differencing and contour detection"""
        if last_frame is None:
            return False, frame
        
        # Convert to grayscale
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_last_frame = cv2.cvtColor(last_frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate absolute difference to detect changes
        frame_diff = cv2.absdiff(gray_frame, gray_last_frame)
        
        # Apply threshold to get binary image
        _, thresh = cv2.threshold(frame_diff, self.exclamation_threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours in the binary image
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by area and shape
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_exclamation_area < area < self.max_exclamation_area:
                # Additional verification - check for bright color (exclamation marks are usually bright)
                x, y, w, h = cv2.boundingRect(contour)
                roi = frame[y:y+h, x:x+w]
                
                # Check if there's a bright area that stands out
                hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                v_channel = hsv_roi[:, :, 2]  # Value channel (brightness)
                
                # If the region has high brightness, consider it an exclamation mark
                if np.mean(v_channel) > 160:
                    # Draw rectangle for debugging
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    
                    # Save the detected exclamation mark region
                    roi_filename = self.save_raw_image(roi, "exclamation_region")
                    
                    # Also save the full frame with rectangle
                    self.save_raw_image(frame, "detection_frame_exclamation")
                    
                    return True, frame
        
        return False, frame
    
    def detect_fish_shadow(self, frame, last_frame=None):
        """Detect fish shadows and bouncy bait in water"""
        if last_frame is None:
            return False, frame, "none"
        
        # Convert to grayscale
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_last_frame = cv2.cvtColor(last_frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate absolute difference to detect motion
        frame_diff = cv2.absdiff(gray_frame, gray_last_frame)
        
        # Apply threshold for motion detection
        _, thresh = cv2.threshold(frame_diff, self.shadow_threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours for motion
        motion_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # For fish shadow detection - look for darker regions in the current frame
        blurred = cv2.GaussianBlur(gray_frame, (15, 15), 0)
        _, shadow_thresh = cv2.threshold(blurred, 100, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours of shadow regions
        shadow_contours, _ = cv2.findContours(shadow_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Check for bouncy bait (usually has motion and specific size/shape)
        for contour in motion_contours:
            area = cv2.contourArea(contour)
            if 100 < area < 500:  # Bouncy bait is usually smaller than fish shadows
                x, y, w, h = cv2.boundingRect(contour)
                
                # Check if it's a bouncy motion (ratio of width/height)
                if 0.7 < w/h < 1.3:  # Approximately square/circular shape
                    # Draw rectangle for debugging
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
                    cv2.putText(frame, "Bait", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                    
                    # Save the detected region
                    roi = frame[y:y+h, x:x+w]
                    self.save_raw_image(roi, "bait_region")
                    self.save_raw_image(frame, "detection_frame_bait")
                    
                    return True, frame, "bait"
        
        # Check for fish shadows (usually larger dark areas with some motion)
        for contour in shadow_contours:
            area = cv2.contourArea(contour)
            if self.min_shadow_area < area < self.max_shadow_area:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Calculate average darkness of the region
                roi = gray_frame[y:y+h, x:x+w]
                darkness = 255 - np.mean(roi)
                
                # If it's dark enough to be a shadow
                if darkness > 50:
                    # Draw rectangle for debugging
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                    cv2.putText(frame, "Shadow", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                    
                    # Save the detected region
                    roi = frame[y:y+h, x:x+w]
                    self.save_raw_image(roi, "shadow_region")
                    self.save_raw_image(frame, "detection_frame_shadow")
                    
                    return True, frame, "shadow"
        
        return False, frame, "none"
    
    def reel_in(self):
        """Perform the reel-in action"""
        print("Fish detected! Reeling in...")
        pyautogui.click()  # Click to reel in
        time.sleep(3)  # Wait for reel-in animation to complete
    
    def cast_rod(self):
        """Cast the fishing rod"""
        print("Casting rod...")
        pyautogui.click()  # Click to cast rod
        time.sleep(2)  # Wait for casting animation
    
    def approach_shadow(self):
        """Move towards detected fish shadow"""
        print("Fish shadow detected! Moving bait...")
        # This would ideally move the bait toward the shadow
        # For now just click near the shadow
        pyautogui.click()
    
    def start_fishing(self):
        """Start the auto-fishing loop"""
        self.is_running = True
        print("Auto-fishing started. Press 'q' to stop.")
        
        # Capture initial frames
        last_exclamation_frame = self.capture_screen(self.exclamation_monitor)
        last_shadow_frame = self.capture_screen(self.shadow_monitor)
        
        # Track state
        waiting_for_fish = False
        
        try:
            while self.is_running:
                # Capture both regions
                exclamation_frame = self.capture_screen(self.exclamation_monitor)
                shadow_frame = self.capture_screen(self.shadow_monitor)
                
                # Save raw images periodically (every 10 seconds)
                if int(time.time()) % 10 == 0:
                    self.save_raw_image(exclamation_frame, "raw_exclamation")
                    self.save_raw_image(shadow_frame, "raw_shadow")
                
                # Detect exclamation mark
                exclamation_detected, exclamation_frame = self.detect_exclamation_mark(
                    exclamation_frame, last_exclamation_frame
                )
                
                # Detect fish shadow or bouncy bait
                shadow_detected, shadow_frame, detection_type = self.detect_fish_shadow(
                    shadow_frame, last_shadow_frame
                )
                
                # Update last frames
                last_exclamation_frame = exclamation_frame.copy()
                last_shadow_frame = shadow_frame.copy()
                
                # Logic for fishing
                if exclamation_detected:
                    print("Exclamation mark detected!")
                    self.reel_in()
                    waiting_for_fish = False
                    time.sleep(1)
                    self.cast_rod()
                elif shadow_detected and not waiting_for_fish:
                    if detection_type == "shadow":
                        print("Fish shadow detected!")
                        self.approach_shadow()
                        waiting_for_fish = True
                    elif detection_type == "bait":
                        print("Bouncy bait detected!")
                        # Optional: do something with bouncy bait detection
                
                # Display frames (debugging)
                # Resize for display
                display_exclamation = cv2.resize(exclamation_frame, (400, 300))
                display_shadow = cv2.resize(shadow_frame, (400, 300))
                
                # Combine frames horizontally
                combined_frame = np.hstack((display_exclamation, display_shadow))
                
                # Add OS and region info text
                cv2.putText(combined_frame, f"OS: {self.os_type}", (10, 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(combined_frame, "Exclamation Mark", (10, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(combined_frame, "Fish Shadow/Bait", (410, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                cv2.imshow("Auto-fisher Regions", combined_frame)
                
                # Break on 'q' key
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
                time.sleep(0.05)  # Control loop speed
                
        except KeyboardInterrupt:
            print("Auto-fishing stopped.")
        finally:
            self.stop_fishing()
    
    def stop_fishing(self):
        """Stop the auto-fishing loop"""
        self.is_running = False
        cv2.destroyAllWindows()
        print("Auto-fishing stopped.")
    
    def calibrate(self):
        """Run calibration to find optimal parameters for each OS"""
        print("Starting calibration for", self.os_type)
        print("Please trigger an exclamation mark and show a fish shadow if possible...")
        
        # Create a window for calibration visualization
        cv2.namedWindow("Calibration")
        
        # Capture a series of frames for both regions
        exclamation_frames = []
        shadow_frames = []
        
        # Show live preview during calibration
        for i in range(20):  # Capture more frames for better calibration
            exclamation_frame = self.capture_screen(self.exclamation_monitor)
            shadow_frame = self.capture_screen(self.shadow_monitor)
            
            # Resize for display
            display_exclamation = cv2.resize(exclamation_frame, (400, 300))
            display_shadow = cv2.resize(shadow_frame, (400, 300))
            
            # Combine frames horizontally
            combined_frame = np.hstack((display_exclamation, display_shadow))
            
            # Add calibration progress text
            cv2.putText(combined_frame, f"Calibrating ({i+1}/20)...", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(combined_frame, "Exclamation", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(combined_frame, "Fish Shadow", (410, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow("Calibration", combined_frame)
            cv2.waitKey(1)
            
            exclamation_frames.append(exclamation_frame)
            shadow_frames.append(shadow_frame)
            
            # Save calibration images
            if i % 5 == 0:  # Save every 5th frame
                self.save_raw_image(exclamation_frame, f"calibration_exclamation_{i}")
                self.save_raw_image(shadow_frame, f"calibration_shadow_{i}")
            
            time.sleep(0.2)
        
        # Analyze brightness and colors to adjust parameters for each region
        exclamation_brightness = []
        shadow_darkness = []
        
        for frame in exclamation_frames:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            v_channel = hsv[:, :, 2]
            exclamation_brightness.append(np.mean(v_channel))
        
        for frame in shadow_frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            shadow_darkness.append(255 - np.mean(gray))
        
        avg_exclamation_brightness = np.mean(exclamation_brightness)
        avg_shadow_darkness = np.mean(shadow_darkness)
        
        # Set OS-specific thresholds
        if self.os_type == "Windows":
            self.exclamation_threshold = max(20, int(avg_exclamation_brightness * 0.25))
            self.shadow_threshold = max(15, int(avg_shadow_darkness * 0.2))
            self.bait_threshold = max(20, int(avg_exclamation_brightness * 0.2))
        else:  # macOS or other
            self.exclamation_threshold = max(25, int(avg_exclamation_brightness * 0.3))
            self.shadow_threshold = max(20, int(avg_shadow_darkness * 0.25))
            self.bait_threshold = max(25, int(avg_exclamation_brightness * 0.25))
        
        print(f"Calibration complete:")
        print(f"- Exclamation Brightness: {avg_exclamation_brightness:.2f}")
        print(f"- Shadow Darkness: {avg_shadow_darkness:.2f}")
        print(f"- Exclamation Threshold: {self.exclamation_threshold}")
        print(f"- Shadow Threshold: {self.shadow_threshold}")
        print(f"- Bait Threshold: {self.bait_threshold}")
        
        # Use destroyAllWindows instead of destroyWindow to be safer
        cv2.destroyAllWindows()

    def interactive_region_setup(self):
        """Interactive setup to allow user to position detection regions"""
        print("\nInteractive Region Setup")
        print("------------------------")
        print("This will help you position the detection regions correctly.")
        print("1. A window will open showing your screen")
        print("2. Click to position Exclamation Mark region")
        print("3. Then click to position Fish Shadow/Bait region")
        
        # Capture full screen as reference
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # Get primary monitor
            screen = np.array(sct.grab(monitor))
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
                        
                        # Update exclamation monitor
                        self.exclamation_monitor = {
                            "top": self.exclamation_y - self.exclamation_height//2,
                            "left": self.exclamation_x - self.exclamation_width//2,
                            "width": self.exclamation_width,
                            "height": self.exclamation_height
                        }
                        
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
                        
                        # Update shadow monitor
                        self.shadow_monitor = {
                            "top": self.shadow_y - self.shadow_height//2,
                            "left": self.shadow_x - self.shadow_width//2,
                            "width": self.shadow_width,
                            "height": self.shadow_height
                        }
                        
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
            
            # Use destroyAllWindows instead of destroyWindow
            cv2.destroyAllWindows()
            
            # Save the final regions image
            self.save_raw_image(screen, "region_setup")
            
            print("\nRegions set successfully:")
            print(f"Exclamation region: ({self.exclamation_x}, {self.exclamation_y}) - {self.exclamation_width}x{self.exclamation_height}")
            print(f"Shadow/Bait region: ({self.shadow_x}, {self.shadow_y}) - {self.shadow_width}x{self.shadow_height}")


if __name__ == "__main__":
    fisher = AutoFisher()
    
    # Interactive region setup
    print("Starting interactive region setup in 3 seconds...")
    print("Position the first region over where exclamation marks appear")
    print("Position the second region over where fish shadows and bait appear")
    time.sleep(3)
    fisher.interactive_region_setup()
    
    # Calibrate
    print("\nStarting calibration in 3 seconds...")
    print("Please make sure an exclamation mark is visible if possible")
    print("Also try to have a fish shadow visible in the second region")
    time.sleep(3)
    fisher.calibrate()
    
    # Start fishing
    print("\nStarting auto-fishing in 3 seconds...")
    print("Press 'q' to stop the program.")
    time.sleep(3)
    fisher.start_fishing() 