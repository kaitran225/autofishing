"""
Image processing utilities for AutoFisher
Provides optimized screen capture and image analysis functions
"""
import numpy as np
import cv2
import mss
import mss.tools
import time
import traceback

def capture_screen_region(region):
    """
    Capture a region of the screen with high reliability
    
    Args:
        region: Tuple (left, top, right, bottom) defining the screen region
        
    Returns:
        tuple: (frame, color_frame) the captured frame and color version
    """
    if not region:
        return None, None
        
    try:
        left, top, right, bottom = region
        width = right - left
        height = bottom - top
        
        if width < 10 or height < 10:
            print("Invalid region size detected")
            return None, None
            
        # Use MSS for best performance and multi-monitor support
        with mss.mss() as sct:
            # Convert region format to MSS format
            mss_region = {
                "left": left,
                "top": top,
                "width": width,
                "height": height
            }
            
            # Capture the region
            screenshot = sct.grab(mss_region)
            
            # Convert to numpy array
            frame = np.array(screenshot)
            
            # Validate frame
            if frame.size == 0:
                print("Captured frame is empty")
                return None, None
                
            # Create color frame (RGB) for visualization
            if len(frame.shape) >= 3:
                color_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
            else:
                color_frame = None
                
            return frame, color_frame
            
    except Exception as e:
        print(f"Error capturing screen: {e}")
        traceback.print_exc()
        return None, None

def calculate_frame_difference(frame1, frame2):
    """
    Calculate the difference between two frames with optimized sensitivity
    for fishing detection
    
    Args:
        frame1: First frame (current)
        frame2: Second frame (reference)
        
    Returns:
        tuple: (diff_frame, change_percent)
    """
    if frame1 is None or frame2 is None:
        return None, 0
        
    try:
        # Ensure frames have same dimensions
        if frame1.shape != frame2.shape:
            frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
        
        # Apply slight blur to reduce noise sensitivity
        frame1_blurred = cv2.GaussianBlur(frame1, (5, 5), 0)
        frame2_blurred = cv2.GaussianBlur(frame2, (5, 5), 0)
        
        # For color images - use HSV for better fishing detection
        if len(frame1.shape) == 3:
            # Convert to HSV for better color sensitivity
            frame1_hsv = cv2.cvtColor(frame1_blurred, cv2.COLOR_BGR2HSV)
            frame2_hsv = cv2.cvtColor(frame2_blurred, cv2.COLOR_BGR2HSV)
            
            # Calculate difference in HSV space
            h_diff = cv2.absdiff(frame1_hsv[:,:,0], frame2_hsv[:,:,0])
            s_diff = cv2.absdiff(frame1_hsv[:,:,1], frame2_hsv[:,:,1])
            v_diff = cv2.absdiff(frame1_hsv[:,:,2], frame2_hsv[:,:,2])
            
            # Weight hue differences more heavily for pastel colors
            h_weight = 2.0  # Increased weight for hue differences
            s_weight = 1.0
            v_weight = 1.0
            
            # Combine channels with weights
            diff_frame = cv2.addWeighted(h_diff, h_weight, s_diff, s_weight, 0)
            diff_frame = cv2.addWeighted(diff_frame, 1.0, v_diff, v_weight, 0)
            
            # Apply morphological operations to highlight larger changes
            kernel = np.ones((3, 3), np.uint8)
            dilated_diff = cv2.dilate(diff_frame, kernel, iterations=1)
            
            # Calculate percentage of pixels that changed significantly
            threshold = 20  # Lower threshold for more sensitivity
            changed_pixels = np.sum(dilated_diff > threshold)
            total_pixels = frame1.shape[0] * frame1.shape[1]
            change_percent = changed_pixels / total_pixels
            
            # For visualization, enhance the difference frame
            enhanced_diff = cv2.convertScaleAbs(dilated_diff, alpha=1.5)
            
            return enhanced_diff, change_percent
        else:
            # For grayscale images
            diff_frame = cv2.absdiff(frame1_blurred, frame2_blurred)
            
            # Apply morphological operations
            kernel = np.ones((3, 3), np.uint8)
            dilated_diff = cv2.dilate(diff_frame, kernel, iterations=1)
            
            # Calculate percentage of changed pixels
            threshold = 20
            changed_pixels = np.sum(dilated_diff > threshold)
            total_pixels = frame1.shape[0] * frame1.shape[1]
            change_percent = changed_pixels / total_pixels
            
            # Enhance for visualization
            enhanced_diff = cv2.convertScaleAbs(dilated_diff, alpha=2.0)
            
            return enhanced_diff, change_percent
            
    except Exception as e:
        print(f"Error calculating frame difference: {e}")
        traceback.print_exc()
        return None, 0

def detect_fishing_bobber(frame, lower_range=(9, 80, 80), upper_range=(35, 255, 255)):
    """
    Detect the fishing bobber in frame (experimental)
    
    Args:
        frame: Input BGR frame
        lower_range: HSV lower range for orange bobber
        upper_range: HSV upper range for orange bobber
        
    Returns:
        tuple: (x, y, radius) of the bobber if found, None otherwise
    """
    try:
        if frame is None:
            return None
            
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Create mask for orange/red bobber
        mask = cv2.inRange(hsv, np.array(lower_range), np.array(upper_range))
        
        # Apply morphological operations
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=1)
        mask = cv2.dilate(mask, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Find the largest contour that could be a bobber
        max_area = 0
        max_contour = None
        for contour in contours:
            area = cv2.contourArea(contour)
            if 50 < area < 2000:  # Filter by area
                if area > max_area:
                    max_area = area
                    max_contour = contour
        
        # If a potential bobber contour is found
        if max_contour is not None:
            # Find the circle enclosing the contour
            (x, y), radius = cv2.minEnclosingCircle(max_contour)
            if 5 < radius < 45:  # Filter by radius
                return (int(x), int(y), int(radius))
                
        return None
        
    except Exception as e:
        print(f"Error detecting bobber: {e}")
        return None

def enhance_visualization(diff_frame, change_percent, threshold):
    """
    Enhance diff frame for better visualization
    
    Args:
        diff_frame: Difference frame
        change_percent: Detected change percentage
        threshold: Detection threshold
        
    Returns:
        numpy.ndarray: Enhanced visualization frame
    """
    try:
        if diff_frame is None:
            return None
            
        # Create a colored visualization
        if len(diff_frame.shape) < 3 or diff_frame.shape[2] < 3:
            # Convert grayscale diff to color heat map
            diff_colored = cv2.applyColorMap(diff_frame, cv2.COLORMAP_INFERNO)
        else:
            # Already in color
            diff_colored = diff_frame.copy()
            
        # Add threshold line visualization
        change_ratio = min(1.0, change_percent / (threshold * 1.5))
        
        # Scale colors based on how close to threshold
        if change_percent > threshold:
            # Above threshold - highlight in green
            color = (0, 255, 0)  # Green
            thickness = 2
        else:
            # Below threshold - normal visualization
            color = (0, 165, 255)  # Orange
            thickness = 1
            
        # Add text showing change percentage
        cv2.putText(
            diff_colored,
            f"Change: {change_percent*100:.2f}%",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            thickness
        )
        
        # Add threshold line
        cv2.putText(
            diff_colored,
            f"Threshold: {threshold*100:.2f}%",
            (10, 60),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 165, 255),
            1
        )
        
        return diff_colored
        
    except Exception as e:
        print(f"Error enhancing visualization: {e}")
        return diff_frame 