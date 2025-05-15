import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import platform
import os
import cv2
import numpy as np
import mss
from PIL import Image, ImageTk

# Import OS-specific modules
if platform.system() == "Windows":
    from region_selector_win import RegionSelectorWin as RegionSelector
    from game_focus_win import GameFocusWin as GameFocus
    from key_sender_win import KeySenderWin as KeySender
elif platform.system() == "Darwin":  # macOS
    from region_selector_mac import RegionSelectorMac as RegionSelector
    from game_focus_mac import GameFocusMac as GameFocus
    from key_sender_mac import KeySenderMac as KeySender
else:
    print("Unsupported OS")
    # Use Windows as fallback
    from region_selector_win import RegionSelectorWin as RegionSelector
    from game_focus_win import GameFocusWin as GameFocus
    from key_sender_win import KeySenderWin as KeySender

# Import utility module
from os_utilities import OSUtilities

class AutoFisherUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Fisher")
        self.root.geometry("800x600")
        self.root.minsize(800, 600)
        
        # Platform detection
        self.os_utils = OSUtilities()
        self.os_name = self.os_utils.get_os_name()
        
        # Initialize OS-specific modules
        self.region_selector = RegionSelector()
        self.game_focus = GameFocus()
        self.key_sender = KeySender()
        
        # Region parameters
        exclamation_region, shadow_region = self.os_utils.get_default_regions()
        self.exclamation_monitor = self.os_utils.create_monitor_dict(exclamation_region)
        self.shadow_monitor = self.os_utils.create_monitor_dict(shadow_region)
        
        # Status variables
        self.is_running = False
        self.is_paused = False
        self.detection_count = 0
        self.last_detection_time = 0
        self.detection_cooldown = 1.0  # Seconds between detections
        
        # Reference frames
        self.reference_exclamation_frame = None
        self.reference_shadow_frame = None
        self.last_exclamation_frame = None
        self.last_shadow_frame = None
        
        # Detection parameters
        self.exclamation_threshold = 30  # Pixel change threshold
        self.shadow_threshold = 20
        self.bait_threshold = 25
        self.min_exclamation_area = 100
        self.max_exclamation_area = 800
        self.min_shadow_area = 500
        self.max_shadow_area = 5000
        
        # Action sequence for fishing
        self.action_sequence = [
            {"action": "press_f", "delay": 0.0},   # Press F immediately
            {"action": "wait", "delay": 3.0},      # Wait 3 seconds
            {"action": "press_esc", "delay": 1.0}, # Press ESC, wait 1 second
            {"action": "wait", "delay": 1.0},      # Wait 1 more second
            {"action": "press_f", "delay": 1.0}    # Press F again, wait 1 second
        ]
        
        # Action sequence control
        self.in_action_sequence = False
        self.action_sequence_step = 0
        
        # Create the screen capture context
        self.sct = mss.mss()
        
        # Build UI
        self.create_ui()
        
        # Start the image update loop
        self.update_preview()
    
    def create_ui(self):
        """Create the user interface"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Split into two parts: controls on left, preview on right
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding="10")
        preview_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # === Control Area ===
        ttk.Label(control_frame, text=f"Detected OS: {self.os_name}", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=5)
        
        # Region setup button
        ttk.Button(control_frame, text="Setup Detection Regions", command=self.setup_regions).pack(fill=tk.X, pady=5)
        
        # Capture reference frames
        ttk.Button(control_frame, text="Capture Reference Frames", command=self.capture_reference_frames).pack(fill=tk.X, pady=5)
        
        # Start/Stop button
        self.start_stop_button = ttk.Button(control_frame, text="Start Fishing", command=self.toggle_fishing)
        self.start_stop_button.pack(fill=tk.X, pady=5)
        
        # Pause/Resume button
        self.pause_resume_button = ttk.Button(control_frame, text="Pause", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_resume_button.pack(fill=tk.X, pady=5)
        
        # Status section
        status_frame = ttk.LabelFrame(control_frame, text="Status", padding="10")
        status_frame.pack(fill=tk.X, pady=10)
        
        self.status_label = ttk.Label(status_frame, text="Idle", font=("Arial", 10))
        self.status_label.pack(anchor=tk.W)
        
        self.detection_label = ttk.Label(status_frame, text="Detections: 0", font=("Arial", 10))
        self.detection_label.pack(anchor=tk.W)
        
        # Detection parameters
        param_frame = ttk.LabelFrame(control_frame, text="Parameters", padding="10")
        param_frame.pack(fill=tk.X, pady=10)
        
        # Exclamation threshold
        ttk.Label(param_frame, text="Exclamation Threshold:").pack(anchor=tk.W)
        exclamation_scale = ttk.Scale(param_frame, from_=5, to=50, orient=tk.HORIZONTAL, 
                                      command=lambda v: self.update_parameter('exclamation_threshold', v))
        exclamation_scale.set(self.exclamation_threshold)
        exclamation_scale.pack(fill=tk.X)
        
        # Shadow threshold
        ttk.Label(param_frame, text="Shadow Threshold:").pack(anchor=tk.W)
        shadow_scale = ttk.Scale(param_frame, from_=5, to=50, orient=tk.HORIZONTAL,
                                command=lambda v: self.update_parameter('shadow_threshold', v))
        shadow_scale.set(self.shadow_threshold)
        shadow_scale.pack(fill=tk.X)
        
        # === Preview Area ===
        self.preview_label = ttk.Label(preview_frame)
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        
        # Info text
        info_text = """
        How to use:
        1. Click "Setup Detection Regions" to position detection areas
        2. Click "Capture Reference Frames" when no fish or markers are visible
        3. Click "Start Fishing" to begin auto-fishing
        
        Tips:
        - Position the exclamation region where '!' marks appear
        - Position the shadow region where fish shadows are visible
        - Adjust thresholds if detection is too sensitive or not sensitive enough
        """
        ttk.Label(preview_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)
    
    def update_parameter(self, param_name, value):
        """Update a detection parameter"""
        if hasattr(self, param_name):
            setattr(self, param_name, int(float(value)))
    
    def setup_regions(self):
        """Run the interactive region setup"""
        if self.is_running:
            messagebox.showwarning("Warning", "Stop fishing before setting up regions")
            return
        
        self.root.iconify()  # Minimize main window
        
        try:
            # Run the region selector
            exclamation_monitor, shadow_monitor = self.region_selector.interactive_region_setup()
            
            # Update monitors
            self.exclamation_monitor = exclamation_monitor
            self.shadow_monitor = shadow_monitor
            
            # Reset reference frames
            self.reference_exclamation_frame = None
            self.reference_shadow_frame = None
            
            messagebox.showinfo("Success", "Regions set successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Error setting up regions: {e}")
        finally:
            self.root.deiconify()  # Restore main window
    
    def capture_reference_frames(self):
        """Capture reference frames for both regions"""
        if self.is_running:
            messagebox.showwarning("Warning", "Stop fishing before capturing reference frames")
            return
        
        try:
            # Capture frames
            self.reference_exclamation_frame = self.os_utils.capture_screen(self.sct, self.exclamation_monitor)
            self.reference_shadow_frame = self.os_utils.capture_screen(self.sct, self.shadow_monitor)
            
            if self.reference_exclamation_frame is not None and self.reference_shadow_frame is not None:
                messagebox.showinfo("Success", "Reference frames captured successfully")
                self.status_label.config(text="Reference frames ready")
            else:
                messagebox.showerror("Error", "Failed to capture reference frames")
        except Exception as e:
            messagebox.showerror("Error", f"Error capturing reference frames: {e}")
    
    def toggle_fishing(self):
        """Start or stop the fishing process"""
        if not self.is_running:
            # Check if reference frames exist
            if self.reference_exclamation_frame is None or self.reference_shadow_frame is None:
                result = messagebox.askyesno("Warning", 
                         "Reference frames have not been captured. This is recommended for best results.\n\nCapture reference frames now?")
                if result:
                    self.capture_reference_frames()
                    return
            
            # Start fishing in a separate thread
            self.is_running = True
            self.is_paused = False
            self.start_stop_button.config(text="Stop Fishing")
            self.pause_resume_button.config(state=tk.NORMAL)
            self.status_label.config(text="Running")
            
            # Start the fishing thread
            self.fishing_thread = threading.Thread(target=self.fishing_loop)
            self.fishing_thread.daemon = True
            self.fishing_thread.start()
        else:
            # Stop fishing
            self.is_running = False
            self.is_paused = False
            self.start_stop_button.config(text="Start Fishing")
            self.pause_resume_button.config(state=tk.DISABLED, text="Pause")
            self.status_label.config(text="Stopped")
    
    def toggle_pause(self):
        """Pause or resume the fishing process"""
        if not self.is_running:
            return
        
        if not self.is_paused:
            self.is_paused = True
            self.pause_resume_button.config(text="Resume")
            self.status_label.config(text="Paused")
        else:
            self.is_paused = False
            self.pause_resume_button.config(text="Pause")
            self.status_label.config(text="Running")
    
    def fishing_loop(self):
        """Main fishing loop that runs in a separate thread"""
        # Try to find game window
        self.game_focus.find_game_window()
        
        # Set up initial frames
        self.last_exclamation_frame = self.os_utils.capture_screen(self.sct, self.exclamation_monitor)
        self.last_shadow_frame = self.os_utils.capture_screen(self.sct, self.shadow_monitor)
        
        # If references don't exist, use first captures
        if self.reference_exclamation_frame is None:
            self.reference_exclamation_frame = self.last_exclamation_frame.copy()
        if self.reference_shadow_frame is None:
            self.reference_shadow_frame = self.last_shadow_frame.copy()
        
        # State variables
        waiting_for_fish = False
        
        try:
            while self.is_running:
                # Check if paused
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                
                # Handle action sequence if one is in progress
                if self.in_action_sequence:
                    self._process_action_sequence()
                    time.sleep(0.05)
                    continue
                
                # Capture frames
                exclamation_frame = self.os_utils.capture_screen(self.sct, self.exclamation_monitor)
                
                # Only capture shadow frame if we're not waiting for a fish (optimization)
                if not waiting_for_fish:
                    shadow_frame = self.os_utils.capture_screen(self.sct, self.shadow_monitor)
                else:
                    shadow_frame = self.last_shadow_frame
                
                if exclamation_frame is None or shadow_frame is None:
                    time.sleep(0.05)
                    continue
                
                # Detect exclamation mark
                exclamation_detected, exclamation_frame_viz = self.detect_exclamation_mark(
                    exclamation_frame, self.reference_exclamation_frame
                )
                
                # Detect fish shadow or bouncy bait if needed
                if not waiting_for_fish:
                    shadow_detected, shadow_frame_viz, detection_type = self.detect_fish_shadow(
                        shadow_frame, self.reference_shadow_frame
                    )
                else:
                    shadow_detected = False
                    shadow_frame_viz = shadow_frame
                    detection_type = "none"
                
                # Update last frames
                self.last_exclamation_frame = exclamation_frame.copy()
                if not waiting_for_fish:
                    self.last_shadow_frame = shadow_frame.copy()
                
                # Logic for fishing
                current_time = time.time()
                if exclamation_detected and (current_time - self.last_detection_time) > self.detection_cooldown:
                    self.last_detection_time = current_time
                    self.detection_count += 1
                    waiting_for_fish = False
                    
                    # Update UI from the main thread
                    self.root.after(0, lambda: self.detection_label.config(text=f"Detections: {self.detection_count}"))
                    self.root.after(0, lambda: self.status_label.config(text="Exclamation detected!"))
                    
                    # Start the action sequence
                    self.in_action_sequence = True
                    self.action_sequence_step = 0
                    # Execute first action immediately
                    self._process_action_sequence()
                    
                elif shadow_detected and not waiting_for_fish and (current_time - self.last_detection_time) > self.detection_cooldown:
                    if detection_type == "shadow":
                        waiting_for_fish = True
                        self.root.after(0, lambda: self.status_label.config(text="Fish shadow detected!"))
                
                # Control loop speed - sleep to reduce CPU usage
                time.sleep(0.03)
                
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Fishing error: {e}"))
        finally:
            # Make sure flags are reset
            self.is_running = False
            self.in_action_sequence = False
            
            # Update UI from the main thread
            self.root.after(0, lambda: self.start_stop_button.config(text="Start Fishing"))
            self.root.after(0, lambda: self.pause_resume_button.config(state=tk.DISABLED, text="Pause"))
            self.root.after(0, lambda: self.status_label.config(text="Stopped"))
    
    def _process_action_sequence(self):
        """Process the current step in the action sequence"""
        if not self.in_action_sequence or self.action_sequence_step >= len(self.action_sequence):
            self.in_action_sequence = False
            self.action_sequence_step = 0
            return
        
        # Get the current action
        action = self.action_sequence[self.action_sequence_step]
        
        # Execute the action based on type
        action_type = action["action"]
        
        if action_type == "press_f":
            self.key_sender.send_key('f')
            self.root.after(0, lambda: self.status_label.config(text="Pressing F"))
        elif action_type == "press_esc":
            self.key_sender.send_key('esc')
            self.root.after(0, lambda: self.status_label.config(text="Pressing ESC"))
        elif action_type == "wait":
            # Update status to show we're waiting
            self.root.after(0, lambda: self.status_label.config(text=f"Waiting {action['delay']}s"))
        
        # Wait for the specified delay
        time.sleep(action["delay"])
        
        # Move to next step
        self.action_sequence_step += 1
        
        # If we've reached the end, exit the sequence
        if self.action_sequence_step >= len(self.action_sequence):
            self.in_action_sequence = False
            self.root.after(0, lambda: self.status_label.config(text="Running"))
    
    def detect_exclamation_mark(self, frame, reference_frame):
        """Detect the exclamation mark using frame differencing and contour detection"""
        if reference_frame is None:
            return False, frame
        
        # Convert to grayscale for faster processing
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_reference = cv2.cvtColor(reference_frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate absolute difference to detect changes
        frame_diff = cv2.absdiff(gray_frame, gray_reference)
        
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
                    # Draw rectangle for visualization
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, "!", (x+w//2-5, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    return True, frame
        
        return False, frame
    
    def detect_fish_shadow(self, frame, reference_frame):
        """Detect fish shadows and bouncy bait in water"""
        if reference_frame is None:
            return False, frame, "none"
        
        # Convert to grayscale for faster processing
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_reference = cv2.cvtColor(reference_frame, cv2.COLOR_BGR2GRAY)
        
        # Calculate absolute difference to detect motion
        frame_diff = cv2.absdiff(gray_frame, gray_reference)
        
        # Apply threshold for motion detection
        _, thresh = cv2.threshold(frame_diff, self.shadow_threshold, 255, cv2.THRESH_BINARY)
        
        # Find contours for motion
        motion_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # For fish shadow detection - look for darker regions
        # Apply blur for noise reduction
        blurred = cv2.GaussianBlur(gray_frame, (9, 9), 0)
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
                    # Draw rectangle for visualization
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
                    cv2.putText(frame, "Bait", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
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
                    # Draw rectangle for visualization
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                    cv2.putText(frame, "Shadow", (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                    return True, frame, "shadow"
        
        return False, frame, "none"
    
    def update_preview(self):
        """Update the preview image in the UI"""
        try:
            # Check if frames exist
            if self.last_exclamation_frame is not None and self.last_shadow_frame is not None:
                # Resize for display
                ex_height, ex_width = self.last_exclamation_frame.shape[:2]
                sh_height, sh_width = self.last_shadow_frame.shape[:2]
                
                # Calculate scaling to fit within preview area
                preview_width = 400  # Width for each preview image
                
                ex_scale = preview_width / ex_width
                sh_scale = preview_width / sh_width
                
                ex_display = cv2.resize(self.last_exclamation_frame, (preview_width, int(ex_height * ex_scale)))
                sh_display = cv2.resize(self.last_shadow_frame, (preview_width, int(sh_height * sh_scale)))
                
                # Add labels
                cv2.putText(ex_display, "Exclamation Region", (10, 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(sh_display, "Shadow/Bait Region", (10, 20), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                # Add status
                status = "RUNNING" if self.is_running and not self.is_paused else "PAUSED" if self.is_paused else "IDLE"
                
                if self.in_action_sequence:
                    status = f"ACTION ({self.action_sequence_step+1}/{len(self.action_sequence)})"
                
                cv2.putText(ex_display, status, (10, ex_display.shape[0]-10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
                
                # Combine horizontally
                combined = np.hstack((ex_display, sh_display))
                
                # Convert BGR to RGB for tkinter
                rgb_image = cv2.cvtColor(combined, cv2.COLOR_BGR2RGB)
                
                # Convert to PhotoImage
                image = Image.fromarray(rgb_image)
                photo = ImageTk.PhotoImage(image=image)
                
                # Update label
                self.preview_label.config(image=photo)
                self.preview_label.image = photo  # Keep a reference to prevent garbage collection
            else:
                # If frames don't exist yet, just create a blank image
                blank = np.zeros((300, 800, 3), dtype=np.uint8)
                cv2.putText(blank, "No preview available - click 'Capture Reference Frames'", (100, 150), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
                
                # Convert to PhotoImage
                rgb_image = cv2.cvtColor(blank, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(rgb_image)
                photo = ImageTk.PhotoImage(image=image)
                
                # Update label
                self.preview_label.config(image=photo)
                self.preview_label.image = photo
        except Exception as e:
            print(f"Error updating preview: {e}")
        
        # Schedule the next update
        self.root.after(100, self.update_preview)

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoFisherUI(root)
    root.mainloop() 