import tkinter as tk
from tkinter import ttk, font as tkfont
import win32gui
import win32con
import win32process
import win32api
import ctypes
from PIL import Image, ImageTk
import os
import threading
import time
import math
import datetime

class BubbleChatOverlay:
    def __init__(self, root=None):
        # Create root window if not provided
        if root is None:
            self.root = tk.Tk()
            self.is_toplevel = False
        else:
            self.root = tk.Toplevel(root)
            self.is_toplevel = True
            
        # Configure the window
        self.root.title("AutoFisher v0.0.01a")
        self.root.geometry("380x580")
        self.root.attributes('-topmost', True)  # Always on top
        self.root.overrideredirect(True)  # Remove window decorations
        self.root.attributes('-alpha', 0.9)  # Slightly transparent
        
        # Colors and style
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
        
        # Configure ttk styles
        self.configure_style()
        
        # Track if window is minimized
        self.is_minimized = False
        self.minimized_width = 50
        self.minimized_height = 50
        self.expanded_width = 380
        self.expanded_height = 580
        
        # Game window tracking
        self.game_window = None
        self.game_window_name = "Play Together"
        self.offset_x = 16  # Offset from game window left edge
        self.offset_y = 36  # Offset from game window top edge
        self.tracking_active = False
        self.tracking_thread = None
        
        # Smooth movement variables
        self.target_x = 0
        self.target_y = 0
        self.current_x = 0
        self.current_y = 0
        self.is_animating = False
        self.animation_speed = 0.15  # Lower = faster animation (0-1)
        self.animation_min_step = 1  # Minimum pixel step for small movements
        self.animation_id = None     # Store animation after() ID
        
        # Track mouse position for dragging
        self.drag_data = {"x": 0, "y": 0, "dragging": False}
        
        # Create the UI (expanded state by default)
        self.main_frame = None
        self.minimized_frame = None
        self.create_widgets()
        
        # Find game window and position the overlay
        self.find_game_window()
        self.position_relative_to_game()
        
        # Start tracking thread
        self.start_tracking()
        
    def configure_style(self):
        """Configure the app style with a matcha and oak wood inspired theme"""
        style = ttk.Style()
        
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
        
        style.configure('Panel.TFrame', padding=6, relief="flat", borderwidth=0, background=self.colors['bg_dark'])
        style.configure('Terminal.TLabelframe', padding=8, relief="solid", borderwidth=1, background=self.colors['bg_dark'])
        style.configure('Terminal.TLabelframe.Label', font=small_font, background=self.colors['bg_dark'], foreground=self.colors['accent'], padding=(5, 0))
        
        style.configure('TEntry', fieldbackground=self.colors['bg_dark'], foreground=self.colors['accent_bright'], insertcolor=self.colors['cursor'], borderwidth=1, relief="solid", font=small_font)
        
        style.configure('TCheckbutton', background=self.colors['bg_dark'], foreground=self.colors['accent'], font=small_font)
        style.map('TCheckbutton', background=[('active', self.colors['bg_dark'])], foreground=[('active', self.colors['accent_bright'])])
        
        style.configure('TScale', background=self.colors['bg_dark'], troughcolor=self.colors['bg_dark'], slidercolor=self.colors['accent'], borderwidth=0)
        
        self.root.configure(background=self.colors['bg_dark'])
        
    def create_widgets(self):
        # Create expanded view
        self.create_expanded_view()
        
        # Create minimized view (but don't show it yet)
        self.create_minimized_view()
    
    def create_expanded_view(self):
        """Create the expanded view with AutoFisher UI"""
        # Main frame
        self.main_frame = tk.Frame(self.root, bg=self.colors['bg_dark'], bd=2, relief=tk.SOLID)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title bar with controls
        self.title_bar = tk.Frame(self.main_frame, bg=self.colors['bg_term'], height=30)
        self.title_bar.pack(fill=tk.X)
        
        # Bind drag events to title bar
        self.title_bar.bind("<ButtonPress-1>", self.start_drag)
        self.title_bar.bind("<ButtonRelease-1>", self.stop_drag)
        self.title_bar.bind("<B1-Motion>", self.on_drag)
        
        # Title label
        self.title_label = tk.Label(self.title_bar, text="AutoFisher v0.0.01a", bg=self.colors['bg_term'],
                                   fg=self.colors['accent'], font=("Segoe UI", 10, "bold"))
        self.title_label.pack(side=tk.LEFT, padx=10)
        
        # Control buttons
        btn_frame = tk.Frame(self.title_bar, bg=self.colors['bg_term'])
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Minimize/Expand toggle button
        self.toggle_button = tk.Button(btn_frame, text="−", width=3, bg=self.colors['bg_term'],
                                     fg=self.colors['text'], bd=0, font=("Segoe UI", 10, "bold"),
                                     command=self.toggle_minimize)
        self.toggle_button.pack(side=tk.LEFT)
        
        # Close button
        self.close_button = tk.Button(btn_frame, text="×", width=3, bg=self.colors['bg_term'],
                                     fg=self.colors['alert'], bd=0, font=("Segoe UI", 10, "bold"),
                                     command=self.close)
        self.close_button.pack(side=tk.LEFT)
        
        # Content area
        self.content_frame = tk.Frame(self.main_frame, bg=self.colors['bg_dark'])
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create AutoFisher UI sections
        self.create_settings_section()
        self.create_monitoring_section()
        self.create_control_section()
        self.create_status_section()
        self.create_log_section()
        
    def create_settings_section(self):
        """Create settings section similar to AutoFisher"""
        settings_frame = ttk.LabelFrame(self.content_frame, text="SETTINGS", style='Terminal.TLabelframe')
        settings_frame.pack(fill=tk.X, pady=(0, 8), padx=0)
        
        # Use a grid layout for settings
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
            relief="flat",
            font=('Segoe UI', 10)
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
            relief="flat",
            font=('Segoe UI', 10)
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
            relief="flat",
            font=('Segoe UI', 10)
        )
        self.fishing_key_entry.pack(side=tk.LEFT)
        
        # Apply Settings button
        apply_button_frame = ttk.Frame(settings_grid, style='Term.TFrame')
        apply_button_frame.grid(row=4, column=0, columnspan=2, sticky='e', padx=(0, 8), pady=(8, 0))
        
        self.apply_button = tk.Button(
            apply_button_frame, 
            text="Apply Settings",
            command=self.dummy_apply_settings,
            bg=self.colors['bg_dark'],
            fg=self.colors['accent'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['accent_alt'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=6,
            font=('Segoe UI', 10, 'bold')
        )
        self.apply_button.pack(side=tk.RIGHT, padx=4)
        
    def create_monitoring_section(self):
        """Create monitoring section similar to AutoFisher"""
        monitoring_frame = ttk.LabelFrame(self.content_frame, text="MONITORING", style='Terminal.TLabelframe')
        monitoring_frame.pack(fill=tk.X, pady=(0, 8), padx=0)

        # Stats details in two columns
        self.stats_frame = ttk.Frame(monitoring_frame, style='Term.TFrame')
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
            
        # Initialize with dummy values
        self.update_stats_display()
        
    def create_control_section(self):
        """Create control section similar to AutoFisher"""
        control_frame = ttk.LabelFrame(self.content_frame, text="CONTROL", style='Terminal.TLabelframe')
        control_frame.pack(fill=tk.X, pady=(0, 8), padx=0)
        
        button_frame = ttk.Frame(control_frame, style='Term.TFrame')
        button_frame.pack(fill=tk.X, pady=4)
        
        self.start_button = tk.Button(
            button_frame, 
            text="start",
            command=self.dummy_start,
            bg=self.colors['bg_dark'],
            fg=self.colors['green'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['green_alt'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=5,
            font=('Segoe UI', 10)
        )
        self.start_button.pack(side=tk.LEFT, padx=(5, 5))
        
        self.stop_button = tk.Button(
            button_frame, 
            text="stop",
            command=self.dummy_stop,
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
            font=('Segoe UI', 10)
        )
        self.stop_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.pause_button = tk.Button(
            button_frame, 
            text="pause",
            command=self.dummy_pause,
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
            font=('Segoe UI', 10)
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
            pady=5,
            font=('Segoe UI', 10)
        )
        self.clear_button.pack(side=tk.LEFT)
        
        # Second row of buttons
        button_frame2 = ttk.Frame(control_frame, style='Term.TFrame')
        button_frame2.pack(fill=tk.X, pady=4)
        
        # Capture reference button
        self.ref_button = tk.Button(
            button_frame2, 
            text="capture-reference",
            command=self.dummy_capture_reference,
            bg=self.colors['bg_dark'],
            fg=self.colors['accent'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['accent_alt'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=15,
            pady=5,
            font=('Segoe UI', 10)
        )
        self.ref_button.pack(side=tk.LEFT, padx=(5, 5))

        self.region_button = tk.Button(
            button_frame2, 
            text="select-region",
            command=self.dummy_select_region,
            bg=self.colors['bg_dark'],
            fg=self.colors['green'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['green_alt'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=5,
            font=('Segoe UI', 10)
        )
        self.region_button.pack(fill=tk.X, padx=(5, 5))
        
    def create_status_section(self):
        """Create status section similar to AutoFisher"""
        status_frame = ttk.LabelFrame(self.content_frame, text="STATUS", style='Terminal.TLabelframe')
        status_frame.pack(fill=tk.X, pady=(0, 8), padx=0)

        # System status
        self.status_label = ttk.Label(status_frame, text="System: monitor.idle", style='Status.TLabel', font=('Segoe UI', 16))
        self.status_label.pack(fill=tk.X, pady=(2, 2), padx=0)
        
    def create_log_section(self):
        """Create log section similar to AutoFisher"""
        log_frame = ttk.LabelFrame(self.content_frame, text="LOGS", style='Terminal.TLabelframe')
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0), padx=0)
        
        self.log_console = tk.Text(
            log_frame,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            font=('Consolas', 9),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=8
        )
        self.log_console.pack(fill=tk.BOTH, expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_console.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_console['yscrollcommand'] = scrollbar.set
        
        # Add initial log message
        self.add_log("AutoFisher initialized!")
        self.add_log("Overlay mode enabled - drag from title bar to move")
        
    def update_stats_display(self):
        """Update the stats display with dummy values"""
        stats_data = {
            "total_detections": "0",
            "session_runtime": "00:00:00",
            "detections_per_hour": "0.0",
            "avg_interval": "N/A",
            "current_threshold": f"{self.threshold_var.get():.3f}",
            "cooldown": f"{self.cooldown_var.get():.1f}s",
            "key_mapping": self.fishing_key_var.get().upper(),
            "processing_fps": "30"
        }
        
        for key, label in self.stats_labels.items():
            label.config(text=f"{label.cget('text').split(':')[0]}: {stats_data.get(key, '...')}")
            
    def dummy_apply_settings(self):
        """Dummy function for apply settings button"""
        self.add_log(f"Settings applied: threshold={self.threshold_var.get():.2f}, cooldown={self.cooldown_var.get()}s, key={self.fishing_key_var.get()}")
        self.update_stats_display()
        
    def dummy_start(self):
        """Dummy function for start button"""
        self.add_log("Starting detection...")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.pause_button.config(state=tk.NORMAL)
        self.status_label.config(text="System: monitor.active", foreground=self.colors['green'])
        
    def dummy_stop(self):
        """Dummy function for stop button"""
        self.add_log("Detection stopped")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED)
        self.status_label.config(text="System: monitor.stopped", foreground=self.colors['alert'])
        
    def dummy_pause(self):
        """Dummy function for pause button"""
        if self.pause_button.cget("text") == "pause":
            self.add_log("Detection paused")
            self.pause_button.config(text="resume")
            self.status_label.config(text="System: monitor.paused", foreground=self.colors['warning'])
        else:
            self.add_log("Detection resumed")
            self.pause_button.config(text="pause")
            self.status_label.config(text="System: monitor.active", foreground=self.colors['green'])
            
    def dummy_capture_reference(self):
        """Dummy function for capture reference button"""
        self.add_log("Reference frame captured")
        
    def dummy_select_region(self):
        """Dummy function for select region button"""
        self.add_log("Please select a region on the screen...")
        
    def add_log(self, message):
        """Add a message to the log console"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        self.log_console.config(state=tk.NORMAL)
        self.log_console.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_console.see(tk.END)  # Auto-scroll to end
        self.log_console.config(state=tk.DISABLED)
        
    def clear_logs(self):
        """Clear the log console"""
        self.log_console.config(state=tk.NORMAL)
        self.log_console.delete(1.0, tk.END)
        self.log_console.config(state=tk.DISABLED)
        self.add_log("Logs cleared")
    
    def create_minimized_view(self):
        """Create the minimized view (just the expand button)"""
        self.minimized_frame = tk.Frame(self.root, bg=self.colors['bg_dark'], bd=2, relief=tk.SOLID)
        # Don't pack it yet - only when minimized
        
        # Create rounded appearance
        self.minimized_content = tk.Frame(self.minimized_frame, bg=self.colors['bg_term'],
                                        width=self.minimized_width, height=self.minimized_height)
        self.minimized_content.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Expand button
        self.expand_button = tk.Button(self.minimized_content, text="+", bg=self.colors['bg_term'],
                                     fg=self.colors['accent'], bd=0, font=("Segoe UI", 12, "bold"),
                                     command=self.toggle_minimize)
        self.expand_button.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        # Bind drag events to minimized view
        self.minimized_frame.bind("<ButtonPress-1>", self.start_drag)
        self.minimized_frame.bind("<ButtonRelease-1>", self.stop_drag)
        self.minimized_frame.bind("<B1-Motion>", self.on_drag)
        
    # Removed chat-related methods as they're no longer needed
            
    def toggle_minimize(self):
        """Toggle between minimized and expanded states with animation"""
        # Store current position for animation reference
        current_position = (self.root.winfo_x(), self.root.winfo_y())
        
        if self.is_minimized:
            # Expand - check if widgets exist first
            if self.minimized_frame and self.main_frame:
                # First animate to target size
                self._animate_size(
                    self.minimized_width, 
                    self.minimized_height,
                    self.expanded_width, 
                    self.expanded_height,
                    lambda: self._complete_expand()
                )
        else:
            # Minimize - check if widgets exist first
            if self.main_frame and self.minimized_frame:
                # First animate to target size
                self._animate_size(
                    self.expanded_width, 
                    self.expanded_height,
                    self.minimized_width, 
                    self.minimized_height,
                    lambda: self._complete_minimize()
                )
                
        self.is_minimized = not self.is_minimized
    
    def _animate_size(self, start_width, start_height, end_width, end_height, callback=None):
        """Animate window size change"""
        # Number of animation steps
        steps = 10
        duration = 16  # ms per step (~60fps)
        
        # Calculate step sizes
        width_step = (end_width - start_width) / steps
        height_step = (end_height - start_height) / steps
        
        # Define animation function
        def _animate_size_step(step=0, current_width=start_width, current_height=start_height):
            if step >= steps:
                # Final step - set exact target size
                self.root.geometry(f"{int(end_width)}x{int(end_height)}")
                if callback:
                    callback()
                return
                
            # Calculate new size
            new_width = current_width + width_step
            new_height = current_height + height_step
            
            # Update window size
            self.root.geometry(f"{int(new_width)}x{int(new_height)}")
            
            # Schedule next step
            self.root.after(duration, lambda: _animate_size_step(
                step + 1, new_width, new_height
            ))
            
        # Start animation
        _animate_size_step()
    
    def _complete_expand(self):
        """Complete the expansion after size animation"""
        if self.minimized_frame and self.main_frame:
            self.minimized_frame.pack_forget()
            self.main_frame.pack(fill=tk.BOTH, expand=True)
            # Reposition relative to game window after changing size
            self.position_relative_to_game()
    
    def _complete_minimize(self):
        """Complete the minimization after size animation"""
        if self.main_frame and self.minimized_frame:
            self.main_frame.pack_forget()
            self.minimized_frame.pack(fill=tk.BOTH, expand=True)
            # Reposition relative to game window after changing size
            self.position_relative_to_game()
        
    def find_game_window(self):
        """Find the Play Together game window"""
        def enum_window_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd).lower()
                if self.game_window_name.lower() in window_text:
                    self.game_window = hwnd
                    return False
            return True
            
        win32gui.EnumWindows(enum_window_callback, None)
        
        if self.game_window:
            return True
        return False
        
    def position_relative_to_game(self):
        """Position the overlay relative to the game window"""
        if not self.game_window:
            # Fall back to default position if game window not found
            self.position_default()
            return
            
        try:
            # Get game window position
            game_rect = win32gui.GetWindowRect(self.game_window)
            game_x, game_y, _, _ = game_rect
            
            # Apply offset
            x = game_x + self.offset_x
            y = game_y + self.offset_y
            
            # Start smooth animation to target position
            self.animate_to_position(x, y)
        except Exception:
            # Fall back to default position
            self.position_default()
            
    def animate_to_position(self, target_x, target_y):
        """Smoothly animate the window to a new position"""
        # Set target position
        self.target_x = target_x
        self.target_y = target_y
        
        # Get current position if not yet set
        if self.current_x == 0 and self.current_y == 0:
            self.current_x = self.root.winfo_x()
            self.current_y = self.root.winfo_y()
        
        # Start animation if not already running
        if not self.is_animating:
            self.is_animating = True
            self._animate_step()
    
    def _animate_step(self):
        """Perform a single step of position animation"""
        # Cancel any existing animation
        if self.animation_id:
            self.root.after_cancel(self.animation_id)
            self.animation_id = None
            
        # Calculate distance to target
        dx = self.target_x - self.current_x
        dy = self.target_y - self.current_y
        distance = math.sqrt(dx*dx + dy*dy)
        
        # If we're close enough, snap to final position
        if distance < 1.0:
            self.current_x = self.target_x
            self.current_y = self.target_y
            self.root.geometry(f"+{int(self.current_x)}+{int(self.current_y)}")
            self.is_animating = False
            return
            
        # Calculate step size (adaptive based on distance)
        step = max(self.animation_min_step, distance * self.animation_speed)
        
        # Calculate new position
        if distance > 0:
            ratio = step / distance
            self.current_x += dx * ratio
            self.current_y += dy * ratio
        
        # Update window position
        self.root.geometry(f"+{int(self.current_x)}+{int(self.current_y)}")
        
        # Schedule next animation step (use faster updates for smoother animation)
        self.animation_id = self.root.after(16, self._animate_step)  # ~60fps
            
    def position_default(self):
        """Position the window in the bottom-right corner of the screen as fallback"""
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        x = screen_width - self.expanded_width - 20
        y = screen_height - self.expanded_height - 50
        
        # Use animation for default position too
        self.animate_to_position(x, y)
        
    def start_tracking(self):
        """Start a thread to track the game window position"""
        self.tracking_active = True
        self.tracking_thread = threading.Thread(target=self._tracking_loop)
        self.tracking_thread.daemon = True  # Thread will exit when main thread exits
        self.tracking_thread.start()
        
    def _tracking_loop(self):
        """Loop that monitors game window position and updates overlay position"""
        last_position = None
        position_samples = []
        max_samples = 3  # Number of position samples to keep for smoothing
        min_update_threshold = 2  # Minimum pixel change to trigger update
        adaptive_sleep = 0.03  # Start with fast updates
        
        while self.tracking_active:
            if self.game_window:
                try:
                    # Check if window still exists
                    if win32gui.IsWindow(self.game_window):
                        # Get current position
                        game_rect = win32gui.GetWindowRect(self.game_window)
                        game_x, game_y, _, _ = game_rect
                        
                        # Add to position samples for smoothing
                        position_samples.append((game_x, game_y))
                        if len(position_samples) > max_samples:
                            position_samples.pop(0)
                        
                        # Calculate smoothed position (average of samples)
                        if len(position_samples) > 0:
                            smooth_x = sum(x for x, _ in position_samples) / len(position_samples)
                            smooth_y = sum(y for _, y in position_samples) / len(position_samples)
                            
                            # Calculate movement magnitude from last position
                            if last_position:
                                last_x, last_y = last_position
                                movement = math.sqrt((smooth_x - last_x)**2 + (smooth_y - last_y)**2)
                                
                                # Adjust polling rate based on movement
                                if movement > 20:  # Fast movement
                                    adaptive_sleep = 0.016  # ~60 fps
                                elif movement > 5:  # Medium movement
                                    adaptive_sleep = 0.033  # ~30 fps
                                else:  # Slow or no movement
                                    adaptive_sleep = max(0.05, min(0.2, adaptive_sleep * 1.1))  # Gradually reduce polling
                                
                                # Only update if position changed significantly
                                if movement > min_update_threshold:
                                    last_position = (smooth_x, smooth_y)
                                    # Use after() to safely update UI from thread
                                    x = smooth_x + self.offset_x
                                    y = smooth_y + self.offset_y
                                    self.root.after(0, lambda x=x, y=y: self.animate_to_position(x, y))
                            else:
                                # First position
                                last_position = (smooth_x, smooth_y)
                                x = smooth_x + self.offset_x
                                y = smooth_y + self.offset_y
                                self.root.after(0, lambda x=x, y=y: self.animate_to_position(x, y))
                    else:
                        # Window closed/changed, try to find it again
                        self.game_window = None
                        self.root.after(0, self.find_game_window)
                        adaptive_sleep = 0.2  # Slower polling when searching
                except Exception:
                    # Error occurred, try to find window again
                    self.game_window = None
                    self.root.after(0, self.find_game_window)
                    adaptive_sleep = 0.2  # Slower polling when searching
            else:
                # Try to find the game window if not found
                self.root.after(0, self.find_game_window)
                adaptive_sleep = 0.2  # Slower polling when searching
                
            # Adaptive sleep based on movement
            time.sleep(adaptive_sleep)
        
    def start_drag(self, event):
        """Begin dragging the window"""
        self.drag_data["x"] = event.x
        self.drag_data["y"] = event.y
        self.drag_data["dragging"] = True
        
        # Pause animation during dragging
        if self.is_animating and self.animation_id:
            self.root.after_cancel(self.animation_id)
            self.is_animating = False
        
    def stop_drag(self, event):
        """End dragging the window"""
        self.drag_data["dragging"] = False
        
        # Update current position after drag
        self.current_x = self.root.winfo_x()
        self.current_y = self.root.winfo_y()
        
    def on_drag(self, event):
        """Handle window dragging"""
        if self.drag_data["dragging"]:
            x = self.root.winfo_x() + (event.x - self.drag_data["x"])
            y = self.root.winfo_y() + (event.y - self.drag_data["y"])
            
            # Update window position directly during drag (no animation)
            self.root.geometry(f"+{x}+{y}")
            
            # Update current position for animation system
            self.current_x = x
            self.current_y = y
            
    def close(self):
        """Close the overlay"""
        # Stop tracking thread
        self.tracking_active = False
        if self.tracking_thread and self.tracking_thread.is_alive():
            self.tracking_thread.join(0.1)  # Wait briefly for thread to terminate
            
        if self.is_toplevel:
            self.root.destroy()
        else:
            self.root.quit()
            
    def run(self):
        """Start the main loop if not a toplevel window"""
        if not self.is_toplevel:
            self.root.mainloop()

# Run the overlay if executed directly
if __name__ == "__main__":
    overlay = BubbleChatOverlay()
    overlay.run() 