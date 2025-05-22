import sys
import time
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QSlider, QFrame, QSplitter, QTextEdit,
    QGroupBox, QMessageBox, QDialog, QDialogButtonBox, QCheckBox,
    QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from src.models.detector import PixelChangeDetector
from src.ui.components.monitoring_display import MonitoringDisplay
from src.ui.components.timeline_plot import TimelinePlot
from src.ui.components.region_selection import RegionSelectionOverlay

class PixelChangeApp(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pixel Change Detector")
        self.setMinimumSize(800, 550)  # More compact minimum size
        
        # Initialize detector
        self.detector = PixelChangeDetector()
        self.detector.log_signal.connect(self.add_log)
        self.detector.frame_updated.connect(self.update_visualization)
        self.detector.detection_signal.connect(self.handle_detection)
        
        # Define color scheme first
        self._define_colors()
        
        # Create UI
        self._init_ui()
        
        # Detection counter
        self.detection_count = 0
        
    def _define_colors(self):
        """Define the color scheme for the application - Matcha Wood Theme"""
        # Define color scheme - Matcha Wood Theme
        self.colors = {
            # Base colors
            'bg_dark': '#2C3639',      # Deep charcoal for background
            'bg_wood': '#3F4E4F',      # Darker wood tone
            'bg_light': '#A27B5C',     # Light wood accent
            'bg_control': '#A27B5C',   # Wood tone for controls
            
            # Text colors
            'text': '#FFFFFF',         # White text
            'text_dim': '#DCD7C9',     # Soft beige for secondary text
            'text_secondary': '#C8B6A6', # Muted wood tone for tertiary text
            'text_dark': '#2C3639',    # Dark text for light backgrounds
            
            # Accent colors - Matcha and wood tones
            'matcha': '#A0C49D',       # Medium matcha green
            'matcha_light': '#DAE5D0',  # Light matcha
            'matcha_dark': '#7D8F69',   # Dark matcha
            'wood_accent': '#C8B6A6',   # Light wood accent
            
            # Status colors
            'success': '#A0C49D',      # Success - matcha green
            'alert': '#F87474',        # Error - soft red
            'warning': '#F9B572',      # Warning - soft orange
            'border': '#454649',       # Border color
        }
        
    def _init_ui(self):
        """Initialize the user interface - Matcha Wood theme"""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        
        # Set application-wide stylesheet - Matcha Wood theme
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ 
                background-color: {self.colors['bg_dark']}; 
                color: {self.colors['text']}; 
                font-family: Helvetica, Arial, sans-serif;
            }}
            
            QGroupBox {{ 
                background-color: {self.colors['bg_wood']}; 
                color: {self.colors['text_dim']}; 
                border: none;
                border-radius: 10px; 
                margin-top: 1.2em;
                font-weight: 500;
                font-size: 13px;
            }}
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                left: 12px; 
                padding: 0 8px 0 8px;
                color: {self.colors['matcha_light']};
            }}
            
            QLabel {{ 
                color: {self.colors['text']}; 
                font-size: 13px;
                background: transparent;
            }}
            
            QPushButton {{ 
                background-color: {self.colors['bg_wood']}; 
                color: {self.colors['text']}; 
                border: none; 
                padding: 8px 16px; 
                border-radius: 8px;
                font-size: 13px;
                font-weight: 500;
                min-height: 28px;
                margin: 2px;
            }}
            QPushButton:hover {{ 
                background-color: {self.colors['matcha_dark']}; 
            }}
            QPushButton:pressed {{ 
                background-color: {self.colors['matcha']}; 
                color: {self.colors['text_dark']};
            }}
            QPushButton:disabled {{ 
                color: {self.colors['text_secondary']}; 
                background-color: {self.colors['bg_wood']};
                opacity: 0.8;
            }}
            
            QTextEdit {{ 
                background-color: {self.colors['bg_wood']}; 
                color: {self.colors['text']}; 
                border: none; 
                border-radius: 8px;
                font-family: 'Menlo', 'Monaco', monospace;
                font-size: 12px;
                padding: 6px;
                selection-background-color: {self.colors['matcha']};
            }}
            
            QSlider::groove:horizontal {{
                border: none;
                height: 4px;
                background: {self.colors['bg_dark']};
                margin: 0px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {self.colors['matcha']};
                border: none;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {self.colors['matcha_light']};
            }}
            
            QCheckBox {{
                color: {self.colors['text']};
                font-size: 13px;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: none;
                background-color: {self.colors['bg_dark']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors['matcha']};
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNCIgaGVpZ2h0PSIxNCIgdmlld0JveD0iMCAwIDE0IDE0Ij48cGF0aCBmaWxsPSIjRkZGRkZGIiBkPSJNNS43MzMgMTBMMTIgMy43MzMgMTAuMjY3IDIgNS43MzMgNi41MzMgMy43MzMgNC41MzMgMiA2LjI2N3oiLz48L3N2Zz4=);
            }}
        """)
        
        # Create left panel (controls) with macOS spacing
        left_panel = QWidget()
        left_panel.setFixedWidth(280)  # Slightly wider for better readability
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)  # Standard macOS spacing
        main_layout.addWidget(left_panel)
        
        # Create right panel (visualization)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)  # Standard macOS spacing
        main_layout.addWidget(right_panel)
        
        # === LEFT PANEL COMPONENTS ===
        
        # 1. Settings group - macOS style
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        settings_layout.setSpacing(12)
        left_layout.addWidget(settings_group)
        
        # Threshold control
        threshold_layout = QHBoxLayout()
        threshold_layout.setSpacing(10)
        threshold_label = QLabel("Threshold:")
        threshold_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        threshold_layout.addWidget(threshold_label)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(1, 50)  # 0.01 to 0.50
        self.threshold_slider.setValue(5)      # Default 0.05
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_value_label = QLabel("0.05")
        self.threshold_value_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        threshold_layout.addWidget(self.threshold_value_label)
        settings_layout.addLayout(threshold_layout)
        
        # Region size control
        size_layout = QHBoxLayout()
        size_layout.setSpacing(10)
        size_label = QLabel("Region Size:")
        size_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        size_layout.addWidget(size_label)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(20, 200)  # 20 to 200 pixels
        self.size_slider.setValue(50)      # Default 100
        self.size_slider.valueChanged.connect(self.update_size_label)
        size_layout.addWidget(self.size_slider)
        
        self.size_value_label = QLabel("50")
        self.size_value_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        size_layout.addWidget(self.size_value_label)
        settings_layout.addLayout(size_layout)
        
        # Add noise reduction controls
        settings_layout.addSpacing(4)
        
        # Noise reduction settings
        noise_layout = QHBoxLayout()
        noise_layout.setSpacing(10)
        noise_label = QLabel("Noise Reduction:")
        noise_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        noise_layout.addWidget(noise_label)
        
        self.noise_checkbox = QCheckBox("On")
        self.noise_checkbox.setChecked(True)
        self.noise_checkbox.toggled.connect(self.toggle_noise_reduction)
        noise_layout.addWidget(self.noise_checkbox)
        
        settings_layout.addLayout(noise_layout)
        
        # Bright background detection settings
        bright_layout = QHBoxLayout()
        bright_layout.setSpacing(10)
        bright_label = QLabel("Bright Detection:")
        bright_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        bright_layout.addWidget(bright_label)
        
        self.bright_checkbox = QCheckBox("Enhanced")
        self.bright_checkbox.setChecked(True)
        self.bright_checkbox.toggled.connect(self.toggle_bright_detection)
        bright_layout.addWidget(self.bright_checkbox)
        
        settings_layout.addLayout(bright_layout)
        
        # 2. Monitoring group - macOS style
        monitoring_group = QGroupBox("Monitoring")
        monitoring_layout = QVBoxLayout(monitoring_group)
        monitoring_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        monitoring_layout.setSpacing(12)
        left_layout.addWidget(monitoring_group)
        
        # Region selection button
        self.region_button = QPushButton("Select Region")
        self.region_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['matcha_dark']};
                color: {self.colors['text']};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {self.colors['matcha']};
            }}
        """)
        self.region_button.clicked.connect(self.select_region)
        monitoring_layout.addWidget(self.region_button)
        
        # Region info display
        region_info_layout = QHBoxLayout()
        region_info_layout.setSpacing(8)
        status_label = QLabel("Status:")
        status_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        region_info_layout.addWidget(status_label)
        
        self.region_info_label = QLabel("No region selected")
        region_info_layout.addWidget(self.region_info_label)
        monitoring_layout.addLayout(region_info_layout)
        
        # 3. Control group - macOS style
        control_group = QGroupBox("Control")
        control_layout = QVBoxLayout(control_group)
        control_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        control_layout.setSpacing(12)
        left_layout.addWidget(control_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        self.start_button = QPushButton("Start")
        self.start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['matcha']};
                color: {self.colors['text_dark']};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self.colors['matcha_light']};
            }}
        """)
        self.start_button.clicked.connect(self.start_detection)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['alert']};
                color: #FFFFFF;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #FF8A8A;
            }}
        """)
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['warning']};
                color: {self.colors['text_dark']};
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #FFCA85;
            }}
        """)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        button_layout.addWidget(self.pause_button)
        
        control_layout.addLayout(button_layout)
        
        # Second row of buttons
        button_layout2 = QHBoxLayout()
        button_layout2.setSpacing(8)
        
        self.reference_button = QPushButton("Capture Reference")
        self.reference_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_light']};
                color: {self.colors['text']};
            }}
            QPushButton:hover {{
                background-color: {self.colors['wood_accent']};
                color: {self.colors['text_dark']};
            }}
        """)
        self.reference_button.clicked.connect(self.capture_reference)
        button_layout2.addWidget(self.reference_button)
        
        self.clear_button = QPushButton("Clear Logs")
        self.clear_button.clicked.connect(self.clear_logs)
        button_layout2.addWidget(self.clear_button)
        
        control_layout.addLayout(button_layout2)
        
        # 4. Log display - macOS style
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        log_layout.setSpacing(8)
        left_layout.addWidget(log_group, stretch=1)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        
        # === RIGHT PANEL COMPONENTS ===
        
        # 1. Monitoring display with matcha wood theme
        monitor_group = QGroupBox("Live Monitor")
        monitor_layout = QVBoxLayout(monitor_group)
        monitor_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        monitor_layout.setSpacing(8)
        
        self.monitor_display = MonitoringDisplay()
        self.monitor_display.setStyleSheet(f"""
            QLabel {{ 
                background-color: {self.colors['bg_wood']}; 
                border: none; 
                border-radius: 8px;
            }}
        """)
        monitor_layout.addWidget(self.monitor_display)
        right_layout.addWidget(monitor_group, stretch=3)
        
        # 2. Timeline plot in its own group
        timeline_group = QGroupBox("Activity Timeline")
        timeline_layout = QVBoxLayout(timeline_group)
        timeline_layout.setContentsMargins(16, 24, 16, 16)  # macOS padding
        
        self.timeline_plot = TimelinePlot(width=5, height=1.5)
        timeline_layout.addWidget(self.timeline_plot)
        
        right_layout.addWidget(timeline_group, stretch=1)
        
        # 3. Status and count display
        status_frame = QFrame()
        status_frame.setMaximumHeight(28)  # Keep it slim
        status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors['bg_wood']};
                border-radius: 6px;
                padding: 0px;
            }}
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 2, 8, 2)  # Very slim padding
        status_layout.setSpacing(8)
        
        self.status_label = QLabel("Status: Waiting")
        self.status_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.status_label)
        
        self.count_label = QLabel("Detections: 0")
        self.count_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.count_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        right_layout.addWidget(status_frame)
        
        # Add a welcome log message
        self.add_log("Pixel Change Detector initialized")
        self.add_log("macOS Modern UI Theme")
        self.add_log("Click 'Select Region' to begin")
        
        # Set initial state of bright detection in monitor display
        self.monitor_display.set_bright_mode(self.detector.enhanced_bright_detection)
    
    def update_threshold(self):
        """Update threshold value from slider"""
        value = self.threshold_slider.value() / 100.0
        self.threshold_value_label.setText(f"{value:.2f}")
        
        if self.detector:
            self.detector.THRESHOLD = value
            
            # Update the threshold line in the timeline plot
            self.timeline_plot.threshold_line.set_ydata([value, value])
            self.timeline_plot.draw()
    
    def update_size_label(self):
        """Update size value label from slider"""
        value = self.size_slider.value()
        self.size_value_label.setText(str(value))
    
    def select_region(self):
        """Open region selection overlay"""
        # Hide main window to ensure it's not in the screenshot
        self.hide()
        
        # Delay to ensure the main window disappears before capturing screen
        # Longer delay for more reliable fullscreen capture
        time.sleep(0.5)
        
        # Make sure all Qt events are processed before taking the screenshot
        QApplication.processEvents()
        
        # Create and show region selection dialog
        region_size = self.size_slider.value()
        self.selection_dialog = RegionSelectionOverlay(None, region_size)
        self.selection_dialog.region_selected.connect(self.set_region)
        
        # Force the selection dialog to stay on top
        self.selection_dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        
        # Show dialog and make it active - fullscreen
        self.selection_dialog.showFullScreen()
        self.selection_dialog.activateWindow()
        self.selection_dialog.raise_()
        
        result = self.selection_dialog.exec()
        
        if result == QDialog.DialogCode.Rejected:
            self.add_log("Region selection canceled")
            
        # Show main window again
        self.show()
        self.activateWindow()
        self.raise_()
    
    def set_region(self, region):
        """Set the selected region"""
        # Ensure region coordinates are valid integers
        left, top, right, bottom = [int(coord) for coord in region]
        
        # Calculate dimensions for display
        width = right - left
        height = bottom - top
        
        # Validate the region
        if width <= 0 or height <= 0:
            self.add_log(f"Invalid region dimensions: {width}x{height}")
            return
            
        # Set the region in the detector
        self.detector.region = (left, top, right, bottom)
        
        # Share game window info if available
        if hasattr(self.selection_dialog, 'play_together_proc') and self.selection_dialog.play_together_proc:
            self.detector.game_process_name = self.selection_dialog.play_together_proc
            self.add_log(f"Game process identified: {self.detector.game_process_name}")
            
        if hasattr(self.selection_dialog, 'play_together_name') and self.selection_dialog.play_together_name:
            self.detector.game_window_name = self.selection_dialog.play_together_name
            self.add_log(f"Game window identified: {self.detector.game_window_name}")
        
        # Update UI
        self.region_info_label.setText(f"region({left},{top},{width}×{height})")
        self.add_log(f"Region selected: ({left},{top}) {width}×{height}")
        
        # Capture a reference frame if detector is initialized
        if self.detector and not self.detector.is_running:
            self.capture_reference()
            self.add_log("Initial reference frame captured")
    
    def start_detection(self):
        """Start the detection process"""
        if not self.detector.region:
            self.add_log("You must select a region first")
            return
            
        # Update threshold from UI
        self.detector.THRESHOLD = self.threshold_slider.value() / 100.0
        
        # Always clear and recapture the reference frame when starting
        self.detector.reference_frame = None
        self.add_log("Capturing new reference frame...")
        if not self.detector.capture_reference():
            self.add_log("Failed to capture reference frame. Please check region selection.")
            return
        
        # Start detection
        self.detector.start_detection()
        
        # Update UI
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.monitor_display.set_status("running")
        self.status_label.setText("Status: Running")
        self.status_label.setStyleSheet(f"color: {self.colors['matcha']}; font-weight: 500; font-size: 12px;")
    
    def stop_detection(self):
        """Stop the detection process"""
        self.detector.stop_detection()
        
        # Update UI
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.monitor_display.set_status("stopped")
        self.status_label.setText("Status: Stopped")
        self.status_label.setStyleSheet(f"color: {self.colors['alert']}; font-weight: 500; font-size: 12px;")
    
    def toggle_pause(self):
        """Pause or resume detection"""
        self.detector.toggle_pause()
        
        if self.detector.is_paused:
            self.pause_button.setText("Resume")
            self.monitor_display.set_status("paused")
            self.status_label.setText("Status: Paused")
            self.status_label.setStyleSheet(f"color: {self.colors['warning']}; font-weight: 500; font-size: 12px;")
        else:
            self.pause_button.setText("Pause")
            self.monitor_display.set_status("running")
            self.status_label.setText("Status: Running")
            self.status_label.setStyleSheet(f"color: {self.colors['matcha']}; font-weight: 500; font-size: 12px;")
    
    def capture_reference(self):
        """Capture a reference frame"""
        if self.detector.region:
            success = self.detector.capture_reference()
            if success:
                self.add_log("Reference frame captured")
        else:
            self.add_log("You must select a region first")
    
    def add_log(self, message):
        """Add message to log display"""
        self.log_display.append(message)
        # Auto-scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_logs(self):
        """Clear log display"""
        self.log_display.clear()
    
    def handle_detection(self):
        """Handle a detection event"""
        # Increment detection counter
        self.detection_count += 1
        self.count_label.setText(f"Detections: {self.detection_count}")
        
        # Update status to show action sequence
        self.monitor_display.set_status("action_sequence")
        self.status_label.setText("Status: Action Sequence")
        self.status_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        
        # Add a log message
        self.add_log(f"Detection #{self.detection_count} - executing action sequence")
        
        # Note: The actual key presses are handled by the detector's action sequence
        
    def update_visualization(self):
        """Update visualization components"""
        if not self.detector:
            return
            
        try:
            # Get latest data from detector
            current_frame = self.detector.color_frame
            diff_frame = self.detector.diff_frame
            
            # Calculate current change percentage
            current_change = self.detector.change_history[-1] if self.detector.change_history else 0
            
            # Update display components
            self.monitor_display.update_display(current_frame, diff_frame, current_change)
            self.timeline_plot.update_plot(self.detector.change_history, self.detector.THRESHOLD)
            
            # Update status if in action sequence
            if self.detector.in_action_sequence:
                step = self.detector.action_sequence_step
                total_steps = len(self.detector.action_sequence)
                self.status_label.setText(f"Status: Action Sequence ({step}/{total_steps})")
                self.status_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        except Exception as e:
            print(f"Error updating visualization: {e}")
            # Don't stop the application on visualization errors
    
    def toggle_noise_reduction(self, checked):
        """Toggle noise reduction processing"""
        if self.detector:
            self.detector.apply_blur = checked
            self.add_log(f"Noise reduction {'enabled' if checked else 'disabled'}")
    
    def toggle_bright_detection(self, checked):
        """Toggle enhanced bright detection"""
        if self.detector:
            self.detector.enhanced_bright_detection = checked
            self.monitor_display.set_bright_mode(checked)
            self.add_log(f"Enhanced bright detection {'enabled' if checked else 'disabled'}")
            
            # Update visualization to show the indicator immediately
            self.update_visualization() 