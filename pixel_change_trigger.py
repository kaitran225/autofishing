import numpy as np
import keyboard
import time
import threading
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import win32gui
import win32con
import win32process
import win32api
import ctypes
import psutil
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import queue
import datetime
from PIL import ImageGrab, Image
import cv2

# For direct key simulation and window focus
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Special key constants
VK_F = 0x46  # Virtual key code for 'F'
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

# Window focus constants
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040

# Input type for SendInput
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_short),
        ("wParamH", ctypes.c_ushort)
    ]

class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("ii", INPUT_UNION)
    ]

# Helper functions for window focus and key press
def force_focus_window(hwnd):
    """Force focus on a window using multiple methods"""
    try:
        if not hwnd or not win32gui.IsWindow(hwnd):
            print("Invalid window handle")
            return False
            
        # Try to bring window to foreground
        if win32gui.IsIconic(hwnd):  # If minimized
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.1)
            
        # Get window thread process ID
        current_thread = kernel32.GetCurrentThreadId()
        target_thread, _ = win32process.GetWindowThreadProcessId(hwnd)
        
        # Attach threads to ensure focus change permission
        user32.AttachThreadInput(current_thread, target_thread, True)
        
        # Set the window position to top-most temporarily
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                             win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
        time.sleep(0.05)
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                             win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
        
        # Multiple focus attempts
        user32.SetForegroundWindow(hwnd)
        user32.SetFocus(hwnd)
        user32.BringWindowToTop(hwnd)
        
        # Force active window
        user32.SwitchToThisWindow(hwnd, True)
        
        # Detach threads
        user32.AttachThreadInput(current_thread, target_thread, False)
        
        # Alt keypress can help with focus
        keyboard.press_and_release('alt')
        time.sleep(0.05)
        
        # One more foreground window attempt
        user32.SetForegroundWindow(hwnd)
        
        # Verify focus
        active_window = user32.GetForegroundWindow()
        result = (active_window == hwnd)
        print(f"Focus result: {result}, Active window: {win32gui.GetWindowText(active_window)}")
        return result
    except Exception as e:
        print(f"Error forcing focus: {e}")
        return False

# Use this function with key presses
def direct_key_press(key_char):
    """Press a key using multiple methods"""
    try:
        # First method - direct keyboard hook
        keyboard.press(key_char)
        time.sleep(0.05)
        keyboard.release(key_char)
        
        # Second method - Send virtual key code directly
        vk_code = ord(key_char.upper())
        win32api.keybd_event(vk_code, 0, 0, 0)  # key down
        time.sleep(0.05)
        win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)  # key up
        
        # Third method - PostMessage to active window
        active_window = user32.GetForegroundWindow()
        if active_window:
            win32gui.PostMessage(active_window, win32con.WM_KEYDOWN, vk_code, 0)
            time.sleep(0.05)
            win32gui.PostMessage(active_window, win32con.WM_KEYUP, vk_code, 0)
            
        return True
    except Exception as e:
        print(f"Error with direct key press: {e}")
        return False

# Main application classes will be implemented next 

class PixelChangeDetectorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Play Together Pixel Change Detector")
        self.root.geometry("700x600")
        self.root.resizable(True, True)
        
        # Create message queue for logging
        self.log_queue = queue.Queue()
        
        # Initialize detector
        self.detector = None
        self.is_running = False
        
        # Pixel visualization data
        self.change_history = []
        
        # Create GUI elements
        self.create_widgets()
        
        # Setup detector after widgets
        self.detector = PixelChangeDetector(self.log_queue)
        self.detector.gui = self
        
        # Setup periodic updates
        self.update_logs()
        
    def log(self, message):
        """Add timestamped message to log queue"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_queue.put(f"[{timestamp}] {message}") 
        
    def create_widgets(self):
        # Style configuration
        style = ttk.Style()
        style.configure('TButton', padding=5)
        style.configure('TLabel', padding=5)
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel for controls
        left_panel = ttk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        
        # Right panel for visualization
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Top control panel
        self.control_frame = ttk.LabelFrame(left_panel, text="Controls", padding="10")
        self.control_frame.pack(fill=tk.X, pady=5)
        
        # Status label
        self.status_label = ttk.Label(self.control_frame, text="Status: Not Running", font=('Arial', 10))
        self.status_label.grid(row=0, column=0, columnspan=2, pady=5, sticky=tk.W)
        
        # Region size input
        size_frame = ttk.Frame(self.control_frame)
        size_frame.grid(row=1, column=0, columnspan=4, pady=5, sticky=tk.W)
        
        ttk.Label(size_frame, text="Region Size (pixels):").pack(side=tk.LEFT, padx=(0, 5))
        self.size_var = tk.StringVar(value="50")
        self.size_entry = ttk.Entry(size_frame, textvariable=self.size_var, width=6)
        self.size_entry.pack(side=tk.LEFT)
        
        # Threshold slider
        ttk.Label(self.control_frame, text="Change Threshold:").grid(row=2, column=0, sticky=tk.W)
        self.threshold_var = tk.DoubleVar(value=0.05)  # Default threshold for pixel change
        self.threshold_slider = ttk.Scale(self.control_frame, from_=0.01, to=0.5, 
                                        variable=self.threshold_var, orient=tk.HORIZONTAL, length=200)
        self.threshold_slider.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        self.threshold_label = ttk.Label(self.control_frame, text="0.05")
        self.threshold_label.grid(row=2, column=2, padx=5)
        self.threshold_slider.config(command=self.update_threshold_label)
        
        # Region selection
        region_frame = ttk.Frame(self.control_frame)
        region_frame.grid(row=3, column=0, columnspan=4, pady=5, sticky=tk.W)
        
        ttk.Label(region_frame, text="Monitoring Region:").grid(row=0, column=0, sticky=tk.W)
        self.region_button = ttk.Button(region_frame, text="Select Region", command=self.select_region)
        self.region_button.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        self.reset_region_button = ttk.Button(region_frame, text="Reset to Full Screen", command=self.reset_region)
        self.reset_region_button.grid(row=0, column=2, padx=5, sticky=tk.W)
        
        # Add region info label 
        self.region_info_label = ttk.Label(self.control_frame, text="No region selected (monitoring full screen)")
        self.region_info_label.grid(row=4, column=0, columnspan=4, padx=5, sticky=tk.W)
        
        # Training mode 
        self.training_var = tk.BooleanVar(value=False)
        training_check = ttk.Checkbutton(self.control_frame, text="Training Mode", 
                                        variable=self.training_var,
                                        command=self.toggle_training_mode)
        training_check.grid(row=1, column=3, padx=10)
        
        # Start/Stop buttons
        button_frame = ttk.Frame(self.control_frame)
        button_frame.grid(row=5, column=0, columnspan=4, pady=5)
        
        self.start_button = ttk.Button(button_frame, text="Start Detection", command=self.start_detection)
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop Detection", command=self.stop_detection, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)
        
        self.capture_button = ttk.Button(button_frame, text="Capture Reference", command=self.capture_reference)
        self.capture_button.grid(row=0, column=2, padx=5)
        
        # Detection count
        self.detection_count = 0
        self.count_label = ttk.Label(self.control_frame, text="Detections: 0")
        self.count_label.grid(row=6, column=0, columnspan=3, pady=5, sticky=tk.W)
        
        # Log console
        log_frame = ttk.LabelFrame(left_panel, text="Console Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.log_console = scrolledtext.ScrolledText(log_frame, height=10, width=40)
        self.log_console.pack(fill=tk.BOTH, expand=True)
        
        # Visualization frame
        viz_frame = ttk.LabelFrame(right_panel, text="Visual Monitoring", padding="10")
        viz_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create matplotlib figure for visualization
        self.fig = plt.Figure(figsize=(6, 6), dpi=100)
        
        # Current frame subplot
        self.current_ax = self.fig.add_subplot(311)
        self.current_ax.set_title("Current Frame")
        self.current_image = self.current_ax.imshow(np.zeros((100, 100, 3)), cmap='gray')
        
        # Difference frame subplot
        self.diff_ax = self.fig.add_subplot(312)
        self.diff_ax.set_title("Difference Frame")
        self.diff_image = self.diff_ax.imshow(np.zeros((100, 100)), cmap='hot')
        
        # Change history subplot
        self.change_ax = self.fig.add_subplot(313)
        self.change_ax.set_title("Change Percentage History")
        self.change_ax.axhline(y=0.05, color='r', linestyle='--', alpha=0.5)  # Threshold line
        self.change_line, = self.change_ax.plot(np.zeros(100))
        self.change_ax.set_ylim(0, 0.5)
        
        self.fig.tight_layout()
        
        # Embed figure in tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, viz_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
    def update_threshold_label(self, value=None):
        self.threshold_label.config(text=f"{float(self.threshold_var.get()):.2f}")
        
    def toggle_training_mode(self):
        """Toggle training mode on/off"""
        is_training = self.training_var.get()
        if is_training:
            self.log("Training mode ENABLED - Detection will not trigger key presses")
        else:
            self.log("Training mode DISABLED - Detection will trigger key presses")
            
    def update_logs(self):
        """Process any new log messages from the queue"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_console.insert(tk.END, message + "\n")
                self.log_console.see(tk.END)  # Auto-scroll to end
        except queue.Empty:
            pass
        
        # Update visualization if running
        if self.is_running and self.detector:
            self.update_visualization()
            
        # Schedule next update
        self.root.after(100, self.update_logs)
        
    def update_visualization(self):
        """Update the visualization with current frames"""
        # Update current frame
        if hasattr(self.detector, 'color_frame') and self.detector.color_frame is not None:
            # Use color frame if available
            self.current_image.set_data(self.detector.color_frame)
        elif hasattr(self.detector, 'current_frame') and self.detector.current_frame is not None:
            # Fallback to grayscale
            self.current_image.set_data(self.detector.current_frame)
            
        # Update difference frame
        if hasattr(self.detector, 'diff_frame') and self.detector.diff_frame is not None:
            # Make a copy to avoid modifying the original
            diff_display = self.detector.diff_frame.copy()
            
            # Enhance contrast for better visibility
            # Scale up differences that are above the detection threshold (typically 30)
            diff_display = cv2.convertScaleAbs(diff_display, alpha=2)
            
            # Apply color map for visualization
            colored_diff = cv2.applyColorMap(diff_display, cv2.COLORMAP_JET)
            
            # Highlight significant changes (over threshold) with white outlines
            if hasattr(self.detector, 'current_frame') and self.detector.current_frame is not None:
                # Find contours of significant changes
                significant_changes = (self.detector.diff_frame > 30).astype(np.uint8) * 255
                contours, _ = cv2.findContours(significant_changes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # Draw contours on the colored diff image
                cv2.drawContours(colored_diff, contours, -1, (255, 255, 255), 1)
            
            # Convert from BGR to RGB for display in matplotlib
            colored_diff = cv2.cvtColor(colored_diff, cv2.COLOR_BGR2RGB)
            
            # Update the display
            self.diff_image.set_data(colored_diff)
            
            # Update title with current change percentage
            if hasattr(self.detector, 'change_history') and len(self.detector.change_history) > 0:
                latest_change = self.detector.change_history[-1]
                self.diff_ax.set_title(f"Difference Frame (Change: {latest_change:.2%})")
                
            # Reset axes limits to match the image
            self.diff_ax.set_xlim(0, colored_diff.shape[1])
            self.diff_ax.set_ylim(colored_diff.shape[0], 0)  # Invert Y for proper image display
            
        # Update change history plot
        if hasattr(self.detector, 'change_history'):
            history = self.detector.change_history[-100:] if len(self.detector.change_history) > 0 else [0]
            self.change_line.set_ydata(history)
            self.change_line.set_xdata(np.arange(len(history)))
            self.change_ax.set_xlim(0, len(history))
            
            # Update threshold line
            for line in self.change_ax.get_lines():
                if line.get_linestyle() == '--':
                    line.set_ydata([self.detector.THRESHOLD, self.detector.THRESHOLD])
            
        # Redraw canvas
        self.fig.tight_layout()
        self.canvas.draw_idle()
        
    def update_status(self, message):
        self.status_label.config(text=f"Status: {message}")
        self.root.update()
        
    def select_region(self):
        """Allow the user to select a region of the screen to monitor"""
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
            
        self.log("Starting region selection - click to place the region")
        
        # Calculate region dimensions based on 1.5:1 ratio
        width = int(size * 1.5)
        height = size
        
        # Temporarily minimize our own window
        self.root.iconify()
        time.sleep(0.5)  # Give time for window to minimize
        
        # Create a fullscreen transparent window for selection
        selection_window = tk.Toplevel(self.root)
        selection_window.attributes('-fullscreen', True)
        selection_window.attributes('-alpha', 0.3)  # Set transparency
        selection_window.attributes('-topmost', True)
        
        # Create canvas for drawing the selection rectangle
        canvas = tk.Canvas(selection_window, cursor="cross", bg="grey")
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Variables to track selection rectangle
        preview_rect = None
        
        def update_preview(event):
            nonlocal preview_rect
            
            # Calculate region coordinates centered on mouse position
            left = event.x - width // 2
            top = event.y - height // 2
            right = left + width
            bottom = top + height
            
            # Ensure region stays within screen bounds
            screen_width = selection_window.winfo_screenwidth()
            screen_height = selection_window.winfo_screenheight()
            
            if left < 0:
                left = 0
                right = width
            elif right > screen_width:
                right = screen_width
                left = right - width
                
            if top < 0:
                top = 0
                bottom = height
            elif bottom > screen_height:
                bottom = screen_height
                top = bottom - height
            
            # Create or update preview rectangle
            if preview_rect:
                canvas.delete(preview_rect)
            preview_rect = canvas.create_rectangle(
                left, top, right, bottom,
                outline="red", width=2,
                fill="red", stipple="gray50"  # Semi-transparent fill
            )
            
            # Update size label position
            size_label.place(x=event.x + 10, y=event.y + 10)
        
        def on_mouse_click(event):
            nonlocal preview_rect
            
            # Calculate region coordinates centered on click
            left = event.x - width // 2
            top = event.y - height // 2
            right = left + width
            bottom = top + height
            
            # Ensure region stays within screen bounds
            screen_width = selection_window.winfo_screenwidth()
            screen_height = selection_window.winfo_screenheight()
            
            if left < 0:
                left = 0
                right = width
            elif right > screen_width:
                right = screen_width
                left = right - width
                
            if top < 0:
                top = 0
                bottom = height
            elif bottom > screen_height:
                bottom = screen_height
                top = bottom - height
            
            # Create final rectangle
            if preview_rect:
                canvas.delete(preview_rect)
            preview_rect = canvas.create_rectangle(
                left, top, right, bottom,
                outline="red", width=2,
                fill="red", stipple="gray50"
            )
            
            # Close selection window
            selection_window.destroy()
            
            # Set region in detector
            if self.detector:
                self.detector.region = (left, top, right, bottom)
                self.log(f"Region selected: {self.detector.region} ({width}x{height})")
                
                # Update UI to show selected region
                self.update_region_label()
            
            # Restore main window
            self.root.deiconify()
        
        # Create size label
        size_label = tk.Label(
            canvas,
            text=f"{width}x{height}",
            font=("Arial", 10),
            bg="white",
            fg="black"
        )
        
        # Bind mouse events
        canvas.bind("<Motion>", update_preview)  # Update preview on mouse move
        canvas.bind("<ButtonPress-1>", on_mouse_click)
        
        # Instructions label
        instructions = tk.Label(
            canvas, 
            text=f"Move mouse to preview region ({width}x{height} pixels, 1.5:1 ratio), click to place, ESC to cancel", 
            font=("Arial", 16), 
            bg="white"
        )
        instructions.place(relx=0.5, rely=0.05, anchor=tk.CENTER)
        
        # Handle ESC key to cancel
        def on_escape(event):
            selection_window.destroy()
            self.root.deiconify()
            self.log("Region selection cancelled")
        
        selection_window.bind("<Escape>", on_escape)
    
    def update_region_label(self):
        """Update the UI to show the selected region"""
        if hasattr(self, 'region_info_label'):
            if self.detector and self.detector.region:
                left, top, right, bottom = self.detector.region
                width = right - left
                height = bottom - top
                self.region_info_label.config(
                    text=f"Selected region: ({left}, {top}) to ({right}, {bottom}), {width}x{height} pixels"
                )
            else:
                self.region_info_label.config(text="No region selected (monitoring full screen)")
        else:
            # Create the label if it doesn't exist
            self.region_info_label = ttk.Label(self.control_frame, text="No region selected (monitoring full screen)")
            self.region_info_label.grid(row=4, column=0, columnspan=4, padx=5, sticky=tk.W)
        
    def capture_reference(self):
        """Capture a reference frame for comparison"""
        if self.detector and hasattr(self.detector, 'capture_reference'):
            self.detector.capture_reference()
            self.log("Reference frame captured")
        else:
            self.log("Detector not initialized properly")
            
    def start_detection(self):
        try:
            if not self.detector:
                self.detector = PixelChangeDetector(self.log_queue)
                self.detector.gui = self
                
            self.detector.THRESHOLD = self.threshold_var.get()
            self.detector.training_mode = self.training_var.get()
            self.log(f"Starting detection with threshold: {self.detector.THRESHOLD}")
            
            self.is_running = True
            self.detector.start_detection()
            
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.update_status("Running")
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.log(f"Error starting detection: {str(e)}")
    
    def stop_detection(self):
        self.is_running = False
        if self.detector:
            self.detector.stop_detection()
        self.log("Detection stopped")
        
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.update_status("Stopped")
        
    def increment_detection_count(self):
        self.detection_count += 1
        self.count_label.config(text=f"Detections: {self.detection_count}")
        self.log(f"Detection #{self.detection_count} triggered")

    def reset_region(self):
        """Reset to monitor the full screen"""
        if self.detector:
            self.detector.region = None
            self.log("Reset to monitoring full screen")
            self.update_region_label()

class PixelChangeDetector:
    def __init__(self, log_queue=None):
        self.THRESHOLD = 0.05  # Default threshold for pixel change
        self.is_running = False
        self.log_queue = log_queue
        self.gui = None
        self.training_mode = False
        
        # Screen capture region (default to full screen)
        self.region = None  # (left, top, right, bottom)
        
        # Initialize visualization data
        self.current_frame = None
        self.previous_frame = None
        self.reference_frame = None
        self.diff_frame = None
        self.change_history = []
        
        # Last detection time for cooldown
        self.last_detection_time = 0
        self.detection_cooldown = 0.5  # Reduced from 2.0 to 0.5 seconds
        
        # Capture interval in seconds
        self.capture_interval = 0.05  # Reduced from 0.1 to 0.05 seconds
        
        # Play Together window tracking
        self.play_together_window = None
        self.play_together_pid = None
        
        # Key code
        self.F_KEY = 0x46  # F key virtual key code
        
        # Health check variables
        self.last_successful_capture = 0
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.health_check_interval = 5  # seconds
        self.last_health_check = 0
        
    def log(self, message):
        """Log a message to the queue if it exists"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted_message = f"[{timestamp}] {message}"
        if self.log_queue:
            self.log_queue.put(formatted_message)
        print(formatted_message)
        
    def reset_state(self):
        """Reset detector state to handle recovery"""
        self.current_frame = None
        self.previous_frame = None
        self.reference_frame = None
        self.diff_frame = None
        self.change_history = []
        self.last_detection_time = 0
        self.consecutive_failures = 0
        self.last_successful_capture = 0
        
    def perform_health_check(self):
        """Check detector health and attempt recovery if needed"""
        current_time = time.time()
        
        # Only perform health check every health_check_interval seconds
        if current_time - self.last_health_check < self.health_check_interval:
            return True
            
        self.last_health_check = current_time
        
        # Check if we've had too many consecutive failures
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.log("Too many consecutive failures, attempting recovery...")
            self.reset_state()
            
            # Try to recapture reference frame
            self.capture_reference()
            
            # Reset failure counter
            self.consecutive_failures = 0
            return True
            
        # Check if we haven't had a successful capture in a while
        if current_time - self.last_successful_capture > self.health_check_interval * 2:
            self.log("No successful captures detected, attempting recovery...")
            self.reset_state()
            self.capture_reference()
            return True
            
        return True
        
    def find_play_together_process(self):
        """Find Play Together process ID and window handle"""
        # List of possible name variations
        name_variations = [
            'play together',
            'playtogether',
            'play-together',
            'play_together',
            'playtogether.exe',
            'play together.exe', 
            'play together game',
            'playtogether game'
        ]
        
        # Explicitly exclude our own detector window
        excluded_titles = ['play together pixel change detector', 'pixel change detector']
        
        # Find process ID first
        found_pid = False
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                process_name = proc.info['name'].lower()
                if any(variation in process_name for variation in name_variations):
                    self.play_together_pid = proc.info['pid']
                    self.log(f"Found Play Together process: {process_name} (PID: {self.play_together_pid})")
                    found_pid = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        # Find window handle using EnumWindows
        def enum_window_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd).lower()
                
                # Skip our own detector window
                if any(excluded in window_text for excluded in excluded_titles):
                    return True
                
                try:
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    
                    # Check if window belongs to our process
                    if self.play_together_pid and found_pid == self.play_together_pid:
                        self.play_together_window = hwnd
                        self.log(f"Found Play Together window: {window_text} (HWND: {hwnd})")
                        return False
                except Exception:
                    pass
                    
                # Or check by window title - but be more strict about matching
                if any(variation == window_text or 
                       window_text.startswith(f"{variation} ") or
                       window_text.endswith(f" {variation}") or
                       f" {variation} " in window_text
                       for variation in name_variations):
                    self.play_together_window = hwnd
                    self.log(f"Found Play Together window by title: {window_text} (HWND: {hwnd})")
                    return False
            return True
            
        win32gui.EnumWindows(enum_window_callback, None)
        
        # If no Play Together window was found, log it clearly
        if not self.play_together_window:
            self.log("No Play Together window found. Please make sure the Play Together application is running.")
        
        return self.play_together_window is not None
            
    def focus_play_together_window(self):
        """Optimized window focus method"""
        if not self.play_together_window and not self.find_play_together_process():
            return False
                
        try:
            if not win32gui.IsWindow(self.play_together_window):
                if not self.find_play_together_process():
                    return False
                
            # Quick focus attempt using SetForegroundWindow
            user32.SetForegroundWindow(self.play_together_window)
            time.sleep(0.05)  # Reduced delay
            
            # Verify focus
            if user32.GetForegroundWindow() == self.play_together_window:
                return True
                
            # If quick focus failed, try enhanced method
            return force_focus_window(self.play_together_window)
            
        except Exception as e:
            self.log(f"Error focusing window: {e}")
            return False

    def send_f_key(self):
        """Optimized key press method"""
        try:
            # Single quick focus check
            if user32.GetForegroundWindow() != self.play_together_window:
                self.focus_play_together_window()
                time.sleep(0.05)  # Reduced delay
            
            # Use most reliable method first - SendInput
            kb_input = INPUT()
            kb_input.type = INPUT_KEYBOARD
            kb_input.ii.ki.wVk = 0x46  # VK_F
            kb_input.ii.ki.wScan = 0
            kb_input.ii.ki.dwFlags = 0
            kb_input.ii.ki.time = 0
            kb_input.ii.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
            
            # Press and release in quick succession
            user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
            time.sleep(0.01)  # Minimal delay
            kb_input.ii.ki.dwFlags = KEYEVENTF_KEYUP
            user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
            
            # Backup method - direct keyboard
            keyboard.press_and_release('f')
            
            return True
            
        except Exception as e:
            self.log(f"Error with key simulation: {e}")
            return False

    def send_esc_key(self):
        """Optimized key press method for ESC key"""
        try:
            # Single quick focus check
            if user32.GetForegroundWindow() != self.play_together_window:
                self.focus_play_together_window()
                time.sleep(0.05)  # Reduced delay
            
            # Use most reliable method first - SendInput
            kb_input = INPUT()
            kb_input.type = INPUT_KEYBOARD
            kb_input.ii.ki.wVk = 0x1B  # VK_ESCAPE
            kb_input.ii.ki.wScan = 0
            kb_input.ii.ki.dwFlags = 0
            kb_input.ii.ki.time = 0
            kb_input.ii.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
            
            # Press and release in quick succession
            user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
            time.sleep(0.01)  # Minimal delay
            kb_input.ii.ki.dwFlags = KEYEVENTF_KEYUP
            user32.SendInput(1, ctypes.byref(kb_input), ctypes.sizeof(INPUT))
            
            # Backup method - direct keyboard
            keyboard.press_and_release('esc')
            
            return True
            
        except Exception as e:
            self.log(f"Error with ESC key simulation: {e}")
            return False

    def capture_screen(self):
        """Capture the screen or region of interest"""
        try:
            if self.region:
                # Validate region size
                left, top, right, bottom = self.region
                width = right - left
                height = bottom - top
                
                if width < 10 or height < 10:
                    self.log("Invalid region size detected. Resetting to full screen.")
                    self.region = None
                    screenshot = ImageGrab.grab()
                else:
                    # Capture specific region
                    screenshot = ImageGrab.grab(bbox=self.region)
                    
                    # Log first capture for debugging
                    if self.current_frame is None:
                        self.log(f"Capturing selected region: {self.region} ({width}x{height})")
            else:
                # Capture full screen
                screenshot = ImageGrab.grab()
                
            # Convert to numpy array for processing
            frame = np.array(screenshot)
            
            # Validate frame
            if frame.size == 0:
                self.log("Error: Captured frame is empty")
                self.consecutive_failures += 1
                return None
                
            # Store color frame for visualization
            self.color_frame = frame.copy() if len(frame.shape) == 3 else None
            
            # Convert to grayscale for processing
            if len(frame.shape) == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            
            # Update health check variables
            self.last_successful_capture = time.time()
            self.consecutive_failures = 0
            return frame
            
        except Exception as e:
            self.log(f"Error capturing screen: {e}")
            self.consecutive_failures += 1
            # Reset to full screen on error
            self.region = None
            return None
            
    def calculate_frame_difference(self, frame1, frame2):
        """Calculate the difference between two frames"""
        if frame1 is None or frame2 is None:
            return None, 0
            
        # Ensure frames have same dimensions
        if frame1.shape != frame2.shape:
            # Resize to match
            frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
            
        # Calculate absolute difference
        diff_frame = cv2.absdiff(frame1, frame2)
        
        # Calculate percentage of pixels that changed significantly
        # Consider a pixel changed if its difference is greater than 30 (out of 255)
        changed_pixels = np.sum(diff_frame > 30)
        total_pixels = frame1.shape[0] * frame1.shape[1]
        change_percent = changed_pixels / total_pixels
        
        return diff_frame, change_percent
    
    def capture_reference(self):
        """Capture a reference frame for comparison"""
        self.reference_frame = self.capture_screen()
        if self.reference_frame is not None:
            self.log(f"Reference frame captured: {self.reference_frame.shape}")
        else:
            self.log("Failed to capture reference frame")
            
    def start_detection(self):
        if not self.find_play_together_process():
            return
            
        self.is_running = True
        self.change_history = []
        
        # Capture initial frame as reference if none exists
        if self.reference_frame is None:
            self.capture_reference()
            
        self.previous_frame = self.reference_frame
        
        detection_thread = threading.Thread(target=self._detection_loop)
        detection_thread.daemon = True
        detection_thread.start()
        
    def stop_detection(self):
        self.is_running = False
        
    def _detection_loop(self):
        while self.is_running:
            try:
                # Perform health check
                if not self.perform_health_check():
                    time.sleep(0.1)
                    continue
                
                # Capture current frame
                self.current_frame = self.capture_screen()
                
                if self.current_frame is None:
                    time.sleep(self.capture_interval)
                    continue
                    
                # Use reference frame if available, otherwise use previous frame
                compare_frame = self.reference_frame if self.reference_frame is not None else self.previous_frame
                
                if compare_frame is None:
                    self.capture_reference()
                    time.sleep(self.capture_interval)
                    continue
                
                # Calculate difference
                self.diff_frame, change_percent = self.calculate_frame_difference(self.current_frame, compare_frame)
                
                # Store in history
                self.change_history.append(change_percent)
                if len(self.change_history) > 1000:
                    self.change_history = self.change_history[-1000:]
                
                # Check for detection with cooldown
                current_time = time.time()
                if change_percent > self.THRESHOLD and (current_time - self.last_detection_time) > self.detection_cooldown:
                    change_percent_display = round(change_percent * 100, 2)
                    self.log(f"Major pixel change detected! Change: {change_percent_display}%")
                    self.last_detection_time = current_time
                    
                    # Update UI in the main thread
                    if self.gui:
                        self.gui.root.after(0, self.gui.increment_detection_count)
                    
                    # Skip key press if in training mode
                    if self.training_mode:
                        self.log("Training mode active - skipping key press")
                    else:
                        # Quick focus and key press
                        if self.focus_play_together_window():
                            self.send_f_key()
                            
                            # Capture new reference frame after detection
                            time.sleep(0.2)  # Reduced from 1.0 to 0.2 seconds
                        else:
                            self.log("Failed to focus window, skipping key press")
                    
                    # Pause detection for 5 seconds after detection
                    self.log("Pausing detection for 5 seconds...")
                    time.sleep(2)
                    # Wait 3 seconds
                    time.sleep(3)
                    if self.is_running:
                        if self.gui:
                            self.gui.root.after(0, lambda: self.gui.update_status(f"Paused: {int(3 - (time.time() - pause_start))}s remaining"))
                    
                    # Press ESC after 3 seconds
                    if self.is_running:
                        self.log("Pressing ESC key...")
                        if self.focus_play_together_window():
                            self.send_esc_key()
                        else:
                            self.log("Failed to focus window, skipping ESC key press")
                    
                    # Wait 2 seconds
                    time.sleep(2)
                    
                    # Press F key
                    if self.is_running:
                        self.log("Pressing F key...")
                        if self.focus_play_together_window():
                            self.send_f_key()
                            # Capture new reference frame after F key press
                            time.sleep(0.2)  # Wait for screen to update
                        else:
                            self.log("Failed to focus window, skipping F key press")
                    
                    # Complete remaining pause time
                    time.sleep(0.5)
                    
                    if self.gui:
                        self.gui.root.after(0, lambda: self.gui.update_status("Running"))
                    
                    time.sleep(2)
                    continue
                
                # Store current frame as previous for next comparison if not using reference
                if self.reference_frame is None:
                    self.previous_frame = self.current_frame
                
                # Sleep to control capture rate
                time.sleep(self.capture_interval)
                
            except Exception as e:
                self.log(f"Error in detection loop: {e}")
                self.consecutive_failures += 1
                time.sleep(0.05)  # Reduced from 0.1 to 0.05 seconds

def main():
    root = tk.Tk()
    app = PixelChangeDetectorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 