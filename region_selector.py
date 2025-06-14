import tkinter as tk
from tkinter import ttk
import time
import threading
import numpy as np
import cv2
import win32gui
import win32con
import win32api
import win32process
import ctypes
from ctypes import wintypes
import psutil
from PIL import ImageGrab, Image, ImageTk

# For direct window access
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=Tue)

# Add new monitor API declarations
MonitorFromPoint = user32.MonitorFromPoint
MonitorFromPoint.argtypes = [wintypes.POINT, ctypes.c_uint]
MonitorFromPoint.restype = ctypes.c_void_p

GetMonitorInfoW = user32.GetMonitorInfoW
GetMonitorInfoW.argtypes = [ctypes.c_void_p, ctypes.py_object]
GetMonitorInfoW.restype = ctypes.c_bool

EnumDisplayMonitors = user32.EnumDisplayMonitors
EnumDisplayMonitors.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
EnumDisplayMonitors.restype = ctypes.c_bool

# Define MONITORINFOEX structure
class MONITORINFOEX(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint),
        ('rcMonitor', wintypes.RECT),
        ('rcWork', wintypes.RECT),
        ('dwFlags', ctypes.c_uint),
        ('szDevice', ctypes.c_wchar * 32)
    ]

# Callback for EnumDisplayMonitors
class MonitorEnumProc:
    def __init__(self):
        self.monitors = []
        
    def callback(self, hMonitor, hdcMonitor, lprcMonitor, dwData):
        info = MONITORINFOEX()
        info.cbSize = ctypes.sizeof(MONITORINFOEX)
        if not GetMonitorInfoW(hMonitor, ctypes.byref(info)):  # Fix: Use byref for structure
            print(f"GetMonitorInfoW failed: {ctypes.get_last_error()}")
            return True
        
        monitor_info = {
            'handle': hMonitor,
            'left': info.rcMonitor.left,
            'top': info.rcMonitor.top,
            'right': info.rcMonitor.right,
            'bottom': info.rcMonitor.bottom,
            'width': info.rcMonitor.right - info.rcMonitor.left,
            'height': info.rcMonitor.bottom - info.rcMonitor.top,
            'is_primary': bool(info.dwFlags & 1),  # MONITORINFOF_PRIMARY
            'device': info.szDevice
        }
        self.monitors.append(monitor_info)
        return True

# Convert MonitorEnumProc.callback to a C callable function
MonitorEnumProcType = ctypes.WINFUNCTYPE(
    ctypes.c_bool,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.wintypes.RECT),
    ctypes.c_void_p
)

class RegionSelectorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Region Selector")
        self.root.geometry("800x600")
        self.root.minsize(800, 600)
        
        # Define colors
        self.colors = {
            'bg_dark': '#050505',
            'bg_term': '#0E0E0E',
            'bg_lighter': '#1A1A1A',
            'text': '#F8F5FF',
            'text_bright': '#FFFFFF',
            'text_dim': '#999999',
            'accent': '#A280FF',
            'green': '#C4E6B5',
            'border': '#2A2A2A',
            'alert': '#FF4D4D',
        }
        
        # Initialize variables
        self.selected_region = None
        self.is_monitoring = False
        self.monitor_thread = None
        self.game_window_rect = None
        self.game_hwnd = None
        self.offset_x = 0  # Offset for fine-tuning
        self.offset_y = 0  # Offset for fine-tuning
        
        # Get monitor information
        self.monitors = self.get_monitor_info()
        
        # Create main container
        main_container = ttk.Frame(self.root, style='TFrame')
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Split into left and right panels
        left_panel = ttk.Frame(main_container, style='TFrame', width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        left_panel.pack_propagate(False)
        
        right_panel = ttk.Frame(main_container, style='TFrame')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Create monitor selection frame
        monitor_frame = ttk.LabelFrame(left_panel, text="MONITOR SELECTION", style='Terminal.TLabelframe')
        monitor_frame.pack(fill=tk.X, pady=(0, 8), padx=0)
        
        # Monitor selection dropdown
        monitor_select_frame = ttk.Frame(monitor_frame, style='Term.TFrame')
        monitor_select_frame.pack(fill=tk.X, pady=(10, 5), padx=5)
        
        ttk.Label(monitor_select_frame, text="monitor:", style='Term.TLabel').pack(side=tk.LEFT, padx=(0, 5))
        
        # Create monitor selection dropdown
        self.monitor_var = tk.StringVar()
        monitor_options = []
        for i, m in enumerate(self.monitors):
            if m['is_primary']:
                monitor_options.append(f"Monitor {i+1}: {m['width']}x{m['height']} [Primary]")
            else:
                monitor_options.append(f"Monitor {i+1}: {m['width']}x{m['height']}")
        
        if not monitor_options:
            monitor_options = ["Monitor 1: Primary"]
        
        self.monitor_var.set(monitor_options[0])
        self.monitor_combo = ttk.Combobox(
            monitor_select_frame, 
            textvariable=self.monitor_var,
            values=monitor_options,
            state="readonly",
            width=25,
            style='TCombobox'
        )
        self.monitor_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Create region selection frame
        self.region_frame = ttk.LabelFrame(left_panel, text="REGION SELECTION", style='Terminal.TLabelframe')
        self.region_frame.pack(fill=tk.X, pady=(0, 8), padx=0)
        
        # Show detected window info
        window_info_frame = ttk.Frame(self.region_frame, style='Term.TFrame')
        window_info_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.window_info_label = ttk.Label(window_info_frame, text="", style='TLabel')
        self.window_info_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Add refresh button
        self.refresh_button = tk.Button(
            window_info_frame, 
            text="refresh",
            command=self.manual_refresh,
            bg=self.colors['bg_dark'],
            fg=self.colors['accent'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['accent'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=5,
            pady=2,
            font=('Segoe UI', 8)
        )
        self.refresh_button.pack(side=tk.RIGHT, padx=(5, 5))
        
        # Region size input
        size_frame = ttk.Frame(self.region_frame, style='Term.TFrame')
        size_frame.pack(fill=tk.X, pady=4)
        
        ttk.Label(size_frame, text="region_size:", style='Term.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        self.size_var = tk.StringVar(value="50")
        self.size_entry = tk.Entry(
            size_frame, 
            textvariable=self.size_var, 
            width=5,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            insertbackground=self.colors['green'],
            highlightthickness=1,
            highlightbackground=self.colors['border'],
            highlightcolor=self.colors['accent'],
            relief="flat",
            font=('Consolas', 10)
        )
        self.size_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(size_frame, text="px", style='Term.TLabel').pack(side=tk.LEFT)
        
        # Add offset adjustment controls
        offset_frame = ttk.Frame(self.region_frame, style='Term.TFrame')
        offset_frame.pack(fill=tk.X, pady=4)
        
        ttk.Label(offset_frame, text="offset_x:", style='Term.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        
        # Add X offset adjustment buttons
        x_minus_btn = tk.Button(
            offset_frame,
            text="-",
            command=lambda: self.adjust_offset('x', -10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            width=1,
            font=('Segoe UI', 8)
        )
        x_minus_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        self.offset_x_var = tk.StringVar(value="0")
        self.offset_x_entry = tk.Entry(
            offset_frame, 
            textvariable=self.offset_x_var, 
            width=4,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            insertbackground=self.colors['green'],
            highlightthickness=1,
            highlightbackground=self.colors['border'],
            highlightcolor=self.colors['accent'],
            relief="flat",
            font=('Consolas', 10)
        )
        self.offset_x_entry.pack(side=tk.LEFT, padx=2)
        
        x_plus_btn = tk.Button(
            offset_frame,
            text="+",
            command=lambda: self.adjust_offset('x', 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            width=1,
            font=('Segoe UI', 8)
        )
        x_plus_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Label(offset_frame, text="offset_y:", style='Term.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        
        # Add Y offset adjustment buttons
        y_minus_btn = tk.Button(
            offset_frame,
            text="-",
            command=lambda: self.adjust_offset('y', -10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            width=1,
            font=('Segoe UI', 8)
        )
        y_minus_btn.pack(side=tk.LEFT, padx=(2, 0))
        
        self.offset_y_var = tk.StringVar(value="0")
        self.offset_y_entry = tk.Entry(
            offset_frame, 
            textvariable=self.offset_y_var, 
            width=4,
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            insertbackground=self.colors['green'],
            highlightthickness=1,
            highlightbackground=self.colors['border'],
            highlightcolor=self.colors['accent'],
            relief="flat",
            font=('Consolas', 10)
        )
        self.offset_y_entry.pack(side=tk.LEFT, padx=2)
        
        y_plus_btn = tk.Button(
            offset_frame,
            text="+",
            command=lambda: self.adjust_offset('y', 10),
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            width=1,
            font=('Segoe UI', 8)
        )
        y_plus_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Monitor information
        monitor_info_frame = ttk.Frame(self.region_frame, style='Term.TFrame')
        monitor_info_frame.pack(fill=tk.X, pady=4)
        
        self.monitor_info_label = ttk.Label(
            monitor_info_frame, 
            text="", 
            style='Term.TLabel',
            wraplength=280
        )
        self.monitor_info_label.pack(side=tk.LEFT, padx=5, fill=tk.X)
        self.update_monitor_info_label()
        
        # Select region button
        button_frame = ttk.Frame(self.region_frame, style='Term.TFrame')
        button_frame.pack(fill=tk.X, pady=4)
        
        self.select_button = tk.Button(
            button_frame, 
            text="select-region",
            command=self.select_region,
            bg=self.colors['bg_dark'],
            fg=self.colors['green'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['green'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=5,
            font=('Segoe UI', 10)
        )
        self.select_button.pack(side=tk.LEFT, padx=(5, 5))
        
        # Add test capture button
        self.test_button = tk.Button(
            button_frame, 
            text="test-capture",
            command=self.test_capture,
            bg=self.colors['bg_dark'],
            fg=self.colors['accent'],
            activebackground=self.colors['bg_lighter'],
            activeforeground=self.colors['accent'],
            relief="flat",
            bd=1,
            highlightthickness=0,
            padx=10,
            pady=5,
            font=('Segoe UI', 10)
        )
        self.test_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Status label
        status_frame = ttk.Frame(self.region_frame, style='Term.TFrame')
        status_frame.pack(fill=tk.X, pady=4)
        
        ttk.Label(status_frame, text="status:", style='Term.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        self.status_label = ttk.Label(status_frame, text="waiting for game window", style='Term.TLabel')
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Create monitor frame
        monitor_frame = ttk.LabelFrame(right_panel, text="MONITOR", style='Terminal.TLabelframe')
        monitor_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create canvas for displaying the selected region
        self.monitor_canvas = tk.Canvas(
            monitor_frame,
            bg=self.colors['bg_dark'],
            highlightthickness=0
        )
        self.monitor_canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Monitor status label
        self.monitor_status = ttk.Label(monitor_frame, text="waiting for region selection", style='Term.TLabel')
        self.monitor_status.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        # Configure styles
        self.configure_styles()
        
        # Add monitor change callback
        self.monitor_combo.bind("<<ComboboxSelected>>", self.on_monitor_changed)
        
        # Detect game window on startup
        self.detect_game_window()
        self.update_window_info_label()
        
        # Schedule periodic window detection
        self.schedule_window_detection()
        
    def on_monitor_changed(self, event=None):
        """Handle monitor selection change"""
        selection = self.monitor_combo.get()
        print(f"Selected monitor: {selection}")
        self.update_monitor_info_label()
        
    def update_monitor_info_label(self):
        """Update the monitor information label"""
        if not hasattr(self, 'monitors') or not self.monitors:
            self.monitor_info_label.config(text="No monitor information available")
            return
            
        try:
            # Get selected monitor index
            selection = self.monitor_combo.get()
            monitor_idx = int(selection.split(':')[0].replace('Monitor ', '')) - 1
            
            if 0 <= monitor_idx < len(self.monitors):
                m = self.monitors[monitor_idx]
                info = (
                    f"Resolution: {m['width']}x{m['height']}\n"
                    f"Position: ({m['left']},{m['top']})\n"
                    f"{'Primary display' if m['is_primary'] else 'Secondary display'}"
                )
                self.monitor_info_label.config(text=info)
            else:
                self.monitor_info_label.config(text="Invalid monitor selection")
        except Exception as e:
            print(f"Error updating monitor info: {e}")
            self.monitor_info_label.config(text="Error getting monitor info")
        
    def schedule_window_detection(self):
        """Schedule periodic window detection to handle game window movement/resizing"""
        self.detect_game_window(log=False)
        self.update_window_info_label()
        self.root.after(2000, self.schedule_window_detection)
        
    def get_monitor_info(self):
        """Get detailed information about all connected monitors"""
        try:
            # Create monitor enum processor
            monitor_enum = MonitorEnumProc()
            callback = MonitorEnumProcType(monitor_enum.callback)
            
            # Enumerate all monitors
            if not EnumDisplayMonitors(None, None, callback, None):
                raise ctypes.WinError(ctypes.get_last_error())
                
            # If no monitors were found, fall back to primary monitor
            if not monitor_enum.monitors:
                # Get primary monitor dimensions
                width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
                height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
                
                monitor_enum.monitors.append({
                    'handle': 0,
                    'left': 0,
                    'top': 0,
                    'right': width,
                    'bottom': height,
                    'width': width,
                    'height': height,
                    'is_primary': True,
                    'device': r"\\.\DISPLAY1"
                })
                
            # Sort monitors (primary first, then by position)
            monitor_enum.monitors.sort(key=lambda m: (not m['is_primary'], m['left'], m['top']))
            
            # Print monitor info for debugging
            print(f"Detected {len(monitor_enum.monitors)} monitors:")
            for i, m in enumerate(monitor_enum.monitors):
                print(f"  Monitor {i}: {m['width']}x{m['height']} at ({m['left']},{m['top']}) " + 
                      f"{'[PRIMARY]' if m['is_primary'] else ''} {m['device']}")
                
            return monitor_enum.monitors
            
        except Exception as e:
            print(f"Error getting monitor info: {e}")
            # Fallback to single monitor
            width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            
            return [{
                'handle': 0,
                'left': 0,
                'top': 0,
                'right': width,
                'bottom': height,
                'width': width,
                'height': height,
                'is_primary': True,
                'device': r"\\.\DISPLAY1"
            }]
        
    def get_selected_monitor(self):
        """Get the currently selected monitor"""
        selection = self.monitor_combo.get()
        if "Primary" in selection:
            return self.monitors[0]
        else:
            return self.monitors[1] if len(self.monitors) > 1 else self.monitors[0]
        
    def configure_styles(self):
        """Configure the app styles"""
        style = ttk.Style()
        
        # Configure base styles
        style.configure('TFrame', background=self.colors['bg_dark'])
        style.configure('Term.TFrame', background=self.colors['bg_dark'])
        
        # Label styles
        style.configure('TLabel', 
                       background=self.colors['bg_dark'], 
                       foreground=self.colors['text'],
                       font=('Segoe UI', 10))
        
        style.configure('Term.TLabel', 
                       background=self.colors['bg_dark'], 
                       foreground=self.colors['text'],
                       font=('Consolas', 10))
        
        # LabelFrame style
        style.configure('Terminal.TLabelframe', 
                       relief="solid", 
                       borderwidth=1,
                       bordercolor=self.colors['border'],
                       background=self.colors['bg_dark'])
        
        style.configure('Terminal.TLabelframe.Label', 
                       font=('Segoe UI', 10),
                       background=self.colors['bg_dark'],
                       foreground=self.colors['green'],
                       padding=(5, 0))
        
        # Combobox style
        style.configure('TCombobox',
                       fieldbackground=self.colors['bg_dark'],
                       background=self.colors['bg_dark'],
                       foreground=self.colors['text'],
                       arrowcolor=self.colors['green'],
                       selectbackground=self.colors['bg_term'],
                       selectforeground=self.colors['green'])
        
        style.map('TCombobox',
                 fieldbackground=[('readonly', self.colors['bg_dark'])],
                 selectbackground=[('readonly', self.colors['bg_term'])],
                 selectforeground=[('readonly', self.colors['green'])])
    
    def start_monitoring(self):
        """Start monitoring the selected region"""
        if not self.selected_region:
            return
            
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """Stop monitoring the selected region"""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
            
    def _monitor_loop(self):
        """Monitor loop for capturing and displaying the region"""
        last_print_time = 0
        capture_errors = 0
        
        while self.is_monitoring:
            try:
                # Capture the region
                if not self.selected_region:
                    time.sleep(0.1)
                    continue
                    
                # Print debug info periodically, not every few seconds
                current_time = time.time()
                if current_time - last_print_time >= 5:  # Every 5 seconds
                    print(f"Capturing region: {self.selected_region}")
                    last_print_time = current_time
                
                # Get region coordinates
                l, t, r, b = self.selected_region
                region_width = r - l
                region_height = b - t
                
                # Check if any part of region is outside screen bounds
                virtual_left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
                virtual_top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
                virtual_right = virtual_left + win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
                virtual_bottom = virtual_top + win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
                
                if (l < virtual_left or t < virtual_top or 
                    r > virtual_right or b > virtual_bottom):
                    # If region is partly outside screen, adjust it
                    adjusted_l = max(l, virtual_left)
                    adjusted_t = max(t, virtual_top)
                    adjusted_r = min(r, virtual_right)
                    adjusted_b = min(b, virtual_bottom)
                    
                    if adjusted_r <= adjusted_l or adjusted_b <= adjusted_t:
                        # Invalid region
                        print(f"Warning: Region {self.selected_region} is outside visible screen area")
                        self.monitor_status.config(text="error: region outside visible screen")
                        time.sleep(0.5)
                        continue
                        
                    capture_box = (adjusted_l, adjusted_t, adjusted_r, adjusted_b)
                    if capture_box != self.selected_region:
                        print(f"Adjusting capture region to: {capture_box}")
                else:
                    capture_box = self.selected_region
                
                # Capture screenshot using adjusted coordinates if needed
                screenshot = ImageGrab.grab(bbox=capture_box)
                
                # Convert to PhotoImage
                photo = ImageTk.PhotoImage(screenshot)
                
                # Update canvas
                self.monitor_canvas.config(width=photo.width(), height=photo.height())
                self.monitor_canvas.delete("all")
                self.monitor_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
                self.monitor_canvas.image = photo
                
                # Update status
                self.monitor_status.config(text=f"monitoring: {region_width}×{region_height} at ({l},{t})")
                
                # Reset error counter on successful capture
                capture_errors = 0
                
            except Exception as e:
                capture_errors += 1
                error_msg = str(e)
                print(f"Error in monitor loop: {error_msg}")
                self.monitor_status.config(text=f"error: {error_msg[:50]}...")
                
                # If we have repeated errors, slow down the capture rate
                if capture_errors > 5:
                    time.sleep(0.5)
                
            # Adaptive framerate depending on system load
            # Start with higher FPS, then reduce if we see CPU usage is high
            try:
                system_load = psutil.cpu_percent(interval=None)
                if system_load > 80:  # High CPU usage
                    time.sleep(0.1)  # 10 FPS
                elif system_load > 50:  # Moderate CPU usage
                    time.sleep(0.05)  # 20 FPS
                else:
                    time.sleep(0.03)  # 33 FPS
            except:
                time.sleep(0.05)  # Default 20 FPS
    
    def manual_refresh(self):
        """Manually refresh the game window detection"""
        self.detect_game_window()
        self.update_window_info_label()
        self.status_label.config(text="manually refreshed window detection")
        
    def detect_game_window(self, log=True):
        """Detect the PLAY TOGETHER game window and get its rect."""
        old_rect = self.game_window_rect
        self.game_window_rect = None
        self.game_hwnd = None
        
        # Get monitor information 
        self.monitors = self.get_monitor_info()
        
        # List of possible name variations (from pixel_change_trigger.py)
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
        
        # For debugging
        all_windows = []
        
        def enum_window_callback(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd).lower()
                rect = win32gui.GetWindowRect(hwnd)
                
                # Skip windows with empty titles or zero size
                if not window_text or rect[2] - rect[0] <= 0 or rect[3] - rect[1] <= 0:
                    return True
                
                # Add to all windows list for debugging
                all_windows.append({
                    'hwnd': hwnd,
                    'title': window_text,
                    'rect': rect
                })
                
                # Check if this window matches any of our target names
                for variation in name_variations:
                    if variation in window_text:
                        if log:
                            print(f"Found game window: '{window_text}' at {rect}")
                        results.append(hwnd)
                        break
                        
            return True
            
        found_hwnds = []
        win32gui.EnumWindows(enum_window_callback, found_hwnds)
        
        # Print top 10 windows for debugging
        if log:
            print("\nTop visible windows:")
            for i, win in enumerate(sorted(all_windows, key=lambda w: w['title'])):
                if i >= 10:
                    break
                print(f"  {win['title']} ({win['hwnd']}) at {win['rect']}")
        
        # If we found target windows, use the first one
        if found_hwnds:
            self.game_hwnd = found_hwnds[0]
            
            # Get window information
            rect = win32gui.GetWindowRect(self.game_hwnd)
            
            # Get window client area to account for borders
            try:
                # Get client rect
                client_rect = win32gui.GetClientRect(self.game_hwnd)
                client_width = client_rect[2] - client_rect[0]
                client_height = client_rect[3] - client_rect[1]
                
                # Get window rect
                window_rect = rect
                window_width = window_rect[2] - window_rect[0]
                window_height = window_rect[3] - window_rect[1]
                
                # Calculate border sizes
                border_x = (window_width - client_width) // 2
                border_y = (window_height - client_height) - border_x  # Assume title bar at top
                
                if log:
                    print(f"Window size: {window_width}x{window_height}")
                    print(f"Client size: {client_width}x{client_height}")
                    print(f"Border size: horizontal={border_x}px, vertical={border_y}px")
                
                # Store the full window rect and the client rect
                self.game_window_rect = rect
                self.game_client_rect = (
                    rect[0] + border_x,
                    rect[1] + border_y,
                    rect[2] - border_x,
                    rect[3] - border_x
                )
                
                # Check which monitor the game window is on
                game_center_x = (rect[0] + rect[2]) // 2
                game_center_y = (rect[1] + rect[3]) // 2
                
                for i, m in enumerate(self.monitors):
                    if (m['left'] <= game_center_x <= m['right'] and 
                        m['top'] <= game_center_y <= m['bottom']):
                        if log:
                            print(f"Game window is on monitor {i}: {m['device']}")
                        self.game_monitor = m
                        break
            
            except Exception as e:
                if log:
                    print(f"Error getting client rect: {e}")
                self.game_window_rect = rect
                self.game_client_rect = rect
        
        # For testing purposes, if we can't find the game window, create a fallback rect
        if not self.game_window_rect:
            if log:
                print("No game window found, using fallback rectangle for testing")
            
            # Use primary monitor dimensions for fallback
            primary_monitor = next((m for m in self.monitors if m['is_primary']), self.monitors[0])
            screen_width = primary_monitor['width']
            screen_height = primary_monitor['height']
            
            # Create a reasonable sized rectangle in the center of the screen
            width, height = 800, 600
            left = primary_monitor['left'] + (screen_width - width) // 2
            top = primary_monitor['top'] + (screen_height - height) // 2
            self.game_window_rect = (left, top, left + width, top + height)
            self.game_client_rect = self.game_window_rect
            self.game_monitor = primary_monitor
        
        # If window rect changed and we're monitoring, update the region
        if old_rect != self.game_window_rect and self.game_window_rect and self.is_monitoring:
            self.selected_region = self.game_client_rect  # Use client area as default selection
            self.status_label.config(text=f"game window moved - updated region")

    def update_window_info_label(self):
        """Update the window info label with game window details"""
        if self.game_window_rect:
            l, t, r, b = self.game_window_rect
            w, h = r - l, b - t
            
            # Get client rect info if available
            if hasattr(self, 'game_client_rect'):
                cl, ct, cr, cb = self.game_client_rect
                cw, ch = cr - cl, cb - ct
                client_info = f" (client: {cw}x{ch})"
            else:
                client_info = ""
                
            # Get monitor info if available
            if hasattr(self, 'game_monitor'):
                monitor_info = f" on {self.game_monitor['device']}"
            else:
                monitor_info = ""
            
            self.window_info_label.config(text=f"PLAY TOGETHER window: {w}x{h}{client_info} at ({l},{t}){monitor_info}")
            self.status_label.config(text="game window detected")
        else:
            self.window_info_label.config(text="PLAY TOGETHER window not found")
            self.status_label.config(text="waiting for game window")

    def select_region(self):
        """Select the game window region for monitoring"""
        # Stop current monitoring if any
        self.stop_monitoring()
        
        # Only allow region selection if game window is found
        if not self.game_window_rect:
            self.status_label.config(text="error: PLAY TOGETHER window not found")
            return
            
        try:
            # Get the size from the input field
            size = int(self.size_var.get())
            if size < 10:
                self.status_label.config(text="error: size must be at least 10px")
                return
        except ValueError:
            self.status_label.config(text="error: invalid size value")
            return
        
        # Get offsets for fine-tuning
        try:
            self.offset_x = int(self.offset_x_var.get())
            self.offset_y = int(self.offset_y_var.get())
        except ValueError:
            self.offset_x = 0
            self.offset_y = 0
            self.offset_x_var.set("0")
            self.offset_y_var.set("0")
        
        # Use client area by default for selection to avoid borders/title bar
        if hasattr(self, 'game_client_rect'):
            l, t, r, b = self.game_client_rect
        else:
            l, t, r, b = self.game_window_rect
            
        win_width = r - l
        win_height = b - t
        
        # Calculate region dimensions based on size parameter
        width = size
        height = size
        
        # Ensure region size isn't larger than the game window
        if width > win_width:
            width = win_width
        if height > win_height:
            height = win_height
            
        print(f"Game window client area: {win_width}x{win_height} at ({l}, {t})")
        
        # Temporarily minimize our window
        self.root.iconify()
        time.sleep(0.5)
        
        # Create a transparent overlay window for selection
        selection_window = tk.Toplevel(self.root)
        selection_window.attributes('-alpha', 0.3)
        selection_window.attributes('-topmost', True)
        selection_window.configure(bg=self.colors['bg_dark'])
        selection_window.overrideredirect(True)  # Remove window decorations
        
        # Position overlay directly on the client area of the game window
        selection_window.geometry(f"{win_width}x{win_height}+{l}+{t}")
        
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
            
            # Ensure region stays within game window bounds
            if left < 0:
                left = 0
                right = width
            elif right > win_width:
                right = win_width
                left = right - width
                
            if top < 0:
                top = 0
                bottom = height
            elif bottom > win_height:
                bottom = win_height
                top = bottom - height
            
            # Clear previous shapes
            if preview_rect:
                canvas.delete(preview_rect)
            if outline_rect:
                canvas.delete(outline_rect)
            for line in grid_lines:
                canvas.delete(line)
            grid_lines = []
            
            # Draw selection rectangle
            outline_rect = canvas.create_rectangle(
                left-1, top-1, right+1, bottom+1,
                outline=self.colors['accent'], width=1
            )
            
            preview_rect = canvas.create_rectangle(
                left, top, right, bottom,
                outline=self.colors['green'], width=1,
                fill=self.colors['accent'], stipple="gray12"
            )
            
            # Add grid lines
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
            
            # Update coordinate display
            canvas.delete("coords")
            
            # Calculate absolute screen coordinates (including offsets)
            screen_left = l + left + self.offset_x
            screen_top = t + top + self.offset_y
            
            # Also show relative coordinates
            coord_text = f"pos: ({screen_left},{screen_top}) • size: {width}×{height}"
            canvas.create_text(
                win_width // 2,
                win_height - 20,
                text=coord_text, 
                fill=self.colors['text_bright'],
                font=("Consolas", 9),
                tags="coords"
            )
        
        def on_mouse_click(event):
            nonlocal preview_rect, outline_rect, grid_lines
            
            # Calculate region coordinates relative to the selection window
            left = event.x - width // 2
            top = event.y - height // 2
            right = left + width
            bottom = top + height
            
            # Ensure region stays within game window bounds
            if left < 0:
                left = 0
                right = width
            elif right > win_width:
                right = win_width
                left = right - width
                
            if top < 0:
                top = 0
                bottom = height
            elif bottom > win_height:
                bottom = win_height
                top = bottom - height
            
            # Convert to absolute screen coordinates with offsets
            screen_left = l + left + self.offset_x
            screen_top = t + top + self.offset_y
            screen_right = l + right + self.offset_x
            screen_bottom = t + bottom + self.offset_y
            
            # Store the selected region in screen coordinates
            self.selected_region = (screen_left, screen_top, screen_right, screen_bottom)
            
            # Close selection window
            selection_window.destroy()
            
            # Restore main window
            self.root.deiconify()
            
            # Update status
            if hasattr(self, 'game_monitor'):
                monitor_info = f" on {self.game_monitor['device']}"
            else:
                monitor_info = ""
                
            self.status_label.config(text=f"region selected: {width}×{height} at ({screen_left},{screen_top}){monitor_info}")
            
            # Print debug info
            print(f"Game window: {self.game_window_rect}")
            print(f"Game client area: {self.game_client_rect if hasattr(self, 'game_client_rect') else 'N/A'}")
            print(f"Selected region: {self.selected_region}")
            print(f"Using offsets: x={self.offset_x}, y={self.offset_y}")
            
            # Start monitoring the selected region
            self.start_monitoring()
        
        # Bind mouse events
        canvas.bind("<Motion>", update_preview)
        canvas.bind("<ButtonPress-1>", on_mouse_click)
        
        # Add instructions
        instructions = tk.Label(
            canvas, 
            text="SELECT REGION • CLICK TO PLACE • ESC TO CANCEL", 
            font=("Consolas", 10), 
            fg=self.colors['green'],
            bg=self.colors['bg_dark'],
            padx=20,
            pady=5
        )
        canvas.create_window(
            win_width // 2,
            30,
            window=instructions
        )
        
        # Add crosshair guides
        canvas.create_line(
            0, win_height // 2,
            win_width, win_height // 2,
            fill=self.colors['accent'], width=1, dash=(5, 5)
        )
        
        canvas.create_line(
            win_width // 2, 0,
            win_width // 2, win_height,
            fill=self.colors['accent'], width=1, dash=(5, 5)
        )
        
        # Handle ESC key to cancel
        def on_escape(event):
            selection_window.destroy()
            self.root.deiconify()
            self.status_label.config(text="region selection cancelled")
        
        selection_window.bind("<Escape>", on_escape)

    def calibrate_window_offset(self, window_left, window_top):
        """Calibrate the window offset to account for borders and DPI scaling"""
        try:
            # Get manual offsets from UI
            try:
                self.offset_x = int(self.offset_x_var.get())
                self.offset_y = int(self.offset_y_var.get())
            except ValueError:
                self.offset_x = 0
                self.offset_y = 0
                self.offset_x_var.set("0")
                self.offset_y_var.set("0")
            
            # Take a screenshot of the top-left corner of the window
            test_region = (window_left, window_top, window_left + 50, window_top + 50)
            test_shot = ImageGrab.grab(bbox=test_region)
            
            print(f"Using manual offsets: x={self.offset_x}, y={self.offset_y}")
        except Exception as e:
            print(f"Error during calibration: {e}")
            self.offset_x = 0
            self.offset_y = 0

    def adjust_offset(self, axis, amount):
        """Adjust the X or Y offset by the given amount"""
        try:
            if axis == 'x':
                current = int(self.offset_x_var.get())
                self.offset_x_var.set(str(current + amount))
            else:
                current = int(self.offset_y_var.get())
                self.offset_y_var.set(str(current + amount))
                
            # If a region is selected, update it and take a test capture
            if self.selected_region:
                self.test_capture()
        except ValueError:
            pass
            
    def test_capture(self):
        """Take a test capture to verify region selection"""
        if not self.selected_region:
            self.status_label.config(text="error: no region selected")
            return
            
        try:
            # Get manual offsets from UI
            try:
                offset_x = int(self.offset_x_var.get())
                offset_y = int(self.offset_y_var.get())
                
                # Update the region with new offsets
                l, t, r, b = self.selected_region
                # Remove old offsets
                l -= self.offset_x
                t -= self.offset_y
                r -= self.offset_x
                b -= self.offset_y
                # Add new offsets
                l += offset_x
                t += offset_y
                r += offset_x
                b += offset_y
                
                self.offset_x = offset_x
                self.offset_y = offset_y
                self.selected_region = (l, t, r, b)
                
                print(f"Updated region with new offsets: {self.selected_region}")
                print(f"Using offsets: x={self.offset_x}, y={self.offset_y}")
            except ValueError:
                pass
                
            # Check if region is outside screen bounds
            virtual_left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            virtual_top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            virtual_right = virtual_left + win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            virtual_bottom = virtual_top + win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
            
            l, t, r, b = self.selected_region
            if (l < virtual_left or t < virtual_top or 
                r > virtual_right or b > virtual_bottom):
                print(f"Warning: Region {self.selected_region} is partly outside visible screen")
                
                # Adjust to visible area
                adjusted_l = max(l, virtual_left)
                adjusted_t = max(t, virtual_top)
                adjusted_r = min(r, virtual_right)
                adjusted_b = min(b, virtual_bottom)
                
                if adjusted_r <= adjusted_l or adjusted_b <= adjusted_t:
                    self.status_label.config(text="error: region completely outside screen")
                    return
                
                # Use adjusted region for capture
                capture_box = (adjusted_l, adjusted_t, adjusted_r, adjusted_b)
            else:
                capture_box = self.selected_region
                
            # Take a single screenshot
            screenshot = ImageGrab.grab(bbox=capture_box)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(screenshot)
            
            # Update canvas
            self.monitor_canvas.config(width=photo.width(), height=photo.height())
            self.monitor_canvas.delete("all")
            self.monitor_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
            self.monitor_canvas.image = photo
            
            # Update status with monitor information
            l, t, r, b = self.selected_region
            region_width = r - l
            region_height = b - t
            
            # Find which monitor the region is primarily on
            region_center_x = (l + r) // 2
            region_center_y = (t + b) // 2
            region_monitor = None
            
            if hasattr(self, 'monitors'):
                for i, m in enumerate(self.monitors):
                    if (m['left'] <= region_center_x <= m['right'] and 
                        m['top'] <= region_center_y <= m['bottom']):
                        region_monitor = m
                        monitor_info = f" on monitor {i+1}"
                        break
                else:
                    monitor_info = " (outside monitor bounds)"
            else:
                monitor_info = ""
                
            self.monitor_status.config(text=f"test capture: {region_width}×{region_height} at ({l},{t}){monitor_info}")
            self.status_label.config(text=f"test capture taken with offsets x={self.offset_x}, y={self.offset_y}")
            
        except Exception as e:
            print(f"Error in test capture: {str(e)}")
            self.monitor_status.config(text=f"error: {str(e)}")

def main():
    root = tk.Tk()
    root.title("Region Selector")
    
    # Configure root window background
    root.configure(bg='#050505')
    
    # Create app
    app = RegionSelectorGUI(root)
    
    # Center window on screen
    window_width = 800
    window_height = 600
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    center_x = int(screen_width/2 - window_width/2)
    center_y = int(screen_height/2 - window_height/2)
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    root.mainloop()

if __name__ == "__main__":
    main() 