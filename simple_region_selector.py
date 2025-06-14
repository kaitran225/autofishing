import sys
import cv2
import numpy as np
import threading
import time
from PIL import Image, ImageQt
import mss
import mss.tools
import pygetwindow as gw
import psutil
import keyboard
import json
import re
import ctypes
import win32gui
import win32con
import win32process
import win32api
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QComboBox, QLineEdit, QScrollArea, 
    QGroupBox, QFrame, QSizePolicy, QSpinBox, QDoubleSpinBox,
    QSlider, QGridLayout, QListWidget, QListWidgetItem, QSplitter,
    QScrollBar, QTextEdit
)
from PyQt6.QtCore import (
    Qt, QSize, QThread, pyqtSignal, QTimer, QRect, QMargins,
    QEvent, QObject, QMetaObject
)
from PyQt6.QtGui import QPixmap, QImage, QColor, QFont, QPalette, QIcon, QPainter

# For direct key simulation
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Special key constants
VK_CODES = {
    'f': 0x46,    # F key
    'esc': 0x1B,  # ESC key
    'enter': 0x0D, # Enter key
    'space': 0x20, # Space key
    'tab': 0x09,   # Tab key
    'backspace': 0x08, # Backspace key
    'shift': 0x10,  # Shift key
    'ctrl': 0x11,   # Ctrl key
    'alt': 0x12     # Alt key
}
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1

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

class MonitorWorker(QObject):
    """Worker class for monitoring in a separate thread"""
    
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        
    def run(self):
        """Run the monitoring function"""
        self.parent.monitor_thread_function()

class RegionSelectorQt(QMainWindow):
    """PyQt6 implementation of the Region Selector with iOS-style UI"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLAY TOGETHER Auto-Fisher")
        self.setMinimumSize(700, 600)  # Reduced size for more compact layout
        
        # Minimal earth-tone color palette
        self.colors = {
            'bg_dark': '#333D29',      # Dark green
            'bg_medium': '#414C33',    # Medium green
            'bg_light': '#A4AC86',     # Light green
            'text': '#F2F2F2',         # Off-white
            'text_secondary': '#C2C5AA', # Light sage
            'accent': '#A68A64',       # Tan
            'accent_light': '#B6AD90', # Light tan
            'warning': '#7F4F24',      # Brown
            'success': '#A4AC86',      # Light green
            'border': '#5D4F3E',       # Dark brown
            'button': '#A68A64'        # Tan
        }
        
        # Initialize variables
        self.target_window = None
        self.selected_region = None
        self.is_monitoring = False
        self.monitor_thread = None
        
        # For difference detection
        self.current_frame = None
        self.reference_frame = None
        self.previous_frame = None
        self.diff_frame = None
        self.change_history = []
        self.color_frame = None
        
        # For action sequence
        self.detection_threshold = 0.05  # Default threshold for triggering actions
        self.detection_cooldown = 1.0    # Seconds between detections
        self.last_detection_time = 0     # Last time actions were triggered
        self.action_sequence = []        # Will store parsed actions
        self.action_frames = []          # Will store action frame widgets
        
        # Default action sequence from pixel_change_trigger.py
        self.default_action_sequence = [
            {"type": "focus", "comment": "Focus the window"},
            {"type": "key", "key": "f", "comment": "Press F key"},
            {"type": "wait", "seconds": 5, "comment": "Wait 5 seconds"},
            {"type": "key", "key": "esc", "comment": "Press ESC key"},
            {"type": "wait", "seconds": 2, "comment": "Wait 2 seconds"},
            {"type": "key", "key": "f", "comment": "Press F key again"}
        ]
        
        # Set application style
        self.setup_ui_style()
        
        # Initialize MSS screen capture
        with mss.mss() as sct:
            self.monitors = sct.monitors
            print(f"Detected {len(self.monitors)} monitors:")
            for i, m in enumerate(self.monitors):
                print(f"  Monitor {i}: {m['width']}x{m['height']} at ({m['left']},{m['top']})")
        
        # Create main UI
        self.setup_ui()
        
        # Load default action sequence
        self.load_default_action_sequence()
        
        # Log monitor information
        for i, m in enumerate(self.monitors):
            self.log_to_terminal(f"Monitor {i}: {m['width']}x{m['height']} at ({m['left']},{m['top']})")
    
    def setup_ui_style(self):
        """Set up minimal style for the application"""
        # Apply global stylesheet
        stylesheet = f"""
        QMainWindow, QDialog {{
            background-color: {self.colors['bg_dark']};
            color: {self.colors['text']};
        }}
        
        QWidget {{
            background-color: {self.colors['bg_dark']};
            color: {self.colors['text']};
            font-family: 'Segoe UI', sans-serif;
        }}
        
        QGroupBox {{
            background-color: {self.colors['bg_medium']};
            color: {self.colors['text']};
            border-radius: 4px;
            border: 1px solid {self.colors['border']};
            margin-top: 8px;
            font-weight: normal;
            padding-top: 8px;
        }}
        
        QGroupBox::title {{
            subcontrol-position: top left;
            margin-left: 8px;
            color: {self.colors['text']};
        }}
        
        QPushButton {{
            background-color: {self.colors['button']};
            color: {self.colors['text']};
            border-radius: 2px;
            padding: 6px 12px;
            font-weight: normal;
            border: none;
            min-height: 24px;
        }}
        
        QPushButton:hover {{
            background-color: {self.colors['accent_light']};
        }}
        
        QPushButton:pressed {{
            background-color: {self.colors['accent']};
        }}
        
        QPushButton:disabled {{
            background-color: {self.colors['bg_medium']};
            color: {self.colors['text_secondary']};
        }}
        
        QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox {{
            background-color: {self.colors['bg_medium']};
            border-radius: 2px;
            padding: 4px;
            border: 1px solid {self.colors['border']};
            color: {self.colors['text']};
        }}
        
        QComboBox:hover, QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover {{
            border: 1px solid {self.colors['accent']};
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        
        QListWidget {{
            background-color: {self.colors['bg_medium']};
            border-radius: 2px;
            border: 1px solid {self.colors['border']};
            color: {self.colors['text']};
            padding: 2px;
        }}
        
        QScrollArea, QScrollBar {{
            background-color: {self.colors['bg_medium']};
            border-radius: 2px;
            border: 1px solid {self.colors['border']};
        }}
        
        QLabel {{
            color: {self.colors['text']};
            background: transparent;
        }}
        
        QFrame[frameShape="4"] {{ /* HLine */
            color: {self.colors['border']};
            border: 1px solid {self.colors['border']};
        }}
        
        QFrame[frameShape="5"] {{ /* VLine */
            color: {self.colors['border']};
            border: 1px solid {self.colors['border']};
        }}
        """
        
        self.setStyleSheet(stylesheet)
    
    def setup_ui(self):
        """Set up the main UI components"""
        # Create central widget
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)  # Changed to vertical layout
        main_layout.setContentsMargins(4, 4, 4, 4)  # Reduced margins
        main_layout.setSpacing(4)  # Reduced spacing
        self.setCentralWidget(central_widget)
        
        # Create top section with control panel
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)  # Changed to vertical layout
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(4)  # Reduced spacing
        
        # Control panel with grid layout
        control_panel = QWidget()
        control_layout = QGridLayout(control_panel)  # Grid layout
        control_layout.setContentsMargins(2, 2, 2, 2)  # Reduced margins
        control_layout.setSpacing(4)  # Reduced spacing
        
        # Set up the control panel with grid layout
        self.setup_control_panel(control_layout)
        
        # Add control panel to top layout
        top_layout.addWidget(control_panel)
        
        # Add top widget to main layout
        main_layout.addWidget(top_widget, 4)  # Increased ratio for top section
        
        # Create terminal output area
        terminal_group = QGroupBox("Terminal Output")
        terminal_layout = QVBoxLayout(terminal_group)
        terminal_layout.setContentsMargins(4, 8, 4, 4)  # Reduced margins
        terminal_layout.setSpacing(2)  # Reduced spacing
        
        # Terminal text area
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setStyleSheet(
            f"background-color: {self.colors['bg_dark']}; "
            f"color: {self.colors['text']}; "
            f"font-family: 'Consolas', monospace; "
            f"font-size: 9pt;"  # Reduced font size
        )
        self.terminal_output.setMaximumHeight(100)  # Limit height
        terminal_layout.addWidget(self.terminal_output)
        
        # Add terminal to main layout
        main_layout.addWidget(terminal_group, 1)  # Reduced ratio for terminal
        
        # Log initial message
        self.log_to_terminal("Application started")
        self.log_to_terminal(f"Detected {len(self.monitors)} monitors")
    
    def log_to_terminal(self, message):
        """Add a message to the terminal output"""
        timestamp = time.strftime("%H:%M:%S")
        self.terminal_output.append(f"[{timestamp}] {message}")
    
    def setup_control_panel(self, layout):
        """Set up the control panel (left side) with 2-column grid layout"""
        # Window selection section (column 0, row 0)
        window_group = self.create_window_section()
        layout.addWidget(window_group, 0, 0)
        
        # Region selection section (column 0, row 1)
        region_group = self.create_region_section()
        layout.addWidget(region_group, 1, 0)
        
        # Action sequence section (column 1, row 0, spans 2 rows)
        action_group = self.create_action_section()
        layout.addWidget(action_group, 0, 1, 2, 1)  # Span 2 rows
        
        # Monitor and status section (column 0-1, row 2)
        monitor_group = self.create_monitoring_section()
        layout.addWidget(monitor_group, 2, 0, 1, 2)  # Span both columns in row 2
    
    def create_window_section(self):
        """Create the window selection section that automatically targets PLAY TOGETHER"""
        window_group = QGroupBox("Game Window")
        window_layout = QVBoxLayout(window_group)
        window_layout.setContentsMargins(4, 8, 4, 4)  # Reduced margins
        window_layout.setSpacing(4)  # Reduced spacing
        
        # Status label
        self.window_status = QLabel("Looking for PLAY TOGETHER window...")
        self.window_status.setWordWrap(True)
        self.window_status.setStyleSheet(f"color: {self.colors['text_secondary']}; padding: 2px;")
        window_layout.addWidget(self.window_status)
        
        # Window info
        self.window_info = QLabel("No window found")
        self.window_info.setWordWrap(True)
        self.window_info.setStyleSheet(f"color: {self.colors['text_secondary']}; background: {self.colors['bg_medium']}; padding: 2px;")
        self.window_info.setMaximumHeight(40)  # Reduced height
        window_layout.addWidget(self.window_info)
        
        # Find game window button
        find_button = QPushButton("Find Game Window")
        find_button.setMaximumHeight(24)  # Reduced height
        find_button.clicked.connect(self.find_game_window)
        window_layout.addWidget(find_button)
        
        # Automatically try to find the window
        QTimer.singleShot(500, self.find_game_window)
        
        return window_group
    
    def find_game_window(self):
        """Find the PLAY TOGETHER game window"""
        self.window_status.setText("Looking for PLAY TOGETHER window...")
        self.log_to_terminal("Searching for PLAY TOGETHER window...")
        
        # Get all windows
        all_windows = gw.getAllWindows()
        
        # Look for PLAY TOGETHER window
        found = False
        for window in all_windows:
            if window.width > 100 and window.height > 100 and window.title:
                if "PLAY TOGETHER" in window.title.upper():
                    self.target_window = window
                    found = True
                    
                    # Update window info
                    info_text = (
                        f"Title: {self.target_window.title}\n"
                        f"Size: {self.target_window.width}×{self.target_window.height}\n"
                        f"Position: ({self.target_window.left}, {self.target_window.top})"
                    )
                    self.window_info.setText(info_text)
                    self.window_status.setText(f"Found: {self.target_window.title}")
                    self.status_label.setText(f"Selected: {self.target_window.title}")
                    
                    # Log to terminal
                    self.log_to_terminal(f"Found game window: {self.target_window.title}")
                    break
        
        if not found:
            self.window_status.setText("Game window not found. Try again.")
            self.window_info.setText("No PLAY TOGETHER window found.\nPlease make sure the game is running.")
            self.log_to_terminal("Game window not found")
            self.target_window = None
    
    def create_region_section(self):
        """Create the region selection section"""
        region_group = QGroupBox("Region Selection")
        region_layout = QVBoxLayout(region_group)
        region_layout.setContentsMargins(4, 8, 4, 4)  # Reduced margins
        region_layout.setSpacing(4)  # Reduced spacing
        
        # Size row
        size_widget = QWidget()
        size_layout = QHBoxLayout(size_widget)
        size_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        size_layout.setSpacing(2)  # Reduced spacing
        
        size_label = QLabel("Size:")
        self.size_input = QSpinBox()
        self.size_input.setMinimum(10)
        self.size_input.setMaximum(500)
        self.size_input.setValue(100)
        self.size_input.setMaximumHeight(20)  # Reduced height
        size_layout.addWidget(size_label)
        size_layout.addWidget(self.size_input)
        size_layout.addWidget(QLabel("px"))
        size_layout.addStretch()
        
        # Threshold row
        threshold_widget = QWidget()
        threshold_layout = QHBoxLayout(threshold_widget)
        threshold_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        threshold_layout.setSpacing(2)  # Reduced spacing
        
        threshold_label = QLabel("Threshold:")
        self.threshold_input = QDoubleSpinBox()
        self.threshold_input.setMinimum(0.01)
        self.threshold_input.setMaximum(1.0)
        self.threshold_input.setValue(self.detection_threshold)
        self.threshold_input.setSingleStep(0.01)
        self.threshold_input.setMaximumHeight(20)  # Reduced height
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.threshold_input)
        threshold_layout.addStretch()
        
        # Select button
        select_region_button = QPushButton("Select Region")
        select_region_button.setMaximumHeight(24)  # Reduced height
        select_region_button.clicked.connect(self.select_region)
        
        # Capture reference button
        reference_button = QPushButton("Capture Reference Frame")
        reference_button.setMaximumHeight(24)  # Reduced height
        reference_button.clicked.connect(self.capture_reference_frame)
        
        region_layout.addWidget(size_widget)
        region_layout.addWidget(threshold_widget)
        region_layout.addWidget(select_region_button)
        region_layout.addWidget(reference_button)
        
        return region_group
    
    def create_action_section(self):
        """Create the action sequence section"""
        action_group = QGroupBox("Action Sequence")
        action_layout = QVBoxLayout(action_group)
        action_layout.setContentsMargins(4, 8, 4, 4)  # Reduced margins
        action_layout.setSpacing(4)  # Reduced spacing
        
        # Create a scroll area for actions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(120)  # Reduced height
        scroll.setMaximumHeight(150)  # Reduced max height
        
        # Container widget for action items
        self.action_container = QWidget()
        self.action_layout = QVBoxLayout(self.action_container)
        self.action_layout.setContentsMargins(2, 2, 2, 2)  # Reduced margins
        self.action_layout.setSpacing(2)  # Reduced spacing
        
        scroll.setWidget(self.action_container)
        action_layout.addWidget(scroll)
        
        # Action buttons
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        buttons_layout.setSpacing(2)  # Reduced spacing
        
        add_button = QPushButton("+ Add")
        add_button.setMaximumHeight(22)  # Reduced height
        add_button.clicked.connect(self.add_action_item)
        
        clear_button = QPushButton("Clear")
        clear_button.setMaximumHeight(22)  # Reduced height
        clear_button.setStyleSheet(
            f"background-color: {self.colors['warning']}; color: {self.colors['text']};"
        )
        clear_button.clicked.connect(self.clear_action_sequence)
        
        default_button = QPushButton("Default")
        default_button.setMaximumHeight(22)  # Reduced height
        default_button.clicked.connect(self.load_default_action_sequence)
        
        test_button = QPushButton("Test")
        test_button.setMaximumHeight(22)  # Reduced height
        test_button.clicked.connect(self.test_action_sequence)
        
        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(clear_button)
        buttons_layout.addWidget(default_button)
        buttons_layout.addWidget(test_button)
        
        action_layout.addWidget(buttons_widget)
        
        return action_group
    
    def create_monitoring_section(self):
        """Create the monitoring section with integrated monitor view"""
        monitor_group = QGroupBox("Monitoring")
        monitor_layout = QHBoxLayout(monitor_group)  # Changed to horizontal layout
        monitor_layout.setContentsMargins(4, 8, 4, 4)  # Reduced margins
        monitor_layout.setSpacing(4)  # Reduced spacing
        
        # Left side: controls
        controls_widget = QWidget()
        controls_layout = QVBoxLayout(controls_widget)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(4)
        
        # Status label
        self.status_label = QLabel("Ready to select window")
        self.status_label.setStyleSheet(f"color: {self.colors['text_secondary']}; padding: 2px;")
        controls_layout.addWidget(self.status_label)
        
        # Start/Stop button
        self.monitor_button = QPushButton("Start Monitoring")
        self.monitor_button.setMaximumHeight(24)  # Reduced height
        self.monitor_button.setEnabled(False)
        self.monitor_button.clicked.connect(self.toggle_monitoring)
        controls_layout.addWidget(self.monitor_button)
        
        # Add stretch to push controls to the top
        controls_layout.addStretch(1)
        
        # Right side: monitor view
        view_widget = QWidget()
        view_layout = QVBoxLayout(view_widget)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(2)
        
        # Monitor view label
        self.monitor_view_label = QLabel("Monitor View")
        self.monitor_view_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.monitor_view_label.setStyleSheet(f"color: {self.colors['text']}; background: none; border: none;")
        view_layout.addWidget(self.monitor_view_label)
        
        # Canvas for the monitor view
        canvas = QLabel()
        canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas.setMinimumSize(200, 200)
        canvas.setMaximumSize(200, 200)  # Enforce 200x200 size
        canvas.setStyleSheet("background-color: black;")
        view_layout.addWidget(canvas)
        
        # Store the canvas for later use
        self.monitor_canvas = canvas
        
        # Add both sides to the main layout
        monitor_layout.addWidget(controls_widget, 1)  # Give controls some space
        monitor_layout.addWidget(view_widget)  # Give view more space
        
        return monitor_group
    
    def update_monitor_view(self):
        """Update the monitor view with the current frame"""
        if self.current_frame is None:
            return
            
        # Convert to QImage and resize to fit the canvas (200x200)
        h, w = self.current_frame.shape[:2]
        bytes_per_line = 3 * w
        
        # Create a copy for display (RGB format)
        display_frame = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
        
        # Resize to fit the canvas (200x200) while maintaining aspect ratio
        max_size = 200
        scale = min(max_size / w, max_size / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize the image
        display_frame = cv2.resize(display_frame, (new_w, new_h))
        
        # Create a black background of 200x200
        background = np.zeros((max_size, max_size, 3), dtype=np.uint8)
        
        # Calculate position to center the image
        y_offset = (max_size - new_h) // 2
        x_offset = (max_size - new_w) // 2
        
        # Place the resized image on the background
        background[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = display_frame
        
        # Convert to QImage
        q_img = QImage(background.data, max_size, max_size, max_size * 3, QImage.Format.Format_RGB888)
        
        # Convert to QPixmap and set to canvas
        pixmap = QPixmap.fromImage(q_img)
        self.monitor_canvas.setPixmap(pixmap)
    
    def select_region(self):
        """Select a region of the screen to monitor"""
        if not self.target_window:
            self.status_label.setText("Error: No window selected")
            self.log_to_terminal("Error: No window selected")
            return
        
        try:
            # Try to activate the window
            try:
                # Minimize our window first
                self.showMinimized()
                time.sleep(0.3)  # Give time to minimize
                self.log_to_terminal(f"Selecting region for window: {self.target_window.title}")
                
                # Activate target window
                if self.target_window.isMinimized:
                    self.target_window.restore()
                self.target_window.activate()
                time.sleep(0.2)  # Give time to activate
            except Exception as e:
                self.status_label.setText(f"Error: Window not available")
                self.log_to_terminal(f"Error activating window: {str(e)}")
                self.showNormal()  # Restore our window
                return
            
            try:
                # Get region size
                size = self.size_input.value()
                if size < 10:
                    self.status_label.setText("Error: Size must be at least 10px")
                    self.log_to_terminal("Error: Region size must be at least 10px")
                    self.showNormal()
                    return
                
                # Get window position and size
                win_left = self.target_window.left
                win_top = self.target_window.top
                win_width = self.target_window.width
                win_height = self.target_window.height
                
                # Create selection overlay
                overlay = QWidget()
                overlay.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
                overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.3);")
                overlay.setGeometry(win_left, win_top, win_width, win_height)
                
                # Create overlay layout with instructions
                overlay_layout = QVBoxLayout(overlay)
                
                # Instructions label
                instructions = QLabel("Click to select region • ESC to cancel")
                instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
                instructions.setStyleSheet(
                    f"color: white; font-size: 14px; font-weight: bold; "
                    f"background-color: rgba(0, 0, 0, 0.5); padding: 10px; border-radius: 5px;"
                )
                overlay_layout.addWidget(instructions, 0, Qt.AlignmentFlag.AlignTop)
                overlay_layout.addStretch()
                
                # Show the overlay
                overlay.show()
                
                # Variables to store selection
                selection_rect = None
                
                # Event filter for handling mouse events on the overlay
                class EventFilter(QObject):
                    def __init__(self, parent, size, win_left, win_top, win_width, win_height):
                        super().__init__()
                        self.parent = parent
                        self.size = size
                        self.win_left = win_left
                        self.win_top = win_top
                        self.win_width = win_width
                        self.win_height = win_height
                        self.selection_made = False
                    
                    def eventFilter(self, obj, event):
                        if event.type() == QEvent.Type.MouseMove:
                            # Handle mouse move to update selection preview
                            x = event.x()
                            y = event.y()
                            
                            # Calculate region coordinates
                            left = max(0, min(x - self.size//2, self.win_width - self.size))
                            top = max(0, min(y - self.size//2, self.win_height - self.size))
                            
                            # Update overlay to show selection preview
                            # In a real implementation, you would draw this
                            
                            return True
                        
                        elif event.type() == QEvent.Type.MouseButtonPress:
                            # Handle mouse click to finalize selection
                            if not self.selection_made:
                                self.selection_made = True
                                
                                x = event.x()
                                y = event.y()
                                
                                # Calculate region coordinates
                                left = max(0, min(x - self.size//2, self.win_width - self.size))
                                top = max(0, min(y - self.size//2, self.win_height - self.size))
                                
                                # Convert to absolute screen coordinates
                                screen_left = self.win_left + left
                                screen_top = self.win_top + top
                                
                                # Store the selection information
                                self.parent.selected_region = {
                                    'left': screen_left,
                                    'top': screen_top,
                                    'width': self.size,
                                    'height': self.size,
                                    'mon': 0  # Default primary monitor
                                }
                                
                                # Log the selection
                                self.parent.log_to_terminal(
                                    f"Region selected: {self.size}×{self.size} at ({screen_left}, {screen_top})"
                                )
                                
                                # Close overlay
                                overlay.close()
                                self.parent.showNormal()
                                
                                # Update status
                                self.parent.status_label.setText(
                                    f"Region selected: {self.size}×{self.size} at ({screen_left}, {screen_top})"
                                )
                                
                                # Enable monitoring button
                                self.parent.monitor_button.setEnabled(True)
                                
                                # Take a preview screenshot
                                self.parent.take_preview_screenshot()
                                
                                return True
                        
                        elif event.type() == QEvent.Type.KeyPress:
                            # Handle escape key to cancel
                            if event.key() == Qt.Key.Key_Escape:
                                self.parent.log_to_terminal("Region selection canceled")
                                overlay.close()
                                self.parent.showNormal()
                                return True
                        
                        return False
                
                # Install event filter
                event_filter = EventFilter(self, size, win_left, win_top, win_width, win_height)
                overlay.installEventFilter(event_filter)
                
            except Exception as e:
                self.status_label.setText(f"Error in region selection: {str(e)}")
                self.log_to_terminal(f"Error in region selection: {str(e)}")
                self.showNormal()
        
        except Exception as e:
            print(f"Error selecting region: {str(e)}")
            self.status_label.setText(f"Error: {str(e)}")
            self.log_to_terminal(f"Error selecting region: {str(e)}")
            self.showNormal()
    
    def take_preview_screenshot(self):
        """Take a preview screenshot of the selected region"""
        if not self.selected_region:
            return
        
        try:
            with mss.mss() as sct:
                # Take screenshot of the region
                region = self.selected_region
                img = sct.grab(region)
                
                # Convert to PIL Image
                img_pil = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                
                # Store the grayscale version for processing
                gray_frame = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2GRAY)
                
                # Store as current frame
                self.previous_frame = self.current_frame if self.current_frame is not None else gray_frame
                self.current_frame = gray_frame
                
                # Calculate difference if we have a reference
                if self.reference_frame is not None:
                    diff_frame, change_percent = self.calculate_frame_difference(
                        self.current_frame, self.reference_frame)
                    self.diff_frame = diff_frame
                    
                    # Add to history
                    self.change_history.append(change_percent)
                    if len(self.change_history) > 30:  # Keep last 30 readings
                        self.change_history.pop(0)
                    
                    # Update status
                    self.status_label.setText(
                        f"Preview: {region['width']}×{region['height']} • Change: {change_percent:.2%}"
                    )
                
                # Process and display the image
                self.process_and_display_image(img_pil)
                
        except Exception as e:
            print(f"Error taking preview screenshot: {str(e)}")
            self.status_label.setText(f"Error: {str(e)}")
    
    def toggle_monitoring(self):
        """Toggle monitoring on/off"""
        if not self.is_monitoring:
            # Start monitoring
            if self.selected_region is None:
                self.log_to_terminal("Error: No region selected")
                return
                
            if self.reference_frame is None:
                self.log_to_terminal("Error: No reference frame captured")
                return
                
            # Update button text
            self.monitor_button.setText("Stop Monitoring")
            self.is_monitoring = True
            
            # Start monitoring thread
            self.monitor_thread = QThread()
            self.monitor_worker = MonitorWorker(self)
            self.monitor_worker.moveToThread(self.monitor_thread)
            self.monitor_thread.started.connect(self.monitor_worker.run)
            self.monitor_thread.start()
            
            self.log_to_terminal("Monitoring started")
        else:
            # Stop monitoring
            self.is_monitoring = False
            if self.monitor_thread:
                self.monitor_thread.quit()
                self.monitor_thread.wait()
            self.monitor_button.setText("Start Monitoring")
            self.log_to_terminal("Monitoring stopped")
    
    def monitor_thread_function(self):
        """Thread function for continuous monitoring"""
        self.log_to_terminal("Monitoring started")
        
        with mss.mss() as sct:
            while self.is_monitoring:
                if self.target_window and self.selected_region:
                    # Capture the selected region
                    x, y, w, h = self.selected_region
                    monitor = {
                        "left": x,
                        "top": y,
                        "width": w,
                        "height": h
                    }
                    
                    try:
                        # Capture the screen region
                        screenshot = sct.grab(monitor)
                        
                        # Convert to numpy array
                        img = np.array(screenshot)
                        
                        # Convert to BGR (OpenCV format)
                        self.current_frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                        
                        # Update the display
                        QMetaObject.invokeMethod(self, "update_frames", Qt.ConnectionType.QueuedConnection)
                        
                    except Exception as e:
                        self.log_to_terminal(f"Error capturing screen: {str(e)}")
                        self.is_monitoring = False
                        break
                        
                # Sleep to reduce CPU usage
                time.sleep(0.1)
                
        self.log_to_terminal("Monitoring stopped")
    
    def process_and_display_image(self, image):
        """Process and display the captured image"""
        if image is None or not hasattr(self, 'canvases') or not self.canvases:
            return
        
        try:
            # Convert PIL image to numpy array for OpenCV processing
            np_img = np.array(image)
            
            # Display the original image
            self.display_image(image, 0)
            
            # Calculate and update change percentage if we have a reference frame
            if self.reference_frame is not None and self.current_frame is not None:
                diff_frame, change_percent = self.calculate_frame_difference(
                    self.current_frame, self.reference_frame)
                
                # Add change percentage text to status
                QTimer.singleShot(0, lambda c=change_percent: 
                    self.status_label.setText(f"Change: {c:.2%}")
                )
            
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            self.log_to_terminal(f"Error processing image: {str(e)}")
    
    def display_image(self, pil_img, index=0):
        """Display a PIL image in the canvas"""
        if index >= len(self.canvases) or pil_img is None:
            return
        
        try:
            # Get canvas dimensions for scaling
            canvas = self.canvases[index]
            canvas_width = canvas.width()
            canvas_height = canvas.height()
            
            # Get image dimensions
            img_width, img_height = pil_img.size
            
            # Calculate scaling factor to fit in canvas
            scale_factor = min(
                canvas_width / img_width,
                canvas_height / img_height
            ) * 0.9  # 90% of available space
            
            # Calculate new dimensions
            new_width = int(img_width * scale_factor)
            new_height = int(img_height * scale_factor)
            
            # Resize the image
            if new_width > 0 and new_height > 0:
                resized_img = pil_img.resize((new_width, new_height), Image.LANCZOS)
                
                # Convert PIL image to Qt image and pixmap
                q_image = ImageQt.toqimage(resized_img)
                pixmap = QPixmap.fromImage(q_image)
                
                # Update canvas
                canvas.setPixmap(pixmap)
                canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        except Exception as e:
            print(f"Error displaying image: {str(e)}")
            self.log_to_terminal(f"Error displaying image: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def calculate_frame_difference(self, frame1, frame2):
        """Calculate the difference between two grayscale frames"""
        if frame1 is None or frame2 is None:
            return np.zeros_like(frame1 if frame1 is not None else frame2), 0.0
        
        # Ensure the frames have the same size
        if frame1.shape != frame2.shape:
            # Resize the smaller one to match the larger one
            if frame1.size < frame2.size:
                frame1 = cv2.resize(frame1, (frame2.shape[1], frame2.shape[0]))
            else:
                frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
        
        # Calculate absolute difference
        diff = cv2.absdiff(frame1, frame2)
        
        # Apply threshold to filter out noise
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        
        # Calculate change percentage
        change_percent = np.sum(thresh > 0) / thresh.size
        
        return thresh, change_percent

    def capture_reference_frame(self):
        """Capture a reference frame for comparison"""
        if not self.selected_region:
            self.status_label.setText("Error: No region selected")
            return
            
        try:
            with mss.mss() as sct:
                # Capture the region
                screenshot = sct.grab(self.selected_region)
                # Convert to numpy array
                img = np.array(Image.frombytes("RGB", screenshot.size, screenshot.rgb))
                
                # Store as reference frame
                self.reference_frame = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                self.status_label.setText("Reference frame captured")
                
                # Also update preview
                self.take_preview_screenshot()
                
        except Exception as e:
            print(f"Error capturing reference frame: {str(e)}")
            self.status_label.setText(f"Error: {str(e)}")
            
    def add_action_item(self, action_type="focus", value=""):
        """Add a new action row with two columns"""
        # Create action frame with horizontal layout
        action_frame = QFrame()
        action_frame.setStyleSheet(f"background-color: {self.colors['bg_medium']}; margin: 0px;")
        action_frame.action_data = {"type": action_type, "value": value}
        
        # Create horizontal layout
        action_layout = QHBoxLayout(action_frame)
        action_layout.setContentsMargins(4, 2, 4, 2)
        action_layout.setSpacing(4)
        
        # First column: Action type dropdown
        type_combo = QComboBox()
        type_combo.addItems(["focus", "key", "wait"])
        type_combo.setCurrentText(action_type)
        type_combo.setMaximumHeight(24)
        
        # Second column: Value input
        value_input = QLineEdit()
        value_input.setText(value)
        value_input.setMaximumHeight(24)
        if action_type == "focus":
            value_input.setEnabled(False)
        else:
            value_input.setEnabled(True)
            if not value:
                if action_type == "key":
                    value_input.setText("f")
                elif action_type == "wait":
                    value_input.setText("1.0")
        
        # Delete button
        delete_btn = QPushButton("×")
        delete_btn.setStyleSheet(
            f"background-color: {self.colors['warning']}; color: {self.colors['text']}; "
            f"min-width: 20px; max-width: 20px; "
            f"min-height: 20px; max-height: 20px; "
            f"padding: 0px; font-weight: bold;"
        )
        delete_btn.clicked.connect(lambda: self.remove_action_item(action_frame))
        
        # Add widgets to layout
        action_layout.addWidget(type_combo, 1)
        action_layout.addWidget(value_input, 1)
        action_layout.addWidget(delete_btn, 0)
        
        # Connect signals to update data
        def update_type(text):
            action_frame.action_data["type"] = text
            if text == "focus":
                value_input.setEnabled(False)
                value_input.clear()
            else:
                value_input.setEnabled(True)
                if not value_input.text():
                    if text == "key":
                        value_input.setText("f")
                    elif text == "wait":
                        value_input.setText("1.0")
        
        def update_value(text):
            action_frame.action_data["value"] = text
        
        type_combo.currentTextChanged.connect(update_type)
        value_input.textChanged.connect(update_value)
        
        # Add to layout and list
        self.action_layout.addWidget(action_frame)
        self.action_frames.append(action_frame)
        
        return action_frame
    
    def remove_action_item(self, frame):
        """Remove an action item"""
        if frame in self.action_frames:
            self.action_frames.remove(frame)
        frame.deleteLater()
    
    def clear_action_sequence(self):
        """Clear all action items"""
        for frame in self.action_frames[:]:  # Use copy to avoid modification during iteration
            self.remove_action_item(frame)
        self.action_frames = []
    
    def load_default_action_sequence(self):
        """Load the default action sequence"""
        self.clear_action_sequence()
        
        for action in self.default_action_sequence:
            if action["type"] == "focus":
                self.add_action_item("focus")
            elif action["type"] == "key":
                self.add_action_item("key", action["key"])
            elif action["type"] == "wait":
                self.add_action_item("wait", str(action["seconds"]))
        
        self.status_label.setText("Default action sequence loaded")
    
    def apply_action_sequence(self):
        """Parse action sequence from UI elements"""
        self.action_sequence = []
        
        for frame in self.action_frames:
            try:
                action_type = frame.action_data["type"]
                action_value = frame.action_data["value"]
                
                if action_type == "focus":
                    self.action_sequence.append({
                        "type": "focus",
                        "comment": "Focus target window"
                    })
                elif action_type == "key":
                    if action_value:
                        self.action_sequence.append({
                            "type": "key", 
                            "key": action_value,
                            "comment": f"Press {action_value} key"
                        })
                elif action_type == "wait":
                    try:
                        wait_time = float(action_value)
                        self.action_sequence.append({
                            "type": "wait",
                            "seconds": wait_time,
                            "comment": f"Wait {wait_time} seconds"
                        })
                    except ValueError:
                        print(f"Invalid wait time: {action_value}")
            except Exception as e:
                print(f"Error parsing action: {e}")
        
        return self.action_sequence
    
    def execute_action_sequence(self):
        """Execute the parsed action sequence"""
        try:
            self.status_label.setText("Executing actions...")
            self.log_to_terminal("Starting action sequence execution")
            
            for i, action in enumerate(self.action_sequence):
                action_type = action["type"]
                
                if action_type == "focus":
                    self.log_to_terminal(f"Action {i+1}/{len(self.action_sequence)}: Focusing window")
                    self.focus_window()
                elif action_type == "key":
                    key = action.get("key", "").lower()
                    if key:
                        self.log_to_terminal(f"Action {i+1}/{len(self.action_sequence)}: Pressing key '{key}'")
                        self.press_key(key)
                    else:
                        self.log_to_terminal(f"Action {i+1}/{len(self.action_sequence)}: Error - Missing key value")
                        print(f"Missing key in action: {action}")
                elif action_type == "wait":
                    wait_time = float(action.get("seconds", 1.0))
                    self.log_to_terminal(f"Action {i+1}/{len(self.action_sequence)}: Waiting {wait_time} seconds")
                    time.sleep(wait_time)
            
            self.log_to_terminal("Action sequence completed")
            # Update status in the main thread
            QTimer.singleShot(0, lambda: self.status_label.setText("Action sequence completed"))
            
        except Exception as e:
            error_msg = f"Error executing action sequence: {e}"
            print(error_msg)
            self.log_to_terminal(error_msg)
            # Update status in the main thread
            QTimer.singleShot(0, lambda: self.status_label.setText(f"Error: {str(e)}"))
    
    def focus_window(self):
        """Focus the target window"""
        try:
            if self.target_window:
                if self.target_window.isMinimized:
                    self.target_window.restore()
                self.target_window.activate()
                time.sleep(0.2)  # Give time to activate
        except Exception as e:
            print(f"Error focusing window: {e}")
    
    def press_key(self, key):
        """Press a key using direct Windows API"""
        try:
            # Check if key is in our virtual key code mapping
            if key.lower() in VK_CODES:
                vk_code = VK_CODES[key.lower()]
                
                # Create keyboard input structure
                extra = ctypes.c_ulong(0)
                ii_ = INPUT_UNION()
                ii_.ki = KEYBDINPUT(vk_code, 0, 0, 0, ctypes.pointer(extra))
                x = INPUT(INPUT_KEYBOARD, ii_)
                
                # Send key down
                ctypes.windll.user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
                
                # Wait a short time
                time.sleep(0.05)
                
                # Send key up
                ii_.ki.dwFlags = KEYEVENTF_KEYUP
                x.ii = ii_
                ctypes.windll.user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
            else:
                # Use pyautogui as fallback
                keyboard.press_and_release(key)
        except Exception as e:
            print(f"Error pressing key: {e}")
    
    def test_action_sequence(self):
        """Test the action sequence without monitoring"""
        # Parse action sequence
        self.apply_action_sequence()
        
        # Check if we have a target window
        if not self.target_window:
            self.status_label.setText("Error: No target window selected")
            return
        
        # Check if we have actions
        if not self.action_sequence:
            self.status_label.setText("Error: No actions defined")
            return
        
        # Create a thread to run the sequence
        test_thread = threading.Thread(target=self.execute_action_sequence)
        test_thread.daemon = True
        test_thread.start()
        
        self.status_label.setText("Testing action sequence...")

    def update_frames(self):
        """Update all frames with the current state"""
        if self.current_frame is None or self.selected_region is None:
            return
            
        # Update the monitor view
        self.update_monitor_view()
        
        # Check for changes if we have a reference frame
        if self.reference_frame is not None:
            # Calculate difference between current frame and reference frame
            self.diff_frame = cv2.absdiff(self.current_frame, self.reference_frame)
            
            # Calculate the percentage of changed pixels
            total_pixels = self.diff_frame.size / 3  # Divide by 3 for BGR channels
            changed_pixels = np.count_nonzero(cv2.cvtColor(self.diff_frame, cv2.COLOR_BGR2GRAY) > 30)
            change_percentage = changed_pixels / total_pixels
            
            # Add to history (keep only the last 10 values)
            self.change_history.append(change_percentage)
            if len(self.change_history) > 10:
                self.change_history.pop(0)
            
            # Update status with change percentage
            avg_change = sum(self.change_history) / len(self.change_history)
            self.status_label.setText(f"Change: {change_percentage:.2%} (avg: {avg_change:.2%})")
            
            # Check if change exceeds threshold and cooldown period has passed
            current_time = time.time()
            if (change_percentage > self.detection_threshold and 
                current_time - self.last_detection_time > self.detection_cooldown):
                self.last_detection_time = current_time
                self.log_to_terminal(f"Change detected: {change_percentage:.2%}")
                
                # Execute action sequence if monitoring is active
                if self.is_monitoring:
                    self.execute_action_sequence()

    def create_action_frame(self, action_data=None):
        """Create a frame for an action item"""
        if action_data is None:
            action_data = {"type": "key", "key": "", "comment": ""}
            
        # Create frame
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            f"background-color: {self.colors['bg_medium']}; "
            f"border: 1px solid {self.colors['border']};"
        )
        
        # Create layout
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(2, 2, 2, 2)  # Reduced margins
        layout.setSpacing(2)  # Reduced spacing
        
        # Type combobox
        type_combo = QComboBox()
        type_combo.addItems(["key", "focus", "wait", "click"])
        type_combo.setCurrentText(action_data.get("type", "key"))
        type_combo.setMaximumWidth(60)  # Reduced width
        type_combo.setMaximumHeight(20)  # Reduced height
        
        # Value input (key, seconds, etc.)
        value_input = QLineEdit()
        if action_data["type"] == "key":
            value_input.setText(action_data.get("key", ""))
            value_input.setPlaceholderText("Key (e.g. f, enter)")
        elif action_data["type"] == "wait":
            value_input.setText(str(action_data.get("seconds", "1")))
            value_input.setPlaceholderText("Seconds")
        elif action_data["type"] == "click":
            value_input.setText(f"{action_data.get('x', '0')},{action_data.get('y', '0')}")
            value_input.setPlaceholderText("x,y")
        value_input.setMaximumHeight(20)  # Reduced height
        
        # Comment input
        comment_input = QLineEdit()
        comment_input.setText(action_data.get("comment", ""))
        comment_input.setPlaceholderText("Comment")
        comment_input.setMaximumHeight(20)  # Reduced height
        
        # Delete button
        delete_button = QPushButton("×")
        delete_button.setMaximumWidth(20)  # Reduced width
        delete_button.setMaximumHeight(20)  # Reduced height
        delete_button.setStyleSheet(
            f"background-color: {self.colors['warning']}; color: {self.colors['text']};"
        )
        
        # Connect type change to update value placeholder
        def update_value_placeholder(action_type):
            if action_type == "key":
                value_input.setPlaceholderText("Key (e.g. f, enter)")
            elif action_type == "wait":
                value_input.setPlaceholderText("Seconds")
            elif action_type == "click":
                value_input.setPlaceholderText("x,y")
            elif action_type == "focus":
                value_input.clear()
                value_input.setPlaceholderText("No value needed")
        
        type_combo.currentTextChanged.connect(update_value_placeholder)
        
        # Add widgets to layout
        layout.addWidget(type_combo)
        layout.addWidget(value_input, 1)  # Give more space to value
        layout.addWidget(comment_input, 1)  # Give more space to comment
        layout.addWidget(delete_button)
        
        # Store references
        frame.type_combo = type_combo
        frame.value_input = value_input
        frame.comment_input = comment_input
        
        # Connect delete button
        delete_button.clicked.connect(lambda: self.remove_action_frame(frame))
        
        return frame

def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    
    # Create and show the main window
    main_window = RegionSelectorQt()
    
    # Position window in center of screen
    screen_geometry = app.primaryScreen().geometry()
    x = (screen_geometry.width() - main_window.width()) // 2
    y = (screen_geometry.height() - main_window.height()) // 2
    main_window.move(x, y)
    
    # Show the window
    main_window.show()
    
    # Start event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 