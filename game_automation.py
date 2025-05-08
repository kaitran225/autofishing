import pyautogui
import cv2
import numpy as np
import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import threading
import win32gui
import win32con
import win32process
import win32api
import ctypes
import statistics
import queue

# --- CYBERPUNK THEME COLORS ---
BG_BLACK = '#101014'         # 70% black
NEON_PURPLE = '#a259ff'     # 20% neon purple
MATCHA_GREEN = '#b6ff68'    # 10% matcha green
CARD_BG = '#181828'
CARD_BORDER = NEON_PURPLE
GLOW_SHADOW = NEON_PURPLE

class GameAutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Game Automation Tool")
        self.root.configure(bg=BG_BLACK)
        self.root.geometry("900x700")
        self.root.minsize(700, 500)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # Variables
        self.is_capturing = False
        self.detection_zone = None  # (x1, y1, x2, y2) in canvas coords
        self.button_location = None  # (x, y) in canvas coords
        self.capture_thread = None
        self.initial_state = None
        self.difference_threshold = 30
        self.selected_window = None
        self.window_list = []
        self.zone_rect = None
        self.resize_handles = []
        self.active_handle = None
        self.last_x = None
        self.last_y = None
        self.handle_size = 7
        self.window_border = None
        self.client_rect = None
        self.current_frame = None
        self.last_capture_time = 0
        self.capture_interval = 0.01
        self.last_click_time = 0
        self.click_cooldown = 0.1
        self.click_sequence = 0
        self.sequence_start_time = 0
        self.canvas_width = 600
        self.canvas_height = 340
        self.detection_state = 'Idle'
        self.current_difference = 0
        self.current_brightness = 0
        self.detection_queue = queue.Queue()
        self.detection_thread = None
        self.stop_event = threading.Event()
        
        # --- STYLES ---
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=BG_BLACK)
        style.configure('Card.TFrame', background=CARD_BG, borderwidth=2, relief='ridge')
        style.configure('TLabel', background=BG_BLACK, foreground=NEON_PURPLE, font=('Orbitron', 11, 'bold'))
        style.configure('Card.TLabel', background=CARD_BG, foreground=NEON_PURPLE, font=('Orbitron', 11, 'bold'))
        style.configure('Accent.TLabel', background=BG_BLACK, foreground=MATCHA_GREEN, font=('Orbitron', 12, 'bold'))
        style.configure('TButton', background=NEON_PURPLE, foreground=BG_BLACK, font=('Orbitron', 10, 'bold'), borderwidth=0, focusthickness=3, focuscolor=MATCHA_GREEN)
        style.map('TButton', background=[('active', MATCHA_GREEN)])
        style.configure('TCombobox', fieldbackground=BG_BLACK, background=BG_BLACK, foreground=NEON_PURPLE, font=('Orbitron', 10))
        
        # --- LAYOUT ---
        self.main_frame = ttk.Frame(self.root, padding=10, style='Card.TFrame')
        self.main_frame.grid(row=0, column=0, sticky='nsew')
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Window selection
        self.window_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        self.window_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=4)
        self.window_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(self.window_frame, text="Select Window:", style='Card.TLabel').pack(side=tk.LEFT, padx=4)
        self.window_combo = ttk.Combobox(self.window_frame, width=28)
        self.window_combo.pack(side=tk.LEFT, padx=4)
        self.window_combo.bind('<<ComboboxSelected>>', self.on_window_select)
        self.refresh_button = ttk.Button(self.window_frame, text="⟳", width=2, command=self.refresh_windows)
        self.refresh_button.pack(side=tk.LEFT, padx=4)
        self.focus_button = ttk.Button(self.window_frame, text="Focus", width=6, command=self.focus_selected_window)
        self.focus_button.pack(side=tk.LEFT, padx=4)
        
        # Main Preview (top, full width)
        self.canvas = tk.Canvas(self.main_frame, width=self.canvas_width, height=self.canvas_height, bg=BG_BLACK, highlightthickness=4, bd=0, highlightbackground=NEON_PURPLE)
        self.canvas.grid(row=1, column=0, columnspan=2, sticky='nsew', pady=(10, 6), padx=10)
        
        # Initial/Current Previews (below, side by side)
        self.subpreview_frame = ttk.Frame(self.main_frame, style='Card.TFrame')
        self.subpreview_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=2)
        self.subpreview_frame.grid_columnconfigure(0, weight=1)
        self.subpreview_frame.grid_columnconfigure(1, weight=1)
        self.initial_preview = tk.Canvas(self.subpreview_frame, width=220, height=120, bg=BG_BLACK, highlightthickness=2, bd=0, highlightbackground=NEON_PURPLE)
        self.initial_preview.grid(row=0, column=0, padx=8, sticky='ew')
        self.current_preview = tk.Canvas(self.subpreview_frame, width=220, height=120, bg=BG_BLACK, highlightthickness=2, bd=0, highlightbackground=NEON_PURPLE)
        self.current_preview.grid(row=0, column=1, padx=8, sticky='ew')
        ttk.Label(self.subpreview_frame, text="Initial", style='Card.TLabel').grid(row=1, column=0, sticky=tk.N)
        ttk.Label(self.subpreview_frame, text="Current", style='Card.TLabel').grid(row=1, column=1, sticky=tk.N)
        
        # Controls (below previews)
        self.control_card = ttk.Frame(self.main_frame, style='Card.TFrame', padding=10)
        self.control_card.grid(row=3, column=0, columnspan=2, sticky='ew', pady=10)
        self.start_button = ttk.Button(self.control_card, text="▶ Start", width=10, command=self.toggle_capture)
        self.start_button.grid(row=0, column=0, padx=6, pady=4)
        self.set_zone_button = ttk.Button(self.control_card, text="✎ Edit Zone", width=10, command=self.set_detection_zone)
        self.set_zone_button.grid(row=0, column=1, padx=6, pady=4)
        self.set_button_button = ttk.Button(self.control_card, text="🎯 Set Button", width=10, command=self.set_button_location)
        self.set_button_button.grid(row=0, column=2, padx=6, pady=4)
        self.capture_initial_button = ttk.Button(self.control_card, text="⏺ Capture State", width=14, command=self.capture_initial_state)
        self.capture_initial_button.grid(row=0, column=3, padx=6, pady=4)
        self.threshold_minus = ttk.Button(self.control_card, text="-", width=2, command=lambda: self.adjust_threshold(-5))
        self.threshold_minus.grid(row=0, column=4, padx=2)
        self.threshold_value = ttk.Label(self.control_card, text=str(self.difference_threshold), style='Accent.TLabel')
        self.threshold_value.grid(row=0, column=5, padx=2)
        self.threshold_plus = ttk.Button(self.control_card, text="+", width=2, command=lambda: self.adjust_threshold(5))
        self.threshold_plus.grid(row=0, column=6, padx=2)
        
        # Ambience/Data Panel (below controls)
        self.data_card = ttk.Frame(self.main_frame, style='Card.TFrame', padding=10)
        self.data_card.grid(row=4, column=0, columnspan=2, sticky='ew', pady=6)
        self.state_label = ttk.Label(self.data_card, text="Detection: Idle", style='Card.TLabel')
        self.state_label.grid(row=0, column=0, sticky=tk.W)
        self.diff_label = ttk.Label(self.data_card, text="Difference: 0", style='Card.TLabel')
        self.diff_label.grid(row=1, column=0, sticky=tk.W)
        self.bright_label = ttk.Label(self.data_card, text="Brightness: 0", style='Card.TLabel')
        self.bright_label.grid(row=2, column=0, sticky=tk.W)
        self.zone_label = ttk.Label(self.data_card, text="Zone: -", style='Card.TLabel')
        self.zone_label.grid(row=3, column=0, sticky=tk.W)
        self.button_label = ttk.Label(self.data_card, text="Button: -", style='Card.TLabel')
        self.button_label.grid(row=4, column=0, sticky=tk.W)
        
        # Status (bottom, matcha green)
        self.status_label = ttk.Label(self.main_frame, text="Status: Ready", style='Accent.TLabel')
        self.status_label.grid(row=5, column=0, columnspan=2, pady=8)
        
        # Responsive weights
        for i in range(6):
            self.main_frame.grid_rowconfigure(i, weight=0)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)
        
        # Init
        self.refresh_windows()
        self.update_preview()
        self.poll_detection_queue()

    def create_resize_handles(self, x1, y1, x2, y2):
        """Create resize handles for the detection zone"""
        # Delete existing handles
        for handle in self.resize_handles:
            self.canvas.delete(handle)
        self.resize_handles = []
        
        # Create handles at corners and midpoints
        handle_positions = [
            (x1, y1, 'nw'),  # Northwest
            (x2, y1, 'ne'),  # Northeast
            (x2, y2, 'se'),  # Southeast
            (x1, y2, 'sw'),  # Southwest
            ((x1 + x2) / 2, y1, 'n'),  # North
            (x2, (y1 + y2) / 2, 'e'),  # East
            ((x1 + x2) / 2, y2, 's'),  # South
            (x1, (y1 + y2) / 2, 'w')   # West
        ]
        
        for x, y, pos in handle_positions:
            handle = self.canvas.create_rectangle(
                x - self.handle_size, y - self.handle_size,
                x + self.handle_size, y + self.handle_size,
                fill='white', outline='black', tags=('handle', pos)
            )
            self.resize_handles.append(handle)

    def get_handle_at_position(self, x, y):
        """Get the resize handle at the given position"""
        for handle in self.resize_handles:
            coords = self.canvas.coords(handle)
            if coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                return handle, self.canvas.gettags(handle)[1]
        return None, None

    def start_resize(self, event):
        """Start resizing the detection zone"""
        handle, position = self.get_handle_at_position(event.x, event.y)
        if handle:
            self.active_handle = (handle, position)
            self.last_x = event.x
            self.last_y = event.y
        else:
            # Start moving the entire box
            coords = self.canvas.coords(self.zone_rect)
            if coords[0] <= event.x <= coords[2] and coords[1] <= event.y <= coords[3]:
                self.active_handle = ('move', None)
                self.last_x = event.x
                self.last_y = event.y

    def resize_zone(self, event):
        """Resize or move the detection zone"""
        if not self.active_handle:
            return
            
        dx = event.x - self.last_x
        dy = event.y - self.last_y
        
        coords = self.canvas.coords(self.zone_rect)
        x1, y1, x2, y2 = coords
        
        if self.active_handle[0] == 'move':
            # Move the entire box
            self.canvas.move(self.zone_rect, dx, dy)
            for handle in self.resize_handles:
                self.canvas.move(handle, dx, dy)
        else:
            # Resize based on handle position
            position = self.active_handle[1]
            if 'n' in position: y1 = event.y
            if 's' in position: y2 = event.y
            if 'w' in position: x1 = event.x
            if 'e' in position: x2 = event.x
            
            # Ensure minimum size
            min_size = self.handle_size * 3
            if x2 - x1 < min_size:
                if 'w' in position: x1 = x2 - min_size
                if 'e' in position: x2 = x1 + min_size
            if y2 - y1 < min_size:
                if 'n' in position: y1 = y2 - min_size
                if 's' in position: y2 = y1 + min_size
            
            # Update rectangle
            self.canvas.coords(self.zone_rect, x1, y1, x2, y2)
            # Update handles
            self.create_resize_handles(x1, y1, x2, y2)
        
        self.last_x = event.x
        self.last_y = event.y
        
        # Update detection zone coordinates
        self.detection_zone = (int(x1), int(y1), int(x2), int(y2))

    def end_resize(self, event):
        """End resizing the detection zone"""
        self.active_handle = None
        self.last_x = None
        self.last_y = None

    def get_window_list(self):
        """Get list of visible windows"""
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    windows.append((hwnd, title))
            return True
        
        windows = []
        win32gui.EnumWindows(callback, windows)
        return windows
    
    def refresh_windows(self):
        """Refresh the window list"""
        self.window_list = self.get_window_list()
        self.window_combo['values'] = [title for _, title in self.window_list]
        if self.window_combo['values']:
            self.window_combo.set(self.window_combo['values'][0])
            self.on_window_select(None)
    
    def on_window_select(self, event):
        """Handle window selection"""
        selected_title = self.window_combo.get()
        for hwnd, title in self.window_list:
            if title == selected_title:
                self.selected_window = hwnd
                # Get window position and client area
                self.get_window_client_rect(hwnd)
                self.status_label.config(text=f"Status: Selected window: {title}")
                break
    
    def focus_selected_window(self):
        """Manually focus the selected window"""
        if not self.selected_window:
            self.status_label.config(text="Status: Error - No window selected!")
            return
            
        try:
            # Get the window's process ID
            _, process_id = win32process.GetWindowThreadProcessId(self.selected_window)
            
            # Get the current process ID
            current_process_id = win32api.GetCurrentProcessId()
            
            # If the window belongs to a different process, we need to use a different approach
            if process_id != current_process_id:
                # Try to use Alt+Tab simulation
                self.simulate_alt_tab()
            else:
                # For windows in our process, we can try to force focus
                win32gui.ShowWindow(self.selected_window, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self.selected_window)
            
            self.status_label.config(text="Status: Window focus requested - please click the target window")
        except Exception as e:
            self.status_label.config(text=f"Status: Error focusing window - {str(e)}")

    def simulate_alt_tab(self):
        """Simulate Alt+Tab to switch windows"""
        try:
            # Press Alt
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # Alt key down
            time.sleep(0.1)
            
            # Press Tab
            ctypes.windll.user32.keybd_event(0x09, 0, 0, 0)  # Tab key down
            time.sleep(0.1)
            
            # Release Tab
            ctypes.windll.user32.keybd_event(0x09, 0, 0x0002, 0)  # Tab key up
            time.sleep(0.1)
            
            # Release Alt
            ctypes.windll.user32.keybd_event(0x12, 0, 0x0002, 0)  # Alt key up
        except Exception as e:
            print(f"Error simulating Alt+Tab: {str(e)}")

    def get_window_client_rect(self, hwnd):
        """Get the client area rectangle of a window"""
        try:
            # Get the window's client area
            client_rect = win32gui.GetClientRect(hwnd)
            # Get the window's position
            window_rect = win32gui.GetWindowRect(hwnd)
            
            # Calculate border sizes
            border_left = client_rect[0] - window_rect[0]
            border_top = client_rect[1] - window_rect[1]
            border_right = window_rect[2] - client_rect[2]
            border_bottom = window_rect[3] - client_rect[3]
            
            self.window_border = (border_left, border_top, border_right, border_bottom)
            self.client_rect = client_rect
            
            return client_rect
        except Exception as e:
            print(f"Error getting client rect: {str(e)}")
            return None

    def get_window_screenshot(self):
        """Capture screenshot of selected window"""
        if not self.selected_window:
            return None
        
        try:
            # Get window position and ensure window is not minimized
            if win32gui.IsIconic(self.selected_window):
                win32gui.ShowWindow(self.selected_window, win32con.SW_RESTORE)
            
            # Get client area rectangle
            client_rect = self.get_window_client_rect(self.selected_window)
            if not client_rect:
                return None
            
            # Get window position
            window_rect = win32gui.GetWindowRect(self.selected_window)
            
            # Calculate client area position
            x = window_rect[0] + self.window_border[0]
            y = window_rect[1] + self.window_border[1]
            width = client_rect[2] - client_rect[0]
            height = client_rect[3] - client_rect[1]
            
            # Capture screenshot
            screenshot = pyautogui.screenshot(region=(x, y, width, height))
            return screenshot
        except Exception as e:
            print(f"Error capturing window: {str(e)}")
            return None
    
    def adjust_threshold(self, delta):
        """Adjust the threshold value"""
        self.difference_threshold = max(0, min(100, self.difference_threshold + delta))
        self.threshold_value.config(text=str(self.difference_threshold))
        self.status_label.config(text=f"Status: Threshold set to {self.difference_threshold}")

    def update_ambience_data(self):
        # Update detection state
        self.state_label.config(text=f"Detection: {self.detection_state}")
        self.diff_label.config(text=f"Difference: {self.current_difference:.2f}")
        self.bright_label.config(text=f"Brightness: {self.current_brightness:.1f}")
        if self.detection_zone:
            x1, y1, x2, y2 = self.detection_zone
            zx1, zy1 = self.canvas_to_window(x1, y1)
            zx2, zy2 = self.canvas_to_window(x2, y2)
            self.zone_label.config(text=f"Zone: ({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}) [canvas] / ({zx1},{zy1},{zx2},{zy2}) [win]")
        else:
            self.zone_label.config(text="Zone: -")
        if self.button_location:
            bx, by = self.button_location
            bxw, byw = self.canvas_to_window(bx, by)
            self.button_label.config(text=f"Button: ({bx:.0f},{by:.0f}) [canvas] / ({bxw},{byw}) [win]")
        else:
            self.button_label.config(text="Button: -")

    def update_preview(self):
        """Update the canvas with current screen capture"""
        if not self.is_capturing:
            current_time = time.time()
            if current_time - self.last_capture_time >= self.capture_interval:
                screenshot = self.get_window_screenshot()
                if screenshot:
                    # Calculate aspect ratio
                    window_ratio = screenshot.width / screenshot.height
                    canvas_ratio = self.canvas_width / self.canvas_height
                    
                    if window_ratio > canvas_ratio:
                        new_width = self.canvas_width
                        new_height = int(self.canvas_width / window_ratio)
                    else:
                        new_height = self.canvas_height
                        new_width = int(self.canvas_height * window_ratio)
                    
                    # Resize screenshot maintaining aspect ratio
                    screenshot = screenshot.resize((new_width, new_height))
                    
                    # Create new image with black background
                    background = Image.new('RGB', (self.canvas_width, self.canvas_height), 'black')
                    # Paste screenshot in center
                    background.paste(screenshot, ((self.canvas_width-new_width)//2, (self.canvas_height-new_height)//2))
                    
                    self.photo = ImageTk.PhotoImage(background)
                    self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)
                    
                    # Update current state preview if detection zone exists
                    if self.detection_zone:
                        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
                        x1, y1, x2, y2 = self.detection_zone
                        try:
                            cropped = frame[int(y1):int(y2), int(x1):int(x2)]
                            current_gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
                            current_preview = Image.fromarray(current_gray)
                            current_preview = current_preview.resize((220, 120))
                            self.current_photo = ImageTk.PhotoImage(current_preview)
                            self.current_preview.create_image(0, 0, image=self.current_photo, anchor=tk.NW)
                        except Exception as e:
                            print(f"Error updating current preview: {str(e)}")
                    
                    # Redraw detection zone and handles if they exist
                    if self.zone_rect:
                        self.canvas.tag_raise(self.zone_rect)
                        for handle in self.resize_handles:
                            self.canvas.tag_raise(handle)
                
                self.last_capture_time = current_time
            
            self.update_ambience_data()
            self.root.after(50, self.update_preview)

    def capture_initial_state(self):
        """Capture the initial state of the detection zone"""
        if not self.detection_zone:
            self.status_label.config(text="Status: Error - Set detection zone first!")
            return
        
        try:
            # Capture the initial state
            screenshot = self.get_window_screenshot()
            if screenshot is None:
                self.status_label.config(text="Status: Error - No window selected!")
                return
            
            # Convert to numpy array and then to grayscale
            frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
            
            # Crop to detection zone
            x1, y1, x2, y2 = self.detection_zone
            cropped = frame[int(y1):int(y2), int(x1):int(x2)]
            self.initial_state = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            
            # Update initial state preview
            initial_preview = Image.fromarray(self.initial_state)
            initial_preview = initial_preview.resize((220, 120))
            self.initial_photo = ImageTk.PhotoImage(initial_preview)
            self.initial_preview.create_image(0, 0, image=self.initial_photo, anchor=tk.NW)
            
            self.status_label.config(text="Status: Initial state captured!")
            
        except Exception as e:
            self.status_label.config(text=f"Status: Error capturing initial state - {str(e)}")
    
    def calculate_difference(self, frame):
        """Calculate the difference between current frame and initial state"""
        if self.initial_state is None:
            return 0
        
        try:
            # Crop current frame to detection zone
            x1, y1, x2, y2 = self.detection_zone
            cropped = frame[int(y1):int(y2), int(x1):int(x2)]
            
            # Convert to grayscale
            current_gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            
            # Ensure same size
            if current_gray.shape != self.initial_state.shape:
                current_gray = cv2.resize(current_gray, (self.initial_state.shape[1], self.initial_state.shape[0]))
            
            # Calculate absolute difference
            diff = cv2.absdiff(current_gray, self.initial_state)
            
            # Calculate mean difference
            mean_diff = np.mean(diff)
            
            # After calculating diff:
            self.current_difference = mean_diff
            # Calculate brightness
            if current_gray.size > 0:
                self.current_brightness = np.mean(current_gray)
            else:
                self.current_brightness = 0
            
            return mean_diff
        except Exception as e:
            print(f"Error calculating difference: {str(e)}")
            return 0
    
    def set_detection_zone(self):
        """Enable editing of the detection zone"""
        if not self.selected_window:
            self.status_label.config(text="Status: Error - Select a window first!")
            return
            
        self.status_label.config(text="Status: Click and drag to create/edit detection zone")
        
        # If no zone exists, create one
        if not self.zone_rect:
            self.start_draw_zone(tk.Event())
        
        # Always enable resizing
        self.canvas.bind("<Button-1>", self.start_resize)
        self.canvas.bind("<B1-Motion>", self.resize_zone)
        self.canvas.bind("<ButtonRelease-1>", self.end_resize)

    def start_draw_zone(self, event):
        """Start drawing detection zone"""
        # Clear existing zone and handles
        if self.zone_rect:
            self.canvas.delete(self.zone_rect)
            for handle in self.resize_handles:
                self.canvas.delete(handle)
        
        # Create initial zone in the center of the canvas
        if not hasattr(event, 'x'):
            x = self.canvas_width // 2
            y = self.canvas_height // 2
        else:
            x = event.x
            y = event.y
        
        self.zone_start_x = x
        self.zone_start_y = y
        self.zone_rect = self.canvas.create_rectangle(
            x-50, y-50,
            x+50, y+50,
            outline='red', width=2
        )
        
        # Create resize handles
        self.create_resize_handles(x-50, y-50, x+50, y+50)
        
        # Store detection zone coordinates
        self.detection_zone = (int(x-50), int(y-50), int(x+50), int(y+50))
        
        # Update bindings for resizing
        self.canvas.bind("<Button-1>", self.start_resize)
        self.canvas.bind("<B1-Motion>", self.resize_zone)
        self.canvas.bind("<ButtonRelease-1>", self.end_resize)

    def set_button_location(self):
        """Set the button location by clicking on the canvas"""
        if not self.selected_window:
            self.status_label.config(text="Status: Error - Select a window first!")
            return
            
        self.status_label.config(text="Status: Click to set button location")
        self.canvas.bind("<Button-1>", self.set_button)
    
    def set_button(self, event):
        """Set the button location"""
        self.button_location = (event.x, event.y)
        self.canvas.create_oval(
            event.x-5, event.y-5,
            event.x+5, event.y+5,
            fill='green', outline='green'
        )
        self.status_label.config(text=f"Status: Button location set: {self.button_location}")
        self.canvas.unbind("<Button-1>")
    
    def toggle_capture(self):
        """Start/Stop the capture and detection process"""
        if not self.is_capturing:
            self.is_capturing = True
            self.start_button.config(text="■ Stop")
            self.detection_state = 'Detecting'
            self.stop_event.clear()
            self.detection_thread = threading.Thread(target=self.capture_and_detect_thread, daemon=True)
            self.detection_thread.start()
            self.canvas.config(highlightbackground=MATCHA_GREEN)  # Neon border when active
        else:
            self.is_capturing = False
            self.start_button.config(text="▶ Start")
            self.detection_state = 'Idle'
            self.stop_event.set()
            if self.detection_thread:
                self.detection_thread.join(timeout=1)
            self.canvas.config(highlightbackground=NEON_PURPLE)

    def capture_and_detect_thread(self):
        while not self.stop_event.is_set():
            try:
                # ... detection logic, do NOT update UI here ...
                # Instead, put results in the queue:
                # self.detection_queue.put({'difference': diff, 'brightness': bright, ...})
                # For example:
                # self.detection_queue.put({'difference': 42, 'brightness': 88, 'state': 'Detecting'})
                pass  # Replace with actual detection logic
            except Exception as e:
                self.detection_queue.put({'error': str(e)})
                break

    def poll_detection_queue(self):
        try:
            while True:
                result = self.detection_queue.get_nowait()
                if 'error' in result:
                    self.status_label.config(text=f"Error: {result['error']}")
                    self.toggle_capture()
                else:
                    # Update UI with detection results
                    self.current_difference = result.get('difference', self.current_difference)
                    self.current_brightness = result.get('brightness', self.current_brightness)
                    self.detection_state = result.get('state', self.detection_state)
                    self.update_ambience_data()
        except queue.Empty:
            pass
        self.root.after(50, self.poll_detection_queue)

    # --- COORDINATE MAPPING ---
    def canvas_to_window(self, x, y):
        """Map canvas coordinates to window client area coordinates"""
        if not self.selected_window or not self.client_rect:
            return 0, 0
        client_w = self.client_rect[2] - self.client_rect[0]
        client_h = self.client_rect[3] - self.client_rect[1]
        scale_x = client_w / self.canvas_width
        scale_y = client_h / self.canvas_height
        return int(x * scale_x), int(y * scale_y)

    def window_to_canvas(self, x, y):
        """Map window client area coordinates to canvas coordinates"""
        if not self.selected_window or not self.client_rect:
            return 0, 0
        client_w = self.client_rect[2] - self.client_rect[0]
        client_h = self.client_rect[3] - self.client_rect[1]
        scale_x = self.canvas_width / client_w
        scale_y = self.canvas_height / client_h
        return int(x * scale_x), int(y * scale_y)

def main():
    root = tk.Tk()
    app = GameAutomationGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 