"""
Main application window for AutoFisher Qt
"""
import time
import queue
import datetime
import threading
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QGridLayout, QLineEdit, QCheckBox, QTextEdit, 
    QFrame, QSplitter, QGroupBox, QSlider
)
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint
from PyQt6.QtGui import QColor

from core import PixelChangeDetector, FishingActionSequence
from ui.visualization import MatplotlibCanvas
from ui.selection import RegionSelectionOverlay
from utils.constants import (
    VERSION, VERSION_NAME, 
    DEFAULT_THRESHOLD, DEFAULT_DETECTION_COOLDOWN, DEFAULT_FISHING_KEY,
    DEFAULT_HIGH_PERFORMANCE, DEFAULT_RESPECT_FULLSCREEN, DEFAULT_DIRECT_CONTROL,
    UI_DARK_BG, UI_LIGHT_TEXT, UI_ACCENT_COLOR, UI_WARNING_COLOR
)

class AutoFisherMainWindow(QMainWindow):
    """Main window for the AutoFisher Qt application"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"AutoFisher Qt v{VERSION} - {VERSION_NAME}")
        self.setMinimumSize(700, 500)
        
        # Create message queue for logging
        self.log_queue = queue.Queue()
        
        # Create detector first so it's available for region selection
        self.detector = PixelChangeDetector(self)
        
        # Initialize UI
        self.init_ui()
        
        # Set up timers and other state variables
        self.detection_running = False
        self.last_detection_time = 0
        
        # Stats tracking
        self.total_detections = 0
        self.start_time = time.time()
        
        # Configure the visualization update timer
        self.vis_timer = QTimer()
        self.vis_timer.setInterval(100)  # 10 FPS for visualization updates
        self.vis_timer.timeout.connect(self.update_visualization)
        
        # Configure logs update timer
        self.log_timer = QTimer()
        self.log_timer.setInterval(100)  # 10 times per second
        self.log_timer.timeout.connect(self.update_logs)
        self.log_timer.start()  # Start the log timer immediately
        
        # Configure stats update timer
        self.stats_timer = QTimer()
        self.stats_timer.setInterval(1000)  # Update stats every second
        self.stats_timer.timeout.connect(self.update_statistics)
        self.stats_timer.start()
        
        # Start with select region and start buttons only
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        
        # Status message
        self.log("AutoFisher Qt initialized")
        self.log("Select a region to begin")
    
    def init_ui(self):
        """Initialize the user interface"""
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
        left_panel.setMaximumWidth(350)  # Limit width of left panel
        
        # Right panel for status and visualization
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Add panels to top container
        top_layout.addWidget(left_panel, 1)
        top_layout.addWidget(right_panel, 2)  # Give more space to right panel
        
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
        self.threshold_slider.setValue(int(DEFAULT_THRESHOLD * 100))  # Default value
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_label = QLabel(f"{DEFAULT_THRESHOLD:.2f}")
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
        self.cooldown_entry = QLineEdit(str(DEFAULT_DETECTION_COOLDOWN))
        self.cooldown_entry.setMaximumWidth(60)
        cooldown_layout.addWidget(self.cooldown_entry)
        cooldown_layout.addWidget(QLabel("sec"))
        cooldown_layout.addStretch()
        settings_layout.addLayout(cooldown_layout, 2, 1)
        
        # Fishing Key
        settings_layout.addWidget(QLabel("Fishing Key:"), 3, 0)
        fishing_key_layout = QHBoxLayout()
        self.fishing_key_entry = QLineEdit(DEFAULT_FISHING_KEY)
        self.fishing_key_entry.setMaximumWidth(40)
        fishing_key_layout.addWidget(self.fishing_key_entry)
        
        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.clicked.connect(self.apply_settings)
        fishing_key_layout.addWidget(self.apply_button)
        settings_layout.addLayout(fishing_key_layout, 3, 1)
        
        # Advanced Options
        options_frame = QFrame()
        options_layout = QVBoxLayout(options_frame)
        options_layout.setContentsMargins(0, 10, 0, 0)
        
        # High Performance Mode
        self.high_performance_checkbox = QCheckBox("High Performance Mode (uses more CPU)")
        self.high_performance_checkbox.setChecked(DEFAULT_HIGH_PERFORMANCE)
        self.high_performance_checkbox.stateChanged.connect(self.update_high_performance)
        options_layout.addWidget(self.high_performance_checkbox)
        
        # Add description
        hp_desc = QLabel("Increases reliability using more system resources")
        hp_desc.setStyleSheet("color: gray; font-size: 10px;")
        options_layout.addWidget(hp_desc)
        
        # Respect Fullscreen Apps
        self.respect_fullscreen_checkbox = QCheckBox("Respect Fullscreen Apps (prevents interruptions)")
        self.respect_fullscreen_checkbox.setChecked(DEFAULT_RESPECT_FULLSCREEN)
        self.respect_fullscreen_checkbox.stateChanged.connect(self.update_respect_fullscreen)
        options_layout.addWidget(self.respect_fullscreen_checkbox)
        
        # Add description
        fs_desc = QLabel("Prevents interruption when other fullscreen applications are active")
        fs_desc.setStyleSheet("color: gray; font-size: 10px;")
        options_layout.addWidget(fs_desc)
        
        # Direct Control Mode
        self.direct_control_checkbox = QCheckBox("Direct Control Mode (recommended)")
        self.direct_control_checkbox.setChecked(DEFAULT_DIRECT_CONTROL)
        self.direct_control_checkbox.stateChanged.connect(self.update_direct_control)
        options_layout.addWidget(self.direct_control_checkbox)
        
        # Add description
        dc_desc = QLabel("Uses direct input methods for maximum reliability")
        dc_desc.setStyleSheet("color: gray; font-size: 10px;")
        options_layout.addWidget(dc_desc)
        
        settings_layout.addWidget(options_frame, 4, 0, 1, 2)
        
        left_layout.addWidget(settings_group)
        
        # Control buttons
        control_group = QGroupBox("Control")
        control_layout = QGridLayout(control_group)
        
        # Region selection button
        self.region_button = QPushButton("Select Region")
        self.region_button.clicked.connect(self.select_region)
        control_layout.addWidget(self.region_button, 0, 0)
        
        # Start button
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_detection)
        control_layout.addWidget(self.start_button, 1, 0)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_detection)
        control_layout.addWidget(self.stop_button, 1, 1)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        control_layout.addWidget(self.pause_button, 2, 0)
        
        self.capture_ref_button = QPushButton("Capture Reference")
        self.capture_ref_button.clicked.connect(self.capture_reference)
        control_layout.addWidget(self.capture_ref_button, 2, 1)
        
        left_layout.addWidget(control_group)
        
        # Stats
        stats_group = QGroupBox("Statistics")
        stats_layout = QGridLayout(stats_group)
        
        stats_layout.addWidget(QLabel("Detections:"), 0, 0)
        self.detections_label = QLabel("0")
        stats_layout.addWidget(self.detections_label, 0, 1)
        
        stats_layout.addWidget(QLabel("Runtime:"), 1, 0)
        self.runtime_label = QLabel("00:00:00")
        stats_layout.addWidget(self.runtime_label, 1, 1)
        
        stats_layout.addWidget(QLabel("Detection Rate:"), 2, 0)
        self.rate_label = QLabel("0.0/min")
        stats_layout.addWidget(self.rate_label, 2, 1)
        
        stats_layout.addWidget(QLabel("Status:"), 3, 0)
        self.status_label = QLabel("Idle")
        stats_layout.addWidget(self.status_label, 3, 1)
        
        left_layout.addWidget(stats_group)
        
        # Region info
        region_group = QGroupBox("Region Information")
        region_layout = QVBoxLayout(region_group)
        
        self.region_info_label = QLabel("No region selected")
        region_layout.addWidget(self.region_info_label)
        
        left_layout.addWidget(region_group)
        
        # Add spacer to left panel
        left_layout.addStretch()
        
        # Add visualization panel to right panel
        viz_group = QGroupBox("Monitoring")
        viz_layout = QVBoxLayout(viz_group)
        
        # Create a frame to contain the canvas with fixed aspect ratio
        viz_frame = QFrame()
        viz_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        viz_frame.setLineWidth(1)
        viz_frame.setStyleSheet(f"background-color: {UI_DARK_BG}; border: 1px solid #444;")
        
        # Use a layout that maintains the aspect ratio
        viz_frame_layout = QVBoxLayout(viz_frame)
        viz_frame_layout.setContentsMargins(4, 4, 4, 4)
        
        # Create matplotlib canvas for visualization with the correct aspect ratio (1.5:1)
        self.viz_canvas = MatplotlibCanvas(self, width=6, height=4, dpi=100, bg_color=UI_DARK_BG)
        
        # Add the canvas to the frame
        viz_frame_layout.addWidget(self.viz_canvas)
        
        # Add the frame to the main viz layout
        viz_layout.addWidget(viz_frame)
        
        # Add monitoring status indicators
        status_panel = QFrame()
        status_layout = QHBoxLayout(status_panel)
        status_layout.setContentsMargins(0, 4, 0, 0)
        
        # Add threshold indicator
        threshold_label = QLabel("Threshold:")
        threshold_label.setStyleSheet("color: #AAA; font-size: 9pt;")
        status_layout.addWidget(threshold_label)
        
        self.monitor_threshold = QLabel("0.05")
        self.monitor_threshold.setStyleSheet(f"color: {UI_WARNING_COLOR}; font-weight: bold; font-size: 9pt;")
        status_layout.addWidget(self.monitor_threshold)
        
        status_layout.addStretch()
        
        # Add FPS indicator
        fps_label = QLabel("FPS:")
        fps_label.setStyleSheet("color: #AAA; font-size: 9pt;")
        status_layout.addWidget(fps_label)
        
        self.monitor_fps = QLabel("0")
        self.monitor_fps.setStyleSheet(f"color: {UI_ACCENT_COLOR}; font-weight: bold; font-size: 9pt;")
        status_layout.addWidget(self.monitor_fps)
        
        # Add the status panel to the viz layout
        viz_layout.addWidget(status_panel)
        
        right_layout.addWidget(viz_group)
        
        # Log console in bottom container
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        
        # Create log console with improved styling
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {UI_DARK_BG};
                color: {UI_LIGHT_TEXT};
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10pt;
                border: 1px solid #333333;
                border-radius: 3px;
                padding: 5px;
            }}
        """)
        log_layout.addWidget(self.log_console)
        
        # Add log control panel with clear button
        log_control_panel = QFrame()
        log_control_layout = QHBoxLayout(log_control_panel)
        log_control_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add spacer to push button to the right
        log_control_layout.addStretch()
        
        # Add clear button
        clear_log_button = QPushButton("Clear Logs")
        clear_log_button.setMaximumWidth(100)
        clear_log_button.clicked.connect(self.clear_logs)
        log_control_layout.addWidget(clear_log_button)
        
        # Add control panel to log layout
        log_layout.addWidget(log_control_panel)
        
        bottom_layout.addWidget(log_group)
        
    def log(self, message):
        """Add timestamped message to log queue"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")
        
    def update_logs(self):
        """Process any new log messages from the queue"""
        try:
            # Check if we need to autoscroll (scroll was at the bottom)
            scroll_bar = self.log_console.verticalScrollBar()
            autoscroll = scroll_bar.value() == scroll_bar.maximum()
            
            # Process messages from queue
            messages = []
            while not self.log_queue.empty():
                try:
                    messages.append(self.log_queue.get_nowait())
                except queue.Empty:
                    break
                    
            # If we have messages, add them to log console
            if messages:
                for message in messages:
                    self.log_console.append(message)
                
                # Autoscroll only if we were already at the bottom
                if autoscroll:
                    self.log_console.verticalScrollBar().setValue(
                        self.log_console.verticalScrollBar().maximum()
                    )
        except Exception as e:
            # Emergency logging if the normal logging system fails
            print(f"Error updating logs: {e}")
            
    def clear_logs(self):
        """Clear the log console"""
        self.log_console.clear()
        self.log("Logs cleared")
            
    def update_threshold_label(self, value):
        """Update threshold label when slider is moved"""
        threshold_value = value / 100.0
        self.threshold_label.setText(f"{threshold_value:.2f}")
            
    def update_high_performance(self):
        """Update high performance mode setting"""
        if self.detector:
            self.detector.high_performance_mode = self.high_performance_checkbox.isChecked()
            mode = "enabled" if self.detector.high_performance_mode else "disabled"
            self.log(f"High performance mode {mode}")
            
    def update_respect_fullscreen(self):
        """Update respect fullscreen setting"""
        if self.detector:
            self.detector.respect_fullscreen = self.respect_fullscreen_checkbox.isChecked()
            mode = "enabled" if self.detector.respect_fullscreen else "disabled"
            self.log(f"Fullscreen respect mode {mode}")
            
    def update_direct_control(self):
        """Update direct control mode setting"""
        if self.detector:
            self.detector.direct_control = self.direct_control_checkbox.isChecked()
            mode = "enabled" if self.detector.direct_control else "disabled"
            self.log(f"Direct control mode {mode}")
                
    def apply_settings(self):
        """Apply settings to the detector"""
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
                old_threshold = self.detector.THRESHOLD
                old_cooldown = self.detector.detection_cooldown
                
                self.detector.THRESHOLD = threshold_value
                self.detector.detection_cooldown = cooldown_value
                self.detector.fishing_key = fishing_key
                self.detector.high_performance_mode = self.high_performance_checkbox.isChecked()
                self.detector.respect_fullscreen = self.respect_fullscreen_checkbox.isChecked()
                self.detector.direct_control = self.direct_control_checkbox.isChecked()
                
                high_perf_status = "enabled" if self.detector.high_performance_mode else "disabled"
                fullscreen_status = "enabled" if self.detector.respect_fullscreen else "disabled"
                direct_control_status = "enabled" if self.detector.direct_control else "disabled"
                
                self.log(f"Settings applied: threshold={threshold_value:.2f}, cooldown={cooldown_value}s, key={fishing_key}")
                
                # Log changes
                if old_threshold != threshold_value:
                    self.log(f"Threshold changed: {old_threshold:.2f} -> {threshold_value:.2f}")
                    
                if old_cooldown != cooldown_value:
                    self.log(f"Cooldown changed: {old_cooldown}s -> {cooldown_value}s")
                
                # Update monitor threshold display
                self.monitor_threshold.setText(f"{threshold_value:.2f}")
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
        """Allow user to select a region of the screen to monitor"""
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
            self.detector = PixelChangeDetector(self)
            
        # Find the window
        if not self.detector.find_play_together_process():
            self.log("Cannot start region selection: Play Together window not found")
            return False
            
        try:
            # Create the selection overlay
            # Use a generic full-screen approach
            selection_overlay = RegionSelectionOverlay(None)
            
            # Connect to signals
            selection_overlay.region_selected.connect(self.on_region_selected)
            selection_overlay.selection_canceled.connect(lambda: self.log("Selection canceled"))
            
            # Show the overlay
            selection_overlay.showFullScreen()
            
            return True
            
        except Exception as e:
            self.log(f"Error starting region selection: {e}")
            return False
            
    def on_region_selected(self, region):
        """Handle when a region is selected"""
        left, top, right, bottom = region
        width = right - left
        height = bottom - top
        
        # Update the detector with new region
        self.detector.region = region
        
        # Update region info display
        self.region_info_label.setText(f"Selected: {left},{top} to {right},{bottom} ({width}×{height} px)")
        
        # Try to validate region
        if self.detector.validate_region():
            # Capture initial reference frame
            self.detector.capture_reference()
            
            # Enable start button now that we have a valid region
            self.start_button.setEnabled(True)
            self.capture_ref_button.setEnabled(True)
            
            self.log(f"Region selection completed at: {left},{top} to {right},{bottom}")
            return True
        else:
            self.log("Failed to validate selected region")
            return False
            
    def update_statistics(self):
        """Update statistics display"""
        if self.detection_running:
            # Update runtime
            runtime_seconds = int(time.time() - self.start_time)
            hours, remainder = divmod(runtime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            runtime_text = f"{hours:02}:{minutes:02}:{seconds:02}"
            self.runtime_label.setText(runtime_text)
            
            # Calculate detections per minute
            if runtime_seconds > 0:
                detections_per_minute = (self.total_detections / runtime_seconds) * 60
                self.rate_label.setText(f"{detections_per_minute:.1f}/min")
        
        # Update detections count
        if self.detector:
            self.detections_label.setText(str(self.detector.stats["total_detections"]))
            
            # Update FPS in monitor
            self.monitor_fps.setText(str(self.detector.performance.get("fps", 0)))
            
    def start_detection(self):
        """Start the detection process"""
        if not self.detector:
            self.log("Detector not initialized")
            return
            
        if not self.detector.region:
            self.log("Please select a region first")
            return
            
        # Apply current settings
        self.apply_settings()
        
        # Start detection
        if self.detector.start_detection():
            self.log("Detection started")
            self.detection_running = True
            self.start_time = time.time()
            self.total_detections = 0
            
            # Update UI state
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            self.status_label.setText("Running - Monitoring for changes")
            
            # Start visualization timer
            self.vis_timer.start()
            
    def stop_detection(self):
        """Stop the detection process"""
        if self.detector:
            self.detector.stop_detection()
            
        self.detection_running = False
        
        # Update UI state
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("Pause")
        self.status_label.setText("Stopped")
        
        # Stop visualization timer
        self.vis_timer.stop()
        
        self.log("Detection stopped")
        
    def toggle_pause(self):
        """Toggle pause state"""
        if not self.detector:
            return
            
        if self.detector.paused:
            self.detector.paused = False
            self.pause_button.setText("Pause")
            self.status_label.setText("Running - Monitoring for changes")
            self.log("Detection resumed")
        else:
            self.detector.paused = True
            self.pause_button.setText("Resume")
            self.status_label.setText("Paused")
            self.log("Detection paused")
            
    def update_visualization(self):
        """Update the visualization display"""
        if not self.detector:
            return
            
        # Update the image display if we have frames
        if hasattr(self.detector, 'color_frame') and self.detector.color_frame is not None:
            self.viz_canvas.update_image(self.detector.color_frame, self.detector.diff_frame)
            
        # Update the timeline
        if hasattr(self.detector, 'change_history') and self.detector.change_history:
            self.viz_canvas.update_timeline(self.detector.change_history, self.detector.THRESHOLD)
            
    def increment_detection_count(self):
        """Increment detection count when signal is received"""
        self.total_detections += 1
        
        # Update UI immediately
        self.detections_label.setText(str(self.total_detections))
        
        # Log the detection
        self.log(f"Detection #{self.total_detections} triggered!") 