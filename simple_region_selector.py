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
from PyQt6.QtGui import QPixmap, QImage, QColor, QFont, QPalette, QIcon, QPainter, QPen

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
        self.setWindowTitle("Auto-Fisher")
        self.setMinimumSize(600, 400)  # Reduced size for more compact layout
        
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
            min-height: 20px;
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
        main_layout.addWidget(top_widget, 1)  # Give stretch factor of 1
        
        # Log initial message
        self.log_to_terminal("Application started")
        self.log_to_terminal(f"Detected {len(self.monitors)} monitors")
    
    def log_to_terminal(self, message):
        """Add a message to the terminal output"""
        timestamp = time.strftime("%H:%M:%S")
        self.terminal_output.append(f"[{timestamp}] {message}")
    
    def setup_control_panel(self, layout):
        """Set up the control panel (left side) with 2-column grid layout"""
        # Game Window & Region Selection section (column 0, row 0)
        window_region_group = self.create_window_region_section()
        layout.addWidget(window_region_group, 0, 0, 2, 1)  # Span 2 rows to give more space
        
        # Action sequence section (column 1, row 0, spans 2 rows)
        action_group = self.create_action_section()
        layout.addWidget(action_group, 0, 1, 2, 1)  # Span 2 rows
        
        # Monitor and status section (column 0-1, row 2)
        monitor_group = self.create_monitoring_section()
        layout.addWidget(monitor_group, 2, 0, 1, 2)  # Span both columns in row 2
    
    def create_window_region_section(self):
        """Create a combined window selection and region selection section with 2 columns"""
        window_region_group = QGroupBox()
        window_region_layout = QVBoxLayout(window_region_group)
        window_region_layout.setContentsMargins(4, 4, 4, 0)  # Reduced top margin
        window_region_layout.setSpacing(0)  # Remove spacing
        
        # Create a widget for the two columns
        columns_widget = QWidget()
        columns_layout = QHBoxLayout(columns_widget)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(4)
        
        # Left column: Window info
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 2, 0)  # Add right margin
        left_layout.setSpacing(2)  # Reduced spacing
        
        # Status label
        self.window_status = QLabel("Looking for PLAY TOGETHER window...")
        self.window_status.setWordWrap(True)
        self.window_status.setStyleSheet(f"color: {self.colors['text_secondary']}; padding: 2px;")
        left_layout.addWidget(self.window_status)
        
        # Window info
        self.window_info = QLabel("No window found")
        self.window_info.setWordWrap(True)
        self.window_info.setStyleSheet(f"color: {self.colors['text_secondary']}; background: {self.colors['bg_medium']}; padding: 2px;")
        self.window_info.setMaximumHeight(50)  # Reduced height
        left_layout.addWidget(self.window_info)
        
        # Find game window button
        find_button = QPushButton("Find Game Window")
        find_button.setMaximumHeight(20)  # Reduced height
        find_button.clicked.connect(self.find_game_window)
        left_layout.addWidget(find_button)
        
        # Add left column to columns layout
        columns_layout.addWidget(left_column)
        
        # Right column: Region settings
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(2, 0, 0, 0)  # Add left margin
        right_layout.setSpacing(2)  # Reduced spacing
        
        # Region settings
        settings_widget = QWidget()
        settings_layout = QGridLayout(settings_widget)
        settings_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        settings_layout.setSpacing(2)  # Minimal spacing
        
        # Size row
        size_label = QLabel("Size:")
        size_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        settings_layout.addWidget(size_label, 0, 0)
        
        self.size_input = QSpinBox()
        self.size_input.setMinimum(10)
        self.size_input.setMaximum(500)
        self.size_input.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.size_input.setValue(100)
        self.size_input.setMaximumHeight(20)  # Reduced height
        self.size_input.setFixedWidth(60)  # Fixed width
        self.size_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # Hide buttons
        self.size_input.setStyleSheet("padding-left: 4px;")  # Add some padding
        settings_layout.addWidget(self.size_input, 0, 1)
        
        unit_label = QLabel("px")
        unit_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        settings_layout.addWidget(unit_label, 0, 2)
        
        # Threshold row
        threshold_label = QLabel("Threshold:")
        threshold_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        settings_layout.addWidget(threshold_label, 1, 0)
        
        self.threshold_input = QDoubleSpinBox()
        self.threshold_input.setMinimum(0.01)
        self.threshold_input.setMaximum(1.0)
        self.threshold_input.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.threshold_input.setValue(self.detection_threshold)
        self.threshold_input.setSingleStep(0.01)
        self.threshold_input.setDecimals(2)
        self.threshold_input.setMaximumHeight(20)  # Reduced height
        self.threshold_input.setFixedWidth(60)  # Fixed width
        self.threshold_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)  # Hide buttons
        self.threshold_input.setStyleSheet("padding-left: 4px;")  # Add some padding
        settings_layout.addWidget(self.threshold_input, 1, 1)
        
        # Add settings widget to right column
        right_layout.addWidget(settings_widget)
        
        # Region buttons
        buttons_widget = QWidget()
        buttons_layout = QVBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        buttons_layout.setSpacing(2)  # Reduced spacing
        
        # Select region button
        select_region_button = QPushButton("Select Region")
        select_region_button.setMaximumHeight(20)  # Reduced height
        select_region_button.clicked.connect(self.select_region)
        buttons_layout.addWidget(select_region_button)
        
        # Capture reference button
        reference_button = QPushButton("Capture Reference")
        reference_button.setMaximumHeight(20)  # Reduced height
        reference_button.clicked.connect(self.capture_reference_frame)
        buttons_layout.addWidget(reference_button)
        
        # Add buttons to right column
        right_layout.addWidget(buttons_widget)
        
        # Add right column to columns layout
        columns_layout.addWidget(right_column)
        
        # Add columns widget to main layout
        window_region_layout.addWidget(columns_widget)
        
        # Control buttons in a grid layout below the columns
        control_widget = QWidget()
        control_layout = QGridLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        control_layout.setSpacing(2)  # Reduced spacing
        
        # Start button
        self.monitor_button = QPushButton("Start")
        self.monitor_button.setMaximumHeight(20)  # Reduced height
        self.monitor_button.setEnabled(False)
        self.monitor_button.clicked.connect(self.toggle_monitoring)
        control_layout.addWidget(self.monitor_button, 0, 0)
        
        # Stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.setMaximumHeight(20)  # Reduced height
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_monitoring)
        control_layout.addWidget(self.stop_button, 0, 1)
        
        # Pause button
        self.pause_button = QPushButton("Pause")
        self.pause_button.setMaximumHeight(20)  # Reduced height
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.toggle_pause)
        control_layout.addWidget(self.pause_button, 0, 2)
        
        # Clear log button
        clear_log_button = QPushButton("Clear Log")
        clear_log_button.setMaximumHeight(20)  # Reduced height
        clear_log_button.clicked.connect(self.clear_log)
        control_layout.addWidget(clear_log_button, 0, 3)
        
        # Add control buttons to main layout
        window_region_layout.addWidget(control_widget)
        
        # Automatically try to find the window
        QTimer.singleShot(500, self.find_game_window)
        
        return window_region_group
    
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
    
    def create_action_section(self):
        """Create the action sequence section"""
        action_group = QGroupBox()
        action_group.setMaximumWidth(300)
        action_layout = QVBoxLayout(action_group)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        action_layout.setContentsMargins(0, 0, 0, 0)  # Reduced margins
        action_layout.setSpacing(0)  # Reduced spacing
        
        # Create a scroll area for actions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(120)  # Reduced height
        
        # Container widget for action items
        self.action_container = QWidget()
        self.action_layout = QVBoxLayout(self.action_container)
        self.action_layout.setContentsMargins(2, 2, 2, 2)  # Reduced margins
        self.action_layout.setSpacing(2)  # Reduced spacing
        self.action_layout.addStretch(0)  # Add stretch to push items to the top
        
        scroll.setWidget(self.action_container)
        action_layout.addWidget(scroll, 1)  # Give scroll area stretch factor
        
        # Action buttons
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        buttons_layout.setSpacing(2)  # Reduced spacing
        
        add_button = QPushButton("+ Add")
        add_button.setMaximumHeight(20)  # Further reduced height
        add_button.clicked.connect(self.add_action_item)
        
        clear_button = QPushButton("Clear")
        clear_button.setMaximumHeight(20)  # Further reduced height
        clear_button.setStyleSheet(
            f"background-color: {self.colors['warning']}; color: {self.colors['text']};"
        )
        clear_button.clicked.connect(self.clear_action_sequence)
        
        default_button = QPushButton("Default")
        default_button.setMaximumHeight(20)  # Further reduced height
        default_button.clicked.connect(self.load_default_action_sequence)
        
        test_button = QPushButton("Test")
        test_button.setMaximumHeight(20)  # Further reduced height
        test_button.clicked.connect(self.test_action_sequence)
        
        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(clear_button)
        buttons_layout.addWidget(default_button)
        buttons_layout.addWidget(test_button)
        
        action_layout.addWidget(buttons_widget, 0)  # No stretch factor
        
        return action_group
    
    def create_monitoring_section(self):
        """Create the monitoring section with integrated monitor view and terminal"""
        monitor_group = QGroupBox()
        monitor_layout = QVBoxLayout(monitor_group)  # Vertical layout
        monitor_group.setMaximumHeight(220)
        monitor_layout.setContentsMargins(0, 0, 0, 0)  # Reduced margins
        monitor_layout.setSpacing(0)  # Reduced spacing
        
        # Top section with monitor view and terminal side by side
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)
        
        # Left side: Monitor view
        view_widget = QWidget()
        view_layout = QVBoxLayout(view_widget)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(2)
        
        # Canvas for the monitor view
        canvas = QLabel()
        canvas.setAlignment(Qt.AlignmentFlag.AlignBottom)
        canvas.setMinimumSize(200, 200)
        canvas.setMaximumSize(200, 200)  # Enforce 200x200 size
        canvas.setStyleSheet("background-color: black;")
        view_layout.addWidget(canvas)
        
        # Store the canvas for later use
        self.monitor_canvas = canvas
        
        # Right side: Terminal output
        terminal_widget = QWidget()
        terminal_layout = QVBoxLayout(terminal_widget)
        terminal_layout.setContentsMargins(0, 0, 0, 0)
        terminal_layout.setSpacing(2)
        
        # Terminal text area
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setStyleSheet(
            f"background-color: {self.colors['bg_dark']}; "
            f"color: {self.colors['text']}; "
            f"font-family: 'Consolas', monospace; "
            f"font-size: 9pt;"  # Reduced font size
        )
        self.terminal_output.setMinimumHeight(60)  # Reduced height
        self.terminal_output.setMaximumHeight(200)  # Limit maximum height
        terminal_layout.addWidget(self.terminal_output, 1)  # Give stretch factor
        
        # Status label directly under the terminal
        self.status_label = QLabel("Ready to select window")
        self.status_label.setStyleSheet(f"color: {self.colors['text_secondary']}; padding: 2px;")
        terminal_layout.addWidget(self.status_label)  # Add to terminal layout
        
        # Add view and terminal to content layout
        content_layout.addWidget(view_widget)
        content_layout.addWidget(terminal_widget, 1)  # Give terminal more space
        
        # Add content widget to main layout
        monitor_layout.addWidget(content_widget, 1)  # Give stretch factor
        
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
        """Allow user to select a region of the screen"""
        # Get the size from the input field
        size = self.size_input.value()
        
        # Calculate region dimensions based on 1.5:1 ratio
        width = int(size * 1.5)
        height = size
        
        # Temporarily minimize our own window
        self.setWindowState(Qt.WindowState.WindowMinimized)
        time.sleep(0.5)  # Give time for window to minimize
        
        # Create a fullscreen transparent window for selection
        selection_window = QWidget(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        selection_window.setWindowOpacity(0.3)
        selection_window.setStyleSheet("background-color: black;")
        selection_window.showFullScreen()
        
        # Variables to track selection rectangle
        preview_rect = None
        rect_x, rect_y = 0, 0
        
        # Create a QPainter for drawing
        class SelectionOverlay(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setGeometry(0, 0, selection_window.width(), selection_window.height())
                self.setCursor(Qt.CursorShape.CrossCursor)
                self.mouse_pos = QPoint(0, 0)
                
            def paintEvent(self, event):
                painter = QPainter(self)
                
                # Draw crosshairs
                painter.setPen(QPen(QColor(self.parent().parent().colors['accent']), 1, Qt.PenStyle.DashLine))
                painter.drawLine(self.mouse_pos.x(), 0, self.mouse_pos.x(), self.height())
                painter.drawLine(0, self.mouse_pos.y(), self.width(), self.mouse_pos.y())
                
                # Draw selection rectangle
                if rect_x != 0 and rect_y != 0:
                    # Draw border
                    painter.setPen(QPen(QColor(self.parent().parent().colors['accent']), 2))
                    painter.drawRect(rect_x - width // 2, rect_y - height // 2, width, height)
                    
                    # Draw grid lines
                    painter.setPen(QPen(QColor(self.parent().parent().colors['green']), 1, Qt.PenStyle.DashLine))
                    cell_width = width // 3
                    cell_height = height // 3
                    
                    # Vertical grid lines
                    for i in range(1, 3):
                        painter.drawLine(
                            rect_x - width // 2 + i * cell_width, rect_y - height // 2,
                            rect_x - width // 2 + i * cell_width, rect_y + height // 2
                        )
                    
                    # Horizontal grid lines
                    for i in range(1, 3):
                        painter.drawLine(
                            rect_x - width // 2, rect_y - height // 2 + i * cell_height,
                            rect_x + width // 2, rect_y - height // 2 + i * cell_height
                        )
                    
                    # Draw coordinates
                    painter.setPen(QPen(QColor(self.parent().parent().colors['text']), 1))
                    painter.setFont(QFont("Consolas", 9))
                    
                    # Calculate actual coordinates
                    left = max(0, rect_x - width // 2)
                    top = max(0, rect_y - height // 2)
                    
                    # Ensure region stays within screen bounds
                    if left + width > self.width():
                        left = self.width() - width
                    if top + height > self.height():
                        top = self.height() - height
                    
                    coord_text = f"pos: ({left},{top}) • size: {width}×{height}"
                    painter.drawText(self.width() // 2 - 100, self.height() - 20, 200, 20, 
                                    Qt.AlignmentFlag.AlignCenter, coord_text)
                
                # Draw instructions
                painter.setPen(QPen(QColor(self.parent().parent().colors['green']), 1))
                painter.setFont(QFont("Consolas", 10))
                painter.drawText(self.width() // 2 - 200, 30, 400, 20, 
                                Qt.AlignmentFlag.AlignCenter, 
                                "SELECT REGION • CLICK TO PLACE • ESC TO CANCEL")
            
            def mouseMoveEvent(self, event):
                self.mouse_pos = event.pos()
                nonlocal rect_x, rect_y
                rect_x = event.pos().x()
                rect_y = event.pos().y()
                self.update()
            
            def mousePressEvent(self, event):
                nonlocal rect_x, rect_y
                rect_x = event.pos().x()
                rect_y = event.pos().y()
                
                # Calculate actual coordinates
                left = max(0, rect_x - width // 2)
                top = max(0, rect_y - height // 2)
                
                # Ensure region stays within screen bounds
                if left + width > self.width():
                    left = self.width() - width
                if top + height > self.height():
                    top = self.height() - height
                
                # Close selection window
                selection_window.close()
                
                # Set region in parent
                self.parent().parent().selected_region = (left, top, width, height)
                self.parent().parent().log_to_terminal(f"Region selected: ({left},{top}) {width}×{height}")
                
                # Update UI to show selected region
                self.parent().parent().update_region_label()
                
                # Enable monitoring button
                self.parent().parent().monitor_button.setEnabled(True)
        
        # Create overlay widget
        overlay = SelectionOverlay(selection_window)
        overlay.setParent(selection_window)
        
        # Handle ESC key to cancel
        def on_escape(event):
            if event.key() == Qt.Key.Key_Escape:
                selection_window.close()
                self.setWindowState(Qt.WindowState.WindowActive)
                self.log_to_terminal("Region selection cancelled")
        
        selection_window.keyPressEvent = on_escape
        
        # Show selection window
        selection_window.show()
        
        # Wait for selection window to close
        selection_window.destroyed.connect(lambda: self.setWindowState(Qt.WindowState.WindowActive))
        
    def update_region_label(self):
        """Update UI to show the selected region"""
        if hasattr(self, 'status_label') and self.selected_region:
            x, y, w, h = self.selected_region
            self.status_label.setText(f"Selected: ({x},{y}) {w}×{h}")
            
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
            self.monitor_button.setText("Start")
            self.monitor_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            self.is_monitoring = True
            self.is_paused = False
            
            # Start monitoring thread
            self.monitor_thread = QThread()
            self.monitor_worker = MonitorWorker(self)
            self.monitor_worker.moveToThread(self.monitor_thread)
            self.monitor_thread.started.connect(self.monitor_worker.run)
            self.monitor_thread.start()
            
            self.log_to_terminal("Monitoring started")
        else:
            # Stop monitoring
            self.stop_monitoring()
    
    def monitor_thread_function(self):
        """Thread function for continuous monitoring"""
        self.log_to_terminal("Monitoring started")
        
        with mss.mss() as sct:
            while self.is_monitoring:
                # Check if paused
                if hasattr(self, 'is_paused') and self.is_paused:
                    time.sleep(0.1)
                    continue
                    
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
        if image is None or not hasattr(self, 'monitor_canvas'):
            return
            
        # Convert PIL image to numpy array
        img_np = np.array(image)
        
        # Convert to RGB if needed
        if len(img_np.shape) == 2:  # Grayscale
            img_rgb = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
        elif img_np.shape[2] == 4:  # RGBA
            img_rgb = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
        else:
            img_rgb = img_np
            
        # Resize to fit the canvas (200x200) while maintaining aspect ratio
        h, w = img_rgb.shape[:2]
        max_size = 200
        scale = min(max_size / w, max_size / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize the image
        img_resized = cv2.resize(img_rgb, (new_w, new_h))
        
        # Create a black background of 200x200
        background = np.zeros((max_size, max_size, 3), dtype=np.uint8)
        
        # Calculate position to center the image
        y_offset = (max_size - new_h) // 2
        x_offset = (max_size - new_w) // 2
        
        # Place the resized image on the background
        background[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = img_resized
        
        # Convert to QImage and display
        h, w, c = background.shape
        bytes_per_line = c * w
        q_img = QImage(background.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        self.monitor_canvas.setPixmap(pixmap)
    
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
        type_combo.setMaximumWidth(60)  # Reduced width
        type_combo.setMaximumHeight(20)  # Reduced height
        
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
        """Parse action frames into action sequence"""
        self.action_sequence = []
        
        # Get all action frames
        for i in range(self.action_layout.count()):
            item = self.action_layout.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QFrame):
                frame = item.widget()
                
                # Get values from the frame
                action_type = frame.type_combo.currentText()
                value = frame.value_input.text()
                comment = frame.comment_input.text()
                
                # Create action based on type
                action = {"type": action_type, "comment": comment}
                
                if action_type == "key":
                    action["key"] = value
                elif action_type == "wait":
                    try:
                        action["seconds"] = float(value)
                    except:
                        action["seconds"] = 1.0
                elif action_type == "click":
                    try:
                        x, y = value.split(",")
                        action["x"] = int(x)
                        action["y"] = int(y)
                    except:
                        action["x"] = 0
                        action["y"] = 0
                elif action_type == "esc":
                    action["key"] = "escape"
                elif action_type == "f":
                    action["key"] = "f"
                
                self.action_sequence.append(action)
                
        return self.action_sequence
    
    def execute_action_sequence(self):
        """Execute the action sequence"""
        if not self.action_sequence:
            self.log_to_terminal("No actions to execute")
            return
            
        self.log_to_terminal("Executing action sequence...")
        
        # Execute each action in sequence
        for action in self.action_sequence:
            action_type = action.get("type")
            
            if action_type == "focus":
                self.log_to_terminal("Focusing window...")
                if self.target_window:
                    self.focus_window(self.target_window)
                    time.sleep(0.1)
                    
            elif action_type == "key":
                key = action.get("key")
                if key:
                    self.log_to_terminal(f"Pressing key: {key}")
                    self.press_key(key)
                    time.sleep(0.1)
                    
            elif action_type == "wait":
                seconds = float(action.get("seconds", 1))
                self.log_to_terminal(f"Waiting for {seconds} seconds...")
                time.sleep(seconds)
                
            elif action_type == "click":
                coords = action.get("coords", "0,0").split(",")
                try:
                    x, y = int(coords[0]), int(coords[1])
                    self.log_to_terminal(f"Clicking at ({x}, {y})...")
                    self.click_at(x, y)
                    time.sleep(0.1)
                except:
                    self.log_to_terminal(f"Invalid click coordinates: {action.get('coords')}")
                    
            elif action_type == "esc":
                self.log_to_terminal("Pressing ESC key...")
                self.press_key("escape")
                time.sleep(0.1)
                
            elif action_type == "f":
                self.log_to_terminal("Pressing F key...")
                self.press_key("f")
                time.sleep(0.1)
                
        self.log_to_terminal("Action sequence completed")
        
    def focus_window(self, window):
        """Focus the target window"""
        try:
            if window:
                if window.isMinimized:
                    window.restore()
                window.activate()
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
        type_combo.addItems(["key", "focus", "wait", "click", "esc", "f"])
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
        elif action_data["type"] in ["esc", "f"]:
            value_input.setPlaceholderText("No value needed")
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
                value_input.setEnabled(True)
            elif action_type == "wait":
                value_input.setPlaceholderText("Seconds")
                value_input.setEnabled(True)
            elif action_type == "click":
                value_input.setPlaceholderText("x,y")
                value_input.setEnabled(True)
            elif action_type in ["focus", "esc", "f"]:
                value_input.clear()
                value_input.setPlaceholderText("No value needed")
                value_input.setEnabled(False)
        
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
        
        # Initialize value input state based on current type
        update_value_placeholder(type_combo.currentText())
        
        return frame

    def click_at(self, x, y):
        """Simulate a mouse click at the specified coordinates"""
        try:
            # Move the cursor to the position
            win32api.SetCursorPos((x, y))
            time.sleep(0.1)
            
            # Perform a click
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True
        except Exception as e:
            self.log_to_terminal(f"Error clicking at ({x}, {y}): {str(e)}")
            return False

    def clear_log(self):
        """Clear the terminal output"""
        self.terminal_output.clear()
        self.log_to_terminal("Log cleared")
        
    def stop_monitoring(self):
        """Stop monitoring"""
        if self.is_monitoring:
            self.is_monitoring = False
            if self.monitor_thread:
                self.monitor_thread.quit()
                self.monitor_thread.wait()
            self.monitor_button.setText("Start")
            self.monitor_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.pause_button.setEnabled(False)
            self.log_to_terminal("Monitoring stopped")
            
    def toggle_pause(self):
        """Toggle pause/resume monitoring"""
        if not self.is_monitoring:
            return
            
        if hasattr(self, 'is_paused') and self.is_paused:
            # Resume monitoring
            self.is_paused = False
            self.pause_button.setText("Pause")
            self.log_to_terminal("Monitoring resumed")
        else:
            # Pause monitoring
            self.is_paused = True
            self.pause_button.setText("Resume")
            self.log_to_terminal("Monitoring paused")

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