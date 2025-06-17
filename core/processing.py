"""
Image processing functions for pixel change detection
"""
import numpy as np
import cv2
import mss
import mss.tools
from PIL import ImageGrab

def capture_screen_region(region):
    """
    Capture a region of the screen using MSS for high performance
    
    Args:
        region (tuple): (left, top, right, bottom) coordinates
        
    Returns:
        tuple: (frame, color_frame) where frame is the raw capture and 
               color_frame is RGB converted for visualization
    """
    try:
        if not region or len(region) != 4:
            return None, None
            
        left, top, right, bottom = region
        width = right - left
        height = bottom - top
        
        if width < 10 or height < 10:
            return None, None
            
        # Use mss library for better performance and multi-monitor support
        with mss.mss() as sct:
            # Convert region format to mss format (left, top, width, height)
            mss_region = {
                "left": left,
                "top": top,
                "width": width,
                "height": height
            }
            
            # Capture the region
            screenshot = sct.grab(mss_region)
            
            # Convert to numpy array - mss.grab returns BGR format
            frame = np.array(screenshot)
            
            # Create RGB version for visualization
            color_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
            
            return frame, color_frame
            
    except Exception as e:
        print(f"Error capturing screen: {e}")
        return None, None

def calculate_frame_difference(frame1, frame2):
    """
    Calculate the difference between two frames with enhanced sensitivity
    
    Args:
        frame1 (numpy.ndarray): First frame
        frame2 (numpy.ndarray): Second frame to compare against
        
    Returns:
        tuple: (diff_frame, change_percent) where diff_frame is the visual difference and
               change_percent is the proportion of pixels that changed significantly
    """
    if frame1 is None or frame2 is None:
        return None, 0
        
    # Ensure frames have same dimensions
    if frame1.shape != frame2.shape:
        # Resize to match
        frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
    
    # Apply slight blur to reduce noise sensitivity
    frame1_blurred = cv2.GaussianBlur(frame1, (5, 5), 0)
    frame2_blurred = cv2.GaussianBlur(frame2, (5, 5), 0)
    
    # For color images - convert to HSV for better color sensitivity
    if len(frame1.shape) >= 3:
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
    else:
        # For grayscale images
        diff_frame = cv2.absdiff(frame1_blurred, frame2_blurred)
    
    # Calculate percentage of pixels that changed significantly
    threshold = 20  # Lower threshold for more sensitivity
    
    # Apply morphological operations to highlight larger changes
    kernel = np.ones((3, 3), np.uint8)
    dilated_diff = cv2.dilate(diff_frame, kernel, iterations=1)
    
    # Count significant pixel changes
    changed_pixels = np.sum(dilated_diff > threshold)
    total_pixels = frame1.shape[0] * frame1.shape[1]
    change_percent = changed_pixels / total_pixels
    
    return dilated_diff, change_percent 