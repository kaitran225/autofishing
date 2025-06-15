import sys
import cv2
import numpy as np
import threading
import time
from PIL import Image, ImageQt, ImageGrab
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
    QEvent, QObject, QMetaObject, QPoint, QEventLoop, Q_ARG
)
from PyQt6.QtGui import QPixmap, QImage, QColor, QFont, QPalette, QIcon, QPainter, QPen

# For direct key simulation
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Special key constants
VK_CODES = {
    # Letters
    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45,
    'f': 0x46, 'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A,
    'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F,
    'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54,
    'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59, 'z': 0x5A,
    
    # Numbers
    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
    
    # Function keys
    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74,
    'f6': 0x75, 'f7': 0x76, 'f8': 0x77, 'f9': 0x78, 'f10': 0x79,
    'f11': 0x7A, 'f12': 0x7B,
    
    # Special keys
    'esc': 0x1B,       # ESC key
    'escape': 0x1B,    # ESC key (alternate name)
    'enter': 0x0D,     # Enter key
    'return': 0x0D,    # Enter key (alternate name)
    'space': 0x20,     # Space key
    'spacebar': 0x20,  # Space key (alternate name)
    'tab': 0x09,       # Tab key
    'backspace': 0x08, # Backspace key
    
    # Modifier keys
    'shift': 0x10,     # Shift key
    'ctrl': 0x11,      # Ctrl key
    'control': 0x11,   # Ctrl key (alternate name)
    'alt': 0x12,       # Alt key
    
    # Arrow keys
    'left': 0x25,      # Left arrow
    'up': 0x26,        # Up arrow
    'right': 0x27,     # Right arrow
    'down': 0x28,      # Down arrow
    
    # Additional keys
    'insert': 0x2D,    # Insert key
    'delete': 0x2E,    # Delete key
    'del': 0x2E,       # Delete key (alternate name)
    'home': 0x24,      # Home key
    'end': 0x23,       # End key
    'pageup': 0x21,    # Page Up key
    'pagedown': 0x22,  # Page Down key
    'caps': 0x14,      # Caps Lock key
    'capslock': 0x14,  # Caps Lock key (alternate name)
    'numlock': 0x90,   # Num Lock key
    'scrolllock': 0x91 # Scroll Lock key
}
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
        return (active_window == hwnd)
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

class MonitorWorker(QObject):
    """Worker class for monitoring in a separate thread"""
    
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        
    def run(self):
        """Run the monitoring function"""
        self.parent.monitor_thread_function()

class PreviewWorker(QObject):
    """Worker class for preview in a separate thread"""
    
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        
    def run(self):
        """Run the preview function"""
        self.parent.preview_thread_function()

class KeyCaptureLineEdit(QLineEdit):
    """A special LineEdit that captures keyboard input"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Press any key...")
        self.captured_key = ""
        # Use the same style as all other input fields
        self.setStyleSheet("background-color: #414C33; color: #A4AC86; font-weight: bold;")
        
    def keyPressEvent(self, event):
        # Don't process modifiers alone
        if event.key() in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            super().keyPressEvent(event)
            return
            
        # Get key name
        key_name = self.get_key_name(event)
        if key_name:
            self.captured_key = key_name
            self.setText(key_name)
            # Keep the same style after capturing
            self.setStyleSheet("background-color: #414C33; color: #A4AC86; font-weight: bold;")
        
        # Stop event from propagating
        event.accept()
    
    def get_key_name(self, event):
        """Convert Qt key event to a standard key name"""
        # Handle special keys
        if event.key() == Qt.Key.Key_Escape:
            return "escape"
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            return "enter"
        elif event.key() == Qt.Key.Key_Tab:
            return "tab"
        elif event.key() == Qt.Key.Key_Backspace:
            return "backspace"
        elif event.key() == Qt.Key.Key_Space:
            return "space"
        elif event.key() == Qt.Key.Key_Up:
            return "up"
        elif event.key() == Qt.Key.Key_Down:
            return "down"
        elif event.key() == Qt.Key.Key_Left:
            return "left"
        elif event.key() == Qt.Key.Key_Right:
            return "right"
        elif event.key() == Qt.Key.Key_Delete:
            return "delete"
        elif event.key() == Qt.Key.Key_Home:
            return "home"
        elif event.key() == Qt.Key.Key_End:
            return "end"
        elif event.key() == Qt.Key.Key_PageUp:
            return "pageup"
        elif event.key() == Qt.Key.Key_PageDown:
            return "pagedown"
        elif event.key() == Qt.Key.Key_Insert:
            return "insert"
        elif Qt.Key.Key_F1 <= event.key() <= Qt.Key.Key_F12:
            # Function keys F1-F12
            return f"f{event.key() - Qt.Key.Key_F1 + 1}"
        else:
            # Regular keys
            key_text = event.text()
            if key_text and key_text.isprintable():
                return key_text.lower()
        
        # Unknown key
        return ""

class RegionSelectorQt(QMainWindow):
    """PyQt6 implementation of the Region Selector with iOS-style UI"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Auto-Fisher v1.0")
        self.setMinimumSize(600, 400)
        
        # Set window icon if available
        try:
            self.setWindowIcon(QIcon("icon.png"))
        except:
            pass  # No icon available
        
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
        
        # For preview functionality
        self.is_previewing = False
        self.preview_thread = None
        
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
        
        # Thread control dictionary for managing execution
        self.thread_control = {
            "running": False,
            "paused": False,
            "stop_requested": False
        }
        
        # Thread safety flag
        self.is_shutting_down = False
        
        # Default action sequence from pixel_change_trigger.py
        self.default_action_sequence = [
            {"type": "focus", "comment": "Focus the window"},
            {"type": "key", "key": "f", "comment": "Press F key"},
            {"type": "wait", "seconds": 5, "comment": "Wait 5 seconds"},
            {"type": "key", "key": "escape", "comment": "Press ESC key"},
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
        
        # Connect close event
        self.closeEvent = self.handle_close_event
        
    def handle_close_event(self, event):
        """Handle application close event by stopping all threads"""
        self.is_shutting_down = True
        
        # Stop all running threads
        self.stop_monitoring()
        self.stop_live_preview()
        
        # Wait for threads to finish
        if hasattr(self, 'monitor_thread') and self.monitor_thread and self.monitor_thread.isRunning():
            self.monitor_thread.quit()
            self.monitor_thread.wait(1000)  # Wait up to 1 second
            
        if hasattr(self, 'preview_thread') and self.preview_thread and self.preview_thread.isRunning():
            self.preview_thread.quit()
            self.preview_thread.wait(1000)  # Wait up to 1 second
            
        # Accept the close event
        event.accept()
    
    def setup_ui_style(self):
        """Set up minimal style for the application"""
        # Apply global stylesheet with consistent spacing and more concise styling
        stylesheet = f"""
        QMainWindow, QDialog, QWidget {{
            background-color: {self.colors['bg_dark']};
            color: {self.colors['text']};
            font-family: 'Segoe UI', sans-serif;
        }}
        
        QGroupBox {{
            background-color: {self.colors['bg_medium']};
            border-radius: 4px;
            border: 1px solid {self.colors['border']};
            margin-top: 6px;
        }}
        
        QGroupBox::title {{
            subcontrol-position: top left;
            margin-left: 6px;
        }}
        
        QPushButton {{
            background-color: {self.colors['button']};
            border-radius: 2px;
            padding: 4px 8px;
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
        
        QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox, QListWidget, QScrollArea, QScrollBar {{
            background-color: {self.colors['bg_medium']};
            border-radius: 2px;
            padding: 2px;
            border: 1px solid {self.colors['border']};
        }}
        
        QComboBox:hover, QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover {{
            border: 1px solid {self.colors['accent']};
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 16px;
        }}
        
        QLabel {{
            background: transparent;
        }}
        
        QFrame[frameShape="4"], QFrame[frameShape="5"] {{ /* HLine and VLine */
            color: {self.colors['border']};
            border: 1px solid {self.colors['border']};
        }}
        """
        
        self.setStyleSheet(stylesheet)
    
    def setup_ui(self):
        """Set up the main UI components"""
        # Create central widget with consistent spacing
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        self.setCentralWidget(central_widget)
        
        # Create control panel with grid layout
        control_panel = QWidget()
        control_layout = QGridLayout(control_panel)
        control_layout.setContentsMargins(2, 2, 2, 2)
        control_layout.setSpacing(4)
        
        # Set up the control panel
        self.setup_control_panel(control_layout)
        
        # Add control panel to main layout
        main_layout.addWidget(control_panel, 1)
        
        # Log initial message
        self.log_to_terminal("Application started")
        self.log_to_terminal(f"Detected {len(self.monitors)} monitors")
    
    def log_to_terminal(self, message):
        """Add a message to the terminal output"""
        try:
            if not self.is_shutting_down and hasattr(self, 'terminal_output'):
                timestamp = time.strftime("%H:%M:%S")
                self.terminal_output.append(f"[{timestamp}] {message}")
        except Exception as e:
            # Only print errors if not shutting down
            if not self.is_shutting_down:
                print(f"Error logging to terminal: {str(e)}")
    
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
        window_region_layout.setContentsMargins(4, 4, 4, 4)
        window_region_layout.setSpacing(4)
        
        # Create a widget for the two columns
        columns_widget = QWidget()
        columns_layout = QHBoxLayout(columns_widget)
        columns_layout.setContentsMargins(0, 0, 0, 0)
        columns_layout.setSpacing(4)
        
        # Left column: Window info
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        # Status label
        self.window_status = QLabel("Looking for PLAY TOGETHER window...")
        self.window_status.setWordWrap(True)
        self.window_status.setStyleSheet(f"color: {self.colors['text_secondary']}; padding: 2px;")
        left_layout.addWidget(self.window_status)
        
        # Window info
        self.window_info = QLabel("No window found")
        self.window_info.setWordWrap(True)
        self.window_info.setStyleSheet(f"color: {self.colors['text_secondary']}; background: {self.colors['bg_medium']}; padding: 2px;")
        self.window_info.setMaximumHeight(50)
        left_layout.addWidget(self.window_info)
        
        # Find game window button
        find_button = QPushButton("Find Game Window")
        find_button.setMaximumHeight(20)
        find_button.clicked.connect(self.find_game_window)
        left_layout.addWidget(find_button)
        
        # Add left column to columns layout
        columns_layout.addWidget(left_column)
        
        # Right column: Region settings
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        
        # Region settings
        settings_widget = QWidget()
        settings_layout = QGridLayout(settings_widget)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(4)
        
        # Size row
        size_label = QLabel("Size:")
        size_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        settings_layout.addWidget(size_label, 0, 0)
        
        self.size_input = QSpinBox()
        self.size_input.setMinimum(10)
        self.size_input.setMaximum(500)
        self.size_input.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.size_input.setValue(100)
        self.size_input.setMaximumHeight(20)
        self.size_input.setFixedWidth(60)
        self.size_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.size_input.setStyleSheet("padding-left: 4px;")
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
        self.threshold_input.setMaximumHeight(20)
        self.threshold_input.setFixedWidth(60)
        self.threshold_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.threshold_input.setStyleSheet("padding-left: 4px;")
        settings_layout.addWidget(self.threshold_input, 1, 1)
        
        # Add settings widget to right column
        right_layout.addWidget(settings_widget)
        
        # Region buttons
        buttons_widget = QWidget()
        buttons_layout = QVBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(4)
        
        # Select region button
        select_region_button = QPushButton("Select Region")
        select_region_button.setMaximumHeight(20)
        select_region_button.clicked.connect(self.select_region)
        buttons_layout.addWidget(select_region_button)
        
        # Capture reference button
        reference_button = QPushButton("Capture Reference")
        reference_button.setMaximumHeight(20)
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
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(4)
        
        # Start button
        self.monitor_button = QPushButton("Start")
        self.monitor_button.setMaximumHeight(20)
        self.monitor_button.setEnabled(False)
        self.monitor_button.clicked.connect(self.toggle_monitoring)
        self.monitor_button.setStyleSheet(
            f"background-color: {self.colors['accent']}; color: {self.colors['text']};"
        )
        control_layout.addWidget(self.monitor_button, 0, 0)
        
        # Stop button
        self.stop_button = QPushButton("Stop")
        self.stop_button.setMaximumHeight(20)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_monitoring)
        self.stop_button.setStyleSheet(
            f"background-color: {self.colors['warning']}; color: {self.colors['text']};"
        )
        control_layout.addWidget(self.stop_button, 0, 1)
        
        # Pause button
        self.pause_button = QPushButton("Pause")
        self.pause_button.setMaximumHeight(20)
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setStyleSheet(
            f"background-color: {self.colors['bg_medium']}; color: {self.colors['text']};"
        )
        control_layout.addWidget(self.pause_button, 0, 2)
        
        # Clear log button
        clear_log_button = QPushButton("Clear Log")
        clear_log_button.setMaximumHeight(20)
        clear_log_button.clicked.connect(self.clear_log)
        clear_log_button.setStyleSheet(
            f"background-color: {self.colors['bg_medium']}; color: {self.colors['text']};"
        )
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
        
        self.log_to_terminal(f"Debug: Found {len(all_windows)} windows")
        
        # Look for PLAY TOGETHER window
        found = False
        for window in all_windows:
            if window.width > 100 and window.height > 100 and window.title:
                # Debug: Log all windows found
                if len(window.title) > 0:
                    self.log_to_terminal(f"Debug: Window: {window.title[:50]}... ({window.width}×{window.height})")
                
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
        
        # Try alternative window selection if standard approach doesn't find the window
        if not found:
            self.window_status.setText("Game window not found. Try selecting any window...")
            
            # Print list of windows and let user choose any window as fallback
            self.log_to_terminal("Available windows:")
            large_windows = []
            
            for i, window in enumerate(all_windows):
                if window.width > 300 and window.height > 200 and window.title:
                    self.log_to_terminal(f"[{i}] {window.title[:50]}... ({window.width}×{window.height})")
                    large_windows.append(window)
            
            if large_windows:
                # Select first large window as fallback
                self.target_window = large_windows[0]
                
                # Update window info
                info_text = (
                    f"Title: {self.target_window.title}\n"
                    f"Size: {self.target_window.width}×{self.target_window.height}\n"
                    f"Position: ({self.target_window.left}, {self.target_window.top})"
                )
                self.window_info.setText(info_text)
                self.window_status.setText(f"Selected: {self.target_window.title}")
                self.status_label.setText(f"Selected: {self.target_window.title}")
                
                # Log to terminal
                self.log_to_terminal(f"Selected fallback window: {self.target_window.title}")
                found = True
        
        if not found:
            self.window_status.setText("No suitable windows found. Try again.")
            self.window_info.setText("No window found.\nPlease make sure the game is running.")
            self.log_to_terminal("No suitable windows found")
            self.target_window = None
    
    def create_action_section(self):
        """Create the action sequence section"""
        action_group = QGroupBox()
        action_group.setMaximumWidth(300)
        action_layout = QVBoxLayout(action_group)
        action_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        action_layout.setContentsMargins(4, 4, 4, 4)
        action_layout.setSpacing(4)
        
        # Create a scroll area for actions
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(120)
        
        # Container widget for action items
        self.action_container = QWidget()
        self.action_layout = QVBoxLayout(self.action_container)
        self.action_layout.setContentsMargins(4, 4, 4, 4)
        self.action_layout.setSpacing(4)
        self.action_layout.addStretch(0)
        
        scroll.setWidget(self.action_container)
        action_layout.addWidget(scroll, 1)
        
        # Action buttons
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(4)
        
        add_button = QPushButton("+ Add")
        add_button.setMaximumHeight(20)
        add_button.clicked.connect(self.add_action_item)
        
        clear_button = QPushButton("Clear")
        clear_button.setMaximumHeight(20)
        clear_button.setStyleSheet(
            f"background-color: {self.colors['warning']}; color: {self.colors['text']};"
        )
        clear_button.clicked.connect(self.clear_action_sequence)
        
        default_button = QPushButton("Default")
        default_button.setMaximumHeight(20)
        default_button.clicked.connect(self.load_default_action_sequence)
        
        test_button = QPushButton("Test")
        test_button.setMaximumHeight(20)
        test_button.clicked.connect(self.test_action_sequence)
        
        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(clear_button)
        buttons_layout.addWidget(default_button)
        buttons_layout.addWidget(test_button)
        
        action_layout.addWidget(buttons_widget, 0)
        
        return action_group
    
    def create_monitoring_section(self):
        """Create the monitoring section with integrated monitor view and terminal"""
        monitor_group = QGroupBox()
        monitor_layout = QVBoxLayout(monitor_group)
        monitor_group.setMaximumHeight(220)
        monitor_layout.setContentsMargins(4, 4, 4, 4)
        monitor_layout.setSpacing(4)
        
        # Top section with monitor view and terminal side by side
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)
        
        # Left side: Monitor view
        view_widget = QWidget()
        view_layout = QVBoxLayout(view_widget)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(4)
        
        # Canvas for the monitor view
        canvas = QLabel()
        canvas.setAlignment(Qt.AlignmentFlag.AlignBottom)
        canvas.setMinimumSize(200, 200)
        canvas.setMaximumSize(200, 200)
        canvas.setStyleSheet("background-color: black;")
        view_layout.addWidget(canvas)
        
        # Store the canvas for later use
        self.monitor_canvas = canvas
        
        # Right side: Terminal output
        terminal_widget = QWidget()
        terminal_layout = QVBoxLayout(terminal_widget)
        terminal_layout.setContentsMargins(0, 0, 0, 0)
        terminal_layout.setSpacing(4)
        
        # Terminal text area
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setMinimumHeight(60)
        self.terminal_output.setMaximumHeight(200)
        terminal_layout.addWidget(self.terminal_output, 1)
        
        # Status label directly under the terminal
        self.status_label = QLabel("Ready to select window")
        self.status_label.setStyleSheet(f"color: {self.colors['text_secondary']}; padding: 2px;")
        terminal_layout.addWidget(self.status_label)
        
        # Add view and terminal to content layout
        content_layout.addWidget(view_widget)
        content_layout.addWidget(terminal_widget, 1)
        
        # Add content widget to main layout
        monitor_layout.addWidget(content_widget, 1)
        
        return monitor_group
    
    def update_monitor_view(self, image=None):
        """Update the monitor view with the current frame"""
        if self.is_shutting_down or not hasattr(self, 'monitor_canvas'):
            return
            
        # If no image specified, use current_frame
        if image is None:
            if self.current_frame is None:
                return
            image = self.current_frame
            
        try:
            # Make sure the image is not empty
            if image.size == 0:
                self.log_to_terminal("Warning: Empty image in update_monitor_view")
                return
                
            # Convert to QImage and resize to fit the canvas (200x200)
            h, w = image.shape[:2]
            
            # Create a copy for display (RGB format)
            display_frame = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Resize to fit the canvas (200x200) while maintaining aspect ratio
            max_size = 200
            scale = min(max_size / w, max_size / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            # Use better interpolation for smoother resizing
            display_frame = cv2.resize(display_frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
            # Create a dark gray background of 200x200
            background = np.ones((max_size, max_size, 3), dtype=np.uint8) * 40  # Dark gray
            
            # Calculate position to center the image
            y_offset = (max_size - new_h) // 2
            x_offset = (max_size - new_w) // 2
            
            # Place the resized image on the background
            background[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = display_frame
            
            # Add a subtle border around the image
            cv2.rectangle(background, 
                        (x_offset-1, y_offset-1), 
                        (x_offset+new_w+1, y_offset+new_h+1), 
                        (80, 80, 80), 1)  # Light gray border
            
            # Convert to QImage
            q_img = QImage(background.data, max_size, max_size, max_size * 3, QImage.Format.Format_RGB888)
            
            # Convert to QPixmap and set to canvas
            pixmap = QPixmap.fromImage(q_img)
            if hasattr(self, 'monitor_canvas'):
                self.monitor_canvas.setPixmap(pixmap)
                # Make sure the monitor_canvas is visible
                self.monitor_canvas.show()
        except Exception as e:
            if not self.is_shutting_down:
                print(f"Error updating monitor view: {e}")
                import traceback
                traceback.print_exc()
                self.log_to_terminal(f"Error displaying image: {str(e)}")
    
    def select_region(self):
        """Allow user to select a region of the screen"""
        if not self.target_window:
            self.status_label.setText("Error: No window selected")
            return
        
        # Ensure window is still valid
        try:
            title = self.target_window.title
            if not self.target_window.isActive:
                self.target_window.activate()
                time.sleep(0.2)  # Give time to activate
        except Exception as e:
            self.status_label.setText(f"Error: Window not available")
            return
            
        try:
            # Get region size
            size = self.size_input.value()
            if size < 10:
                self.status_label.setText("Error: Size must be at least 10px")
                return
            
            # Temporarily minimize our window
            self.setWindowState(Qt.WindowState.WindowMinimized)
            time.sleep(0.3)
            
            # Get window position and size
            win_left = self.target_window.left
            win_top = self.target_window.top
            win_width = self.target_window.width
            win_height = self.target_window.height
            
            # Focus the game window and move cursor to center
            self.target_window.activate()
            win32api.SetCursorPos((win_left + win_width // 2, win_top + win_height // 2))
            time.sleep(0.2)  # Give time for window to focus and cursor to move
            
            # Create selection overlay
            class SelectionOverlay(QWidget):
                def __init__(self, parent=None):
                    super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
                    self.mouse_x = win_width // 2
                    self.mouse_y = win_height // 2
                    self.region_size = size
                    self.win_left = win_left
                    self.win_top = win_top
                    self.win_width = win_width
                    self.win_height = win_height
                    self.accept_selection = False
                    self.selected_region = None
                    self.setGeometry(win_left, win_top, win_width, win_height)
                    self.setWindowOpacity(0.3)
                    self.setStyleSheet("background-color: black;")
                    self.setMouseTracking(True)
                    self.setCursor(Qt.CursorShape.CrossCursor)
                
                def paintEvent(self, event):
                    painter = QPainter(self)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    
                    # Calculate region coordinates
                    left = max(0, min(self.mouse_x - self.region_size // 2, self.win_width - self.region_size))
                    top = max(0, min(self.mouse_y - self.region_size // 2, self.win_height - self.region_size))
                    
                    # Draw semi-transparent background
                    painter.fillRect(0, 0, self.win_width, self.win_height, QColor(0, 0, 0, 80))
                    
                    # Draw selection rectangle with green outline
                    painter.setPen(QPen(QColor('#00FF00'), 2))
                    painter.drawRect(left, top, self.region_size, self.region_size)
                    
                    # Draw crosshair
                    painter.setPen(QPen(QColor('#00FFFF'), 1, Qt.PenStyle.DashLine))
                    painter.drawLine(0, self.mouse_y, self.win_width, self.mouse_y)  # Horizontal line
                    painter.drawLine(self.mouse_x, 0, self.mouse_x, self.win_height)  # Vertical line
                    
                    # Show coordinates
                    painter.setPen(QPen(QColor('white'), 1))
                    painter.setFont(QFont("Arial", 10))
                    coord_text = f"Position: ({self.win_left + left}, {self.win_top + top}) • Size: {self.region_size}×{self.region_size}"
                    painter.drawText(self.win_width//2 - 150, self.win_height - 30, 300, 30, 
                                    Qt.AlignmentFlag.AlignCenter, coord_text)
                    
                    # Add instruction text
                    painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                    painter.drawText(self.win_width//2 - 200, 30, 400, 30, 
                                    Qt.AlignmentFlag.AlignCenter, "Click to select region • ESC to cancel")
                    
                    # Draw semi-transparent highlight around selection
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                    highlight = QColor('#00FFFF')
                    highlight.setAlpha(30)
                    painter.fillRect(left, top, self.region_size, self.region_size, highlight)
                    
                    # Draw a zoom preview window (magnifying glass effect)
                    try:
                        # Display zoom preview if region is small enough
                        if self.region_size < 100:
                            # Define zoom preview size and position
                            zoom_size = 120
                            zoom_scale = 3.0
                            zoom_x = self.win_width - zoom_size - 20
                            zoom_y = 60
                            
                            # Draw zoom preview background
                            painter.fillRect(zoom_x - 5, zoom_y - 5, zoom_size + 10, zoom_size + 10, QColor(0, 0, 0, 200))
                            painter.setPen(QPen(QColor('#FFFFFF'), 1))
                            painter.drawRect(zoom_x - 5, zoom_y - 5, zoom_size + 10, zoom_size + 10)
                            
                            # Get the scaled region to magnify around the mouse cursor
                            mag_size = int(zoom_size / zoom_scale)
                            mag_x = max(0, min(self.mouse_x - mag_size // 2, self.win_width - mag_size))
                            mag_y = max(0, min(self.mouse_y - mag_size // 2, self.win_height - mag_size))
                            
                            # Create a "magnifying glass" preview by scaling and drawing the region
                            # (This is just a visual approximation since we don't have the actual window content)
                            painter.setPen(QPen(QColor('#444444')))
                            
                            # Draw a grid to represent pixels
                            cell_size = zoom_scale
                            for i in range(int(zoom_size // cell_size) + 1):
                                painter.drawLine(zoom_x, zoom_y + i * cell_size, 
                                                zoom_x + zoom_size, zoom_y + i * cell_size)
                                painter.drawLine(zoom_x + i * cell_size, zoom_y, 
                                                zoom_x + i * cell_size, zoom_y + zoom_size)
                            
                            # Draw crosshair in the zoom preview
                            painter.setPen(QPen(QColor('#00FFFF'), 2))
                            painter.drawLine(zoom_x, zoom_y + zoom_size // 2, 
                                            zoom_x + zoom_size, zoom_y + zoom_size // 2)
                            painter.drawLine(zoom_x + zoom_size // 2, zoom_y, 
                                            zoom_x + zoom_size // 2, zoom_y + zoom_size)
                            
                            # Draw border around zoom preview
                            painter.setPen(QPen(QColor('#00FFFF'), 2))
                            painter.drawRect(zoom_x, zoom_y, zoom_size, zoom_size)
                            
                            # Label the zoom preview
                            painter.setPen(QPen(QColor('#FFFFFF')))
                            painter.setFont(QFont("Arial", 9))
                            painter.drawText(zoom_x, zoom_y - 8, zoom_size, 20, 
                                            Qt.AlignmentFlag.AlignCenter, f"{zoom_scale}x Zoom")
                    except Exception as e:
                        pass  # Ignore any errors in the zoom preview
                
                def mouseMoveEvent(self, event):
                    self.mouse_x = int(event.position().x())
                    self.mouse_y = int(event.position().y())
                    self.update()  # Trigger repaint
                
                def mousePressEvent(self, event):
                    # Calculate region coordinates
                    left = max(0, min(self.mouse_x - self.region_size // 2, self.win_width - self.region_size))
                    top = max(0, min(self.mouse_y - self.region_size // 2, self.win_height - self.region_size))
                    
                    # Convert to absolute screen coordinates
                    screen_left = self.win_left + left
                    screen_top = self.win_top + top
                    
                    # Store the selected region
                    self.selected_region = (int(screen_left), int(screen_top), self.region_size, self.region_size)
                    self.accept_selection = True
                    
                    # Print the coordinates to console
                    print(f"Selected region: ({screen_left}, {screen_top}, {self.region_size}, {self.region_size})")
                    
                    # Close overlay
                    self.close()
                
                def keyPressEvent(self, event):
                    if event.key() == Qt.Key.Key_Escape:
                        self.accept_selection = False
                        self.close()
            
            # Create overlay with our custom class
            selection_overlay = SelectionOverlay()
            selection_overlay.show()
            
            # Create an event loop to wait for overlay to close
            loop = QEventLoop()
            selection_overlay.destroyed.connect(loop.quit)
            loop.exec()
            
            # Restore our window immediately
            self.setWindowState(Qt.WindowState.WindowActive)
            self.activateWindow()
            self.raise_()  # Bring window to front
            
            # Check if selection was accepted
            if hasattr(selection_overlay, 'accept_selection') and selection_overlay.accept_selection and hasattr(selection_overlay, 'selected_region'):
                self.selected_region = selection_overlay.selected_region
                x, y, w, h = self.selected_region
                coordinates_msg = f"Region selected: {w}×{h} at ({x}, {y})"
                print(coordinates_msg)  # Print to console
                self.log_to_terminal(coordinates_msg)  # Log to app terminal
                self.status_label.setText(coordinates_msg)
                
                # Enable monitoring button
                self.monitor_button.setEnabled(True)
                
                # Take a preview screenshot
                self.take_preview_screenshot()
            else:
                self.log_to_terminal("Selection canceled")
            
        except Exception as e:
            print(f"Error in region selection: {str(e)}")
            import traceback
            traceback.print_exc()
            self.status_label.setText(f"Error: {str(e)}")
            self.setWindowState(Qt.WindowState.WindowActive)
    
    def update_region_label(self):
        """Update UI to show the selected region"""
        if hasattr(self, 'status_label') and self.selected_region:
            x, y, w, h = self.selected_region
            self.status_label.setText(f"Selected: ({x},{y}) {w}×{h}")
            
    def handle_multi_monitor_capture(self, x, y, width, height):
        """Adjust capture coordinates for multi-monitor setups"""
        # MSS sometimes struggles with negative coordinates on multi-monitor setups
        # This method provides alternative capture approaches for such cases
        
        self.log_to_terminal(f"Debug: Handling multi-monitor capture for ({x},{y}) {width}×{height}")
        
        with mss.mss() as sct:
            # Find the monitor that contains our region
            target_monitor = None
            target_monitor_idx = 0
            
            for i, monitor in enumerate(sct.monitors[1:], 1):  # Skip the 'all monitors' entry at index 0
                mon_left, mon_top = monitor['left'], monitor['top']
                mon_right, mon_bottom = mon_left + monitor['width'], mon_top + monitor['height']
                
                # Check if the region center is in this monitor
                region_center_x = x + width // 2
                region_center_y = y + height // 2
                
                if (mon_left <= region_center_x < mon_right and 
                    mon_top <= region_center_y < mon_bottom):
                    target_monitor = monitor
                    target_monitor_idx = i
                    break
            
            if not target_monitor:
                self.log_to_terminal("Warning: Could not find monitor containing the region")
                # Use primary monitor as fallback
                target_monitor = sct.monitors[1]  # Primary monitor is usually at index 1
                target_monitor_idx = 1
            
            self.log_to_terminal(f"Debug: Using monitor {target_monitor_idx}: {target_monitor}")
            
            # Calculate coordinates relative to the target monitor
            rel_x = x - target_monitor['left']
            rel_y = y - target_monitor['top']
            
            # Ensure coordinates are not negative within the monitor
            if rel_x < 0:
                rel_x = 0
                self.log_to_terminal("Warning: Adjusted x coordinate to monitor boundary")
            if rel_y < 0:
                rel_y = 0
                self.log_to_terminal("Warning: Adjusted y coordinate to monitor boundary")
                
            # Ensure region fits within monitor
            if rel_x + width > target_monitor['width']:
                width = target_monitor['width'] - rel_x
                self.log_to_terminal(f"Warning: Adjusted width to {width}")
            if rel_y + height > target_monitor['height']:
                height = target_monitor['height'] - rel_y
                self.log_to_terminal(f"Warning: Adjusted height to {height}")
                
            # Create a region dict with coordinates relative to the monitor
            region = {
                "top": target_monitor['top'] + rel_y,
                "left": target_monitor['left'] + rel_x,
                "width": width,
                "height": height,
                "mon": target_monitor_idx  # Specify which monitor to capture from
            }
            
            return region
        
    def capture_reference_frame(self):
        """Capture a reference frame for comparison with reliable screen capture"""
        if not self.selected_region:
            self.status_label.setText("Error: No region selected")
            return False
            
        try:
            # Use PIL's ImageGrab directly instead of MSS for more reliability
            x, y, width, height = self.selected_region
            
            self.log_to_terminal(f"Capturing reference frame at ({x}, {y}) {width}x{height}")
            
            # Use ImageGrab for more reliable capture (especially with negative coordinates)
            screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            
            if screenshot:
                # Convert to numpy array
                img_np = np.array(screenshot)
                
                # Store as reference frame - make sure it's grayscale
                if len(img_np.shape) == 3:
                    self.reference_frame = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                else:
                    self.reference_frame = img_np
                    
                self.log_to_terminal(f"Reference frame captured successfully: {self.reference_frame.shape}")
                
                # Create color version for display
                self.current_frame = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR) if len(img_np.shape) == 3 else cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
                
                # Update monitor view
                self.update_monitor_view()
                
                self.status_label.setText("Reference frame captured")
                
                # Also update preview
                self.take_preview_screenshot()
                return True
            else:
                self.log_to_terminal("Failed to capture reference frame - empty screenshot")
                return False
                
        except Exception as e:
            self.log_to_terminal(f"Error capturing reference frame: {str(e)}")
            import traceback
            traceback.print_exc()
            self.status_label.setText(f"Error: {str(e)}")
            return False
    
    def take_preview_screenshot(self):
        """Take a preview screenshot of the selected region"""
        if not self.selected_region:
            self.log_to_terminal("Error: No region selected")
            return False
        
        try:
            # Use PIL's ImageGrab directly for reliable capture
            x, y, width, height = self.selected_region
            
            self.log_to_terminal(f"Taking preview at ({x}, {y}) {width}×{height}")
            
            # Handle negative coordinates which can occur with multi-monitor setups
            try:
                # First attempt with PIL's ImageGrab
                screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            except Exception as e:
                self.log_to_terminal(f"Error with direct capture: {e}, trying alternative capture method")
                # Try alternative approach for negative coordinates
                with mss.mss() as sct:
                    # Get monitor containing this region
                    monitor_num = 0
                    for i, m in enumerate(sct.monitors[1:], 1):  # Skip the "all monitors" at index 0
                        if (m['left'] <= x <= m['left'] + m['width'] and 
                            m['top'] <= y <= m['top'] + m['height']):
                            monitor_num = i
                            break
                    
                    # Adjust coordinates to be relative to the monitor
                    mon = sct.monitors[monitor_num]
                    rel_x = x - mon['left']
                    rel_y = y - mon['top']
                    
                    # Create the region dict for MSS
                    region = {
                        "top": mon['top'] + rel_y,
                        "left": mon['left'] + rel_x,
                        "width": width,
                        "height": height,
                        "mon": monitor_num
                    }
                    
                    self.log_to_terminal(f"Using monitor {monitor_num} for capture")
                    
                    # Capture and convert to PIL Image
                    sct_img = sct.grab(region)
                    screenshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            if screenshot:
                # Convert to numpy array for processing
                img_np = np.array(screenshot)
                
                if img_np.size == 0:
                    self.log_to_terminal("Error: Captured empty image")
                    return False
                    
                # Store as current frame
                self.previous_frame = self.current_frame if self.current_frame is not None else cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
                self.current_frame = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)  # Store color version
                
                # Process the image in multiple ways (like in prototype.py)
                self.color_frame = self.current_frame.copy()  # Normal color frame
                
                # Create grayscale version
                gray_frame = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
                gray_frame_display = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2BGR)
                
                # Create edge detection version
                edges = cv2.Canny(gray_frame, 100, 200)
                edges_display = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
                
                # Create color threshold version (for green detection)
                hsv = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2HSV)
                # Green range in HSV
                lower_green = np.array([40, 40, 40])
                upper_green = np.array([80, 255, 255])
                # Create a mask for the specified HSV range
                mask = cv2.inRange(hsv, lower_green, upper_green)
                green_mask = cv2.bitwise_and(self.current_frame, self.current_frame, mask=mask)
                
                # Update the monitor view with the color frame
                self.update_monitor_view(self.color_frame)
                
                # Calculate difference if we have a reference
                if self.reference_frame is None:
                    # Automatically create a reference frame if none exists
                    self.log_to_terminal("No reference frame detected, using current frame as reference")
                    self.reference_frame = gray_frame
                else:
                    diff_frame, change_percent = self.calculate_frame_difference(
                        gray_frame, self.reference_frame)
                    self.diff_frame = diff_frame
                    
                    # Add to history
                    self.change_history.append(change_percent)
                    if len(self.change_history) > 30:  # Keep last 30 readings
                        self.change_history.pop(0)
                    
                    # Update status
                    self.status_label.setText(
                        f"Preview: {width}×{height} • Change: {change_percent:.2%}"
                    )
                
                # Start live preview
                self.start_live_preview()
                
                # Enable monitoring button if it was disabled
                self.monitor_button.setEnabled(True)
                
                return True
            else:
                self.log_to_terminal("Failed to take preview - empty screenshot")
                return False
                
        except Exception as e:
            self.log_to_terminal(f"Error taking preview screenshot: {str(e)}")
            import traceback
            traceback.print_exc()
            self.status_label.setText(f"Error: {str(e)}")
            return False
    
    def preview_thread_function(self):
        """Thread function for continuous preview with reliable screen capture"""
        try:
            self.log_to_terminal("Live preview started")
            
            # Print info about screens
            screen_width = QApplication.primaryScreen().size().width()
            screen_height = QApplication.primaryScreen().size().height()
            self.log_to_terminal(f"Primary screen size: {screen_width}×{screen_height}")
            
            # Frame rate control
            fps_target = 30
            frame_interval = 1.0 / fps_target
            
            while self.is_previewing and not self.is_shutting_down:
                loop_start = time.time()
                
                try:
                    if self.target_window and self.selected_region:
                        # Use PIL's ImageGrab - most reliable across platforms/configurations
                        x, y, width, height = self.selected_region
                        
                        # Handle negative coordinates which can occur with multi-monitor setups
                        try:
                            # First attempt with PIL's ImageGrab
                            screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
                        except Exception as e:
                            self.log_to_terminal(f"Preview error: {e}, trying alternative capture")
                            # Try alternative approach using MSS
                            with mss.mss() as sct:
                                # Find monitor containing the region
                                monitor_num = 0
                                for i, m in enumerate(sct.monitors[1:], 1):
                                    if (m['left'] <= x <= m['left'] + m['width'] and 
                                        m['top'] <= y <= m['top'] + m['height']):
                                        monitor_num = i
                                        break
                                
                                # Adjust coordinates relative to the monitor
                                mon = sct.monitors[monitor_num]
                                rel_x = x - mon['left']
                                rel_y = y - mon['top']
                                
                                # Create region dict for MSS
                                region = {
                                    "top": mon['top'] + rel_y,
                                    "left": mon['left'] + rel_x,
                                    "width": width,
                                    "height": height,
                                    "mon": monitor_num
                                }
                                
                                # Capture and convert to PIL Image
                                sct_img = sct.grab(region)
                                screenshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                        
                        if screenshot:
                            # Convert to numpy array for processing
                            img_np = np.array(screenshot)
                            
                            if img_np.size > 0:
                                # Store as current frame
                                self.current_frame = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                                
                                # Process the image in multiple ways (like in prototype.py)
                                self.color_frame = self.current_frame.copy()  # Normal color frame
                                
                                # Create grayscale version
                                gray_frame = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
                                gray_frame_display = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2BGR)
                                
                                # Create edge detection version
                                edges = cv2.Canny(gray_frame, 100, 200)
                                edges_display = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
                                
                                # Create color threshold version (for green detection)
                                hsv = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2HSV)
                                # Green range in HSV
                                lower_green = np.array([40, 40, 40])
                                upper_green = np.array([80, 255, 255])
                                # Create a mask for the specified HSV range
                                mask = cv2.inRange(hsv, lower_green, upper_green)
                                green_mask = cv2.bitwise_and(self.current_frame, self.current_frame, mask=mask)
                                
                                # Calculate difference if we have a reference
                                if self.reference_frame is not None:
                                    self.diff_frame, change_percent = self.calculate_frame_difference(
                                        gray_frame, self.reference_frame)
                                    
                                    # Update history
                                    self.change_history.append(change_percent)
                                    if len(self.change_history) > 30:  # Keep last 30 values
                                        self.change_history.pop(0)
                                
                                # Update the display - only if not shutting down
                                if not self.is_shutting_down:
                                    try:
                                        QMetaObject.invokeMethod(self, "update_frames", Qt.ConnectionType.QueuedConnection)
                                    except Exception as invoke_error:
                                        if not self.is_shutting_down:
                                            print(f"Error invoking update_frames: {invoke_error}")
                                        # Don't break - continue trying
                                        time.sleep(0.1)
                                        continue
                            else:
                                self.log_to_terminal("Warning: Empty image captured in preview")
                        else:
                            self.log_to_terminal("Warning: Failed to capture screenshot in preview")
                    
                    # Maintain target frame rate
                    elapsed = time.time() - loop_start
                    sleep_time = max(0, frame_interval - elapsed)
                    time.sleep(sleep_time)
                    
                except Exception as e:
                    if not self.is_shutting_down:
                        print(f"Error in preview loop: {str(e)}")
                    time.sleep(0.5)
                    
            if not self.is_shutting_down:
                self.log_to_terminal("Live preview stopped")
                
        except Exception as outer_e:
            if not self.is_shutting_down:
                print(f"Critical error in preview thread: {outer_e}")
                
    def monitor_thread_function(self):
        """Main monitoring thread function with pixel change detection logic"""
        try:
            self.log_to_terminal("Monitoring thread started")
            
            # Frame rate control
            fps_target = 30
            frame_interval = 1.0 / fps_target
            
            # Variables for health check
            last_successful_capture = time.time()
            consecutive_failures = 0
            max_consecutive_failures = 5
            
            # Detection count for this session
            detection_count = 0
            
            while self.is_monitoring and not self.is_shutting_down:
                loop_start = time.time()
                
                try:
                    # Check if paused
                    if hasattr(self, 'is_paused') and self.is_paused:
                        time.sleep(0.1)
                        continue
                        
                    # Check if thread should stop
                    if self.thread_control.get("stop_requested", False):
                        self.log_to_terminal("Stop requested, exiting monitoring thread")
                        break
                    
                    if self.target_window and self.selected_region and not self.is_shutting_down:
                        # Use PIL's ImageGrab for reliable capture
                        x, y, width, height = self.selected_region
                        
                        # Use ImageGrab for reliable capture
                        screenshot = ImageGrab.grab(bbox=(x, y, x + width, y + height))
                        
                        if screenshot:
                            # Convert to numpy array for processing
                            img_np = np.array(screenshot)
                            
                            if img_np.size > 0:
                                # Store as current frame
                                self.current_frame = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                                
                                # Process the image for visualization
                                self.color_frame = self.current_frame.copy()
                                
                                # Convert to grayscale for comparison
                                current_gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
                                
                                # Check if we have a reference frame
                                if self.reference_frame is not None:
                                    # Calculate difference between current frame and reference frame
                                    if current_gray.shape != self.reference_frame.shape:
                                        # Resize to match if needed
                                        current_gray = cv2.resize(current_gray, (self.reference_frame.shape[1], self.reference_frame.shape[0]))
                                        
                                    diff_frame, change_percentage = self.calculate_frame_difference(current_gray, self.reference_frame)
                                    self.diff_frame = diff_frame
                                    
                                    # Add to history (keep only the last 30 values)
                                    self.change_history.append(change_percentage)
                                    if len(self.change_history) > 30:
                                        self.change_history.pop(0)
                                    
                                    # Update the display - only if not shutting down
                                    if not self.is_shutting_down:
                                        try:
                                            QMetaObject.invokeMethod(self, "update_frames", Qt.ConnectionType.QueuedConnection)
                                            
                                            # Update status with change percentage
                                            avg_change = sum(self.change_history) / len(self.change_history)
                                            QMetaObject.invokeMethod(
                                                self.status_label, 
                                                "setText", 
                                                Qt.ConnectionType.QueuedConnection,
                                                Q_ARG(str, f"Change: {change_percentage:.2%} (avg: {avg_change:.2%}) • Detections: {detection_count}")
                                            )
                                        except Exception as invoke_error:
                                            if not self.is_shutting_down:
                                                print(f"Error invoking update_frames: {invoke_error}")
                                            consecutive_failures += 1
                                            continue
                                    
                                    # Check if change exceeds threshold and cooldown period has passed
                                    current_time = time.time()
                                    threshold = self.threshold_input.value()
                                    
                                    # Enhanced detection: require sustained change above threshold
                                    # Check if most recent measurements are consistently above threshold
                                    recent_measurements = self.change_history[-3:] if len(self.change_history) >= 3 else self.change_history
                                    sustained_change = all(m > threshold * 0.8 for m in recent_measurements)
                                    
                                    if (change_percentage > threshold and 
                                        sustained_change and
                                        current_time - self.last_detection_time > self.detection_cooldown):
                                        
                                        # Increment detection counter
                                        detection_count += 1
                                        
                                        # Log detection
                                        self.log_to_terminal(f"Change detected: {change_percentage:.2%} (threshold: {threshold:.2f})")
                                        self.last_detection_time = current_time
                                        
                                        # Execute action sequence in a separate thread
                                        action_thread = threading.Thread(target=self.execute_action_sequence)
                                        action_thread.daemon = True
                                        action_thread.start()
                                        
                                # Reset health check variables on success
                                last_successful_capture = time.time()
                                consecutive_failures = 0
                            else:
                                self.log_to_terminal("Warning: Empty image captured in monitoring")
                                consecutive_failures += 1
                        else:
                            self.log_to_terminal("Warning: Failed to capture screenshot in monitoring")
                            consecutive_failures += 1
                            
                        # Health check
                        current_time = time.time()
                        if consecutive_failures >= max_consecutive_failures:
                            if not self.is_shutting_down:
                                self.log_to_terminal("Too many consecutive failures, attempting recovery...")
                                # Try to recapture reference
                                self.capture_reference_frame()
                                consecutive_failures = 0
                                last_successful_capture = time.time()
                                
                        if current_time - last_successful_capture > 10:  # 10 seconds without success
                            if not self.is_shutting_down:
                                self.log_to_terminal("No successful captures detected, attempting recovery...")
                                # Reset state and recapture reference
                                self.capture_reference_frame()
                                last_successful_capture = current_time
                    
                    # Maintain target frame rate
                    elapsed = time.time() - loop_start
                    sleep_time = max(0, frame_interval - elapsed)
                    time.sleep(sleep_time)
                    
                except Exception as e:
                    if not self.is_shutting_down:
                        print(f"Error in monitoring loop: {str(e)}")
                    consecutive_failures += 1
                    time.sleep(0.1)
                    
            if not self.is_shutting_down:
                self.log_to_terminal("Monitoring thread stopped")
                
        except Exception as outer_e:
            if not self.is_shutting_down:
                print(f"Critical error in monitor thread: {outer_e}")
                
    def execute_action_sequence(self):
        """Execute the action sequence with reliable focusing and key handling"""
        if not self.action_sequence:
            self.log_to_terminal("No actions to execute")
            return
            
        if not self.target_window:
            self.log_to_terminal("No target window selected")
            return
            
        self.log_to_terminal("Executing action sequence...")
        
        # Get window handle for more reliable focusing
        hwnd = None
        try:
            hwnd = win32gui.FindWindow(None, self.target_window.title)
            if not hwnd:
                self.log_to_terminal(f"Warning: Could not find window handle for {self.target_window.title}")
        except Exception as e:
            self.log_to_terminal(f"Error finding window handle: {str(e)}")
        
        # Always focus the window first, regardless of the first action
        self.log_to_terminal("Focusing window before executing actions...")
        
        # Use force_focus_window for better reliability
        focus_success = False
        if hwnd:
            focus_success = force_focus_window(hwnd)
            
        if not focus_success:
            self.log_to_terminal("Warning: Force focus failed, trying standard approach")
            if self.target_window:
                focus_success = self.target_window.activate()
            
        # Give time for the window to be properly focused
        time.sleep(0.5)
        
        # Log detection in terminal and update status
        QMetaObject.invokeMethod(
            self.status_label, 
            "setText", 
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, "Fish detected! Executing fishing sequence...")
        )
        
        # Re-verify focus succeeded
        active_hwnd = user32.GetForegroundWindow()
        if hwnd and active_hwnd == hwnd:
            self.log_to_terminal("Window focus verified successfully")
        else:
            self.log_to_terminal("Warning: Window focus may not be correct, but continuing")
        
        # Execute each action in sequence with enhanced error handling
        for i, action in enumerate(self.action_sequence):
            action_type = action.get("type")
            
            # Check if the action should be executed
            if self.thread_control.get("stop_requested", False):
                self.log_to_terminal("Stopping action sequence execution - stop requested")
                break
            
            if action_type == "focus":
                self.log_to_terminal(f"Action {i+1}: Focusing window again...")
                if hwnd:
                    # Use force_focus_window for better reliability
                    force_focus_window(hwnd)
                    # Verify focus
                    active_hwnd = user32.GetForegroundWindow()
                    if active_hwnd == hwnd:
                        self.log_to_terminal("Window focus successful")
                    else:
                        self.log_to_terminal("Warning: Force focus failed")
                time.sleep(0.3)
                    
            elif action_type == "key":
                key = action.get("key", "")
                if key:
                    self.log_to_terminal(f"Action {i+1}: Pressing key: {key}")
                    # First force focus before every key press for reliability
                    if hwnd:
                        force_focus_window(hwnd)
                    time.sleep(0.2)  # Short delay to ensure focus
                    
                    # First, try using direct_key_press for single character keys
                    if len(key) == 1:
                        success = direct_key_press(key)
                        if success:
                            self.log_to_terminal(f"Successfully sent key '{key}'")
                        else:
                            # Fall back to standard key press
                            self.press_key(key)
                    # For special keys, use the standard mechanism
                    else:
                        self.press_key(key)
                        
                    time.sleep(0.3)  # Wait after key press
                    
            elif action_type == "wait":
                seconds = float(action.get("seconds", 1))
                self.log_to_terminal(f"Action {i+1}: Waiting for {seconds} seconds...")
                
                # Update status with remaining time
                for remaining in range(int(seconds), 0, -1):
                    if self.thread_control.get("stop_requested", False):
                        self.log_to_terminal("Stopping action sequence - wait interrupted")
                        break
                    
                    # Update status with countdown
                    QMetaObject.invokeMethod(
                        self.status_label, 
                        "setText", 
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(str, f"Fishing sequence: waiting {remaining}s...")
                    )
                    time.sleep(1.0)
                
                # Split longer waits into smaller chunks to check for stop requests
                if seconds > 1.0:
                    chunks = int(seconds)
                    for _ in range(chunks):
                        time.sleep(1.0)
                        # Check if we should stop
                        if self.thread_control.get("stop_requested", False):
                            self.log_to_terminal("Stopping action sequence execution - stop requested")
                            break
                    # Sleep any remaining fraction of a second
                    remaining = seconds - chunks
                    if remaining > 0:
                        time.sleep(remaining)
                else:
                    time.sleep(seconds)
            
            # Check for stop request after each action
            if self.thread_control.get("stop_requested", False):
                self.log_to_terminal("Stopping action sequence execution - stop requested")
                break
                    
        # Update status after sequence completes
        if not self.thread_control.get("stop_requested", False):
            self.log_to_terminal("Action sequence completed")
            QMetaObject.invokeMethod(
                self.status_label, 
                "setText", 
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, "Fishing sequence completed - monitoring for next fish...")
            )
            
        # After fishing sequence, capture a new reference frame
        self.log_to_terminal("Capturing new reference frame after fishing sequence")
        self.capture_reference_frame()
    
    def press_key(self, key):
        """Press a key using direct Windows API for greater reliability"""
        try:
            if not key:
                self.log_to_terminal("Error: No key specified")
                return False
                
            # Convert key to lowercase string
            key_str = str(key).lower()
            self.log_to_terminal(f"Pressing key: '{key_str}'")
            
            # For single character keys, use direct_key_press
            if len(key_str) == 1 and key_str.isalpha():
                success = direct_key_press(key_str)
                if success:
                    self.log_to_terminal(f"Successfully sent key: '{key_str}' using direct_key_press")
                    return True
            
            # Check if key is in our virtual key code mapping
            if key_str in VK_CODES:
                vk_code = VK_CODES[key_str]
                
                # Create keyboard input structure for SendInput API
                extra = ctypes.c_ulong(0)
                ii_ = INPUT_UNION()
                ii_.ki = KEYBDINPUT(vk_code, 0, 0, 0, ctypes.pointer(extra))
                x = INPUT(INPUT_KEYBOARD, ii_)
                
                # Send key down
                result = ctypes.windll.user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
                if result != 1:
                    error = ctypes.get_last_error()
                    self.log_to_terminal(f"SendInput failed with error code: {error}")
                    return False
                
                # Wait a short time
                time.sleep(0.05)
                
                # Send key up
                ii_.ki.dwFlags = KEYEVENTF_KEYUP
                x.ii = ii_
                result = ctypes.windll.user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))
                if result != 1:
                    error = ctypes.get_last_error()
                    self.log_to_terminal(f"SendInput (keyup) failed with error code: {error}")
                    return False
                
                # As a backup, also try the standard keyboard module
                try:
                    keyboard.press_and_release(key_str)
                except:
                    pass  # Ignore errors from keyboard module
                
                self.log_to_terminal(f"Successfully sent key: '{key_str}'")
                return True
            else:
                # Use keyboard module as fallback
                self.log_to_terminal(f"Key '{key_str}' not found in VK_CODES, using keyboard module fallback")
                try:
                    keyboard.press_and_release(key_str)
                    self.log_to_terminal(f"Successfully sent key using keyboard module: '{key_str}'")
                    return True
                except Exception as e:
                    self.log_to_terminal(f"Keyboard module failed: {str(e)}")
                    return False
                
        except Exception as e:
            self.log_to_terminal(f"Error pressing key: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def calculate_frame_difference(self, frame1, frame2):
        """Calculate the difference between two grayscale frames with enhanced detection"""
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
        
        # Apply median blur to reduce noise (from pixel_change_trigger.py)
        diff = cv2.medianBlur(diff, 3)
        
        # Apply threshold to filter out noise with more sensitivity (from pixel_change_trigger.py)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        
        # Calculate change percentage
        change_percent = np.sum(thresh > 0) / thresh.size
        
        return thresh, change_percent

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
        
        # Use better interpolation for smoother resizing
        img_resized = cv2.resize(img_rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Create a dark gray background of 200x200
        background = np.ones((max_size, max_size, 3), dtype=np.uint8) * 40  # Dark gray
        
        # Calculate position to center the image
        y_offset = (max_size - new_h) // 2
        x_offset = (max_size - new_w) // 2
        
        # Place the resized image on the background
        background[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = img_resized
        
        # Add a subtle border around the image
        cv2.rectangle(background, 
                     (x_offset-1, y_offset-1), 
                     (x_offset+new_w+1, y_offset+new_h+1), 
                     (80, 80, 80), 1)  # Light gray border
        
        # Convert to QImage and display
        h, w, c = background.shape
        bytes_per_line = c * w
        q_img = QImage(background.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        self.monitor_canvas.setPixmap(pixmap)
    
    def add_action_item(self, action_type="focus", value=""):
        """Add a new action row with two columns"""
        # Create action frame with horizontal layout
        action_frame = QFrame()
        action_frame.setStyleSheet(f"background-color: {self.colors['bg_medium']}; margin: 0px;")
        action_frame.action_data = {"type": action_type, "value": value}
        
        # Create horizontal layout
        action_layout = QHBoxLayout(action_frame)
        action_layout.setContentsMargins(4, 4, 4, 4)
        action_layout.setSpacing(4)
        
        # Common input field style
        input_style = "background-color: #414C33; color: #A4AC86; font-weight: bold;"
        
        # First column: Action type dropdown
        type_combo = QComboBox()
        type_combo.addItems(["focus", "key", "wait"])
        
        # Make sure action_type is a string
        action_type_str = str(action_type) if not isinstance(action_type, str) else action_type
        type_combo.setCurrentText(action_type_str)
        
        type_combo.setMaximumWidth(60)
        type_combo.setMaximumHeight(20)
        
        # Second column: Value input - use a different widget based on type
        if action_type_str == "key":
            # Use our special key capture input
            value_input = KeyCaptureLineEdit()
            if value:
                value_input.setText(str(value))
                value_input.captured_key = str(value)
                value_input.setStyleSheet(input_style)
        else:
            # Use regular line edit for other types
            value_input = QLineEdit()
            value_input.setText(str(value) if value else "")
            value_input.setStyleSheet(input_style)
            
        value_input.setMaximumHeight(24)
        
        # Configure value input based on action type
        if action_type_str == "focus":
            value_input.setEnabled(False)
        else:
            value_input.setEnabled(True)
            if not value:
                if action_type_str == "key":
                    value_input.setPlaceholderText("Press any key...")
                elif action_type_str == "wait":
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
        action_layout.addWidget(delete_btn)
        
        # Connect signals to update data
        def update_type(text):
            old_type = action_frame.action_data["type"]
            action_frame.action_data["type"] = text
            
            # If changing to or from key type, we need to replace the input widget
            if (old_type == "key" and text != "key") or (old_type != "key" and text == "key"):
                old_input = value_input
                old_value = old_input.text() if hasattr(old_input, 'text') else ""
                
                # Remove the old input
                action_layout.removeWidget(old_input)
                old_input.setParent(None)
                old_input.deleteLater()
                
                # Create and add new input
                if text == "key":
                    new_input = KeyCaptureLineEdit()
                    new_input.setPlaceholderText("Press any key...")
                else:
                    new_input = QLineEdit()
                    if text == "wait":
                        new_input.setText("1.0")
                    else:
                        new_input.setText(old_value)
                
                # Apply consistent styling
                new_input.setStyleSheet(input_style)
                new_input.setMaximumHeight(24)
                action_layout.insertWidget(1, new_input)
                
                # Update reference and connections
                action_frame.value_input = new_input
                
                if text == "key":
                    # For KeyCaptureLineEdit we need to monitor textChanged
                    new_input.textChanged.connect(lambda t: update_key_value(t))
                else:
                    # Regular text input
                    new_input.textChanged.connect(update_value)
                    
            if text == "focus":
                value_input.setEnabled(False)
                value_input.clear()
            else:
                value_input.setEnabled(True)
        
        def update_value(text):
            action_frame.action_data["value"] = text
            
        def update_key_value(text):
            if hasattr(value_input, 'captured_key'):
                action_frame.action_data["value"] = value_input.captured_key
            else:
                action_frame.action_data["value"] = text
        
        # Connect signals
        type_combo.currentTextChanged.connect(update_type)
        
        # Connect different signal based on widget type
        if isinstance(value_input, KeyCaptureLineEdit):
            value_input.textChanged.connect(update_key_value)
        else:
            value_input.textChanged.connect(update_value)
        
        # Store widgets in the frame for later access
        action_frame.type_combo = type_combo
        action_frame.value_input = value_input
        
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
        for frame in self.action_frames:
            if frame and hasattr(frame, 'action_data'):
                # Extract action data directly from the stored dictionary
                action_data = frame.action_data
                action_type = action_data.get('type', 'focus')
                value = action_data.get('value', '')
                
                # Create action based on type
                action = {"type": action_type}
                
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
                
                # Add comment if available
                if "comment" in action_data:
                    action["comment"] = action_data.get("comment", "")
                
                self.action_sequence.append(action)
                
        return self.action_sequence
    
    def toggle_monitoring(self):
        """Toggle monitoring on/off with improved functionality similar to pixel_change_trigger.py"""
        if not self.is_monitoring:
            # Start monitoring
            if self.selected_region is None:
                self.log_to_terminal("Error: No region selected")
                return
                
            if self.reference_frame is None:
                # Try to capture a reference frame automatically
                self.log_to_terminal("No reference frame - capturing one now")
                success = self.capture_reference_frame()
                if not success:
                    self.log_to_terminal("Error: Could not capture reference frame")
                    return
            
            # Stop live preview if it's running
            self.stop_live_preview()
            
            # Apply threshold from UI
            self.detection_threshold = self.threshold_input.value()
            self.log_to_terminal(f"Starting monitoring with threshold: {self.detection_threshold:.2f}")
            
            # Update button text
            self.monitor_button.setText("Stop")
            self.monitor_button.setStyleSheet(
                f"background-color: {self.colors['warning']}; color: {self.colors['text']};"
            )
            self.monitor_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            self.is_monitoring = True
            self.is_paused = False
            
            # Reset thread control
            self.thread_control = {
                "running": True,
                "paused": False,
                "stop_requested": False
            }
            
            # Reset detection statistics
            self.last_detection_time = time.time()
            self.detection_count = 0
            
            # Start monitoring thread
            self.monitor_thread = QThread()
            self.monitor_worker = MonitorWorker(self)
            self.monitor_worker.moveToThread(self.monitor_thread)
            self.monitor_thread.started.connect(self.monitor_worker.run)
            self.monitor_thread.start()
            
            self.log_to_terminal("Monitoring started")
            self.status_label.setText("Monitoring active")
        else:
            # Stop monitoring
            self.stop_monitoring()
    
    def perform_health_check(self, consecutive_failures, last_successful_capture):
        """Check monitoring health and attempt recovery if needed"""
        if self.is_shutting_down:
            return False
            
        current_time = time.time()
        
        # Check if we've had too many consecutive failures
        if consecutive_failures >= 5:  # Max consecutive failures
            self.log_to_terminal("Too many consecutive failures, attempting recovery...")
            
            # Try to recapture reference frame
            self.capture_reference_frame()
            
            # Reset state
            self.current_frame = None
            self.previous_frame = None
            self.diff_frame = None
            self.change_history = []
            
            return True
            
        # Check if we haven't had a successful capture in a while
        if current_time - last_successful_capture > 10:  # 10 seconds without success
            self.log_to_terminal("No successful captures detected, attempting recovery...")
            
            # Try to refocus window and recapture reference
            if self.target_window:
                self.focus_window(self.target_window)
                time.sleep(0.2)
            
            self.capture_reference_frame()
            return True
            
        return False
    
    def stop_monitoring(self):
        """Stop monitoring with robust thread cleanup"""
        # Stop live preview if it's running
        self.stop_live_preview()
        
        if self.is_monitoring:
            try:
                # Signal thread to stop via thread_control
                self.thread_control["stop_requested"] = True
                self.thread_control["running"] = False
                self.is_monitoring = False
                
                # Give thread time to respond to stop request
                time.sleep(0.2)
                
                # Stop the thread safely
                if self.monitor_thread and self.monitor_thread.isRunning():
                    self.monitor_thread.quit()
                    success = self.monitor_thread.wait(1000)  # Wait up to 1 second
                    if not success:
                        print("Warning: Monitor thread did not terminate gracefully")
            except Exception as e:
                print(f"Error stopping monitoring: {e}")
            
            # Reset UI regardless of any errors
            self.monitor_button.setText("Start")
            self.monitor_button.setEnabled(True)
            self.monitor_button.setStyleSheet(
                f"background-color: {self.colors['accent']}; color: {self.colors['text']};"
            )
            self.stop_button.setEnabled(False)
            self.pause_button.setEnabled(False)
            self.pause_button.setText("Pause")
            self.status_label.setText("Monitoring stopped")
            
            # Log only if we're not shutting down
            if not self.is_shutting_down:
                self.log_to_terminal("Monitoring stopped")

    def toggle_pause(self):
        """Toggle pause/resume monitoring"""
        if not self.is_monitoring:
            return
            
        if hasattr(self, 'is_paused') and self.is_paused:
            # Resume monitoring
            self.is_paused = False
            self.thread_control["paused"] = False
            self.pause_button.setText("Pause")
            self.pause_button.setStyleSheet(
                f"background-color: {self.colors['bg_medium']}; color: {self.colors['text']};"
            )
            self.status_label.setText("Monitoring resumed")
            self.log_to_terminal("Monitoring resumed")
        else:
            # Pause monitoring
            self.is_paused = True
            self.thread_control["paused"] = True
            self.pause_button.setText("Resume")
            self.pause_button.setStyleSheet(
                f"background-color: {self.colors['accent_light']}; color: {self.colors['text']};"
            )
            self.status_label.setText("Monitoring paused")
            self.log_to_terminal("Monitoring paused")

    def start_live_preview(self):
        """Start or stop live preview of the selected region"""
        # Stop any existing preview
        self.stop_live_preview()
        
        if not self.selected_region:
            self.status_label.setText("Error: No region selected")
            return
        
        # Start preview
        self.is_previewing = True
        self.log_to_terminal("Starting live preview...")
        
        # Start preview thread
        self.preview_thread = QThread()
        self.preview_worker = PreviewWorker(self)
        self.preview_worker.moveToThread(self.preview_thread)
        self.preview_thread.started.connect(self.preview_worker.run)
        self.preview_thread.start()
        
        self.status_label.setText("Live preview active")

    def stop_live_preview(self):
        """Stop the live preview with robust thread cleanup"""
        if hasattr(self, 'is_previewing') and self.is_previewing:
            try:
                self.is_previewing = False
                
                # Wait for thread to finish cleanly
                if self.preview_thread and self.preview_thread.isRunning():
                    self.preview_thread.quit()
                    success = self.preview_thread.wait(1000)  # Wait up to 1 second
                    if not success and not self.is_shutting_down:
                        print("Warning: Preview thread did not terminate gracefully")
                
                # Log only if we're not shutting down
                if not self.is_shutting_down:
                    self.log_to_terminal("Live preview stopped")
            except Exception as e:
                if not self.is_shutting_down:
                    print(f"Error stopping preview: {e}")

    def clear_log(self):
        """Clear the terminal output"""
        self.terminal_output.clear()
        self.log_to_terminal("Log cleared")

    def test_action_sequence(self):
        """Test the action sequence without monitoring"""
        # Parse action sequence
        self.apply_action_sequence()
        
        # Debug output
        self.log_to_terminal(f"Action sequence created: {len(self.action_sequence)} actions")
        for i, action in enumerate(self.action_sequence):
            self.log_to_terminal(f"Action {i+1}: {action}")
        
        # Check if we have a target window
        if not self.target_window:
            self.status_label.setText("Error: No target window selected")
            self.log_to_terminal("Error: No target window selected")
            return
        
        # Check if we have actions
        if not self.action_sequence:
            self.status_label.setText("Error: No actions defined")
            self.log_to_terminal("Error: No actions defined")
            return
        
        # Create a thread to run the sequence
        self.log_to_terminal("Starting test sequence...")
        test_thread = threading.Thread(target=self.execute_action_sequence)
        test_thread.daemon = True
        test_thread.start()
        
        self.status_label.setText("Testing action sequence...")

    def update_frames(self):
        """Update all frames with the current state using enhanced detection"""
        # Check if we're shutting down
        if self.is_shutting_down:
            return
            
        if self.current_frame is None or self.selected_region is None:
            return
            
        try:
            # Update the monitor view
            self.update_monitor_view()
            
            # Check for changes if we have a reference frame
            if self.reference_frame is not None:
                # Get grayscale version of current frame if it's color
                if len(self.current_frame.shape) == 3:
                    current_gray = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2GRAY)
                else:
                    current_gray = self.current_frame
                    
                # Calculate difference between current frame and reference frame
                if current_gray.shape != self.reference_frame.shape:
                    # Resize to match if needed
                    current_gray = cv2.resize(current_gray, (self.reference_frame.shape[1], self.reference_frame.shape[0]))
                    
                diff_frame, change_percentage = self.calculate_frame_difference(current_gray, self.reference_frame)
                self.diff_frame = diff_frame
                
                # Add to history (keep only the last 30 values)
                self.change_history.append(change_percentage)
                if len(self.change_history) > 30:
                    self.change_history.pop(0)
                
                # Update status with change percentage - check if status_label still exists
                if hasattr(self, 'status_label'):
                    avg_change = sum(self.change_history) / len(self.change_history)
                    self.status_label.setText(f"Change: {change_percentage:.2%} (avg: {avg_change:.2%})")
                
                # Check if change exceeds threshold and cooldown period has passed
                current_time = time.time()
                threshold = self.threshold_input.value() if hasattr(self, 'threshold_input') else self.detection_threshold
                
                # Enhanced detection: require sustained change above threshold
                # Check if most recent measurements are consistently above threshold
                recent_measurements = self.change_history[-3:] if len(self.change_history) >= 3 else self.change_history
                sustained_change = all(m > threshold * 0.8 for m in recent_measurements)
                
                if (change_percentage > threshold and 
                    sustained_change and
                    current_time - self.last_detection_time > self.detection_cooldown):
                    self.last_detection_time = current_time
                    self.log_to_terminal(f"Change detected: {change_percentage:.2%}")
                    
                    # Execute action sequence if monitoring is active
                    if self.is_monitoring and (not hasattr(self, 'is_paused') or not self.is_paused):
                        # Execute in a separate thread to avoid blocking the UI
                        action_thread = threading.Thread(target=self.execute_action_sequence)
                        action_thread.daemon = True
                        action_thread.start()
        except Exception as e:
            if not self.is_shutting_down:
                print(f"Error in update_frames: {e}")

    def focus_window(self, window):
        """Focus the target window using enhanced methods"""
        try:
            if window:
                self.log_to_terminal(f"Focusing window: {window.title}")
                
                # Get window handle
                try:
                    hwnd = win32gui.FindWindow(None, window.title)
                    if hwnd:
                        self.log_to_terminal(f"Found window handle: {hwnd}")
                        # Use the enhanced focus method
                        if force_focus_window(hwnd):
                            self.log_to_terminal("Window focused successfully")
                            time.sleep(0.2)  # Give time for window to activate
                            return True
                        else:
                            # Fall back to pygetwindow method
                            if window.isMinimized:
                                window.restore()
                            window.activate()
                            time.sleep(0.3)
                            return True
                    else:
                        self.log_to_terminal(f"Could not find window handle for: {window.title}")
                except Exception as e:
                    self.log_to_terminal(f"Error using win32gui to focus: {str(e)}")
                    
                    # Fall back to pygetwindow
                    if window.isMinimized:
                        window.restore()
                    window.activate()
                    time.sleep(0.3)
                    return True
        except Exception as e:
            self.log_to_terminal(f"Error focusing window: {str(e)}")
            return False
        return False

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
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Type combobox
        type_combo = QComboBox()
        type_combo.addItems(["key", "focus", "wait", "click", "esc", "f"])
        type_combo.setCurrentText(action_data.get("type", "key"))
        type_combo.setMaximumWidth(60)
        type_combo.setMaximumHeight(20)
        
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
        value_input.setMaximumHeight(20)
        
        # Comment input
        comment_input = QLineEdit()
        comment_input.setText(action_data.get("comment", ""))
        comment_input.setPlaceholderText("Comment")
        comment_input.setMaximumHeight(20)
        
        # Delete button
        delete_button = QPushButton("×")
        delete_button.setMaximumWidth(20)
        delete_button.setMaximumHeight(20)
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
        layout.addWidget(value_input, 1)
        layout.addWidget(comment_input, 1)
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