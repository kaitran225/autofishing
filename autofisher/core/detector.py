"""
Core detector class for pixel change detection
"""
import time
import datetime
import numpy as np
import cv2

class PixelChangeDetector:
    """Base class for pixel change detection functionality"""
    
    def __init__(self):
        # Detection settings
        self.THRESHOLD = 0.05  # Default threshold for pixel change detection
        self.is_running = False
        self.is_paused = False
        
        # Screen capture region
        self.region = None  # (left, top, right, bottom)
        
        # Frames for comparison
        self.current_frame = None
        self.previous_frame = None
        self.reference_frame = None
        self.diff_frame = None
        self.color_frame = None
        
        # Change history
        self.change_history = []
        
        # Callback functions
        self.on_detection = None
        self.on_log = None
        self.on_frame_updated = None
        
        # Last detection time for cooldown
        self.last_detection_time = 0
        self.detection_cooldown = 0.5  # Seconds between detections
        
        # Noise reduction parameters
        self.apply_blur = True
        self.blur_kernel_size = 3
        
        # Bright background detection
        self.enhanced_bright_detection = True  # Enable enhanced detection for bright backgrounds
        
        # Action sequence control
        self.in_action_sequence = False
        self.action_sequence_step = 0
        
    def log(self, message):
        """Log a message"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        if self.on_log:
            self.on_log(formatted_message)
        
    def calculate_frame_difference(self, frame1, frame2):
        """Calculate the difference between two frames with improved handling for bright backgrounds"""
        if frame1 is None or frame2 is None:
            return None, 0
            
        # Ensure frames have same dimensions
        if frame1.shape != frame2.shape:
            # Resize to match - use faster INTER_NEAREST for performance
            frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]), interpolation=cv2.INTER_NEAREST)
            
        # Ensure both frames are grayscale for accurate comparison
        if len(frame1.shape) == 3 and len(frame2.shape) == 2:
            # Convert frame1 to grayscale
            frame1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        elif len(frame1.shape) == 2 and len(frame2.shape) == 3:
            # Convert frame2 to grayscale
            frame2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        elif len(frame1.shape) == 3 and len(frame2.shape) == 3:
            # Convert both to grayscale
            frame1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            frame2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            
        # Base threshold value
        threshold_base = 30  # Default threshold for significant change
        
        if self.enhanced_bright_detection:
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to improve contrast
            # This helps with detecting changes in bright backgrounds
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            frame1_eq = clahe.apply(frame1)
            frame2_eq = clahe.apply(frame2)
                
            # Calculate absolute difference from contrast-enhanced images
            diff_frame = cv2.absdiff(frame1_eq, frame2_eq)
        else:
            # Standard difference calculation
            diff_frame = cv2.absdiff(frame1, frame2)
            
        # Calculate the percentage of changed pixels
        change_percent = np.count_nonzero(diff_frame > threshold_base) / diff_frame.size
            
        return diff_frame, change_percent
        
    def capture_reference(self):
        """Capture a reference frame - to be implemented by platform-specific subclasses"""
        raise NotImplementedError("This method must be implemented by subclasses")
        
    def capture_screen(self):
        """Capture the defined region of the screen - to be implemented by platform-specific subclasses"""
        raise NotImplementedError("This method must be implemented by subclasses")
        
    def start_detection(self):
        """Start the detection process - to be implemented by platform-specific subclasses"""
        raise NotImplementedError("This method must be implemented by subclasses")
        
    def stop_detection(self):
        """Stop the detection process - to be implemented by platform-specific subclasses"""
        raise NotImplementedError("This method must be implemented by subclasses")
        
    def toggle_pause(self):
        """Pause/resume the detection process"""
        self.is_paused = not self.is_paused
        self.log(f"Detection {'paused' if self.is_paused else 'resumed'}")
        
    def _detection_loop(self):
        """Main detection loop - to be implemented by platform-specific subclasses"""
        raise NotImplementedError("This method must be implemented by subclasses")
        
    def _process_action_sequence(self):
        """Process fishing action sequence - to be implemented by platform-specific subclasses"""
        raise NotImplementedError("This method must be implemented by subclasses")
        
    def _send_key(self, key):
        """Send a key press - to be implemented by platform-specific subclasses"""
        raise NotImplementedError("This method must be implemented by subclasses") 