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
import matplotlib.collections
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import queue
import datetime
from PIL import ImageGrab, Image
import cv2
from tkinter import font as tkfont  # For custom fonts
import mss
import mss.tools

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
        self.root.title("Pixel Change Detector")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        self.root.resizable(True, True)
        
        # Set app icon and configure style
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
        
        # Create GUI elements
        self.create_widgets()
        
        # Setup detector after widgets
        self.detector = PixelChangeDetector(self.log_queue)
        self.detector.gui = self
        
        # Setup periodic updates
        self.update_logs()
        
    def configure_style(self):
        """Configure the app style with a matcha and oak wood inspired theme, and consistent font size everywhere."""
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
        small_font = tkfont.Font(family="Segoe UI", size=9)
        heading_font = tkfont.Font(family="Segoe UI", size=11, weight="bold")
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
        """Add timestamped message to log queue in minimal format"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")
        
    def create_widgets(self):
        """Create all GUI widgets with modern minimal terminal design"""
        # Main container with minimal padding
        main_container = ttk.Frame(self.root, padding="8", style='TFrame')
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Split into left and right panels - removing top status area
        panel_container = ttk.Frame(main_container, style='TFrame')
        panel_container.pack(fill=tk.BOTH, expand=True)
        
        # Left control panel (fixed width)
        left_panel = ttk.Frame(panel_container, width=360, style='TFrame')
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left_panel.pack_propagate(False)  # Fix the width
        
        # Right visualization panel (expanding)
        right_panel = ttk.Frame(panel_container, style='TFrame')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Section 1: Detection Settings
        settings_frame = ttk.LabelFrame(left_panel, text="SETTINGS", style='Terminal.TLabelframe')
        settings_frame.pack(fill=tk.X, pady=(0, 8), padx=0)
        
        # --- Refined Settings UI ---
        # Use a two-column grid for better layout (labels left, widgets right)
        settings_grid = ttk.Frame(settings_frame, style='Term.TFrame')
        settings_grid.pack(fill=tk.X, padx=4, pady=4)

        # Threshold (row 0)
        ttk.Label(settings_grid, text="Threshold", style='Term.TLabel',font=('Segoe UI', 10)).grid(row=0, column=0, sticky='w', padx=(0, 8), pady=2)
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
            length=120,
            font=('Segoe UI', 10)
        )
        self.threshold_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.threshold_label = ttk.Label(threshold_frame, text="0.05", width=5, style='Term.TLabel',font=('Segoe UI', 10))
        self.threshold_label.pack(side=tk.LEFT, padx=(8, 0))

        # Region Size (row 1)
        ttk.Label(settings_grid, text="Region Size", style='Term.TLabel',font=('Segoe UI', 10)).grid(row=1, column=0, sticky='w', padx=(0, 8), pady=2)
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
            relief="flat",
            font=('Segoe UI', 10)
        )
        self.size_entry.pack(side=tk.LEFT)
        ttk.Label(region_size_frame, text="px", style='Term.TLabel',font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=(4, 0))

        # Cooldown (row 2)
        ttk.Label(settings_grid, text="Cooldown", style='Term.TLabel',font=('Segoe UI', 10)).grid(row=2, column=0, sticky='w', padx=(0, 8), pady=2)
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
            relief="flat",
            font=('Segoe UI', 10)
        )
        self.cooldown_entry.pack(side=tk.LEFT)
        ttk.Label(cooldown_frame, text="sec", style='Term.TLabel',font=('Segoe UI', 10)).pack(side=tk.LEFT, padx=(4, 0))

        # Fishing Key (row 3)
        ttk.Label(settings_grid, text="Fishing Key", style='Term.TLabel',font=('Segoe UI', 10)).grid(row=3, column=0, sticky='w', padx=(0, 8), pady=2)
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
            relief="flat",
            font=('Segoe UI', 10)
        )
        self.fishing_key_entry.pack(side=tk.LEFT)

        # Apply Settings button (bottom right, span both columns)
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
            padx=4,
            pady=4,
            font=('Segoe UI', 10)
        )
        apply_button.pack(pady=(0, 8), padx=4, anchor='e')
        # --- End refined Settings UI ---
        
        # Section 2: Region Selection (now only info, no button)
        region_frame = ttk.LabelFrame(left_panel, text="MONITORING", style='Terminal.TLabelframe')
        region_frame.pack(fill=tk.X, pady=(0, 0), padx=(4 , 0))

        # System status and detections count (moved from visualization)
        self.status_label = ttk.Label(region_frame, text="System: monitor.idle", style='Monitor.Status.TLabel',font=('Segoe UI', 16))
        self.status_label.pack(fill=tk.X, pady=(2, 2), padx=8)

        # --- Stats details in two columns ---
        self.stats_frame = ttk.Frame(region_frame, style='Term.TFrame')
        self.stats_frame.pack(fill=tk.X, pady=(2, 2), padx=8)
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
            l = ttk.Label(self.stats_frame, text=f"{label}: ...", style='Term.TLabel',font=('Segoe UI', 10))
            l.grid(row=row, column=col, sticky='w', pady=1, padx=8)
            self.stats_labels[key] = l

        # Section 3: Control Buttons (now includes select-region)
        control_frame = ttk.LabelFrame(left_panel, text="CONTROL", style='Terminal.TLabelframe')
        control_frame.pack(fill=tk.X, pady=(0, 8), padx=0)
        button_frame = ttk.Frame(control_frame, style='Term.TFrame')
        button_frame.pack(fill=tk.X, pady=4)
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
            pady=5,
                        font=('Segoe UI', 10)  # Updated to more modern font
        )
        self.start_button.pack(side=tk.LEFT, padx=(5, 5))
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
            disabledforeground='grey',
                        font=('Segoe UI', 10)  # Updated to more modern font
        )
        self.stop_button.pack(side=tk.LEFT, padx=(0, 5))
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
            disabledforeground='grey',
                        font=('Segoe UI', 10)  # Updated to more modern font
        )
        self.pause_button.pack(side=tk.LEFT, padx=(0, 5))

 # Clear logs button
        self.clear_button = tk.Button(
            button_frame, 
            text="clear-logs",
            command=self.clear_logs,
            bg=self.colors['bg_dark'],
            fg=self.colors['text_dim'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['text'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=5,  # Reduced padding
            font=('Segoe UI', 10)  # Updated to more modern font
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
            padx=10,
            pady=5,  # Reduced padding
            font=('Segoe UI', 10)  # Updated to more modern font
        )
        self.ref_button.pack(side=tk.LEFT, padx=(5, 5))

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
            pady=5,
                        font=('Segoe UI', 10)  # Updated to more modern font
        )
        self.region_button.pack(fill=tk.X,padx=(0, 5))
        
        # Configure visualization panel
        viz_frame = ttk.LabelFrame(right_panel, text="VISUALIZATION", style='Terminal.TLabelframe')
        viz_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create matplotlib figure for monitoring
        self.create_monitoring_figure(viz_frame)
        
        # Create status bar at the bottom of the visualization for detection count and status
        self.status_frame = ttk.Frame(viz_frame, style='Term.TFrame')
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=8, pady=4)
        
        
        # --- Move log display here, under visualization ---
        log_frame = ttk.LabelFrame(right_panel, text="LOGS", style='Terminal.TLabelframe')
        log_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 0), padx=0)
        self.log_console = scrolledtext.ScrolledText(
            log_frame,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            font=('Consolas', 9),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,  # Remove highlighting
            padx=8,
            pady=8
        )
        self.log_console.pack(fill=tk.BOTH, expand=True)
        self.log_console.vbar.configure(
            troughcolor=self.colors['bg_dark'],
            background=self.colors['bg_dark'],
            activebackground=self.colors['border_light'],
            borderwidth=0,
            width=8,
            relief="flat"
        )
        # --- End move log display ---
    
    def blink_cursor(self):
        """Create a blinking cursor effect for the terminal style"""
        self.cursor_visible = not self.cursor_visible
        self.cursor_label.config(text="_" if self.cursor_visible else " ")
        self.root.after(500, self.blink_cursor)  # Blink every half second
        
    def create_monitoring_figure(self, parent_frame, aspect_ratio=1.5):
        """Create the monitoring visualization with minimal command-line style, with dynamic aspect ratio."""
        import matplotlib
        plt.rcParams['font.family'] = 'Segoe UI'
        plt.rcParams['font.size'] = 10
        # Create frame for matplotlib with border - updated border
        viz_content_frame = ttk.Frame(parent_frame, style='Border.TFrame')
        viz_content_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        canvas_frame = ttk.Frame(viz_content_frame, style='Term.TFrame')
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        # Use a more compact figure size, and set aspect ratio
        fig_width = 5  # inches
        fig_height = max(3, fig_width / aspect_ratio)
        self.fig = plt.Figure(figsize=(fig_width, fig_height), dpi=100, facecolor=self.colors['bg_dark'])
        gs = plt.GridSpec(1, 1, figure=self.fig, left=0.05, right=0.95, top=0.95, bottom=0.15)
        self.current_ax = self.fig.add_subplot(gs[0])
        self.current_image = self.current_ax.imshow(np.zeros((100, 150, 3)), cmap='gray', aspect='auto')
        self.diff_overlay = self.current_ax.imshow(np.zeros((100, 150, 4)), alpha=0.5, aspect='auto')
        self.current_ax.set_xticks([])
        self.current_ax.set_yticks([])
        self.current_ax.set_facecolor(self.colors['bg_dark'])
        self.current_ax.axis('off')
        rect = plt.Rectangle((0, 0), 1, 1, fill=False, ec=self.colors['border_light'], linewidth=1.5, transform=self.current_ax.transAxes, clip_on=False)
        self.current_ax.add_patch(rect)
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
        for spine in self.timeline_ax.spines.values():
            spine.set_visible(False)
        self.timeline_ax.set_yticks([0, 0.5, 1])
        self.timeline_ax.set_yticklabels(['0', '', '1'])
        self.timeline_ax.tick_params(axis='y', colors=self.colors['text_dim'], labelsize=6)
        self.timeline_ax.text(0.5, 0.5, "ACTIVITY", color=self.colors['green'], fontsize=7, ha='center', va='center', transform=self.timeline_ax.transAxes, alpha=0.7, fontfamily='Segoe UI')
        self.canvas = FigureCanvasTkAgg(self.fig, canvas_frame)
        self.canvas.get_tk_widget().configure(bg=self.colors['bg_dark'], highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self.fig.text(0.5, 0.5, "awaiting data", color=self.colors['text_dim'], fontsize=10, ha='center', va='center', fontfamily='Segoe UI')

    def update_monitoring_aspect(self):
        """Update the aspect ratio of the monitoring view to match the selected region, in-place."""
        if self.detector and self.detector.region:
            left, top, right, bottom = self.detector.region
            width = right - left
            height = bottom - top
            if width > 0 and height > 0:
                aspect = width / height
                # Update the figure size to match the new aspect ratio
                fig_width = 5
                fig_height = max(3, fig_width / aspect)
                self.fig.set_size_inches(fig_width, fig_height, forward=True)
                self.canvas.draw_idle()

    def set_status_indicator(self, status):
        """Update the status indicator in minimal terminal style"""
        if status == "running":
            self.status_label.config(text="System: monitor.active", style="Running.Status.TLabel")
        elif status == "stopped":
            self.status_label.config(text="System: monitor.stopped", style="Stopped.Status.TLabel")
        elif status == "paused":
            self.status_label.config(text="System: monitor.paused", style="Paused.Status.TLabel")
        else:
            # Default to just updating the text
            self.status_label.config(text=f"System: monitor.{status}", style="Status.TLabel")
        
    def update_threshold_label(self, value=None):
        """Update threshold label and apply to detector if it exists"""
        threshold_value = float(self.threshold_var.get())
        self.threshold_label.config(text=f"{threshold_value:.2f}")
        
        # Update detector threshold if it exists
        if hasattr(self, 'detector') and self.detector is not None:
            self.detector.THRESHOLD = threshold_value
            self.log(f"Detection threshold updated to {threshold_value:.2f}")
            
            # Show suggested values based on current threshold
            if threshold_value < 0.03:
                self.log("Current threshold is very sensitive - may cause false positives")
            elif threshold_value > 0.2:
                self.log("Current threshold is not very sensitive - may miss subtle changes")
        
    def update_logs(self):
        """Process any new log messages from the queue and update stats in real time"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_console.insert(tk.END, message + "\n")
                self.log_console.see(tk.END)  # Auto-scroll to end
        except queue.Empty:
            pass

        # Update stats in real time
        self.show_stats()

        # Update visualization if running
        if self.is_running and self.detector:
            self.update_visualization()
            
        # Schedule next update
        self.root.after(100, self.update_logs)
        
    def update_visualization(self):
        """Update the visualization with current frames in minimal style"""
        try:
            # Clear any initial status text
            for txt in self.fig.texts:
                txt.remove()
            # Update current frame
            if hasattr(self.detector, 'color_frame') and self.detector.color_frame is not None:
                self.current_image.set_data(self.detector.color_frame)
                # self.current_ax.set_aspect('auto')  # Only set on the axes, not the image
                self.current_ax.axis('off')
            elif hasattr(self.detector, 'current_frame') and self.detector.current_frame is not None:
                gray_display = cv2.cvtColor(self.detector.current_frame, cv2.COLOR_GRAY2RGB)
                self.current_image.set_data(gray_display)
                # self.current_ax.set_aspect('auto')
                self.current_ax.axis('off')
            # Create overlay for difference frame
            if hasattr(self.detector, 'diff_frame') and self.detector.diff_frame is not None:
                diff_display = self.detector.diff_frame.copy()
                diff_display = cv2.convertScaleAbs(diff_display, alpha=3)
                diff_colored = cv2.applyColorMap(diff_display, cv2.COLORMAP_INFERNO)
                colored_diff = cv2.cvtColor(diff_colored, cv2.COLOR_BGR2RGB)
                colored_diff_alpha = np.zeros((colored_diff.shape[0], colored_diff.shape[1], 4), dtype=np.uint8)
                colored_diff_alpha[..., :3] = colored_diff
                alpha_threshold = 30
                for i in range(diff_display.shape[0]):
                    for j in range(diff_display.shape[1]):
                        if diff_display[i, j] > alpha_threshold:
                            colored_diff_alpha[i, j, 3] = min(255, int(diff_display[i, j] * 2))
                        else:
                            colored_diff_alpha[i, j, 3] = 0
                self.diff_overlay.set_data(colored_diff_alpha)
                # self.diff_overlay.set_aspect('auto')  # REMOVE THIS LINE
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
                                         color=self.colors['green'], fontsize=8, fontweight='normal')
            
            # Redraw canvas
            self.canvas.draw_idle()
        except Exception as e:
            self.log(f"Error updating visualization: {e}")
        
    def increment_detection_count(self):
        """Increment detection counter and update UI"""
        self.detection_count += 1
        self.count_label.config(text=f"detections: {self.detection_count}")
        
        # Add minimal timeline marker at the detection point
        if hasattr(self.detector, 'change_history') and len(self.detector.change_history) > 0:
            idx = len(self.detector.change_history) - 1
            if idx >= 0 and hasattr(self, 'timeline_ax'):
                # Remove any previous markers
                for artist in self.timeline_ax.get_lines():
                    if hasattr(artist, 'detection_marker'):
                        artist.remove()
                
                # Add vertical line marker
                marker = self.timeline_ax.axvline(
                    x=idx if idx < 100 else 99, 
                    color=self.colors['alert'], 
                    linewidth=1, 
                    alpha=0.7
                )
                setattr(marker, 'detection_marker', True)
                
                # Add dot marker
                y_val = self.activity_line.get_ydata()[idx if idx < 100 else 99]
                dot = self.timeline_ax.plot(
                    idx if idx < 100 else 99, 
                    y_val, 
                    'o', 
                    color=self.colors['success'], 
                    markersize=4
                )[0]
                setattr(dot, 'detection_marker', True)
                
                # Schedule removal after a delay
                self.root.after(2000, lambda: self._clean_markers())
                
    def show_stats(self):
        """Update stats details in the MONITORING section in real time (called from update_logs)"""
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
    
    def _clean_markers(self):
        """Remove detection markers from timeline"""
        if hasattr(self, 'timeline_ax'):
            for artist in self.timeline_ax.get_lines():
                if hasattr(artist, 'detection_marker'):
                    artist.remove()
            self.canvas.draw_idle()
        
    def select_region(self):
        """
        Allow the user to select a region of the screen to monitor within the Play Together window
        """
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
        
        # First find the Play Together window
        if not self.detector:
            self.detector = PixelChangeDetector(self.log_queue)
            self.detector.gui = self
            
        if not self.detector.find_play_together_process():
            self.log("Cannot start region selection: Play Together window not found")
            return
            
        # Get window position and size
        try:
            window_rect = win32gui.GetWindowRect(self.detector.play_together_window)
            win_left, win_top, win_right, win_bottom = window_rect
            win_width = win_right - win_left
            win_height = win_bottom - win_top
            
            # Get the client area (actual game content area)
            client_rect = win32gui.GetClientRect(self.detector.play_together_window)
            client_left, client_top, client_right, client_bottom = client_rect
            
            # Convert client coordinates to screen coordinates
            client_left, client_top = win32gui.ClientToScreen(self.detector.play_together_window, (client_left, client_top))
            client_right, client_bottom = win32gui.ClientToScreen(self.detector.play_together_window, (client_right, client_bottom))
            
            # Use client area dimensions for more accurate game content area
            game_width = client_right - client_left
            game_height = client_bottom - client_top
            
            self.log(f"Game window found: {win_width}x{win_height} at ({win_left},{win_top})")
            self.log(f"Game content area: {game_width}x{game_height} at ({client_left},{client_top})")
        except Exception as e:
            self.log(f"Error getting window dimensions: {e}")
            return
        
        # Calculate region dimensions based on 1.5:1 ratio
        width = int(size * 1.5)
        height = size
        
        # Temporarily minimize our own window
        self.root.iconify()
        time.sleep(0.5)  # Give time for window to minimize
        
        # Create a transparent window for selection that matches the game window exactly
        selection_window = tk.Toplevel(self.root)
        selection_window.geometry(f"{game_width}x{game_height}+{client_left}+{client_top}")
        selection_window.attributes('-alpha', 0.2)
        selection_window.attributes('-topmost', True)
        selection_window.overrideredirect(True)  # Remove window decorations
        selection_window.configure(bg=self.colors['bg_dark'])
        
        # Create canvas for drawing the selection rectangle
        canvas = tk.Canvas(selection_window, cursor="cross", bg=self.colors['bg_dark'], highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Variables to track selection rectangle
        preview_rect = None
        outline_rect = None
        grid_lines = []
        info_text = None
        
        def update_preview(event):
            nonlocal preview_rect, outline_rect, grid_lines, info_text
            
            # Calculate region coordinates centered on mouse position
            left = event.x - width // 2
            top = event.y - height // 2
            right = left + width
            bottom = top + height
            
            # Ensure region stays within game window bounds
            if left < 0:
                left = 0
                right = width
            elif right > game_width:
                right = game_width
                left = right - width
                
            if top < 0:
                top = 0
                bottom = height
            elif bottom > game_height:
                bottom = game_height
                top = bottom - height
            
            # Clear previous shapes
            if preview_rect:
                canvas.delete(preview_rect)
            if outline_rect:
                canvas.delete(outline_rect)
            for line in grid_lines:
                canvas.delete(line)
            grid_lines = []
            if info_text:
                canvas.delete(info_text)
            
            # Draw a clean, minimal border (slightly larger for visibility)
            outline_rect = canvas.create_rectangle(
                left-2, top-2, right+2, bottom+2,
                outline=self.colors['accent'], width=2
            )
            
            # Draw the inner rectangle with minimal styling
            preview_rect = canvas.create_rectangle(
                left, top, right, bottom,
                outline=self.colors['green'], width=1,
                fill=self.colors['accent'], stipple="gray12"  # Sparse fill
            )
            
            # Add grid lines (3x3 grid)
            cell_width = width // 3
            cell_height = height // 3
            
            # Vertical grid lines
            for i in range(1, 3):
                line = canvas.create_line(
                    left + i * cell_width, top,
                    left + i * cell_width, bottom,
                    fill=self.colors['green'], width=1, dash=(2, 2)
                )
                grid_lines.append(line)
                
            # Horizontal grid lines
            for i in range(1, 3):
                line = canvas.create_line(
                    left, top + i * cell_height,
                    right, top + i * cell_height,
                    fill=self.colors['green'], width=1, dash=(2, 2)
                )
                grid_lines.append(line)
            
            # Create coordinate display with more information
            # Convert to absolute screen coordinates
            abs_left = client_left + left
            abs_top = client_top + top
            coord_text = f"position: ({abs_left},{abs_top}) • size: {width}×{height}"
            
            # Display information at the bottom center
            info_text = canvas.create_text(
                game_width // 2, game_height - 30,
                text=coord_text,
                fill=self.colors['text_bright'],
                font=("Consolas", 10)
            )
        
        def on_mouse_click(event):
            nonlocal preview_rect, outline_rect, grid_lines
            
            # Calculate region coordinates centered on mouse position
            left = event.x - width // 2
            top = event.y - height // 2
            right = left + width
            bottom = top + height
            
            # Ensure region stays within game window bounds
            if left < 0:
                left = 0
                right = width
            elif right > game_width:
                right = game_width
                left = right - width
                
            if top < 0:
                top = 0
                bottom = height
            elif bottom > game_height:
                bottom = game_height
                top = bottom - height
            
            # Close selection window
            selection_window.destroy()
            
            # Convert to absolute screen coordinates
            abs_left = client_left + left
            abs_top = client_top + top
            abs_right = client_left + right
            abs_bottom = client_top + bottom
            
            # Store absolute screen coordinates
            if self.detector:
                # Store as (left, top, right, bottom) for direct capture
                self.detector.region = (abs_left, abs_top, abs_right, abs_bottom)
                self.log(f"Region selected: ({abs_left},{abs_top}) to ({abs_right},{abs_bottom}), size: {width}×{height}")
                
                # Validate the region with a preview capture
                if self.detector.validate_region():
                    # Also capture a reference frame right away
                    self.detector.capture_reference()
                    self.log("Reference frame captured for the selected region")
                
                # Update UI to show selected region
                self.update_region_label()
                # Update the monitoring aspect ratio
                self.update_monitoring_aspect()
            
            # Restore main window
            self.root.deiconify()
        
        # Bind mouse events
        canvas.bind("<Motion>", update_preview)  # Update preview on mouse move
        canvas.bind("<ButtonPress-1>", on_mouse_click)
        
        # Create a more visible instruction panel
        instruction_frame = tk.Frame(
            canvas,
            bg=self.colors['bg_dark'],
            highlightbackground=self.colors['accent'],
            highlightthickness=1,
            padx=15,
            pady=10
        )
        
        instruction_label = tk.Label(
            instruction_frame,
            text="SELECT REGION • CLICK TO PLACE • ESC TO CANCEL",
            font=("Segoe UI", 11, "bold"),
            fg=self.colors['green'],
            bg=self.colors['bg_dark']
        )
        instruction_label.pack()
        
        # Add second line of instructions
        detail_label = tk.Label(
            instruction_frame,
            text=f"Region size: {width}×{height} pixels • Move mouse to position",
            font=("Segoe UI", 10),
            fg=self.colors['text'],
            bg=self.colors['bg_dark']
        )
        detail_label.pack()
        
        # Place instruction frame at top center
        canvas.create_window(game_width // 2, 50, window=instruction_frame)
        
        # Add crosshair guides
        # Horizontal line
        canvas.create_line(
            0, game_height // 2,
            game_width, game_height // 2,
            fill=self.colors['accent'], width=1, dash=(8, 8)
        )
        
        # Vertical line
        canvas.create_line(
            game_width // 2, 0,
            game_width // 2, game_height,
            fill=self.colors['accent'], width=1, dash=(8, 8)
        )
        
        # Handle ESC key to cancel
        def on_escape(event):
            selection_window.destroy()
            self.root.deiconify()
            self.log("Region selection cancelled")
        
        selection_window.bind("<Escape>", on_escape)
    
    def update_region_label(self):
        """Update the UI to show the selected region in minimal style"""
        if hasattr(self, 'region_info_label'):
            if self.detector and self.detector.region:
                left, top, right, bottom = self.detector.region
                width = right - left
                height = bottom - top
                # More detailed information about the selected region
                self.region_info_label.config(
                    text=f"region({left},{top}) size({width}x{height})"
                )
            else:
                self.region_info_label.config(text="waiting_for_region_selection")
        
    def capture_reference(self):
        """Capture a reference frame for comparison"""
        if self.detector and hasattr(self.detector, 'capture_reference'):
            success = self.detector.capture_reference()
            if success:
                self.log("Reference frame captured successfully")
            else:
                self.log("Failed to capture reference frame")
        else:
            self.log("Detector not initialized properly")
            
    def start_detection(self):
        """Start the detection process with improved thread control"""
        try:
            if self.is_running:
                self.log("Detection is already running")
                return
                
            if not self.detector:
                self.detector = PixelChangeDetector(self.log_queue)
                self.detector.gui = self
                
            # Check if region is selected
            if not self.detector.region:
                self.log("You must select a region first")
                return
                
            # Update detector settings from UI
            self.detector.THRESHOLD = self.threshold_var.get()
            
            # Reset thread control variables
            self.thread_control = {
                "detection_thread": None,
                "running": True,
                "paused": False,
                "stop_requested": False
            }
            
            self.log(f"Starting detection with threshold: {self.detector.THRESHOLD:.2f}")
            
            # Start the detector
            self.is_running = True
            self.detector.start_detection(self.thread_control)
            
            # Store the thread reference
            self.thread_control["detection_thread"] = self.detector.detection_thread
            
            # Update UI
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.NORMAL, text="pause")
            self.set_status_indicator("running")
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.log(f"Error starting detection: {str(e)}")
    
    def stop_detection(self):
        """Stop the detection process with improved thread management"""
        if not self.is_running:
            return
            
        # Signal thread to stop
        self.thread_control["stop_requested"] = True
        self.thread_control["running"] = False
        self.is_running = False
        
        # Wait for thread to finish (with timeout)
        if self.thread_control["detection_thread"] and self.thread_control["detection_thread"].is_alive():
            self.log("Waiting for detection thread to stop...")
            self.thread_control["detection_thread"].join(timeout=2.0)
            
            # Check if thread is still alive after timeout
            if self.thread_control["detection_thread"].is_alive():
                self.log("Warning: Detection thread did not stop gracefully")
            
        # Stop the detector
        if self.detector:
            self.detector.stop_detection()
            
        self.log("Detection stopped")
        
        # Reset UI
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED, text="pause")
        self.set_status_indicator("stopped")
    
    def toggle_pause(self):
        """Pause or resume the detection thread"""
        if not self.is_running:
            return
            
        if self.thread_control["paused"]:
            # Resume detection
            self.thread_control["paused"] = False
            self.pause_button.config(text="pause")
            self.set_status_indicator("running")
            self.log("Detection resumed")
        else:
            # Pause detection
            self.thread_control["paused"] = True
            self.pause_button.config(text="resume")
            self.set_status_indicator("paused")
            self.log("Detection paused")
    
    def clear_logs(self):
        """Clear the log console"""
        self.log_console.delete(1.0, tk.END)
        
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

class PixelChangeDetector:
    def __init__(self, log_queue=None):
        self.THRESHOLD = 0.05  # Default threshold for pixel change
        self.is_running = False
        self.log_queue = log_queue
        self.gui = None
        
        # Screen capture region (required)
        self.region = None  # (left, top, right, bottom)
        
        # Initialize visualization data
        self.current_frame = None
        self.previous_frame = None
        self.reference_frame = None
        self.reference_color_frame = None  # Store color reference frame
        self.diff_frame = None
        self.change_history = []
        self.color_frame = None
        
        # Last detection time for cooldown
        self.last_detection_time = 0
        self.detection_cooldown = 5.0  # Cooldown between detections (increased from 0.5 to 5.0)
        
        # Capture interval in seconds
        self.capture_interval = 0.05  # Capture interval
        self.max_fps = 30  # Maximum frames per second
        
        # Play Together window tracking
        self.play_together_window = None
        self.play_together_pid = None
        
        # Key settings
        self.fishing_key = "f"  # Default fishing key
        self.F_KEY = 0x46  # F key virtual key code (will be updated based on fishing_key)
        
        # Detection statistics
        self.stats = {
            "total_detections": 0,
            "false_positives": 0,
            "session_start_time": time.time(),
            "last_detection_time": 0,
            "avg_detection_interval": 0
        }
        
        # Health check variables
        self.last_successful_capture = 0
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        self.health_check_interval = 5  # seconds
        self.last_health_check = 0
        
        # Detection thread reference
        self.detection_thread = None
        
        # Performance monitoring
        self.performance = {
            "avg_processing_time": 0.05,
            "processing_samples": 0,
            "cpu_usage": 0
        }
        
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
        self.diff_frame = None
        # Don't reset reference_frame unless explicitly asked
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

    def send_fishing_key(self):
        """Send the configured fishing key"""
        try:
            # Update virtual key code based on the configured fishing key
            key = self.fishing_key.lower()
            vk_code = None
            
            # Handle special key names
            if key == "f":
                vk_code = 0x46  # VK_F
            elif key == "e":
                vk_code = 0x45  # VK_E
            elif key == "space":
                vk_code = 0x20  # VK_SPACE
            elif len(key) == 1:  # Single letter/number
                vk_code = ord(key.upper())
            else:
                self.log(f"Unknown key: {key}, falling back to 'f'")
                vk_code = 0x46  # Default to F
            
            # Single quick focus check
            if user32.GetForegroundWindow() != self.play_together_window:
                self.focus_play_together_window()
                time.sleep(0.05)  # Reduced delay
            
            # Use most reliable method first - SendInput
            kb_input = INPUT()
            kb_input.type = INPUT_KEYBOARD
            kb_input.ii.ki.wVk = vk_code
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
            keyboard.press_and_release(key)
            
            # Update stats
            self.stats["total_detections"] += 1
            current_time = time.time()
            if self.stats["last_detection_time"] > 0:
                # Calculate interval since last detection
                interval = current_time - self.stats["last_detection_time"]
                # Update average detection interval using moving average
                if self.stats["avg_detection_interval"] == 0:
                    self.stats["avg_detection_interval"] = interval
                else:
                    self.stats["avg_detection_interval"] = (
                        0.8 * self.stats["avg_detection_interval"] + 0.2 * interval
                    )
            self.stats["last_detection_time"] = current_time
            
            return True
            
        except Exception as e:
            self.log(f"Error with key simulation: {e}")
            return False
            
    def send_f_key(self):
        """Legacy method for compatibility - redirects to send_fishing_key"""
        return self.send_fishing_key()

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
        """Capture the screen or region of interest using MSS for better multi-monitor support"""
        try:
            if not self.region:
                self.log("No region selected. Please select a region first.")
                return None
                
            # Validate region size
            left, top, right, bottom = self.region
            width = right - left
            height = bottom - top
            
            if width < 10 or height < 10:
                self.log("Invalid region size detected. Please select a new region.")
                return None
                
            # Use mss library which has better performance and multi-monitor support
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
                
                # Log first capture for debugging
                if not hasattr(self, 'first_capture_logged'):
                    self.log(f"First capture from region: ({left},{top}) to ({right},{bottom}), size: {width}x{height}")
                    monitor_info = f"Monitor info: {sct.monitors}"
                    self.log(monitor_info)
                    self.first_capture_logged = True
                
                # Convert to numpy array - sct.grab returns BGR
                frame = np.array(screenshot)
                
            # Validate frame
            if frame.size == 0:
                self.log("Error: Captured frame is empty")
                self.consecutive_failures += 1
                return None
                
            # Store color frame for visualization (convert BGR to RGB)
            if len(frame.shape) >= 3:
                self.color_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
            else:
                self.color_frame = None
                
            # Convert to grayscale for processing (directly from BGR)
            if len(frame.shape) >= 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
            
            # Update health check variables
            self.last_successful_capture = time.time()
            self.consecutive_failures = 0
            return frame
            
        except Exception as e:
            self.log(f"Error capturing screen: {e}")
            self.consecutive_failures += 1
            return None
            
    def calculate_frame_difference(self, frame1, frame2):
        """Calculate the difference between two frames with improved sensitivity"""
        if frame1 is None or frame2 is None:
            return None, 0
            
        # Ensure frames have same dimensions
        if frame1.shape != frame2.shape:
            # Resize to match
            frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
        
        # Apply slight blur to reduce noise sensitivity
        frame1_blurred = cv2.GaussianBlur(frame1, (5, 5), 0)
        frame2_blurred = cv2.GaussianBlur(frame2, (5, 5), 0)
            
        # Calculate absolute difference
        diff_frame = cv2.absdiff(frame1_blurred, frame2_blurred)
        
        # Calculate percentage of pixels that changed significantly
        # Apply adaptive thresholding based on frame characteristics
        threshold = 30  # Default threshold
        
        # Apply morphological operations to highlight larger changes
        kernel = np.ones((3, 3), np.uint8)
        dilated_diff = cv2.dilate(diff_frame, kernel, iterations=1)
        
        # Count significant pixel changes
        changed_pixels = np.sum(dilated_diff > threshold)
        total_pixels = frame1.shape[0] * frame1.shape[1]
        change_percent = changed_pixels / total_pixels
        
        # For visualization, enhance the difference frame
        enhanced_diff = cv2.convertScaleAbs(dilated_diff, alpha=1.5)
        
        return enhanced_diff, change_percent
    
    def capture_reference(self):
        """Capture a reference frame for comparison"""
        frame = self.capture_screen()
        if frame is not None:
            self.reference_frame = frame
            self.log(f"Reference frame captured: {self.reference_frame.shape}")
            
            # If we have a color frame, store it for visualization
            if hasattr(self, 'color_frame') and self.color_frame is not None:
                self.reference_color_frame = self.color_frame.copy()
                
            return True
        else:
            self.log("Failed to capture reference frame")
            return False
            
    def validate_region(self):
        """Validate the selected region with a preview capture"""
        frame = self.capture_screen()
        if frame is not None:
            self.log(f"Region validation successful: captured {frame.shape}")
            return True
        else:
            self.log("Failed to validate region")
            return False
            
    def start_detection(self, thread_control=None):
        """Start detection with improved thread control"""
        if not self.find_play_together_process():
            self.log("Cannot start detection: Play Together window not found")
            return False
            
        self.is_running = True
        self.change_history = []
        
        # Capture initial frame as reference if none exists
        if self.reference_frame is None:
            self.capture_reference()
            
        self.previous_frame = self.reference_frame
        
        # Use thread control if provided
        self.thread_control = thread_control if thread_control else {
            "running": True,
            "paused": False,
            "stop_requested": False
        }
        
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        return True
        
    def stop_detection(self):
        """Stop detection cleanly"""
        self.is_running = False
        
    def _detection_loop(self):
        """Main detection loop with improved thread control and performance optimizations"""
        # Initialize frame skip counter for performance tuning
        frame_counter = 0
        fps_counter = 0
        fps_timer = time.time()
        last_fps_update = time.time()
        fps = 0
        
        # Load system resources
        cpu_load = psutil.cpu_percent(interval=0.1)
        
        # Adaptive performance based on system resources
        adaptive_interval = self.capture_interval
        
        self.log("Starting detection loop")
        
        while self.is_running and not self.thread_control.get("stop_requested", False):
            loop_start = time.time()
            try:
                # Check if paused
                if self.thread_control.get("paused", False):
                    time.sleep(0.1)
                    continue
                
                # Update FPS counter
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    fps = fps_counter
                    fps_counter = 0
                    fps_timer = time.time()
                    
                    # Update FPS in GUI every 5 seconds
                    if time.time() - last_fps_update >= 5.0:
                        if self.gui:
                            self.gui.root.after(0, lambda f=fps: self.gui.log(f"Processing at {f} FPS"))
                        last_fps_update = time.time()
                        
                        # Update CPU load
                        cpu_load = psutil.cpu_percent(interval=None)
                        
                        # Adjust capture interval based on CPU load
                        if cpu_load > 80:
                            adaptive_interval = max(0.05, self.capture_interval * 1.5)
                        elif cpu_load > 60:
                            adaptive_interval = self.capture_interval * 1.2
                        else:
                            adaptive_interval = self.capture_interval
                
                # Only perform health check every 10th frame
                if frame_counter % 10 == 0:
                    if not self.perform_health_check():
                        time.sleep(0.1)
                        continue
                
                # Capture current frame
                self.current_frame = self.capture_screen()
                
                if self.current_frame is None:
                    time.sleep(adaptive_interval)
                    continue
                    
                # Use reference frame if available, otherwise use previous frame
                compare_frame = self.reference_frame if self.reference_frame is not None else self.previous_frame
                
                if compare_frame is None:
                    self.capture_reference()
                    time.sleep(adaptive_interval)
                    continue
                
                # Calculate difference
                self.diff_frame, change_percent = self.calculate_frame_difference(self.current_frame, compare_frame)
                
                # Store in history (with downsampling for better performance)
                if frame_counter % 2 == 0:  # Only store every other frame
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
                    
                    # Enhanced detection handling
                    self._handle_detection()
                    
                    # Continue with next frame
                    continue
                
                # Store current frame as previous for next comparison if not using reference
                if self.reference_frame is None:
                    self.previous_frame = self.current_frame
                
                # Update frame counter
                frame_counter += 1
                
                # Calculate time spent in this iteration
                loop_time = time.time() - loop_start
                
                # Update performance metrics
                self.performance["processing_samples"] += 1
                if self.performance["processing_samples"] > 100:
                    self.performance["processing_samples"] = 1
                    
                # Update moving average of processing time
                alpha = 0.05  # Weight for new samples (lower = more stable average)
                self.performance["avg_processing_time"] = (1 - alpha) * self.performance["avg_processing_time"] + alpha * loop_time
                
                # Sleep to control capture rate, adjust based on processing time
                sleep_time = max(0, adaptive_interval - loop_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
            except Exception as e:
                self.log(f"Error in detection loop: {e}")
                self.consecutive_failures += 1
                time.sleep(0.05)  # Short delay on error
        
        # Thread is exiting
        self.log("Detection thread exiting")
        self.is_running = False
        
    def _handle_detection(self):
        """Handle detection event with optimized sequence"""
        try:
            # Quick focus and key press
            if self.focus_play_together_window():
                self.log(f"Pressing {self.fishing_key.upper()} key to catch fish...")
                self.send_fishing_key()
                # Capture new reference frame after detection
                time.sleep(0.2)
            else:
                self.log("Failed to focus window, skipping key press")
            
            # Pause detection based on the configured cooldown
            cooldown = self.detection_cooldown
            self.log(f"Pausing detection for {cooldown:.1f} seconds...")
            
            # Initial delay
            time.sleep(min(2.0, cooldown / 2))
            
            pause_start = time.time()
            
            # Wait additional time, checking for stop requests
            pause_end = pause_start + cooldown
            while time.time() < pause_end and self.is_running and not self.thread_control.get("stop_requested", False):
                remaining = int(pause_end - time.time())
                if self.gui:
                    self.gui.root.after(0, lambda r=remaining: self.gui.status_label.config(
                        text=f"System: monitor.paused ({r}s)",
                        style="Paused.Status.TLabel"
                    ))
                time.sleep(0.1)
            
            # Press ESC after pause
            if self.is_running and not self.thread_control.get("stop_requested", False):
                self.log("Pressing ESC key to exit fishing menu...")
                if self.focus_play_together_window():
                    self.send_esc_key()
                else:
                    self.log("Failed to focus window, skipping ESC key press")
            
            # Wait before casting again
            esc_end = time.time() + 2
            while time.time() < esc_end and self.is_running and not self.thread_control.get("stop_requested", False):
                time.sleep(0.1)
            
            # Cast fishing line again
            if self.is_running and not self.thread_control.get("stop_requested", False):
                self.log(f"Pressing {self.fishing_key.upper()} key to cast fishing line...")
                if self.focus_play_together_window():
                    self.send_fishing_key()
                    # Capture new reference frame after casting
                    time.sleep(2)  # Wait for screen to update
                    
                    # Get a new reference frame
                    self.capture_reference()
                    self.log("New reference frame captured after casting")
                else:
                    self.log("Failed to focus window, skipping fishing cast")
            
            # Update status to running
            if self.gui and self.is_running and not self.thread_control.get("stop_requested", False):
                self.gui.root.after(0, lambda: self.gui.set_status_indicator("running"))
            
            # Pause a bit more to let the game stabilize
            stabilize_time = min(2.0, self.detection_cooldown * 0.2)
            time.sleep(stabilize_time)
        
        except Exception as e:
            self.log(f"Error handling detection: {e}")
            # Try to recover
            if self.gui:
                self.gui.root.after(0, lambda: self.gui.set_status_indicator("running"))

VERSION = "1.2"
VERSION_NAME = "Multi-Monitor Optimized Edition"

def main():
    root = tk.Tk()
    root.title(f"AutoFisher v{VERSION}")
    
    # Set app icon (if available)
    try:
        root.iconbitmap("app_icon.ico")
    except:
        pass  # Icon file not found, use default
    
    # Create and start the application
    app = PixelChangeDetectorGUI(root)
    
    # Get primary monitor dimensions
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    
    # Set window size based on monitor resolution - scale for different resolutions
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
        app.log(f"Detected {len(monitors)-1} physical monitors")
        app.log(f"Primary monitor: {screen_width}x{screen_height}")
    
    # Add welcome message
    app.log(f"AutoFisher v{VERSION} initialized")
    app.log(f"{VERSION_NAME}")
    app.log("System ready - Please select a region to begin")
    app.log("To get started: (1) Select region size (2) Click select-region (3) Click start")
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    main() 