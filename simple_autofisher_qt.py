import sys
import numpy as np
import keyboard
import time
import threading
import os
import queue
import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QLineEdit, QCheckBox, QGroupBox,
    QGridLayout, QTextEdit, QFrame, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QPalette
import win32gui
import win32con
import win32process
import win32api
import ctypes
import psutil
from PIL import ImageGrab
import cv2
import mss
import mss.tools

# Import the core functionality from the original file
from autofisher import (
    PixelChangeDetector, force_focus_window, direct_key_press, 
    MOUSEINPUT, KEYBDINPUT, HARDWAREINPUT, INPUT_UNION, INPUT,
    user32, kernel32, VK_F, KEYEVENTF_KEYUP, INPUT_KEYBOARD,
    HWND_TOPMOST, SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW
)

# Application version
VERSION = "1.0"

# Main application class
class SimpleAutoFisherGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"AutoFisher Qt v{VERSION}")
        self.setMinimumSize(700, 500)
        
        # Create message queue for logging
        self.log_queue = queue.Queue()
        
        # Initialize detector
        self.detector = None
        self.is_running = False
        
        # Detection counter
        self.detection_count = 0
        
        # Background mode options
        self.background_mode_var = False
        self.high_performance_var = False
        self.respect_fullscreen_var = True
        
        # Thread control variables
        self.thread_control = {
            "detection_thread": None,
            "running": False,
            "paused": False,
            "stop_requested": False
        }
        
        # Statistics
        self.stats = {
            "session_start_time": time.time(),
            "total_detections": 0,
            "fps": 0
        }
        
        # Set dark theme
        self.apply_dark_theme()
        
        # Create UI elements
        self.create_widgets()
        
        # Setup detector after widgets
        self.detector = PixelChangeDetector(self.log_queue)
        self.detector.gui = self
        
        # Setup periodic updates using QTimer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_logs)
        self.update_timer.start(100)  # Update every 100ms
        
        # Setup statistics update timer
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_statistics)
        self.stats_timer.start(1000)  # Update every second
        
    def apply_dark_theme(self):
        """Apply a dark theme to the application"""
        palette = QPalette()
        
        # Base colors
        bg_color = QColor(30, 30, 30)
        text_color = QColor(220, 220, 220)
        highlight_color = QColor(42, 130, 218)
        dark_accent = QColor(45, 45, 45)
        
        # Set palette colors
        palette.setColor(QPalette.ColorRole.Window, bg_color)
        palette.setColor(QPalette.ColorRole.WindowText, text_color)
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, dark_accent)
        palette.setColor(QPalette.ColorRole.ToolTipBase, bg_color)
        palette.setColor(QPalette.ColorRole.ToolTipText, text_color)
        palette.setColor(QPalette.ColorRole.Text, text_color)
        palette.setColor(QPalette.ColorRole.Button, bg_color)
        palette.setColor(QPalette.ColorRole.ButtonText, text_color)
        palette.setColor(QPalette.ColorRole.Link, highlight_color)
        palette.setColor(QPalette.ColorRole.Highlight, highlight_color)
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
        
        # Apply palette
        QApplication.instance().setPalette(palette)
        
    def create_widgets(self):
        # Main central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout using splitter for adjustable sections
        main_layout = QVBoxLayout(central_widget)
        
        # Create splitter for top and bottom sections
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(self.main_splitter)
        
        # Top container
        top_container = QWidget()
        top_layout = QHBoxLayout(top_container)
        
        # Left panel for settings and controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Right panel for status and visualization (future enhancement)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Add panels to top container
        top_layout.addWidget(left_panel, 1)
        top_layout.addWidget(right_panel, 1)
        
        # Bottom container for logs
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        
        # Add containers to splitter
        self.main_splitter.addWidget(top_container)
        self.main_splitter.addWidget(bottom_container)
        self.main_splitter.setSizes([350, 150])  # Initial size distribution
        
        # Create settings group in left panel
        settings_group = QGroupBox("Settings")
        settings_layout = QGridLayout(settings_group)
        
        # Threshold
        settings_layout.addWidget(QLabel("Threshold:"), 0, 0)
        threshold_layout = QHBoxLayout()
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(1)
        self.threshold_slider.setMaximum(50)
        self.threshold_slider.setValue(5)  # Default value of 0.05
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_label = QLabel("0.05")
        threshold_layout.addWidget(self.threshold_label)
        settings_layout.addLayout(threshold_layout, 0, 1)
        
        # Region Size
        settings_layout.addWidget(QLabel("Region Size:"), 1, 0)
        region_size_layout = QHBoxLayout()
        self.size_entry = QLineEdit("50")
        self.size_entry.setMaximumWidth(60)
        region_size_layout.addWidget(self.size_entry)
        region_size_layout.addWidget(QLabel("px"))
        region_size_layout.addStretch()
        settings_layout.addLayout(region_size_layout, 1, 1)
        
        # Cooldown
        settings_layout.addWidget(QLabel("Cooldown:"), 2, 0)
        cooldown_layout = QHBoxLayout()
        self.cooldown_entry = QLineEdit("5.0")
        self.cooldown_entry.setMaximumWidth(60)
        cooldown_layout.addWidget(self.cooldown_entry)
        cooldown_layout.addWidget(QLabel("sec"))
        cooldown_layout.addStretch()
        settings_layout.addLayout(cooldown_layout, 2, 1)
        
        # Fishing Key
        settings_layout.addWidget(QLabel("Fishing Key:"), 3, 0)
        fishing_key_layout = QHBoxLayout()
        self.fishing_key_entry = QLineEdit("f")
        self.fishing_key_entry.setMaximumWidth(40)
        fishing_key_layout.addWidget(self.fishing_key_entry)
        
        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.clicked.connect(self.apply_settings)
        fishing_key_layout.addWidget(self.apply_button)
        settings_layout.addLayout(fishing_key_layout, 3, 1)
        
        # Background Mode Options
        options_frame = QFrame()
        options_layout = QVBoxLayout(options_frame)
        options_layout.setContentsMargins(0, 10, 0, 0)
        
        # Background Mode
        self.background_checkbox = QCheckBox("Background Mode (don't steal focus)")
        self.background_checkbox.setChecked(self.background_mode_var)
        self.background_checkbox.stateChanged.connect(self.update_background_mode)
        options_layout.addWidget(self.background_checkbox)
        
        # Add description
        bg_desc = QLabel("Background mode sends keys without interrupting your work")
        bg_desc.setStyleSheet("color: gray; font-size: 10px;")
        options_layout.addWidget(bg_desc)
        
        # High Performance Mode
        self.high_performance_checkbox = QCheckBox("High Performance Mode (uses more CPU)")
        self.high_performance_checkbox.setChecked(self.high_performance_var)
        self.high_performance_checkbox.stateChanged.connect(self.update_high_performance)
        options_layout.addWidget(self.high_performance_checkbox)
        
        # Add description
        hp_desc = QLabel("Increases reliability of background mode using more system resources")
        hp_desc.setStyleSheet("color: gray; font-size: 10px;")
        options_layout.addWidget(hp_desc)
        
        # Respect Fullscreen Apps
        self.respect_fullscreen_checkbox = QCheckBox("Respect Fullscreen Apps (prevents interruptions)")
        self.respect_fullscreen_checkbox.setChecked(self.respect_fullscreen_var)
        self.respect_fullscreen_checkbox.stateChanged.connect(self.update_respect_fullscreen)
        options_layout.addWidget(self.respect_fullscreen_checkbox)
        
        # Add description
        fs_desc = QLabel("Prevents any interruption when other fullscreen applications are active")
        fs_desc.setStyleSheet("color: gray; font-size: 10px;")
        options_layout.addWidget(fs_desc)
        
        settings_layout.addWidget(options_frame, 4, 0, 1, 2)
        
        left_layout.addWidget(settings_group)
        
        # Control buttons
        control_group = QGroupBox("Control")
        control_layout = QGridLayout(control_group)
        
        # First row of buttons
        self.region_button = QPushButton("Select Region")
        self.region_button.clicked.connect(self.select_region)
        control_layout.addWidget(self.region_button, 0, 0)
        
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_detection)
        control_layout.addWidget(self.start_button, 0, 1)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button, 0, 2)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        control_layout.addWidget(self.pause_button, 0, 3)
        
        # Second row of buttons
        self.ref_button = QPushButton("Capture Reference")
        self.ref_button.clicked.connect(self.capture_reference)
        control_layout.addWidget(self.ref_button, 1, 0, 1, 2)
        
        self.clear_logs_button = QPushButton("Clear Logs")
        self.clear_logs_button.clicked.connect(self.clear_logs)
        control_layout.addWidget(self.clear_logs_button, 1, 2, 1, 2)
        
        left_layout.addWidget(control_group)
        
        # Status and Statistics in right panel
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("Ready - Select a region to begin")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        # Add a separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        status_layout.addWidget(separator)
        
        # Statistics grid
        stats_frame = QFrame()
        stats_layout = QGridLayout(stats_frame)
        stats_layout.setContentsMargins(0, 5, 0, 0)
        
        # Create statistics labels
        self.stats_labels = {}
        stats_items = [
            ("Detections", "total_detections"),
            ("Session Runtime", "session_runtime"),
            ("Detection Rate", "detections_per_hour"),
            ("Avg. Interval", "avg_interval"),
            ("Processing FPS", "processing_fps"),
            ("Threshold", "current_threshold"),
            ("Cooldown", "cooldown"),
            ("Key Mapping", "key_mapping")
        ]
        
        # Create grid of stats
        for i, (label, key) in enumerate(stats_items):
            row = i // 2
            col = i % 2
            
            # Label widget
            label_widget = QLabel(f"{label}:")
            stats_layout.addWidget(label_widget, row, col*2)
            
            # Value widget
            value_widget = QLabel("...")
            stats_layout.addWidget(value_widget, row, col*2+1)
            self.stats_labels[key] = value_widget
        
        status_layout.addWidget(stats_frame)
        right_layout.addWidget(status_group)
        
        # Region info display
        region_group = QGroupBox("Region Information")
        region_layout = QVBoxLayout(region_group)
        
        self.region_info_label = QLabel("No region selected")
        region_layout.addWidget(self.region_info_label)
        
        right_layout.addWidget(region_group)
        
        # Add spacer to right panel
        right_layout.addStretch()
        
        # Log console in bottom container
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        log_layout.addWidget(self.log_console)
        
        bottom_layout.addWidget(log_group)
        
    def log(self, message):
        """Add timestamped message to log queue"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")
        
    def update_logs(self):
        """Process any new log messages from the queue"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_console.append(message)
                # Ensure the latest log is visible
                self.log_console.verticalScrollBar().setValue(
                    self.log_console.verticalScrollBar().maximum()
                )
        except queue.Empty:
            pass
            
    def clear_logs(self):
        """Clear the log console"""
        self.log_console.clear()
        self.log("Logs cleared")
            
    def update_threshold_label(self, value):
        """Update threshold label"""
        threshold_value = value / 100.0
        self.threshold_label.setText(f"{threshold_value:.2f}")
        
    def update_background_mode(self):
        """Update background mode setting"""
        self.background_mode_var = self.background_checkbox.isChecked()
        if self.detector:
            self.detector.background_mode = self.background_mode_var
            mode = "enabled" if self.detector.background_mode else "disabled"
            self.log(f"Background mode {mode}")
            
    def update_high_performance(self):
        """Update high performance mode setting"""
        self.high_performance_var = self.high_performance_checkbox.isChecked()
        if self.detector:
            self.detector.high_performance_mode = self.high_performance_var
            mode = "enabled" if self.detector.high_performance_mode else "disabled"
            self.log(f"High performance mode {mode}")
            if self.detector.high_performance_mode:
                self.log("Warning: High performance mode may increase CPU usage")
                
    def update_respect_fullscreen(self):
        """Update respect fullscreen setting"""
        self.respect_fullscreen_var = self.respect_fullscreen_checkbox.isChecked()
        if self.detector:
            self.detector.respect_fullscreen = self.respect_fullscreen_var
            mode = "enabled" if self.detector.respect_fullscreen else "disabled"
            self.log(f"Fullscreen respect mode {mode}")
            if self.detector.respect_fullscreen:
                self.log("Fishing won't interrupt fullscreen applications")
            
    def apply_settings(self):
        """Apply the settings to the detector"""
        try:
            # Get the settings from UI
            threshold_value = float(self.threshold_slider.value()) / 100.0
            cooldown_value = float(self.cooldown_entry.text())
            fishing_key = self.fishing_key_entry.text().strip().lower()
            
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
                old_threshold = self.detector.THRESHOLD if hasattr(self.detector, 'THRESHOLD') else 0
                old_cooldown = self.detector.detection_cooldown if hasattr(self.detector, 'detection_cooldown') else 0
                
                self.detector.THRESHOLD = threshold_value
                self.detector.detection_cooldown = cooldown_value
                self.detector.fishing_key = fishing_key
                self.detector.background_mode = self.background_mode_var
                self.detector.high_performance_mode = self.high_performance_var
                self.detector.respect_fullscreen = self.respect_fullscreen_var
                
                background_status = "enabled" if self.detector.background_mode else "disabled"
                high_perf_status = "enabled" if self.detector.high_performance_mode else "disabled"
                fullscreen_status = "enabled" if self.detector.respect_fullscreen else "disabled"
                
                self.log(f"Settings applied: threshold={threshold_value:.2f}, cooldown={cooldown_value}s, key={fishing_key}, background={background_status}, high_perf={high_perf_status}, respect_fullscreen={fullscreen_status}")
                
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
        
    def capture_reference(self):
        """Capture a reference frame for comparison"""
        if not self.detector:
            self.log("Detector not initialized")
            return
            
        if not self.detector.region:
            self.log("Please select a region first")
            return
            
        success = self.detector.capture_reference()
        if success:
            self.log("Reference frame captured successfully")
        else:
            self.log("Failed to capture reference frame")
        
    def select_region(self):
        """Allow the user to select a region of the screen to monitor"""
        try:
            # Get the size from the input field
            size = int(self.size_entry.text())
            if size < 10:
                self.log("Size must be at least 10 pixels")
                return
        except ValueError:
            self.log("Invalid size value. Using default of 50 pixels")
            size = 50
            self.size_entry.setText("50")
        
        self.log("Starting region selection...")
        
        # First find the Play Together window
        if not self.detector:
            self.detector = PixelChangeDetector(self.log_queue)
            self.detector.gui = self
            
        if not self.detector.find_play_together_process():
            self.log("Cannot start region selection: Play Together window not found")
            return
            
        # Minimize our window during selection
        self.showMinimized()
        time.sleep(0.5)  # Give time for window to minimize
        
        # Get window position and size
        try:
            window_rect = win32gui.GetWindowRect(self.detector.play_together_window)
            win_left, win_top, win_right, win_bottom = window_rect
            
            # Get the client area (actual game content area)
            client_rect = win32gui.GetClientRect(self.detector.play_together_window)
            client_left, client_top, client_right, client_bottom = client_rect
            
            # Convert client coordinates to screen coordinates
            client_left, client_top = win32gui.ClientToScreen(self.detector.play_together_window, (client_left, client_top))
            client_right, client_bottom = win32gui.ClientToScreen(self.detector.play_together_window, (client_right, client_bottom))
            
            # Use client area dimensions for game content area
            game_width = client_right - client_left
            game_height = client_bottom - client_top
            
            self.log(f"Game window found: {win_right-win_left}x{win_bottom-win_top} at ({win_left},{win_top})")
            self.log(f"Game content area: {game_width}x{game_height} at ({client_left},{client_top})")
        except Exception as e:
            self.log(f"Error getting window dimensions: {e}")
            self.showNormal()  # Restore window
            return
            
        # Calculate region dimensions based on 1.5:1 ratio
        width = int(size * 1.5)
        height = size
        
        # Center of game window
        center_x = client_left + game_width // 2
        center_y = client_top + game_height // 2
        
        # Calculate region coordinates
        left = center_x - width // 2
        top = center_y - height // 2
        right = left + width
        bottom = top + height
        
        # Ensure region stays within game window bounds
        if left < client_left:
            left = client_left
            right = left + width
        elif right > client_right:
            right = client_right
            left = right - width
            
        if top < client_top:
            top = client_top
            bottom = top + height
        elif bottom > client_bottom:
            bottom = client_bottom
            top = bottom - height
        
        # Store the region in detector
        self.detector.region = (left, top, right, bottom)
        self.log(f"Region selected: ({left},{top}) to ({right},{bottom}), size: {width}×{height}")
        
        # Update region info display
        self.region_info_label.setText(f"Position: ({left},{top}) • Size: {width}×{height}")
        
        # Validate the region and capture reference frame
        if self.detector.validate_region():
            self.detector.capture_reference()
            self.log("Reference frame captured for the selected region")
            self.status_label.setText(f"Region selected: {width}×{height} at ({left},{top})")
        
        # Restore window
        self.showNormal()
    
    def update_statistics(self):
        """Update statistics display"""
        if not self.detector:
            return
            
        # Calculate runtime
        runtime_secs = time.time() - self.stats["session_start_time"]
        hours = int(runtime_secs // 3600)
        mins = int((runtime_secs % 3600) // 60)
        secs = int(runtime_secs % 60)
        runtime_str = f"{hours:02}:{mins:02}:{secs:02}"
        
        # Detection rate
        detections_per_hour = 0
        if runtime_secs > 0:
            detections_per_hour = (self.detection_count / runtime_secs) * 3600
            
        # Average interval
        avg_interval = "N/A"
        if hasattr(self.detector, 'stats') and "avg_detection_interval" in self.detector.stats:
            interval = self.detector.stats["avg_detection_interval"]
            if interval > 0:
                interval_mins = int(interval // 60)
                interval_secs = int(interval % 60)
                avg_interval = f"{interval_mins}m {interval_secs}s"
                
        # FPS
        fps = 0
        if hasattr(self.detector, 'performance') and "avg_processing_time" in self.detector.performance:
            fps = int(1.0 / max(0.01, self.detector.performance["avg_processing_time"]))
            
        # Update stats labels
        stats_data = {
            "total_detections": str(self.detection_count),
            "session_runtime": runtime_str,
            "detections_per_hour": f"{detections_per_hour:.1f}/hr",
            "avg_interval": avg_interval,
            "processing_fps": f"{fps} FPS",
            "current_threshold": f"{self.detector.THRESHOLD:.3f}" if hasattr(self.detector, 'THRESHOLD') else "N/A",
            "cooldown": f"{self.detector.detection_cooldown:.1f}s" if hasattr(self.detector, 'detection_cooldown') else "N/A",
            "key_mapping": self.detector.fishing_key.upper() if hasattr(self.detector, 'fishing_key') else "N/A"
        }
        
        for key, label in self.stats_labels.items():
            if key in stats_data:
                label.setText(stats_data[key])
        
    def start_detection(self):
        """Start the detection process"""
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
            self.apply_settings()
            
            # Reset thread control variables
            self.thread_control = {
                "detection_thread": None,
                "running": True,
                "paused": False,
                "stop_requested": False
            }
            
            # Reset statistics
            self.stats["session_start_time"] = time.time()
            self.detection_count = 0
            
            self.log(f"Starting detection with threshold: {self.detector.THRESHOLD:.2f}")
            
            # Start the detector
            self.is_running = True
            self.detector.start_detection(self.thread_control)
            
            # Store the thread reference
            self.thread_control["detection_thread"] = self.detector.detection_thread
            
            # Update UI
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            self.status_label.setText("Running - Monitoring for changes")
            self.status_label.setStyleSheet("font-weight: bold; color: #77DD77;")  # Green color
            
        except Exception as e:
            self.log(f"Error starting detection: {str(e)}")
            
    def stop_detection(self):
        """Stop the detection process"""
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
            
        # Stop the detector
        if self.detector:
            self.detector.stop_detection()
            
        self.log("Detection stopped")
        
        # Reset UI
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("Pause")
        self.status_label.setText("Stopped")
        self.status_label.setStyleSheet("font-weight: bold; color: #FF6961;")  # Red color
        
    def toggle_pause(self):
        """Pause or resume the detection thread"""
        if not self.is_running:
            return
            
        if self.thread_control["paused"]:
            # Resume detection
            self.thread_control["paused"] = False
            self.pause_button.setText("Pause")
            self.status_label.setText("Running - Monitoring for changes")
            self.status_label.setStyleSheet("font-weight: bold; color: #77DD77;")  # Green color
            self.log("Detection resumed")
        else:
            # Pause detection
            self.thread_control["paused"] = True
            self.pause_button.setText("Resume")
            self.status_label.setText("Paused")
            self.status_label.setStyleSheet("font-weight: bold; color: #FFB347;")  # Orange color
            self.log("Detection paused")
            
    def increment_detection_count(self):
        """Increment detection counter and update UI"""
        self.detection_count += 1
        # Statistics will be updated on the next timer tick

# Main function
def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show the main window
    main_window = SimpleAutoFisherGUI()
    main_window.show()
    
    # Get primary monitor dimensions to center the window
    screen = app.primaryScreen().geometry()
    screen_width, screen_height = screen.width(), screen.height()
    
    # Set window size based on monitor resolution
    window_width = min(int(screen_width * 0.5), 800)
    window_height = min(int(screen_height * 0.6), 600)
    
    # Center window on primary monitor
    center_x = int(screen_width/2 - window_width/2)
    center_y = int(screen_height/2 - window_height/2)
    
    main_window.resize(window_width, window_height)
    main_window.move(center_x, center_y)
    
    # Log monitor information
    with mss.mss() as sct:
        monitors = sct.monitors
        main_window.log(f"Detected {len(monitors)-1} physical monitors")
        main_window.log(f"Primary monitor: {screen_width}x{screen_height}")
    
    # Add welcome message
    main_window.log(f"AutoFisher Qt v{VERSION} initialized")
    main_window.log("System ready - Please select a region to begin")
    main_window.log("To get started: (1) Select region size (2) Click select-region (3) Click start")
    
    # Start the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 