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
        """Configure the app style with a clean minimalist terminal-inspired theme"""
        # Configure ttk style with a terminal theme
        style = ttk.Style()
        
        # Define color scheme with colors from App.xaml
        self.colors = {
            # Main black colors
            'bg_dark': '#050505',       # PrimaryBlackColor
            'bg_term': '#0E0E0E',       # PrimaryBackgroundDarkColor
            'bg_lighter': '#1A1A1A',    # SecondaryBlackColor
            'bg_alt': '#191919',        # AlternativeDarkColor
            'bg_matte': '#121212',      # MatteBlackColor
            
            # Text colors
            'text': '#F8F5FF',          # PrimaryTextColor
            'text_bright': '#FFFFFF',   # WhiteColor
            'text_dim': '#999999',      # SecondaryTextColor
            'text_tertiary': '#616161', # TertiaryTextColor
            
            # Accent colors
            'accent': '#A280FF',        # PrimaryPurpleColor
            'accent_alt': '#8F66FF',    # SecondaryPurpleColor
            'accent_bright': '#7C4CFF',  # TertiaryPurpleColor
            'accent_special': '#6933FF', # SpecialPurpleColor
            
            # Green colors
            'green': '#C4E6B5',         # PrimaryGreenColor
            'green_alt': '#A8D699',     # SecondaryGreenColor
            'green_matcha': '#BCD9B4',  # MatchaGreenColor
            
            # Status colors
            'success': '#47D068',       # SuccessColor
            'border': '#2A2A2A',        # Updated for modern look
            'border_light': '#333333',  # Updated for modern look
            'cursor': '#C4E6B5',        # Using PrimaryGreenColor
            'alert': '#FF4D4D',         # ErrorColor
            'warning': '#FFB940',       # WarningColor
            'selection': '#264F78'      # Keep existing selection color
        }
        
        # Define custom fonts
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(size=10, family="Consolas")
        term_font = tkfont.Font(family="Consolas", size=10)
        heading_font = tkfont.Font(family="Consolas", size=11, weight="bold")
        
        # Configure base styles
        style.configure('TFrame', background=self.colors['bg_dark'])
        style.configure('Term.TFrame', background=self.colors['bg_dark'])
        
        # Add separator style
        style.configure('Separator.TFrame', background=self.colors['border'])
        
        # Add modern border style with rounded corners
        style.configure('Border.TFrame', 
                       background=self.colors['bg_dark'],
                       borderwidth=1,
                       relief="solid")
        
        style.configure('TLabel', 
                       background=self.colors['bg_dark'], 
                       foreground=self.colors['text'],
                       font=term_font)
        
        style.configure('Term.TLabel', 
                       background=self.colors['bg_dark'], 
                       foreground=self.colors['text'],
                       font=term_font)
        
        style.configure('Heading.TLabel', 
                       font=heading_font, 
                       background=self.colors['bg_dark'], 
                       foreground=self.colors['text_bright'])
        
        # Status indicators
        style.configure('Status.TLabel', 
                       font=term_font, 
                       background=self.colors['bg_dark'],
                       foreground=self.colors['text_dim'])
        
        style.configure('Running.Status.TLabel', 
                       foreground=self.colors['green'],
                       background=self.colors['bg_dark'])
        
        style.configure('Stopped.Status.TLabel', 
                       foreground=self.colors['alert'],
                       background=self.colors['bg_dark'])
        
        style.configure('Paused.Status.TLabel', 
                       foreground=self.colors['warning'],
                       background=self.colors['bg_dark'])
        
        # Define custom button layout with rounded corners
        self.root.tk.eval("""
            ttk::style layout Custom.TButton {
                Custom.Button.focus -children {
                    Custom.Button.padding -children {
                        Custom.Button.label
                    }
                }
            }
            ttk::style configure Custom.TButton -background %(bg_term)s -foreground %(text)s -padding {8 6}
            ttk::style map Custom.TButton -background [list active %(bg_lighter)s] -foreground [list active %(text_bright)s]
        """ % self.colors)
        
        # Configure standard buttons with material-inspired styling
        style.configure('TButton', 
                       background=self.colors['bg_dark'],
                       foreground=self.colors['text'],
                       borderwidth=0,
                       focusthickness=0,
                       relief="flat",
                       padding=(8, 6),
                       font=term_font)
        
        style.map('TButton',
                 background=[('active', self.colors['bg_lighter']), ('pressed', self.colors['bg_alt'])],
                 foreground=[('active', self.colors['text_bright']), ('pressed', self.colors['accent'])])
        
        # Primary command button style (green-accented with black bg)
        style.configure('Command.TButton', 
                       background=self.colors['bg_dark'],
                       foreground=self.colors['green'],
                       borderwidth=1,
                       focusthickness=0,
                       relief="flat",
                       padding=(10, 6),
                       font=term_font)
        
        style.map('Command.TButton',
                 background=[('active', self.colors['bg_lighter']), ('pressed', self.colors['bg_alt'])],
                 foreground=[('active', self.colors['green_alt']), ('pressed', self.colors['green'])])
        
        # Warning style button (red accent)
        style.configure('Warning.TButton', 
                       background=self.colors['bg_dark'],
                       foreground=self.colors['alert'],
                       borderwidth=1,
                       focusthickness=0,
                       relief="flat",
                       padding=(10, 6),
                       font=term_font)
        
        style.map('Warning.TButton',
                 background=[('active', self.colors['bg_lighter']), ('pressed', self.colors['bg_alt'])],
                 foreground=[('active', self.colors['alert']), ('pressed', self.colors['text_bright'])])
        
        # Secondary button style (purple accent)
        style.configure('Secondary.TButton', 
                       background=self.colors['bg_dark'],
                       foreground=self.colors['accent'],
                       borderwidth=1,
                       focusthickness=0,
                       relief="flat", 
                       padding=(10, 6),
                       font=term_font)
        
        style.map('Secondary.TButton',
                 background=[('active', self.colors['bg_lighter']), ('pressed', self.colors['bg_alt'])],
                 foreground=[('active', self.colors['accent_alt']), ('pressed', self.colors['text_bright'])])
        
        # Frame containers with minimal borders
        style.configure('Panel.TFrame', 
                       padding=8, 
                       relief="flat", 
                       borderwidth=0,
                       background=self.colors['bg_dark'])
        
        # Modern LabelFrame style
        style.configure('Terminal.TLabelframe', 
                       padding=10, 
                       relief="solid", 
                       borderwidth=1,
                       bordercolor=self.colors['border_light'],
                       background=self.colors['bg_dark'])
        
        style.configure('Terminal.TLabelframe.Label', 
                       font=heading_font,
                       background=self.colors['bg_dark'],
                       foreground=self.colors['green'],
                       padding=(5, 0))
        
        # Entry, Checkbutton, Scale styles
        style.configure('TEntry', 
                       fieldbackground=self.colors['bg_dark'],
                       foreground=self.colors['text'],
                       insertcolor=self.colors['cursor'],
                       borderwidth=1,
                       relief="solid",
                       font=term_font)
        
        style.configure('TCheckbutton', 
                       background=self.colors['bg_dark'],
                       foreground=self.colors['text'],
                       font=term_font)
        
        style.map('TCheckbutton',
                 background=[('active', self.colors['bg_dark'])],
                 foreground=[('active', self.colors['green'])])
        
        style.configure('TScale', 
                       background=self.colors['bg_dark'],
                       troughcolor=self.colors['bg_dark'],
                       slidercolor=self.colors['accent'],
                       borderwidth=0)
        
        # Apply overall tkinter styling
        self.root.configure(background=self.colors['bg_dark'])
        
    def log(self, message):
        """Add timestamped message to log queue in minimal format"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")
        
    def create_widgets(self):
        """Create all GUI widgets with modern minimal terminal design"""
        # Main container with minimal padding
        main_container = ttk.Frame(self.root, padding="10", style='TFrame')
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Top command line prompt
        cmd_frame = ttk.Frame(main_container, style='Term.TFrame')
        cmd_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Status as command output
        self.status_label = ttk.Label(cmd_frame, text="system:monitor.idle", style='Status.TLabel')
        self.status_label.pack(side=tk.LEFT)
        
        # Blinking cursor at end of command
        self.cursor_label = ttk.Label(cmd_frame, text="_", style='Term.TLabel')
        self.cursor_label.pack(side=tk.LEFT)
        self.cursor_visible = True
        self.blink_cursor()
        
        # Detection counter in command line style
        count_frame = ttk.Frame(cmd_frame, style='Term.TFrame')
        count_frame.pack(side=tk.RIGHT, padx=(0, 5))
        
        self.detection_count = 0
        self.count_label = ttk.Label(count_frame, text="detections: 0", style='Term.TLabel')
        self.count_label.pack(side=tk.RIGHT)
        
        # Thin separator line
        separator = ttk.Frame(main_container, height=1, style='Separator.TFrame')
        separator.pack(fill=tk.X, pady=(0, 10))
        
        # Split into left and right panels
        panel_container = ttk.Frame(main_container, style='TFrame')
        panel_container.pack(fill=tk.BOTH, expand=True)
        
        # Left control panel (fixed width)
        left_panel = ttk.Frame(panel_container, width=300, style='TFrame')
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)  # Fix the width
        
        # Right visualization panel (expanding)
        right_panel = ttk.Frame(panel_container, style='TFrame')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Section 1: Detection Settings
        settings_frame = ttk.LabelFrame(left_panel, text="SETTINGS", style='Terminal.TLabelframe')
        settings_frame.pack(fill=tk.X, pady=(0, 10), padx=0)
        
        # Threshold control with clean minimal slider
        threshold_frame = ttk.Frame(settings_frame, style='Term.TFrame')
        threshold_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(threshold_frame, text="threshold:", style='Term.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        
        threshold_value_frame = ttk.Frame(settings_frame, style='Term.TFrame')
        threshold_value_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.threshold_var = tk.DoubleVar(value=0.05)
        
        # Custom slider with black background
        slider_frame = tk.Frame(threshold_value_frame, bg=self.colors['bg_dark'])
        slider_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        
        self.threshold_slider = tk.Scale(
            slider_frame, 
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
            sliderrelief="flat"
        )
        self.threshold_slider.pack(fill=tk.X, expand=True)
        
        self.threshold_label = ttk.Label(threshold_value_frame, text="0.05", width=4, style='Term.TLabel')
        self.threshold_label.pack(side=tk.RIGHT, padx=(0, 5))
        self.threshold_slider.config(command=self.update_threshold_label)
        
        # Region size input
        size_frame = ttk.Frame(settings_frame, style='Term.TFrame')
        size_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(size_frame, text="region_size:", style='Term.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        self.size_var = tk.StringVar(value="50")
        self.size_entry = tk.Entry(
            size_frame, 
            textvariable=self.size_var, 
            width=5,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            insertbackground=self.colors['cursor'],
            highlightthickness=1,
            highlightbackground=self.colors['border'],
            highlightcolor=self.colors['accent'],
            relief="flat",
            font=('Consolas', 10)
        )
        self.size_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(size_frame, text="px", style='Term.TLabel').pack(side=tk.LEFT)
        
        # Section 2: Region Selection
        region_frame = ttk.LabelFrame(left_panel, text="MONITORING", style='Terminal.TLabelframe')
        region_frame.pack(fill=tk.X, pady=(0, 10), padx=0)
        
        # Region buttons in command line style
        region_buttons = ttk.Frame(region_frame, style='Term.TFrame')
        region_buttons.pack(fill=tk.X, pady=5)
        
        # Custom button for region selection
        self.region_button = tk.Button(
            region_buttons, 
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
            pady=6,
            font=('Consolas', 10)
        )
        self.region_button.pack(side=tk.LEFT, padx=(5, 5))
        
        # Status label
        region_info_frame = ttk.Frame(region_frame, style='Term.TFrame')
        region_info_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(region_info_frame, text="status:", style='Term.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        self.region_info_label = ttk.Label(region_info_frame, text="waiting_for_region_selection", style='Term.TLabel')
        self.region_info_label.pack(side=tk.LEFT, padx=5)
        
        # Section 3: Control Buttons
        control_frame = ttk.LabelFrame(left_panel, text="CONTROL", style='Terminal.TLabelframe')
        control_frame.pack(fill=tk.X, pady=(0, 10), padx=0)
        
        button_frame = ttk.Frame(control_frame, style='Term.TFrame')
        button_frame.pack(fill=tk.X, pady=5)
        
        # Main control buttons with custom tk styling
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
            pady=6,
            font=('Consolas', 10)
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
            pady=6,
            font=('Consolas', 10),
            disabledforeground='grey'
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
            pady=6,
            font=('Consolas', 10),
            disabledforeground='grey'
        )
        self.pause_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Second row of buttons
        button_frame2 = ttk.Frame(control_frame, style='Term.TFrame')
        button_frame2.pack(fill=tk.X, pady=5)
        
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
            pady=6,
            font=('Consolas', 10)
        )
        self.ref_button.pack(side=tk.LEFT, padx=(5, 5))
        
        # Clear logs button
        self.clear_button = tk.Button(
            button_frame2, 
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
            pady=6,
            font=('Consolas', 10)
        )
        self.clear_button.pack(side=tk.LEFT)
        
        # Section 4: Log Display
        log_frame = ttk.LabelFrame(left_panel, text="LOGS", style='Terminal.TLabelframe')
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0), padx=0)
        
        # Log console with retro terminal styling
        self.log_console = scrolledtext.ScrolledText(
            log_frame,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            font=('Consolas', 9),
            relief="flat",
            borderwidth=0
        )
        self.log_console.pack(fill=tk.BOTH, expand=True)
        
        # Configure visualization panel
        viz_frame = ttk.LabelFrame(right_panel, text="VISUALIZATION", style='Terminal.TLabelframe')
        viz_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create matplotlib figure for monitoring
        self.create_monitoring_figure(viz_frame)
        
    def blink_cursor(self):
        """Create a blinking cursor effect for the terminal style"""
        self.cursor_visible = not self.cursor_visible
        self.cursor_label.config(text="_" if self.cursor_visible else " ")
        self.root.after(500, self.blink_cursor)  # Blink every half second
        
    def create_monitoring_figure(self, parent_frame):
        """Create the monitoring visualization with minimal command-line style"""
        # Create frame for matplotlib with border - updated border
        viz_content_frame = ttk.Frame(parent_frame, style='Border.TFrame')
        viz_content_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        canvas_frame = ttk.Frame(viz_content_frame, style='Term.TFrame')
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # Configure figure with a clean minimal appearance
        plt.rcParams['text.color'] = self.colors['text']
        plt.rcParams['axes.labelcolor'] = self.colors['text']
        plt.rcParams['xtick.color'] = self.colors['text_dim']
        plt.rcParams['ytick.color'] = self.colors['text_dim']
        
        self.fig = plt.Figure(figsize=(8, 6), dpi=100, facecolor=self.colors['bg_dark'])
        
        # Use GridSpec for better control over subplot sizing
        gs = plt.GridSpec(2, 1, height_ratios=[4, 1], hspace=0.2)
        
        # Combined frame subplot - larger with correct ratio
        self.current_ax = self.fig.add_subplot(gs[0])
        self.current_ax.set_title("OVERLAID FEED", color=self.colors['green'], fontsize=9, fontweight='normal')
        self.current_image = self.current_ax.imshow(np.zeros((100, 150, 3)), cmap='gray')
        
        # Create an overlay image for differences with alpha transparency
        self.diff_overlay = self.current_ax.imshow(np.zeros((100, 150, 4)), alpha=0.5)
        
        self.current_ax.set_xticks([])
        self.current_ax.set_yticks([])
        self.current_ax.set_facecolor(self.colors['bg_dark'])
        
        # Clean up borders
        for spine in self.current_ax.spines.values():
            spine.set_visible(False)
        
        # Add thin border around feed - more modern with slightly thicker border
        rect = plt.Rectangle((0, 0), 1, 1, fill=False, ec=self.colors['border_light'], 
                           linewidth=1.5, transform=self.current_ax.transAxes, clip_on=False)
        self.current_ax.add_patch(rect)
        
        # Create a small timeline below the main frame
        self.timeline_height = 0.10  # Height of timeline in figure fraction
        timeline_bottom = 0.05  # Bottom position in figure fraction
        self.timeline_ax = self.fig.add_axes([0.1, timeline_bottom, 0.8, self.timeline_height])
        
        # Create a clean, minimal timeline
        self.timeline_ax.set_title("ACTIVITY", color=self.colors['green'], fontsize=8, fontweight='normal')
        self.timeline_ax.axhline(y=0.5, color=self.colors['border'], linestyle='-', alpha=0.3, linewidth=0.5)
        
        # Create the timeline with a flat line initially
        x_data = np.arange(100)
        y_data = np.ones(100) * 0.5  # Middle line
        self.activity_line, = self.timeline_ax.plot(x_data, y_data, color=self.colors['accent'], linewidth=1)
        
        # Add threshold marker (horizontal line)
        self.threshold_line = self.timeline_ax.axhline(
            y=0.05, color=self.colors['alert'], linestyle='--', alpha=0.5, linewidth=0.5
        )
        
        # Clean up timeline appearance
        self.timeline_ax.set_ylim(0, 1)
        self.timeline_ax.set_xlim(0, 99)
        self.timeline_ax.set_facecolor(self.colors['bg_dark'])
        self.timeline_ax.set_xticks([])
        self.timeline_ax.set_yticks([])
        
        # Remove spines for cleaner look
        for spine in self.timeline_ax.spines.values():
            spine.set_visible(False)
        
        # Add minimal tick marks on left side
        self.timeline_ax.set_yticks([0, 0.5, 1])
        self.timeline_ax.set_yticklabels(['0', '', '1'])
        self.timeline_ax.tick_params(axis='y', colors=self.colors['text_dim'], labelsize=6)
        
        # Add thin border around timeline - more modern
        rect = plt.Rectangle((0, 0), 1, 1, fill=False, ec=self.colors['border_light'], 
                           linewidth=1.5, alpha=0.5, transform=self.timeline_ax.transAxes, clip_on=False)
        self.timeline_ax.add_patch(rect)
        
        # We're not using tight_layout to avoid warnings
        # Instead, manually adjust the figure spacing
        self.fig.subplots_adjust(left=0.10, right=0.95, top=0.95, bottom=0.15)
        
        # Embed figure in tkinter with proper padding
        self.canvas = FigureCanvasTkAgg(self.fig, canvas_frame)
        self.canvas.get_tk_widget().configure(bg=self.colors['bg_dark'], highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Initial status update for visualization
        self.fig.text(0.5, 0.5, "awaiting data", color=self.colors['text_dim'], 
                     fontsize=10, ha='center', va='center', fontfamily='Consolas')

    def set_status_indicator(self, status):
        """Update the status indicator in minimal terminal style"""
        if status == "running":
            self.status_label.config(text="system:monitor.active", style="Running.Status.TLabel")
        elif status == "stopped":
            self.status_label.config(text="system:monitor.stopped", style="Stopped.Status.TLabel")
        elif status == "paused":
            self.status_label.config(text="system:monitor.paused", style="Paused.Status.TLabel")
        else:
            # Default to just updating the text
            self.status_label.config(text=f"system:monitor.{status}", style="Status.TLabel")
        
    def update_threshold_label(self, value=None):
        self.threshold_label.config(text=f"{float(self.threshold_var.get()):.2f}")
        
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
        """Update the visualization with current frames in minimal style"""
        try:
            # Clear any initial status text
            for txt in self.fig.texts:
                txt.remove()
            
            # Update current frame
            if hasattr(self.detector, 'color_frame') and self.detector.color_frame is not None:
                # Use color frame if available
                self.current_image.set_data(self.detector.color_frame)
                
                # Set axis limits to match the image
                self.current_ax.set_xlim(0, self.detector.color_frame.shape[1])
                self.current_ax.set_ylim(self.detector.color_frame.shape[0], 0)
            elif hasattr(self.detector, 'current_frame') and self.detector.current_frame is not None:
                # Fallback to grayscale
                gray_display = cv2.cvtColor(self.detector.current_frame, cv2.COLOR_GRAY2RGB)
                self.current_image.set_data(gray_display)
                
                # Set axis limits to match the image
                self.current_ax.set_xlim(0, gray_display.shape[1])
                self.current_ax.set_ylim(gray_display.shape[0], 0)
                
            # Create overlay for difference frame
            if hasattr(self.detector, 'diff_frame') and self.detector.diff_frame is not None:
                # Make a copy to avoid modifying the original
                diff_display = self.detector.diff_frame.copy()
                
                # Enhance contrast for better visibility
                diff_display = cv2.convertScaleAbs(diff_display, alpha=3)  # Less extreme contrast
                
                # Convert to heat map with inferno colormap (cleaner look)
                diff_colored = cv2.applyColorMap(diff_display, cv2.COLORMAP_INFERNO)
                
                # Convert from BGR to RGB for display in matplotlib
                colored_diff = cv2.cvtColor(diff_colored, cv2.COLOR_BGR2RGB)
                
                # Add alpha channel for transparency
                colored_diff_alpha = np.zeros((colored_diff.shape[0], colored_diff.shape[1], 4), dtype=np.uint8)
                colored_diff_alpha[..., :3] = colored_diff
                
                # Set alpha based on intensity for better visualization
                # Only show differences above a certain threshold for cleaner look
                alpha_threshold = 30
                for i in range(diff_display.shape[0]):
                    for j in range(diff_display.shape[1]):
                        if diff_display[i, j] > alpha_threshold:
                            colored_diff_alpha[i, j, 3] = min(255, int(diff_display[i, j] * 2))
                        else:
                            colored_diff_alpha[i, j, 3] = 0
                
                # Update the overlay display
                self.diff_overlay.set_data(colored_diff_alpha)
                
                # Update title with current change percentage
                if hasattr(self.detector, 'change_history') and len(self.detector.change_history) > 0:
                    latest_change = self.detector.change_history[-1]
                    self.current_ax.set_title(f"FEED+DIFF OVERLAY [{latest_change:.2%}]", 
                                         color=self.colors['green'], fontsize=9, fontweight='normal')
                
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
    
    def _clean_markers(self):
        """Remove detection markers from timeline"""
        if hasattr(self, 'timeline_ax'):
            for artist in self.timeline_ax.get_lines():
                if hasattr(artist, 'detection_marker'):
                    artist.remove()
            self.canvas.draw_idle()
        
    def select_region(self):
        """Allow the user to select a region of the screen to monitor with minimal styling"""
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
        
        # Calculate region dimensions based on 1.5:1 ratio
        width = int(size * 1.5)
        height = size
        
        # Temporarily minimize our own window
        self.root.iconify()
        time.sleep(0.5)  # Give time for window to minimize
        
        # Create a fullscreen transparent window for selection
        selection_window = tk.Toplevel(self.root)
        selection_window.attributes('-fullscreen', True)
        selection_window.attributes('-alpha', 0.2)  # Slightly more transparent
        selection_window.attributes('-topmost', True)
        selection_window.configure(bg=self.colors['bg_dark'])  # Use black from our color palette
        
        # Create canvas for drawing the selection rectangle
        canvas = tk.Canvas(selection_window, cursor="cross", bg=self.colors['bg_dark'])
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Variables to track selection rectangle
        preview_rect = None
        outline_rect = None
        grid_lines = []
        
        def update_preview(event):
            nonlocal preview_rect, outline_rect, grid_lines
            
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
            
            # Clear previous shapes
            if preview_rect:
                canvas.delete(preview_rect)
            if outline_rect:
                canvas.delete(outline_rect)
            for line in grid_lines:
                canvas.delete(line)
            grid_lines = []
            
            # Draw a clean, minimal border
            outline_rect = canvas.create_rectangle(
                left-1, top-1, right+1, bottom+1,
                outline=self.colors['accent'], width=1
            )
            
            # Draw the inner rectangle with minimal styling
            preview_rect = canvas.create_rectangle(
                left, top, right, bottom,
                outline=self.colors['green'], width=1,
                fill=self.colors['accent'], stipple="gray12"  # Sparse fill
            )
            
            # Add minimal grid lines
            cell_width = width // 3
            cell_height = height // 3
            
            # Vertical grid lines
            for i in range(1, 3):
                line = canvas.create_line(
                    left + i * cell_width, top,
                    left + i * cell_width, bottom,
                    fill=self.colors['green'], width=1, dash=(1, 3)
                )
                grid_lines.append(line)
                
            # Horizontal grid lines
            for i in range(1, 3):
                line = canvas.create_line(
                    left, top + i * cell_height,
                    right, top + i * cell_height,
                    fill=self.colors['green'], width=1, dash=(1, 3)
                )
                grid_lines.append(line)
            
            # Update coordinate display with minimal styling
            canvas.delete("coords")
            
            # Create minimal coordinate display
            coord_text = f"pos: ({left},{top}) • size: {width}×{height}"
            
            # Simple text - no background
            coords_text = canvas.create_text(
                screen_width // 2, screen_height - 20,
                text=coord_text, 
                fill=self.colors['text_bright'],
                font=("Consolas", 9),
                tags="coords"
            )
        
        def on_mouse_click(event):
            nonlocal preview_rect, outline_rect, grid_lines
            
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
            
            # Close selection window
            selection_window.destroy()
            
            # Set region in detector
            if self.detector:
                self.detector.region = (left, top, right, bottom)
                self.log(f"Region selected: ({left},{top}) {width}×{height}")
                
                # Update UI to show selected region
                self.update_region_label()
            
            # Restore main window
            self.root.deiconify()
        
        # Bind mouse events
        canvas.bind("<Motion>", update_preview)  # Update preview on mouse move
        canvas.bind("<ButtonPress-1>", on_mouse_click)
        
        # Add visual guides - crosshairs
        screen_width = selection_window.winfo_screenwidth()
        screen_height = selection_window.winfo_screenheight()
        
        # Minimal instructions
        instructions = tk.Label(
            canvas, 
            text="SELECT REGION • CLICK TO PLACE • ESC TO CANCEL", 
            font=("Consolas", 10), 
            fg=self.colors['green'],
            bg=self.colors['bg_dark'],
            padx=20,
            pady=5
        )
        canvas.create_window(screen_width // 2, 30, window=instructions)
        
        # Add minimal crosshair guides
        # Horizontal line
        canvas.create_line(
            0, screen_height // 2,
            screen_width, screen_height // 2,
            fill=self.colors['accent'], width=1, dash=(5, 5)
        )
        
        # Vertical line
        canvas.create_line(
            screen_width // 2, 0,
            screen_width // 2, screen_height,
            fill=self.colors['accent'], width=1, dash=(5, 5)
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
                self.region_info_label.config(
                    text=f"region({left},{top},{width}x{height})"
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
        self.diff_frame = None
        self.change_history = []
        self.color_frame = None
        
        # Last detection time for cooldown
        self.last_detection_time = 0
        self.detection_cooldown = 0.5  # Cooldown between detections
        
        # Capture interval in seconds
        self.capture_interval = 0.05  # Capture interval
        
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
        
        # Detection thread reference
        self.detection_thread = None
        
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
                    self.log("Invalid region size detected. Please select a new region.")
                    return None
                else:
                    # Capture specific region
                    screenshot = ImageGrab.grab(bbox=self.region)
            else:
                # Region is required
                self.log("No region selected. Please select a region first.")
                return None
                
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
        frame = self.capture_screen()
        if frame is not None:
            self.reference_frame = frame
            self.log(f"Reference frame captured: {self.reference_frame.shape}")
            return True
        else:
            self.log("Failed to capture reference frame")
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
        """Main detection loop with improved thread control"""
        while self.is_running and not self.thread_control.get("stop_requested", False):
            try:
                # Check if paused
                if self.thread_control.get("paused", False):
                    time.sleep(0.1)
                    continue
                    
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
                    
                    # Quick focus and key press
                    if self.focus_play_together_window():
                        self.send_f_key()
                        
                        # Capture new reference frame after detection
                        time.sleep(0.2)  # Reduced from 1.0 to 0.2 seconds
                    else:
                        self.log("Failed to focus window, skipping key press")
                    
                    # Pause detection for 5 seconds after detection
                    pause_start = time.time()
                    self.log("Pausing detection for 5 seconds...")
                    time.sleep(2)
                    
                    # Wait additional time, checking for stop requests
                    pause_end = pause_start + 5
                    while time.time() < pause_end and self.is_running and not self.thread_control.get("stop_requested", False):
                        remaining = int(pause_end - time.time())
                        if self.gui:
                            self.gui.root.after(0, lambda r=remaining: self.gui.status_label.config(
                                text=f"system:monitor.paused ({r}s)",
                                style="Paused.Status.TLabel"
                            ))
                        time.sleep(0.1)
                    
                    # Press ESC after pause
                    if self.is_running and not self.thread_control.get("stop_requested", False):
                        self.log("Pressing ESC key...")
                        if self.focus_play_together_window():
                            self.send_esc_key()
                        else:
                            self.log("Failed to focus window, skipping ESC key press")
                    
                    # Wait 2 seconds, checking for stop requests
                    esc_end = time.time() + 2
                    while time.time() < esc_end and self.is_running and not self.thread_control.get("stop_requested", False):
                        time.sleep(0.1)
                    
                    # Press F key
                    if self.is_running and not self.thread_control.get("stop_requested", False):
                        self.log("Pressing F key...")
                        if self.focus_play_together_window():
                            self.send_f_key()
                            # Capture new reference frame after F key press
                            time.sleep(0.2)  # Wait for screen to update
                        else:
                            self.log("Failed to focus window, skipping F key press")
                    
                    # Update status to running
                    if self.gui and self.is_running and not self.thread_control.get("stop_requested", False):
                        self.gui.root.after(0, lambda: self.gui.set_status_indicator("running"))
                    
                    # Check one more time for stop request
                    if not self.is_running or self.thread_control.get("stop_requested", False):
                        break
                        
                    # Complete remaining pause time
                    time.sleep(0.5)
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
                
        # Thread is exiting
        self.log("Detection thread exiting")
        self.is_running = False

def main():
    root = tk.Tk()
    root.title("Pixel Change Monitor")
    
    # Set app icon (if available)
    try:
        root.iconbitmap("app_icon.ico")
    except:
        pass  # Icon file not found, use default
    
    # Create and start the application
    app = PixelChangeDetectorGUI(root)
    
    # Center window on screen
    window_width = 900
    window_height = 600
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    center_x = int(screen_width/2 - window_width/2)
    center_y = int(screen_height/2 - window_height/2)
    
    # Set window size and position
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    # Add welcome message
    app.log("Pixel Change Monitor initialized")
    app.log("Version 1.0 • Minimalist Terminal Edition")
    app.log("Color palette: Dark + Green/Purple accents")
    app.log("System ready")
    
    # Start the main loop
    root.mainloop()

if __name__ == "__main__":
    main() 