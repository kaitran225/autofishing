import sys
import time
import threading
import queue
import datetime
import numpy as np
import cv2
import mss
import subprocess
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, font as tkfont
import os


class RegionSelectionOverlay:
    """Overlay for selecting a screen region with macOS-specific functionality"""
    def __init__(self, parent=None, default_size=100, callback=None):
        self.parent = parent
        self.callback = callback
        self.default_size = default_size

        # Get the default display resolution
        self.get_screen_dimensions()
        
        # Create the selection window
        self.selection_window = tk.Toplevel(parent)
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.attributes('-alpha', 0.3)
        self.selection_window.attributes('-topmost', True)
        
        # Set window title and background color
        self.selection_window.title("Select Region")
        self.selection_window.configure(bg='black')
        
        # Capture the current screen before showing the selection overlay
        self.background_image = self.capture_screen_background()
        
        # Selection box dimensions (1.5:1 ratio)
        self.box_width = int(default_size * 1.5)
        self.box_height = default_size
        
        # Variables for tracking mouse position and selection state
        self.start_x = 0
        self.start_y = 0
        self.current_x = 0
        self.current_y = 0
        self.is_selecting = False
        
        # Colors for the UI elements
        self.colors = {
            'overlay': '#101010',
            'selection': '#00FF00',
            'grid': '#FFFFFF',
            'instruction': '#FFFFFF',
        }
        
        # Create canvas for drawing
        self.canvas = tk.Canvas(
            self.selection_window, 
            bg='black',
            highlightthickness=0,
            width=self.screen_width,
            height=self.screen_height
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Display the background image if available
        if self.background_image:
            self.bg_image_tk = ImageTk.PhotoImage(self.background_image)
            self.image_id = self.canvas.create_image(0, 0, image=self.bg_image_tk, anchor=tk.NW)
        
        # For play together window detection
        self.play_together_rect = None
        self.find_play_together_window()
        
        # Draw instructions
        self.draw_instructions()
        
        # Prepare selection box and guides
        self.selection_box = None
        self.guide_h = None
        self.guide_v = None
        self.info_text = None
        
        # Bind mouse events
        self.canvas.bind("<Motion>", self.on_mouse_move)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.selection_window.bind("<Escape>", self.on_escape)
        
        # Initial position of selection box (center screen)
        self.on_mouse_move(None)
        
        # Add button to find Play Together window
        if self.play_together_rect:
            self.add_play_together_button()
            
    def get_screen_dimensions(self):
        """Get the dimensions of the main screen"""
        # For macOS, get the screen size using Python's toolkit
        self.root = tk.Tk()
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        self.root.withdraw()  # Hide the temporary root window
        
        # When using mss, try to get more precise dimensions
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # Primary monitor
                self.screen_width = monitor["width"]
                self.screen_height = monitor["height"]
        except Exception as e:
            print(f"Error getting screen dimensions: {e}")
            
    def capture_screen_background(self):
        """Capture the entire screen to use as background"""
        try:
            # Wait briefly to ensure any other windows are properly hidden
            time.sleep(0.2)
            
            # Capture the entire screen using mss
            with mss.mss() as sct:
                # Capture the primary monitor
                monitor = sct.monitors[1]  # Primary monitor
                screenshot = sct.grab(monitor)
                
                # Convert to PIL Image
                img = Image.frombytes("RGB", (screenshot.width, screenshot.height), 
                                     screenshot.rgb)
                
                return img
                
        except Exception as e:
            print(f"Error capturing screen: {e}")
            return None
            
    def find_play_together_window(self):
        """Try to find the PLAY TOGETHER game window using AppleScript"""
        try:
            # AppleScript to find windows with PLAY TOGETHER in the title
            script = '''
            tell application "System Events"
                set windowInfo to {}
                repeat with proc in application processes
                    set procName to name of proc
                    repeat with w in windows of proc
                        if name of w contains "PLAY TOGETHER" or name of w contains "Play Together" then
                            set winPos to position of w
                            set winSize to size of w
                            set winName to name of w
                            return {item 1 of winPos, item 2 of winPos, item 1 of winSize, item 2 of winSize, procName, winName}
                        end if
                    end repeat
                end repeat
                return ""
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=False)
            output = result.stdout.strip()
            
            if output:
                try:
                    values = output.split(", ")
                    if len(values) >= 4:
                        left = int(values[0])
                        top = int(values[1])
                        width = int(values[2])
                        height = int(values[3])
                        
                        # Store process name and window name if available
                        self.play_together_proc = values[4] if len(values) > 4 else ""
                        self.play_together_name = values[5] if len(values) > 5 else "PLAY TOGETHER"
                        
                        self.play_together_rect = (left, top, left + width, top + height)
                        print(f"Found game window: {self.play_together_name} at {left},{top} size {width}x{height}")
                        return True
                except Exception as e:
                    print(f"Error parsing window info: {e}")
            
            return False
            
        except Exception as e:
            print(f"Error finding PLAY TOGETHER window: {e}")
            return False
            
    def add_play_together_button(self):
        """Add a button to position on Play Together window"""
        button_frame = tk.Frame(self.selection_window, bg='black')
        button_frame.place(x=self.screen_width - 250, y=70)
        
        button = tk.Button(
            button_frame,
            text="Position on PLAY TOGETHER",
            bg='#0A84FF',
            fg='white',
            bd=0,
            padx=10,
            pady=5,
            font=('Segoe UI', 10, 'bold'),
            command=self.position_on_play_together
        )
        button.pack()
        
    def position_on_play_together(self):
        """Position the selection box centered on the PLAY TOGETHER window"""
        if self.play_together_rect:
            left, top, right, bottom = self.play_together_rect
            center_x = (left + right) // 2
            center_y = (top + bottom) // 2
            
            # Update box position
            self.current_x = center_x
            self.current_y = center_y
            
            # Update display
            self.on_mouse_move(None)
            
    def draw_instructions(self):
        """Draw instruction text at the top of the screen"""
        # Instruction panel background
        panel_bg = self.canvas.create_rectangle(
            self.screen_width/2 - 250,
            50,
            self.screen_width/2 + 250,
            110, 
            fill='#282828',
            outline='#0A84FF',
            width=2,
            stipple='gray25'
        )
        
        # Main instruction text
        self.canvas.create_text(
            self.screen_width/2,
            70,
            text="Click and drag to move selection box. Release to place.",
            fill='#FFFFFF',
            font=('Segoe UI', 10, 'bold')
        )
        
        # Secondary instructions
        self.canvas.create_text(
            self.screen_width/2,
            90,
            text="Press ESC to cancel",
            fill='#AAAAAA',
            font=('Segoe UI', 10)
        )
            
    def update_selection_box(self):
        """Update the selection box display"""
        # Delete previous box and guides if they exist
        if self.selection_box:
            self.canvas.delete(self.selection_box)
        if self.guide_h:
            self.canvas.delete(self.guide_h)
        if self.guide_v:
            self.canvas.delete(self.guide_v)
        if self.info_text:
            self.canvas.delete(self.info_text)
            
        # Calculate box coordinates
        left = self.current_x - self.box_width // 2
        top = self.current_y - self.box_height // 2
        right = left + self.box_width
        bottom = top + self.box_height
        
        # Ensure box stays within screen bounds
        if left < 0:
            left = 0
            right = self.box_width
        elif right > self.screen_width:
            right = self.screen_width
            left = right - self.box_width
            
        if top < 0:
            top = 0
            bottom = self.box_height
        elif bottom > self.screen_height:
            bottom = self.screen_height
            top = bottom - self.box_height
            
        # Draw guides (lines across the screen)
        self.guide_h = self.canvas.create_line(
            0, self.current_y, 
            self.screen_width, self.current_y,
            fill=self.colors['grid'],
            dash=(4, 4),
            width=1
        )
        
        self.guide_v = self.canvas.create_line(
            self.current_x, 0,
            self.current_x, self.screen_height,
            fill=self.colors['grid'],
            dash=(4, 4),
            width=1
        )
        
        # Draw selection box
        self.selection_box = self.canvas.create_rectangle(
            left, top,
            right, bottom,
            outline=self.colors['selection'],
            width=2
        )
        
        # Add grid lines in the box
        cell_width = self.box_width // 3
        for i in range(1, 3):
            self.canvas.create_line(
                left + i * cell_width, top,
                left + i * cell_width, bottom,
                fill=self.colors['grid'],
                dash=(2, 2),
                width=1
            )
            
        cell_height = self.box_height // 3
        for i in range(1, 3):
            self.canvas.create_line(
                left, top + i * cell_height,
                right, top + i * cell_height,
                fill=self.colors['grid'],
                dash=(2, 2),
                width=1
            )
            
        # Display coordinate information
        info_text = f"Position: ({left},{top}) • Size: {self.box_width}×{self.box_height}"
        self.info_text = self.canvas.create_text(
            self.screen_width // 2,
            self.screen_height - 50,
            text=info_text,
            fill='white',
            font=('Segoe UI', 10)
        )
        
        # Store the current box coordinates
        self.current_box = (left, top, right, bottom)
        
    def on_mouse_move(self, event):
        """Handle mouse movement"""
        if event:
            self.current_x = event.x
            self.current_y = event.y
            
        # Update the selection box
        self.update_selection_box()
        
    def on_press(self, event):
        """Handle mouse press"""
        self.is_selecting = True
        self.start_x = event.x
        self.start_y = event.y
        
    def on_release(self, event):
        """Handle mouse release to finalize selection"""
        if self.is_selecting:
            self.is_selecting = False
            
            # Get the final box coordinates
            left, top, right, bottom = self.current_box
            
            # Close the window
            self.selection_window.destroy()
            
            # Call the callback with the selected region
            if self.callback:
                # Get game window info if available
                game_info = {}
                if hasattr(self, 'play_together_proc') and self.play_together_proc:
                    game_info['process'] = self.play_together_proc
                if hasattr(self, 'play_together_name') and self.play_together_name:
                    game_info['window'] = self.play_together_name
                    
                self.callback((left, top, right, bottom), game_info)
                
    def on_escape(self, event):
        """Cancel selection on ESC key"""
        self.selection_window.destroy()
        
        # Call callback with None to indicate cancellation
        if self.callback:
            self.callback(None, None)


class PixelChangeDetector:
    """Core detector class for monitoring pixel changes in a screen region"""
    def __init__(self, log_queue=None):
        self.THRESHOLD = 0.05  # Default threshold for pixel change detection
        self.is_running = False
        self.is_paused = False
        self.log_queue = log_queue
        self.gui = None
        
        # Screen capture region
        self.region = None  # (left, top, right, bottom)
        
        # Game window info for focusing
        self.game_process_name = ""
        self.game_window_name = "PLAY TOGETHER"
        
        # Frames for comparison
        self.current_frame = None
        self.previous_frame = None
        self.reference_frame = None
        self.diff_frame = None
        self.color_frame = None
        
        # Change history
        self.change_history = []
        
        # Last detection time for cooldown
        self.last_detection_time = 0
        self.detection_cooldown = 5.0  # Increased from mac.py's 0.5 to align with autofisher.py
        
        # Thread control
        self.detection_thread = None
        self.thread_control = {
            "running": False,
            "paused": False,
            "stop_requested": False
        }
        
        # Noise reduction parameters
        self.apply_blur = True
        self.blur_kernel_size = 3
        
        # Bright background detection
        self.enhanced_bright_detection = True
        
        # Performance optimization
        self.capture_interval = 0.05  # 20fps
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.last_successful_capture = 0
        
        # Key settings
        self.fishing_key = "f"  # Default fishing key
        
        # Detection statistics
        self.stats = {
            "total_detections": 0,
            "false_positives": 0,
            "session_start_time": time.time(),
            "last_detection_time": 0,
            "avg_detection_interval": 0
        }
        
        # Performance monitoring
        self.performance = {
            "avg_processing_time": 0.05,
            "processing_samples": 0,
            "cpu_usage": 0
        }
        
    def log(self, message):
        """Log a message"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        if self.log_queue:
            self.log_queue.put(formatted_message)
        print(formatted_message)
        
    def perform_health_check(self):
        """Check detector health and attempt recovery if needed"""
        current_time = time.time()
        
        # Check if we've had too many consecutive failures
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.log("Too many consecutive failures, attempting recovery...")
            # Reset state
            self.current_frame = None
            self.diff_frame = None
            
            # Try to recapture reference frame
            self.capture_reference()
            
            # Reset failure counter
            self.consecutive_failures = 0
            
        # Check if we haven't had a successful capture in a while
        if self.last_successful_capture > 0 and (current_time - self.last_successful_capture) > 5.0:
            self.log("No successful captures detected, attempting recovery...")
            self.capture_reference()
            
        return True
    
    def capture_screen(self):
        """Capture the defined region of the screen"""
        try:
            if not self.region:
                self.log("No region selected")
                return None
                
            left, top, right, bottom = self.region
            width = right - left
            height = bottom - top
            
            # Using mss for screen capture
            with mss.mss() as sct:
                monitor = {"top": top, "left": left, "width": width, "height": height}
                screenshot = sct.grab(monitor)
                
                # Use numpy array with zero copy when possible
                frame = np.array(screenshot, dtype=np.uint8)
                
                # Store color frame for visualization
                self.color_frame = frame.copy()
                
                # Convert to grayscale for processing
                if len(frame.shape) > 2:
                    if frame.shape[2] == 4:  # BGRA format from mss
                        # Faster grayscale conversion using weighted sum
                        frame = np.dot(frame[..., :3], [0.114, 0.587, 0.299])
                    else:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    
                    # Ensure uint8 type
                    frame = frame.astype(np.uint8)
                
                # Apply Gaussian blur to reduce noise if enabled
                if self.apply_blur and self.blur_kernel_size > 0:
                    frame = cv2.GaussianBlur(frame, (self.blur_kernel_size, self.blur_kernel_size), 0)
                
                # Update health check variables
                self.last_successful_capture = time.time()
                self.consecutive_failures = 0
                
                return frame
                
        except Exception as e:
            self.log(f"Error capturing screen: {e}")
            self.consecutive_failures += 1
            return None
            
    def calculate_frame_difference(self, frame1, frame2):
        """Calculate the difference between two frames with improved handling for bright backgrounds"""
        if frame1 is None or frame2 is None:
            return None, 0
            
        # Ensure frames have same dimensions
        if frame1.shape != frame2.shape:
            # Resize to match
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
            
            # Identify bright areas
            bright_mask = frame1 > 180
            
            # Apply the adaptive threshold to get binary difference
            _, thresholded_diff = cv2.threshold(diff_frame, threshold_base, 255, cv2.THRESH_BINARY)
            
            # Additional processing for bright regions to enhance sensitivity
            if np.any(bright_mask):
                # Apply a more sensitive threshold to bright areas
                bright_diff = cv2.bitwise_and(diff_frame, diff_frame, mask=bright_mask.astype(np.uint8) * 255)
                _, bright_thresh = cv2.threshold(bright_diff, threshold_base // 2, 255, cv2.THRESH_BINARY)
                
                # Combine normal threshold with enhanced bright area threshold
                thresholded_diff = cv2.bitwise_or(thresholded_diff, bright_thresh)
        else:
            # Standard detection method
            diff_frame = cv2.absdiff(frame1, frame2)
            _, thresholded_diff = cv2.threshold(diff_frame, threshold_base, 255, cv2.THRESH_BINARY)
        
        # Use morphological operations to reduce noise
        kernel = np.ones((2, 2), np.uint8)
        thresholded_diff = cv2.morphologyEx(thresholded_diff, cv2.MORPH_OPEN, kernel)
        
        # Calculate percentage by counting non-zero pixels
        non_zero_pixels = cv2.countNonZero(thresholded_diff)
        total_pixels = frame1.size
        change_percent = non_zero_pixels / total_pixels
        
        # Store the thresholded difference for visualization
        self.diff_frame = thresholded_diff
        
        return thresholded_diff, change_percent
        
    def capture_reference(self):
        """Capture a reference frame"""
        if self.region:
            success = self.capture_screen() is not None
            if success:
                self.reference_frame = self.color_frame
                self.log("Reference frame captured")
                return True
        else:
            self.log("You must select a region first")
            return False
    
    def start_detection(self, thread_control=None):
        """Start the detection process"""
        if not self.region:
            self.log("You must select a region first")
            return False
            
        # Set running state
        self.is_running = True
        self.is_paused = False
        self.change_history = []
        self.consecutive_failures = 0
        self.last_successful_capture = 0
        
        # Try to find the game window
        if not self.game_process_name or not self.game_window_name:
            self.find_game_window()
        
        # Always clear and recapture the reference frame when starting
        self.reference_frame = None
        self.log("Capturing new reference frame...")
        if not self.capture_reference():
            self.log("Failed to capture reference frame. Please check region selection.")
            self.is_running = False
            return False
            
        self.previous_frame = self.reference_frame
        
        # Use thread control if provided
        self.thread_control = thread_control if thread_control else {
            "running": True,
            "paused": False,
            "stop_requested": False
        }
        
        # Start detection thread
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        self.log("Detection started")
        return True
        
    def stop_detection(self):
        """Stop the detection process"""
        self.thread_control["stop_requested"] = True
        self.is_running = False
        self.is_paused = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=1.0)
            
        # Reset state
        self.is_running = False
        self.is_paused = False
        self.change_history = []
        self.consecutive_failures = 0
        self.last_successful_capture = 0
            
        self.log("Detection stopped")
        return True
    
    def toggle_pause(self):
        """Pause or resume detection"""
        self.is_paused = not self.is_paused
        self.thread_control["paused"] = self.is_paused
        
        if self.is_paused:
            self.log("Detection paused")
        else:
            self.log("Detection resumed")
            
    def _detection_loop(self):
        """Main detection loop"""
        # Initialize frame skip counter and performance metrics
        frame_counter = 0
        fps_counter = 0
        fps_timer = time.time()
        last_fps_update = time.time()
        fps = 0
        
        # Local variables for performance
        local_threshold = self.THRESHOLD
        local_interval = self.capture_interval
        
        self.log("Starting detection loop")
        
        while self.is_running and not self.thread_control.get("stop_requested", False):
            loop_start = time.time()
            try:
                # Skip if paused
                if self.is_paused or self.thread_control.get("paused", False):
                    time.sleep(local_interval * 2)
                    continue
                
                # Update FPS counter
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    fps = fps_counter
                    fps_counter = 0
                    fps_timer = time.time()
                    
                    # Update FPS in performance stats
                    self.performance["cpu_usage"] = 0  # No direct CPU measurement on Mac
                    
                    # Only log FPS every 5 seconds to avoid spamming
                    if time.time() - last_fps_update >= 5.0:
                        self.log(f"Processing at {fps} FPS")
                        last_fps_update = time.time()
                
                # Perform health check periodically
                if frame_counter % 10 == 0:
                    self.perform_health_check()
                    
                # Capture current frame
                self.current_frame = self.capture_screen()
                
                if self.current_frame is None:
                    time.sleep(local_interval)
                    continue
                    
                # Determine which frame to compare against
                compare_frame = self.reference_frame if self.reference_frame is not None else self.previous_frame
                
                if compare_frame is None:
                    self.capture_reference()
                    time.sleep(local_interval)
                    continue
                
                # Calculate difference
                self.diff_frame, change_percent = self.calculate_frame_difference(
                    self.current_frame, compare_frame
                )
                
                # Store in history
                self.change_history.append(change_percent)
                if len(self.change_history) > 100:
                    self.change_history = self.change_history[-100:]
                
                # Check for detection with cooldown
                current_time = time.time()
                if (change_percent > local_threshold and 
                        (current_time - self.last_detection_time) > self.detection_cooldown):
                    self.log(f"Change detected! {change_percent:.2%}")
                    self.last_detection_time = current_time
                    
                    # Handle detection event
                    self._handle_detection()
                    
                    # Continue to next frame
                    continue
                
                # Store current frame as previous for next comparison
                self.previous_frame = self.current_frame
                
                # Control capture rate
                frame_counter += 1
                
                # Calculate time spent in this iteration
                loop_time = time.time() - loop_start
                
                # Update performance metrics
                self.performance["processing_samples"] += 1
                if self.performance["processing_samples"] > 100:
                    self.performance["processing_samples"] = 1
                
                # Update moving average of processing time
                alpha = 0.05  # Weight for new samples
                self.performance["avg_processing_time"] = (1 - alpha) * self.performance["avg_processing_time"] + alpha * loop_time
                
                # Sleep to control capture rate
                sleep_time = max(0, local_interval - loop_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                self.log(f"Error in detection loop: {e}")
                self.consecutive_failures += 1
                time.sleep(local_interval)
                
        # Cleanup when loop exits
        self.log("Detection thread exiting")
        
    def _handle_detection(self):
        """Handle a detection event with the fishing sequence"""
        try:
            # Update stats
            self.stats["total_detections"] += 1
            current_time = time.time()
            
            # Calculate interval since last detection
            if self.stats["last_detection_time"] > 0:
                interval = current_time - self.stats["last_detection_time"]
                # Update average detection interval using moving average
                if self.stats["avg_detection_interval"] == 0:
                    self.stats["avg_detection_interval"] = interval
                else:
                    self.stats["avg_detection_interval"] = (
                        0.8 * self.stats["avg_detection_interval"] + 0.2 * interval
                    )
            self.stats["last_detection_time"] = current_time
            
            # Focus game window and press fishing key
            if self.focus_game_window():
                self.log(f"Pressing {self.fishing_key.upper()} key")
                self._send_key(self.fishing_key)
            
            # Wait a moment
            time.sleep(4.0)
            
            # Press ESC to exit fishing menu
            if self.focus_game_window():
                self.log("Pressing ESC key")
                self._send_key('esc')
                
            # Wait before casting again
            time.sleep(2.0)
            
            # Cast fishing line again
            if self.focus_game_window():
                self.log(f"Pressing {self.fishing_key.upper()} key to cast line")
                self._send_key(self.fishing_key)
                
            # Take a new reference frame after completing the sequence
            time.sleep(2.0)
            self.capture_reference()
            
        except Exception as e:
            self.log(f"Error handling detection: {e}")
    
    def find_game_window(self):
        """Try to find the game window using AppleScript"""
        try:
            script = '''
            tell application "System Events"
                set windowInfo to {}
                repeat with proc in application processes
                    if exists (windows of proc) then
                        repeat with w in windows of proc
                            if name of w contains "PLAY TOGETHER" or name of w contains "Play Together" then
                                set procName to name of proc
                                set winName to name of w
                                return {procName, winName}
                            end if
                        end repeat
                    end if
                end repeat
                return ""
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=False)
            output = result.stdout.strip()
            
            if output:
                values = output.split(", ")
                if len(values) >= 2:
                    self.game_process_name = values[0]
                    self.game_window_name = values[1]
                    self.log(f"Found game window: {self.game_window_name} ({self.game_process_name})")
                    return True
                    
            self.log("Game window not found. Will use generic search during keystroke sending.")
            return False
            
        except Exception as e:
            self.log(f"Error finding game window: {e}")
            return False
            
    def focus_game_window(self):
        """Focus the game window using AppleScript"""
        try:
            if not self.game_process_name and not self.game_window_name:
                if not self.find_game_window():
                    return False
                    
            if self.game_process_name and self.game_window_name:
                focus_script = f'''
                tell application "System Events"
                    tell process "{self.game_process_name}"
                        set frontmost to true
                        tell window "{self.game_window_name}"
                            perform action "AXRaise"
                        end tell
                    end tell
                    delay 0.2
                end tell
                '''
            else:
                # Fallback to generic window search
                focus_script = '''
                tell application "System Events"
                    # Try to find and focus on the game window
                    repeat with proc in application processes
                        if exists (windows of proc) then
                            repeat with w in windows of proc
                                if name of w contains "PLAY TOGETHER" or name of w contains "Play Together" then
                                    set frontmost of proc to true
                                    perform action "AXRaise" of w
                                    delay 0.2
                                    exit repeat
                                end if
                            end repeat
                        end if
                    end repeat
                end tell
                '''
                
            # Execute the focus script
            subprocess.run(['osascript', '-e', focus_script], check=True, capture_output=True)
            self.log("Focused on game window")
            return True
            
        except Exception as e:
            self.log(f"Error focusing game window: {e}")
            return False
            
    def _send_key(self, key_char):
        """Send keypress using AppleScript"""
        try:
            # Map common key names to key codes
            key_map = {
                'f': 'key code 3',      # F key
                'esc': 'key code 53',   # ESC key
                'e': 'key code 14',     # E key
                'space': 'key code 49'  # Space key
            }
            
            key_command = key_map.get(key_char.lower(), f'keystroke "{key_char}"')
            
            # Create script to send key
            key_script = f'''
            tell application "System Events"
                {key_command}
            end tell
            '''
            
            subprocess.run(['osascript', '-e', key_script], check=True, capture_output=True)
            self.log(f"{key_char.upper()} key sent")
            return True
            
        except Exception as e:
            self.log(f"Error sending {key_char} key: {e}")
            return False 


class PixelChangeDetectorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Fisher for macOS")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        self.root.resizable(True, True)
        
        # Set app style and configuration
        self.configure_style()
        
        # Set window background explicitly
        self.root.configure(background=self.colors['bg_dark'])
        
        # Create message queue for logging
        self.log_queue = queue.Queue()
        
        # Initialize detector
        self.detector = None
        self.is_running = False
        
        # Thread control variables
        self.thread_control = {
            "detection_thread": None,
            "running": False,
            "paused": False,
            "stop_requested": False
        }
        
        # Pixel visualization data
        self.change_history = []
        
        # Detection counter
        self.detection_count = 0
        
        # Create GUI elements
        self.create_widgets()
        
        # Setup detector after widgets
        self.detector = PixelChangeDetector(self.log_queue)
        self.detector.gui = self
        
        # Setup periodic updates
        self.update_logs()
        
    def configure_style(self):
        """Configure the app style with a matcha and oak wood inspired theme"""
        style = ttk.Style()
        # Matcha and oak wood color palette
        self.colors = {
            'bg_dark': '#181914',         # Oak wood dark
            'bg_term': '#23281e',         # Slightly lighter for panels
            'bg_lighter': '#2e3324',      # Lighter panel
            'bg_alt': '#3e3c2f',          # Alternative dark
            'text': '#F8F5E3',            # Warm off-white
            'text_bright': '#FFFFFF',
            'text_dim': '#A3A08C',        # Dimmed text
            'accent': '#A3D977',          # Matcha green
            'accent_alt': '#7CB518',      # Deeper matcha
            'accent_bright': '#C4E6B5',   # Bright matcha
            'accent_special': '#E6CBA5',  # Oak highlight
            'green': '#A3D977',           # Matcha green
            'green_alt': '#BCD9B4',
            'border': '#6B6E58',
            'border_light': '#A3A08C',
            'cursor': '#A3D977',
            'alert': '#FF4D4D',
            'warning': '#FFB940',
            'selection': '#A3D977'
        }
        # Use a modern sans-serif font for a clean look
        main_font = tkfont.Font(family="Segoe UI", size=10)
        small_font = tkfont.Font(family="Segoe UI", size=10)
        heading_font = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self.root.option_add("*Font", main_font)
        
        # Configure base styles
        style.configure('TFrame', background=self.colors['bg_dark'])
        style.configure('Term.TFrame', background=self.colors['bg_dark'])
        style.configure('Separator.TFrame', background=self.colors['border'])
        style.configure('Border.TFrame', background=self.colors['bg_dark'], borderwidth=1, relief="solid")
        style.configure('Material.TFrame', background=self.colors['bg_dark'], borderwidth=0, relief="flat")
        style.configure('TLabel', background=self.colors['bg_dark'], foreground=self.colors['text'], font=small_font)
        style.configure('Term.TLabel', background=self.colors['bg_dark'], foreground=self.colors['text'], font=small_font)
        style.configure('Heading.TLabel', font=heading_font, background=self.colors['bg_dark'], foreground=self.colors['accent'])
        style.configure('Status.TLabel', font=small_font, background=self.colors['bg_dark'], foreground=self.colors['text_dim'])
        style.configure('Running.Status.TLabel', foreground=self.colors['green'], background=self.colors['bg_dark'])
        style.configure('Stopped.Status.TLabel', foreground=self.colors['alert'], background=self.colors['bg_dark'])
        style.configure('Paused.Status.TLabel', foreground=self.colors['warning'], background=self.colors['bg_dark'])
        style.configure('Monitor.Status.TLabel', font=small_font, background=self.colors['bg_dark'], foreground=self.colors['accent_bright'], padding=(5, 2))
        style.configure('TButton', background=self.colors['bg_dark'], foreground=self.colors['accent'], borderwidth=0, focusthickness=0, relief="flat", padding=(8, 6), font=small_font)
        style.map('TButton', background=[('active', self.colors['bg_lighter']), ('pressed', self.colors['bg_alt'])], foreground=[('active', self.colors['accent_bright']), ('pressed', self.colors['accent_alt'])])
        style.configure('Command.TButton', background=self.colors['bg_dark'], foreground=self.colors['green'], borderwidth=1, focusthickness=0, relief="flat", padding=(10, 6), font=small_font)
        style.map('Command.TButton', background=[('active', self.colors['bg_lighter']), ('pressed', self.colors['bg_alt'])], foreground=[('active', self.colors['green_alt']), ('pressed', self.colors['green'])])
        style.configure('Warning.TButton', background=self.colors['bg_dark'], foreground=self.colors['alert'], borderwidth=1, focusthickness=0, relief="flat", padding=(10, 6), font=small_font)
        style.map('Warning.TButton', background=[('active', self.colors['bg_lighter']), ('pressed', self.colors['bg_alt'])], foreground=[('active', self.colors['alert']), ('pressed', self.colors['text_bright'])])
        style.configure('Secondary.TButton', background=self.colors['bg_dark'], foreground=self.colors['accent_alt'], borderwidth=1, focusthickness=0, relief="flat", padding=(10, 6), font=small_font)
        style.map('Secondary.TButton', background=[('active', self.colors['bg_lighter']), ('pressed', self.colors['bg_alt'])], foreground=[('active', self.colors['accent']), ('pressed', self.colors['accent_bright'])])
        style.configure('Panel.TFrame', padding=6, relief="flat", borderwidth=0, background=self.colors['bg_dark'])
        style.configure('Terminal.TLabelframe', padding=8, relief="solid", borderwidth=1, bordercolor=self.colors['border_light'], background=self.colors['bg_dark'])
        style.configure('Terminal.TLabelframe.Label', font=small_font, background=self.colors['bg_dark'], foreground=self.colors['accent'], padding=(5, 0))
        style.configure('TEntry', fieldbackground=self.colors['bg_dark'], foreground=self.colors['accent_bright'], insertcolor=self.colors['cursor'], borderwidth=1, relief="solid", font=small_font)
        style.configure('TCheckbutton', background=self.colors['bg_dark'], foreground=self.colors['accent'], font=small_font)
        style.map('TCheckbutton', background=[('active', self.colors['bg_dark'])], foreground=[('active', self.colors['accent_bright'])])
        style.configure('TScale', background=self.colors['bg_dark'], troughcolor=self.colors['bg_dark'], slidercolor=self.colors['accent'], borderwidth=0)
        self.root.configure(background=self.colors['bg_dark'])

    def log(self, message):
        """Add timestamped message to log queue"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")
        
    def update_logs(self):
        """Process any new log messages from the queue and update stats in real time"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_console.insert(tk.END, message + "\n")
                self.log_console.see(tk.END)  # Auto-scroll to end
        except queue.Empty:
            pass

        # Update stats in real time if detector exists
        if hasattr(self, 'stats_labels') and self.detector:
            self.show_stats()

        # Update visualization if running
        if self.is_running and self.detector:
            self.update_visualization()
            
        # Schedule next update
        self.root.after(100, self.update_logs)
        
    def create_widgets(self):
        """Create all GUI widgets with modern minimal terminal design"""
        # Main container with minimal padding
        main_container = ttk.Frame(self.root, padding="8", style='TFrame')
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Create a single column layout
        content_frame = ttk.Frame(main_container, style='TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top section: Settings and controls
        top_section = ttk.Frame(content_frame, style='TFrame')
        top_section.pack(fill=tk.X, pady=(0, 8))
        
        # Left panel for settings (fixed width)
        left_panel = ttk.Frame(top_section, width=360, style='TFrame')
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left_panel.pack_propagate(False)  # Fix the width
        
        # Right panel for controls (fixed width)
        right_panel = ttk.Frame(top_section, width=360, style='TFrame')
        right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        right_panel.pack_propagate(False)  # Fix the width
        
        # Create settings panel contents
        self.create_settings_panel(left_panel)
        
        # Create control panel contents
        self.create_control_panel(right_panel)
        
        # Middle section: Visualization with 1.5:1 aspect ratio
        viz_section = ttk.Frame(content_frame, style='TFrame')
        viz_section.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        # Create visualization
        self.create_visualization(viz_section)
        
        # Bottom section: Logs
        log_section = ttk.Frame(content_frame, style='TFrame')
        log_section.pack(fill=tk.BOTH, expand=True)
        
        # Create logs
        self.create_logs(log_section)
        
    def create_settings_panel(self, parent):
        """Create the settings panel"""
        # Section 1: Settings
        settings_frame = ttk.LabelFrame(parent, text="SETTINGS", style='Terminal.TLabelframe')
        settings_frame.pack(fill=tk.X, pady=(0, 8), padx=0)
        
        # Use a grid layout for better organization
        settings_grid = ttk.Frame(settings_frame, style='Term.TFrame')
        settings_grid.pack(fill=tk.X, padx=4, pady=4)

        # Threshold (row 0)
        ttk.Label(settings_grid, text="Threshold", style='Term.TLabel', font=('Segoe UI', 10)).grid(row=0, column=0, sticky='w', padx=(0, 8), pady=2)
        threshold_frame = ttk.Frame(settings_grid, style='Term.TFrame')
        threshold_frame.grid(row=0, column=1, sticky='ew', padx=(0, 8), pady=2)
        self.threshold_var = tk.DoubleVar(value=0.05)
        self.threshold_slider = tk.Scale(
            threshold_frame,
            from_=0.01, to=0.5,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            variable=self.threshold_var,
            command=self.update_threshold_label,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            highlightthickness=0,
            troughcolor=self.colors['bg_lighter'],
            activebackground=self.colors['accent'],
            sliderrelief="flat",
            length=120, font=('Segoe UI', 10)
        )
        self.threshold_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.threshold_label = ttk.Label(threshold_frame, text="0.05", width=5, style='Term.TLabel', font=('Segoe UI', 10))
        self.threshold_label.pack(side=tk.LEFT, padx=(8, 0))

        # Region Size (row 1)
        ttk.Label(settings_grid, text="Region Size", style='Term.TLabel', font=('Segoe UI', 10)).grid(row=1, column=0, sticky='w', padx=(0, 8), pady=2)
        region_size_frame = ttk.Frame(settings_grid, style='Term.TFrame')
        region_size_frame.grid(row=1, column=1, sticky='ew', padx=(0, 8), pady=2)
        self.size_var = tk.StringVar(value="50")
        self.size_entry = tk.Entry(
            region_size_frame,
            textvariable=self.size_var,
            width=6,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            insertbackground=self.colors['cursor'],
            highlightthickness=1,
            highlightbackground=self.colors['border'],
            highlightcolor=self.colors['accent'],
            relief="flat", font=('Segoe UI', 10)
        )
        self.size_entry.pack(side=tk.LEFT)
        ttk.Label(region_size_frame, text="px", style='Term.TLabel', font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=(4, 0))

        # Cooldown (row 2)
        ttk.Label(settings_grid, text="Cooldown", style='Term.TLabel', font=('Segoe UI', 10)).grid(row=2, column=0, sticky='w', padx=(0, 8), pady=2)
        cooldown_frame = ttk.Frame(settings_grid, style='Term.TFrame')
        cooldown_frame.grid(row=2, column=1, sticky='ew', padx=(0, 8), pady=2)
        self.cooldown_var = tk.DoubleVar(value=5.0)
        self.cooldown_entry = tk.Entry(
            cooldown_frame,
            textvariable=self.cooldown_var,
            width=6,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            insertbackground=self.colors['cursor'],
            highlightthickness=1,
            highlightbackground=self.colors['border'],
            highlightcolor=self.colors['accent'],
            relief="flat", font=('Segoe UI', 10)
        )
        self.cooldown_entry.pack(side=tk.LEFT)
        ttk.Label(cooldown_frame, text="sec", style='Term.TLabel', font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=(4, 0))

        # Fishing Key (row 3)
        ttk.Label(settings_grid, text="Fishing Key", style='Term.TLabel', font=('Segoe UI', 10)).grid(row=3, column=0, sticky='w', padx=(0, 8), pady=2)
        fishing_key_frame = ttk.Frame(settings_grid, style='Term.TFrame')
        fishing_key_frame.grid(row=3, column=1, sticky='ew', padx=(0, 8), pady=2)
        self.fishing_key_var = tk.StringVar(value="f")
        self.fishing_key_entry = tk.Entry(
            fishing_key_frame,
            textvariable=self.fishing_key_var,
            width=4,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            insertbackground=self.colors['cursor'],
            highlightthickness=1,
            highlightbackground=self.colors['border'],
            highlightcolor=self.colors['accent'],
            relief="flat", font=('Segoe UI', 10)
        )
        self.fishing_key_entry.pack(side=tk.LEFT)

        # Apply Settings button
        apply_button = tk.Button(
            fishing_key_frame,
            text="Apply Settings",
            command=self.apply_settings,
            bg=self.colors['bg_dark'],
            fg=self.colors['accent'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['accent_alt'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=8,
            pady=4,font=('Segoe UI', 10)
        )
        apply_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Section 2: Monitoring
        monitor_frame = ttk.LabelFrame(parent, text="MONITORING", style='Terminal.TLabelframe')
        monitor_frame.pack(fill=tk.X, pady=(0, 8), padx=0)
        
        # Stats details in two columns
        self.stats_frame = ttk.Frame(monitor_frame, style='Term.TFrame')
        self.stats_frame.pack(fill=tk.X, pady=(0, 0), padx=0)
        self.stats_labels = {}
        stats_keys = [
            ("Detections", "total_detections"),
            ("Session Runtime", "session_runtime"),
            ("Detection Rate", "detections_per_hour"),
            ("Avg. Interval", "avg_interval"),
            ("Threshold", "current_threshold"),
            ("Cooldown", "cooldown"),
            ("Key Mapping", "key_mapping"),
            ("Processing FPS", "processing_fps")
        ]
        
        # Arrange in two columns
        for i, (label, key) in enumerate(stats_keys):
            row = i // 2
            col = i % 2
            l = ttk.Label(self.stats_frame, text=f"{label}: ...", style='Term.TLabel', font=('Segoe UI', 10))
            l.grid(row=row, column=col, sticky='w', pady=1, padx=8)
            self.stats_labels[key] = l
            
    def create_control_panel(self, parent):
        """Create the control panel"""
        # Section 3: Control
        control_frame = ttk.LabelFrame(parent, text="CONTROL", style='Terminal.TLabelframe')
        control_frame.pack(fill=tk.X, pady=(0, 8), padx=0)
        
        # Control buttons layout
        button_frame = ttk.Frame(control_frame, style='Term.TFrame')
        button_frame.pack(fill=tk.X, pady=4)
        
        # Start button
        self.start_button = tk.Button(
            button_frame, 
            text="start",
            command=self.start_detection,
            bg=self.colors['bg_dark'],
            fg=self.colors['green'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['green_alt'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=5, font=('Segoe UI', 10)
        )
        self.start_button.pack(side=tk.LEFT, padx=(5, 5))
        
        # Stop button
        self.stop_button = tk.Button(
            button_frame, 
            text="stop",
            command=self.stop_detection,
            state=tk.DISABLED,
            bg=self.colors['bg_dark'],
            fg=self.colors['alert'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['alert'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=5,
            disabledforeground='grey', font=('Segoe UI', 10)
        )
        self.stop_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Pause button
        self.pause_button = tk.Button(
            button_frame, 
            text="pause",
            command=self.toggle_pause,
            state=tk.DISABLED,
            bg=self.colors['bg_dark'],
            fg=self.colors['warning'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['warning'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=5,
            disabledforeground='grey', font=('Segoe UI', 10)
        )
        self.pause_button.pack(side=tk.LEFT, padx=(0, 5))

        # Clear logs button
        self.clear_button = tk.Button(
            button_frame, 
            text="clear-logs",
            command=self.clear_logs,
            bg=self.colors['bg_dark'],
            fg=self.colors['text_dim'],
            justify=tk.RIGHT,
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['text'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=5, font=('Segoe UI', 10)
        )
        self.clear_button.pack(side=tk.LEFT)
        
        # Second row of buttons
        button_frame2 = ttk.Frame(control_frame, style='Term.TFrame')
        button_frame2.pack(fill=tk.X, pady=4)
        
        # Capture reference button
        self.ref_button = tk.Button(
            button_frame2, 
            text="capture-reference",
            command=self.capture_reference,
            bg=self.colors['bg_dark'],
            fg=self.colors['accent'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['accent_alt'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=15,
            pady=5, font=('Segoe UI', 10)
        )
        self.ref_button.pack(side=tk.LEFT, padx=(5, 5))

        # Region selection button
        self.region_button = tk.Button(
            button_frame2, 
            text="select-region",
            command=self.select_region,
            bg=self.colors['bg_dark'],
            fg=self.colors['green'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['green_alt'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=5, font=('Segoe UI', 10)
        )
        self.region_button.pack(side=tk.LEFT, padx=(5, 5))
        
    def create_visualization(self, parent):
        """Create the visualization section with 1.5:1 aspect ratio"""
        # Visualization section
        viz_frame = ttk.LabelFrame(parent, text="VISUALIZATION", style='Terminal.TLabelframe')
        viz_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create the monitoring visualization with matplotlib
        self.create_monitoring_display(viz_frame)
        
        # Create status bar at the bottom of the visualization
        self.status_frame = ttk.Frame(viz_frame, style='Term.TFrame')
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=8, pady=4)
        
        self.status_label = ttk.Label(self.status_frame, text="Status: Waiting", style='Status.TLabel')
        self.status_label.pack(side=tk.LEFT)
        
        self.count_label = ttk.Label(self.status_frame, text="Detections: 0", style='Status.TLabel')
        self.count_label.pack(side=tk.RIGHT)
        
    def create_monitoring_display(self, parent):
        """Create the monitoring visualization with matplotlib using 1.5:1 aspect ratio"""
        viz_content_frame = ttk.Frame(parent, style='Border.TFrame')
        viz_content_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        canvas_frame = ttk.Frame(viz_content_frame, style='Term.TFrame')
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # Create a figure with 1.5:1 aspect ratio (matches region selection box)
        self.fig = plt.Figure(figsize=(9, 6), dpi=100, facecolor=self.colors['bg_dark'])
        gs = plt.GridSpec(1, 1, figure=self.fig, left=0.05, right=0.95, top=0.95, bottom=0.15)
        
        # Create the main axes for displaying current frame
        self.current_ax = self.fig.add_subplot(gs[0])
        self.current_image = self.current_ax.imshow(np.zeros((100, 150, 3)), cmap='gray', aspect='auto')
        self.diff_overlay = self.current_ax.imshow(np.zeros((100, 150, 4)), alpha=0.5, aspect='auto')
        self.current_ax.set_xticks([])
        self.current_ax.set_yticks([])
        self.current_ax.set_facecolor(self.colors['bg_dark'])
        self.current_ax.axis('off')
        
        # Add border rectangle
        rect = plt.Rectangle((0, 0), 1, 1, fill=False, ec=self.colors['border_light'], 
                           linewidth=1.5, transform=self.current_ax.transAxes, clip_on=False)
        self.current_ax.add_patch(rect)
        
        # Add timeline at the bottom
        self.timeline_ax = self.current_ax.inset_axes([0.0, -0.15, 1.0, 0.1], transform=self.current_ax.transAxes)
        self.timeline_ax.axhline(y=0.5, color=self.colors['border'], linestyle='-', alpha=0.3, linewidth=0.5)
        
        x_data = np.arange(100)
        y_data = np.ones(100) * 0.5
        self.activity_line, = self.timeline_ax.plot(x_data, y_data, color=self.colors['accent'], linewidth=1)
        self.threshold_line = self.timeline_ax.axhline(y=0.05, color=self.colors['alert'], linestyle='--', alpha=0.5, linewidth=0.5)
        
        self.timeline_ax.set_ylim(0, 1)
        self.timeline_ax.set_xlim(0, 99)
        self.timeline_ax.set_facecolor(self.colors['bg_dark'])
        self.timeline_ax.set_xticks([])
        self.timeline_ax.set_yticks([])
        
        # Configure timeline appearance
        for spine in self.timeline_ax.spines.values():
            spine.set_visible(False)
            
        self.timeline_ax.set_yticks([0, 0.5, 1])
        self.timeline_ax.set_yticklabels(['0', '', '1'])
        self.timeline_ax.tick_params(axis='y', colors=self.colors['text_dim'], labelsize=10)
        self.timeline_ax.text(0.5, 0.5, "", color=self.colors['green'], fontsize=10, 
                            ha='center', va='center', transform=self.timeline_ax.transAxes, alpha=0.7)
        
        # Create canvas and pack it
        self.canvas = FigureCanvasTkAgg(self.fig, canvas_frame)
        self.canvas.get_tk_widget().configure(bg=self.colors['bg_dark'], highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Add initial text
        self.fig.text(0.5, 0.5, "awaiting data", color=self.colors['text_dim'], fontsize=10, 
                     ha='center', va='center', family='Segoe UI')
        
    def create_logs(self, parent):
        """Create the log section"""
        # Section 4: Logs
        log_frame = ttk.LabelFrame(parent, text="LOGS", style='Terminal.TLabelframe')
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0), padx=0)
        
        self.log_console = scrolledtext.ScrolledText(
            log_frame,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            font=('Segoe UI', 10),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=8
        )
        self.log_console.pack(fill=tk.BOTH, expand=True)
        
    def update_threshold_label(self, value=None):
        """Update threshold label and apply to detector if it exists"""
        threshold_value = float(self.threshold_var.get())
        self.threshold_label.config(text=f"{threshold_value:.2f}")
        
        # Update detector threshold if it exists
        if hasattr(self, 'detector') and self.detector is not None:
            self.detector.THRESHOLD = threshold_value
            self.log(f"Detection threshold updated to {threshold_value:.2f}")
            
    def apply_settings(self):
        """Apply the advanced settings to the detector"""
        try:
            # Get the settings from UI
            threshold_value = float(self.threshold_var.get())
            cooldown_value = float(self.cooldown_var.get())
            fishing_key = self.fishing_key_var.get().strip().lower()
            
            # Validate settings
            if threshold_value < 0.01 or threshold_value > 0.5:
                self.log("Error: Threshold must be between 0.01 and 0.5")
                return
                
            if cooldown_value < 0.1 or cooldown_value > 30:
                self.log("Error: Cooldown must be between 0.1 and 30 seconds")
                return
                
            if not fishing_key:
                self.log("Error: Fishing key cannot be empty")
                return
                
            # Apply settings to detector
            if self.detector:
                old_threshold = self.detector.THRESHOLD
                old_cooldown = self.detector.detection_cooldown
                
                # Update detector settings
                self.detector.THRESHOLD = threshold_value
                self.detector.detection_cooldown = cooldown_value
                self.detector.fishing_key = fishing_key
                
                self.log(f"Settings applied: threshold={threshold_value:.2f}, cooldown={cooldown_value}s, key={fishing_key}")
                
                # Log changes
                if old_threshold != threshold_value:
                    self.log(f"Threshold changed: {old_threshold:.2f} -> {threshold_value:.2f}")
                    
                if old_cooldown != cooldown_value:
                    self.log(f"Cooldown changed: {old_cooldown}s -> {cooldown_value}s")
            else:
                self.log("Error: Detector not initialized")
                
        except ValueError as e:
            self.log(f"Error applying settings: {e}")
            return False
            
        return True
    
    def update_visualization(self):
        """Update the visualization with current frames"""
        try:
            # Clear any initial status text
            for txt in self.fig.texts:
                txt.remove()
                
            # Update current frame
            if hasattr(self.detector, 'color_frame') and self.detector.color_frame is not None:
                self.current_image.set_data(self.detector.color_frame)
                self.current_ax.axis('off')
            elif hasattr(self.detector, 'current_frame') and self.detector.current_frame is not None:
                gray_display = cv2.cvtColor(self.detector.current_frame, cv2.COLOR_GRAY2RGB)
                self.current_image.set_data(gray_display)
                self.current_ax.axis('off')
                
            # Create overlay for difference frame
            if hasattr(self.detector, 'diff_frame') and self.detector.diff_frame is not None:
                diff_display = self.detector.diff_frame.copy()
                diff_display = cv2.convertScaleAbs(diff_display, alpha=3)
                diff_colored = cv2.applyColorMap(diff_display, cv2.COLORMAP_INFERNO)
                colored_diff = cv2.cvtColor(diff_colored, cv2.COLOR_BGR2RGB)
                colored_diff_alpha = np.zeros((colored_diff.shape[0], colored_diff.shape[1], 4), dtype=np.uint8)
                colored_diff_alpha[..., :3] = colored_diff
                
                # Create alpha mask based on difference intensity
                alpha_threshold = 30
                for i in range(diff_display.shape[0]):
                    for j in range(diff_display.shape[1]):
                        if diff_display[i, j] > alpha_threshold:
                            colored_diff_alpha[i, j, 3] = min(255, int(diff_display[i, j] * 2))
                        else:
                            colored_diff_alpha[i, j, 3] = 0
                            
                self.diff_overlay.set_data(colored_diff_alpha)
                
            # Update timeline activity
            if hasattr(self.detector, 'change_history'):
                history = self.detector.change_history[-100:] if len(self.detector.change_history) > 0 else [0]
                
                # Normalize values to 0-1 range for clean display
                max_val = max(history) if max(history) > 0 else 1
                normalized_history = [min(h / max_val, 1.0) for h in history]
                
                # Pad with zeros if needed
                if len(normalized_history) < 100:
                    normalized_history = [0] * (100 - len(normalized_history)) + normalized_history
                
                # Update the line data
                self.activity_line.set_ydata(normalized_history)
                
                # Update threshold line position (normalized to the same scale)
                threshold_value = min(self.detector.THRESHOLD / max_val, 1.0)
                self.threshold_line.set_ydata([threshold_value, threshold_value])
                
                # Update title with threshold value in minimal format
                self.timeline_ax.set_title(f"ACTIVITY [t:{self.detector.THRESHOLD:.2f}]", 
                                         color=self.colors['green'], fontsize=10, fontweight='normal')
            
            # Redraw canvas
            self.canvas.draw_idle()
        except Exception as e:
            self.log(f"Error updating visualization: {e}")
            
    def show_stats(self):
        """Update stats details in the MONITORING section in real time"""
        if not hasattr(self, 'detector') or not self.detector:
            return
            
        # Calculate runtime
        runtime_secs = time.time() - self.detector.stats["session_start_time"]
        hours = int(runtime_secs // 3600)
        mins = int((runtime_secs % 3600) // 60)
        secs = int(runtime_secs % 60)
        runtime_str = f"{hours:02}:{mins:02}:{secs:02}"
        
        # Calculate detection rate (per hour)
        detections_per_hour = 0
        if runtime_secs > 0:
            detections_per_hour = (self.detector.stats["total_detections"] / runtime_secs) * 3600
            
        # Average interval between detections
        avg_interval = self.detector.stats["avg_detection_interval"]
        if avg_interval > 0:
            interval_mins = int(avg_interval // 60)
            interval_secs = int(avg_interval % 60)
            interval_str = f"{interval_mins}m {interval_secs}s"
        else:
            interval_str = "N/A"
            
        # Stats data
        stats_data = {
            "total_detections": str(self.detector.stats["total_detections"]),
            "session_runtime": runtime_str,
            "detections_per_hour": f"{detections_per_hour:.1f}",
            "avg_interval": interval_str,
            "current_threshold": f"{self.detector.THRESHOLD:.3f}",
            "cooldown": f"{self.detector.detection_cooldown:.1f}s",
            "key_mapping": self.detector.fishing_key.upper(),
            "processing_fps": str(int(1.0 / max(0.01, self.detector.performance["avg_processing_time"])))
        }
        
        for key, label in self.stats_labels.items():
            label.config(text=f"{label.cget('text').split(':')[0]}: {stats_data.get(key, '...')}")

    def select_region(self):
        """Open region selection overlay for the user to select a screen area"""
        try:
            # Get the size from the input field
            size = int(self.size_var.get())
            if size < 10:
                self.log("Size must be at least 10 pixels")
                return
        except ValueError:
            self.log("Invalid size value. Using default of 50 pixels")
            size = 50
            self.size_var.set("50")
        
        self.log("Starting region selection...")
        
        # Hide the main window temporarily
        self.root.withdraw()
        
        # Create the selection overlay
        self.selection_overlay = RegionSelectionOverlay(self.root, size, self.set_region)
        
        # Restore main window when selection is done (in the callback)
        
    def set_region(self, region, game_info):
        """Handle the selected region from the overlay"""
        # Always restore main window
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        
        if region is None:
            self.log("Region selection canceled")
            return
            
        # Set the region in the detector
        if self.detector:
            self.detector.region = region
            
            # Update game window info if available
            if game_info:
                if 'process' in game_info:
                    self.detector.game_process_name = game_info['process']
                    self.log(f"Game process identified: {self.detector.game_process_name}")
                    
                if 'window' in game_info:
                    self.detector.game_window_name = game_info['window']
                    self.log(f"Game window identified: {self.detector.game_window_name}")
            
            # Update UI
            left, top, right, bottom = region
            width = right - left
            height = bottom - top
            self.log(f"Region selected: ({left},{top}) {width}×{height}")
            
            # Capture a reference frame if detector is initialized
            if not self.detector.is_running:
                self.capture_reference()
                self.log("Initial reference frame captured")
                
    def start_detection(self):
        """Start the detection process"""
        if not self.detector.region:
            self.log("You must select a region first")
            return
            
        # Update threshold from UI
        self.detector.THRESHOLD = self.threshold_var.get()
        
        # Update cooldown from UI
        try:
            cooldown = float(self.cooldown_var.get())
            if 0.1 <= cooldown <= 30:
                self.detector.detection_cooldown = cooldown
        except ValueError:
            pass
            
        # Update fishing key from UI
        fishing_key = self.fishing_key_var.get().strip().lower()
        if fishing_key:
            self.detector.fishing_key = fishing_key
        
        # Reset thread control
        self.thread_control = {
            "detection_thread": None,
            "running": True,
            "paused": False,
            "stop_requested": False
        }
        
        # Start detection
        success = self.detector.start_detection(self.thread_control)
        
        if success:
            # Update UI state
            self.is_running = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.NORMAL)
            self.set_status_indicator("running")
        else:
            self.log("Failed to start detection")
            
    def stop_detection(self):
        """Stop the detection process"""
        if not self.is_running:
            return
            
        # Signal thread to stop
        self.thread_control["stop_requested"] = True
        self.thread_control["running"] = False
        self.is_running = False
        
        # Stop the detector
        self.detector.stop_detection()
        
        # Update UI
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED, text="pause")
        self.set_status_indicator("stopped")
        
    def toggle_pause(self):
        """Pause or resume the detection thread"""
        if not self.is_running:
            return
            
        # Update thread control
        self.thread_control["paused"] = not self.thread_control.get("paused", False)
        
        if self.thread_control["paused"]:
            # Paused state
            self.detector.toggle_pause()
            self.pause_button.config(text="resume")
            self.set_status_indicator("paused")
        else:
            # Resumed state
            self.detector.toggle_pause()
            self.pause_button.config(text="pause")
            self.set_status_indicator("running")
            
    def capture_reference(self):
        """Capture a reference frame"""
        if self.detector and hasattr(self.detector, 'capture_reference'):
            if not self.detector.region:
                self.log("You must select a region first")
                return False
                
            success = self.detector.capture_reference()
            if success:
                self.log("Reference frame captured successfully")
            else:
                self.log("Failed to capture reference frame")
        else:
            self.log("Detector not initialized properly")
            
    def clear_logs(self):
        """Clear the log console"""
        self.log_console.delete(1.0, tk.END)
        
    def set_status_indicator(self, status):
        """Update the status indicator"""
        if status == "running":
            self.status_label.config(text="System: monitor.active", style="Running.Status.TLabel")
        elif status == "stopped":
            self.status_label.config(text="System: monitor.stopped", style="Stopped.Status.TLabel")
        elif status == "paused":
            self.status_label.config(text="System: monitor.paused", style="Paused.Status.TLabel")
        else:
            self.status_label.config(text=f"System: monitor.{status}", style="Status.TLabel")


VERSION = "1.0"
VERSION_NAME = "macOS Edition"

def main():
    root = tk.Tk()
    root.title(f"AutoFisher v{VERSION}")
    
    # Create and start the application
    app = PixelChangeDetectorGUI(root)
    
    # Get primary monitor dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    # Set window size based on monitor resolution
    window_width = min(int(screen_width * 0.5), 900)  # At most 50% of screen width or 900px
    window_height = min(int(screen_height * 0.6), 600)  # At most 60% of screen height or 600px
    
    # Center window on primary monitor
    center_x = int(screen_width/2 - window_width/2)
    center_y = int(screen_height/2 - window_height/2)
    
    # Set window size and position
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    # Log monitor information
    with mss.mss() as sct:
        monitors = sct.monitors
        app.log("Detected Display:")
        for i, monitor in enumerate(monitors):
            if i > 0:  # Skip the "all monitors combined" entry
                app.log(f"Monitor {i}: {monitor['width']}x{monitor['height']}")
    
    # Add welcome message
    app.log(f"AutoFisher v{VERSION} initialized")
    app.log(f"{VERSION_NAME}")
    app.log("System ready - Please select a region to begin")
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    main() 