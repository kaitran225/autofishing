import sys
import time
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QSlider, QFrame, QSplitter, QTextEdit,
    QGroupBox, QMessageBox, QDialog, QDialogButtonBox, QCheckBox,
    QApplication, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

from src.models.detector import PixelChangeDetector
from src.ui.components.monitoring_display import MonitoringDisplay
from src.ui.components.timeline_plot import TimelinePlot
from src.ui.components.region_selection import RegionSelectionOverlay
from src.utils.permissions import show_permissions_help, check_screen_recording_permission

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
        
        # Add new properties for toggleable features
        self.detector.enable_repair_detection = True    # Toggle for repair dialog detection
        self.detector.enable_action_sequence = True     # Toggle for action sequence execution
        
        # Define color scheme first
        self._define_colors()
        
        # Create UI
        self._init_ui()
        
        # Detection counter
        self.detection_count = 0
        
        # Add properties for right panel collapse/expand
        self.right_panel_collapsed = False
        self.original_sizes = [320, 440]  # Default sizes for left and right panels
        
    def _define_colors(self):
        """Define the color scheme for the application - Modern Clean Theme"""
        # Define color scheme - Modern Clean Theme
        self.colors = {
            # Base colors - Subtle dark theme
            'bg_dark': '#1E1E2E',      # Deep blue-gray for background
            'bg_panel': '#2A2A3C',     # Slightly lighter panel bg
            'bg_card': '#313244',      # Card/control backgrounds
            'bg_accent': '#45475A',    # Accent backgrounds
            
            # Text colors
            'text': '#CDD6F4',         # Main text - light lavender
            'text_dim': '#A6ADC8',     # Secondary text
            'text_muted': '#7F849C',   # Muted text
            'text_dark': '#181825',    # Dark text for light backgrounds
            
            # Accent colors
            'primary': '#89B4FA',      # Light blue primary
            'primary_light': '#B4BEFE', # Light blue highlight
            'primary_dark': '#74C7EC',  # Darker blue
            'secondary': '#CBA6F7',    # Purple secondary
            'highlight': '#F5E0DC',    # Peach highlight
            
            # Status colors
            'success': '#A6E3A1',      # Success - light green
            'alert': '#F38BA8',        # Error - soft red 
            'warning': '#FAB387',      # Warning - soft orange
            'border': '#313244',       # Border color
        }
        
    def _init_ui(self):
        """Initialize the user interface - Modern Clean theme"""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)
        
        # Set application-wide stylesheet - Modern Clean theme, using system fonts
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ 
                background-color: {self.colors['bg_dark']}; 
                color: {self.colors['text']}; 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                font-size: 13px;
            }}
            
            QGroupBox {{ 
                background-color: {self.colors['bg_panel']}; 
                color: {self.colors['text_dim']}; 
                border: none;
                border-radius: 10px; 
                margin-top: 1.5em;
                font-weight: 500;
                font-size: 13px;
            }}
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                left: 12px; 
                padding: 0 8px 0 8px;
                color: {self.colors['secondary']};
            }}
            
            QLabel {{ 
                color: {self.colors['text']}; 
                font-size: 13px;
                background: transparent;
            }}
            
            QPushButton {{ 
                background-color: {self.colors['bg_card']}; 
                color: {self.colors['text']}; 
                border: none; 
                border-radius: 8px;
                padding: 8px 16px; 
                font-size: 13px;
                font-weight: 500;
                min-height: 32px;
                margin: 2px;
            }}
            QPushButton:hover {{ 
                background-color: {self.colors['primary_dark']}; 
                color: {self.colors['text_dark']};
            }}
            QPushButton:pressed {{ 
                background-color: {self.colors['primary']}; 
                color: {self.colors['text_dark']};
            }}
            QPushButton:disabled {{ 
                color: {self.colors['text_muted']}; 
                background-color: {self.colors['bg_card']};
                opacity: 0.6;
            }}
            
            QTextEdit {{ 
                background-color: {self.colors['bg_card']}; 
                color: {self.colors['text']}; 
                border: none; 
                border-radius: 8px;
                font-family: Menlo, Monaco, 'Courier New', monospace;
                font-size: 12px;
                padding: 8px;
                selection-background-color: {self.colors['primary']};
                selection-color: {self.colors['text_dark']};
            }}
            
            QSlider::groove:horizontal {{
                border: none;
                height: 6px;
                background: {self.colors['bg_accent']};
                margin: 2px 0;
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {self.colors['primary']};
                border: none;
                width: 18px;
                height: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {self.colors['primary_light']};
            }}
            
            QCheckBox {{
                color: {self.colors['text']};
                font-size: 13px;
                spacing: 8px;
                min-height: 24px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 5px;
                border: none;
                background-color: {self.colors['bg_accent']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors['primary']};
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNCIgaGVpZ2h0PSIxNCIgdmlld0JveD0iMCAwIDE0IDE0Ij48cGF0aCBmaWxsPSIjRkZGRkZGIiBkPSJNNS43MzMgMTBMMTIgMy43MzMgMTAuMjY3IDIgNS43MzMgNi41MzMgMy43MzMgNC41MzMgMiA2LjI2N3oiLz48L3N2Zz4=);
            }}
            QCheckBox::indicator:hover {{
                background-color: {self.colors['primary_dark']};
            }}
        """)
        
        # Create a container that will resize with window
        self.container = QWidget()
        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        main_layout.addWidget(self.container)
        
        # Create a splitter for the main panels
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False) # Prevent panels from being collapsed to zero size
        container_layout.addWidget(self.main_splitter)
        
        # Create left panel (controls)
        self.left_panel = QWidget()
        self.left_panel.setMinimumWidth(320)  # Slightly wider for better readability
        self.left_panel.setMaximumWidth(380)  # Limit maximum width
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 12, 0)
        left_layout.setSpacing(12)
        self.main_splitter.addWidget(self.left_panel)
        
        # Create right panel (visualization)
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(12, 0, 0, 0)
        right_layout.setSpacing(12)
        self.main_splitter.addWidget(self.right_panel)
        
        # Create a persistent button frame that stays visible when right panel is collapsed
        self.persistent_button_frame = QFrame()
        self.persistent_button_frame.setFixedWidth(40)
        self.persistent_button_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors['bg_dark']};
                border: none;
                padding: 0px;
            }}
        """)
        persistent_layout = QVBoxLayout(self.persistent_button_frame)
        persistent_layout.setContentsMargins(0, 0, 0, 0)
        persistent_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # Create expand button for collapsed state
        self.expand_button = QPushButton("▶")
        self.expand_button.setFixedSize(40, 80)
        self.expand_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['primary_dark']};
                color: {self.colors['text_dark']};
                border-radius: 0px 6px 6px 0px;
                padding: 2px;
                font-size: 14px;
                font-weight: bold;
                margin: 0px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['primary']};
            }}
        """)
        self.expand_button.clicked.connect(self.expand_right_panel)
        persistent_layout.addWidget(self.expand_button)
        persistent_layout.addStretch()
        
        # Initially hide the expand button
        self.expand_button.hide()
        
        # Don't add this to main layout yet - will add only when needed
        self.persistent_button_widget = self.persistent_button_frame
        
        # Add "Controls" header to left panel
        header_font = QFont()
        header_font.setPointSize(15)
        header_font.setBold(True)
        
        left_header = QLabel("Controls")
        left_header.setFont(header_font)
        left_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        left_header.setStyleSheet(f"color: {self.colors['secondary']}; margin-bottom: 8px; padding-left: 2px;")
        left_layout.addWidget(left_header)
        
        # Create toggle button
        self.toggle_button = QPushButton("◀ Hide")
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_accent']};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 12px;
                max-width: 70px;
                margin-left: auto;
            }}
            QPushButton:hover {{
                background-color: {self.colors['primary_dark']};
                color: {self.colors['text_dark']};
            }}
        """)
        self.toggle_button.clicked.connect(self.toggle_right_panel)
        
        # Add "View" header to right panel with collapse button
        right_header = QLabel("Monitoring View")
        right_header.setFont(header_font)
        right_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        right_header.setStyleSheet(f"color: {self.colors['secondary']}; margin-bottom: 8px; padding-left: 2px;")
        
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(right_header)
        header_layout.addStretch()
        header_layout.addWidget(self.toggle_button)
        right_layout.addLayout(header_layout)
        
        # Store the original sizes for later restoration
        self.original_sizes = [320, 480]  # Default sizes for left and right panels
        
        # === LEFT PANEL COMPONENTS ===
        
        # 1. Settings group - cleaner style
        settings_group = QGroupBox("Settings")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(16, 24, 16, 16)
        settings_layout.setSpacing(14)
        left_layout.addWidget(settings_group)
        
        # Threshold control - using grid layout for better alignment
        settings_grid = QGridLayout()
        settings_grid.setVerticalSpacing(12)
        settings_grid.setHorizontalSpacing(10)
        settings_grid.setColumnStretch(1, 1)  # Make slider column stretch
        
        threshold_label = QLabel("Threshold:")
        threshold_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        settings_grid.addWidget(threshold_label, 0, 0)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(1, 50)  # 0.01 to 0.50
        self.threshold_slider.setValue(5)      # Default 0.05
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        settings_grid.addWidget(self.threshold_slider, 0, 1)
        
        self.threshold_value_label = QLabel("0.05")
        self.threshold_value_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        self.threshold_value_label.setFixedWidth(50)
        self.threshold_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        settings_grid.addWidget(self.threshold_value_label, 0, 2)
        
        # Region size control
        size_label = QLabel("Region Size:")
        size_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        settings_grid.addWidget(size_label, 1, 0)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(20, 200)  # 20 to 200 pixels
        self.size_slider.setValue(50)      # Default 100
        self.size_slider.valueChanged.connect(self.update_size_label)
        settings_grid.addWidget(self.size_slider, 1, 1)
        
        self.size_value_label = QLabel("50")
        self.size_value_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        self.size_value_label.setFixedWidth(50)
        self.size_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        settings_grid.addWidget(self.size_value_label, 1, 2)
        
        settings_layout.addLayout(settings_grid)
        
        # Add horizontal separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet(f"background-color: {self.colors['bg_accent']}; max-height: 1px;")
        settings_layout.addWidget(separator)
        
        # Features section title
        features_label = QLabel("Features")
        features_label.setStyleSheet(f"color: {self.colors['primary_light']}; font-weight: 600; font-size: 13px;")
        settings_layout.addWidget(features_label)
        
        # Feature toggles - arranged in a cleaner grid
        features_grid = QGridLayout()
        features_grid.setVerticalSpacing(12)
        features_grid.setHorizontalSpacing(10)
        features_grid.setColumnStretch(1, 1)  # Make the second column stretch
        
        # Noise reduction
        noise_label = QLabel("Noise Reduction:")
        noise_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        features_grid.addWidget(noise_label, 0, 0)
        
        self.noise_checkbox = QCheckBox("On")
        self.noise_checkbox.setChecked(True)
        self.noise_checkbox.toggled.connect(self.toggle_noise_reduction)
        features_grid.addWidget(self.noise_checkbox, 0, 1)
        
        # Bright detection
        bright_label = QLabel("Bright Detection:")
        bright_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        features_grid.addWidget(bright_label, 1, 0)
        
        self.bright_checkbox = QCheckBox("Enhanced")
        self.bright_checkbox.setChecked(True)
        self.bright_checkbox.toggled.connect(self.toggle_bright_detection)
        features_grid.addWidget(self.bright_checkbox, 1, 1)
        
        # Repair detection
        repair_label = QLabel("Repair Detection:")
        repair_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        features_grid.addWidget(repair_label, 2, 0)
        
        self.repair_checkbox = QCheckBox("Enabled")
        self.repair_checkbox.setChecked(True)
        self.repair_checkbox.toggled.connect(self.toggle_repair_detection)
        features_grid.addWidget(self.repair_checkbox, 2, 1)
        
        # Action sequence
        action_label = QLabel("Action Sequence:")
        action_label.setStyleSheet(f"color: {self.colors['text_dim']};")
        features_grid.addWidget(action_label, 3, 0)
        
        self.action_checkbox = QCheckBox("Enabled")
        self.action_checkbox.setChecked(True)
        self.action_checkbox.toggled.connect(self.toggle_action_sequence)
        features_grid.addWidget(self.action_checkbox, 3, 1)
        
        settings_layout.addLayout(features_grid)
        
        # 2. Monitoring group - cleaner style
        monitoring_group = QGroupBox("Monitoring")
        monitoring_layout = QVBoxLayout(monitoring_group)
        monitoring_layout.setContentsMargins(16, 24, 16, 16)
        monitoring_layout.setSpacing(12)
        left_layout.addWidget(monitoring_group)
        
        # Region selection button
        self.region_button = QPushButton("Select Region")
        self.region_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['primary']};
                color: {self.colors['text_dark']};
                font-weight: 600;
                padding: 10px 16px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['primary_light']};
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
        
        # 3. Control group - cleaner style
        control_group = QGroupBox("Control")
        control_layout = QVBoxLayout(control_group)
        control_layout.setContentsMargins(16, 24, 16, 16)
        control_layout.setSpacing(14)
        left_layout.addWidget(control_group)
        
        # Control buttons in a grid for better alignment
        button_grid = QGridLayout()
        button_grid.setHorizontalSpacing(10)
        button_grid.setVerticalSpacing(10)
        
        self.start_button = QPushButton("Start")
        self.start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['success']};
                color: {self.colors['text_dark']};
                font-weight: 600;
                font-size: 14px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #BEF0C0;
            }}
        """)
        self.start_button.clicked.connect(self.start_detection)
        button_grid.addWidget(self.start_button, 0, 0)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['alert']};
                color: {self.colors['text_dark']};
                font-weight: 600;
                font-size: 14px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #F7A8BB;
            }}
        """)
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        button_grid.addWidget(self.stop_button, 0, 1)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['warning']};
                color: {self.colors['text_dark']};
                font-weight: 600;
                font-size: 14px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #FFC7A4;
            }}
        """)
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        button_grid.addWidget(self.pause_button, 0, 2)
        
        control_layout.addLayout(button_grid)
        
        # Second row of utility buttons - fixed layout
        utility_layout = QHBoxLayout()
        utility_layout.setSpacing(10)
        
        self.reference_button = QPushButton("Capture Reference")
        self.reference_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['secondary']};
                color: {self.colors['text']};
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: #D9B6FF;
                color: {self.colors['text_dark']};
            }}
        """)
        self.reference_button.clicked.connect(self.capture_reference)
        utility_layout.addWidget(self.reference_button)
        
        self.clear_button = QPushButton("Clear Logs")
        self.clear_button.setStyleSheet(f"""
            QPushButton {{
                padding: 6px 12px;
            }}
        """)
        self.clear_button.clicked.connect(self.clear_logs)
        utility_layout.addWidget(self.clear_button)
        
        control_layout.addLayout(utility_layout)
        
        # Add permissions help button
        permissions_button = QPushButton("Fix Permissions")
        permissions_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_accent']};
                color: {self.colors['text']};
                padding: 5px 10px;
                font-size: 12px;
                border: 1px solid {self.colors['secondary']};
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_card']};
                border-color: {self.colors['primary']};
            }}
        """)
        permissions_button.clicked.connect(lambda: show_permissions_help(self))
        control_layout.addWidget(permissions_button)
        
        # 4. Log display - cleaner style
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(16, 24, 16, 16)
        log_layout.setSpacing(8)
        left_layout.addWidget(log_group, stretch=1)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        
        # === RIGHT PANEL COMPONENTS ===
        
        # 1. Monitoring display with cleaner theme
        monitor_group = QGroupBox("Live Monitor")
        monitor_layout = QVBoxLayout(monitor_group)
        monitor_layout.setContentsMargins(16, 24, 16, 16)
        monitor_layout.setSpacing(10)
        
        self.monitor_display = MonitoringDisplay()
        self.monitor_display.setStyleSheet(f"""
            QLabel {{ 
                background-color: {self.colors['bg_card']}; 
                border: none;
                border-radius: 8px;
            }}
        """)
        monitor_layout.addWidget(self.monitor_display)
        right_layout.addWidget(monitor_group, stretch=3)
        
        # 2. Timeline plot in its own group
        timeline_group = QGroupBox("Activity Timeline")
        timeline_layout = QVBoxLayout(timeline_group)
        timeline_layout.setContentsMargins(16, 24, 16, 16)
        
        self.timeline_plot = TimelinePlot(width=5, height=1.5)
        timeline_layout.addWidget(self.timeline_plot)
        
        right_layout.addWidget(timeline_group, stretch=1)
        
        # 3. Status and count display - cleaner style
        status_frame = QFrame()
        status_frame.setMaximumHeight(36)
        status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors['bg_card']};
                border-radius: 8px;
                padding: 0px;
            }}
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(12, 4, 12, 4)
        status_layout.setSpacing(8)
        
        self.status_label = QLabel("Status: Waiting")
        self.status_label.setStyleSheet(f"color: {self.colors['primary_light']}; font-weight: 500; font-size: 13px;")
        status_layout.addWidget(self.status_label)
        
        self.count_label = QLabel("Detections: 0")
        self.count_label.setStyleSheet(f"color: {self.colors['primary_light']}; font-weight: 500; font-size: 13px;")
        status_layout.addWidget(self.count_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        right_layout.addWidget(status_frame)
        
        # Set initial sizes for splitter - give more space to the right panel
        self.main_splitter.setSizes([320, 480])
        
        # Add a welcome log message
        self.add_log("Pixel Change Detector initialized")
        self.add_log("Modern Clean UI Theme")
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
        # Check for screen recording permission first
        if not check_screen_recording_permission():
            self.add_log("ERROR: Screen recording permission denied")
            
            # Show helpful message to the user
            QMessageBox.warning(
                self,
                "Permission Error",
                "Screen recording permission is required but not granted.\n\n"
                "Please follow these steps:\n"
                "1. Open System Settings > Privacy & Security > Screen Recording\n"
                "2. Ensure this application is allowed\n"
                "3. If not in the list, run the app once, then add it\n"
                "4. Restart the application after granting permission\n\n"
                "Note: If running from a packaged app, you must grant permission to the app itself, not Python."
            )
            return
            
        # Hide main window to ensure it's not in the screenshot
        self.hide()
        
        # Delay to ensure the main window disappears before capturing screen
        # Longer delay for more reliable fullscreen capture
        time.sleep(0.5)
        
        # Make sure all Qt events are processed before taking the screenshot
        QApplication.processEvents()
        
        # Create and show region selection dialog
        region_size = self.size_slider.value()
        try:
            self.selection_dialog = RegionSelectionOverlay(None, region_size)
            self.selection_dialog.region_selected.connect(self.set_region)
            
            # Force the selection dialog to stay on top
            self.selection_dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            
            # Show dialog and make it active - fullscreen
            self.selection_dialog.showFullScreen()
            self.selection_dialog.activateWindow()
            self.selection_dialog.raise_()
            
            # Use Apple Script to ensure window focus and bring to front (for macOS)
            try:
                import os
                import subprocess
                script = '''
                tell application "System Events" 
                    set frontmost of every process whose unix id is %d to true
                end tell
                ''' % os.getpid()
                subprocess.run(['osascript', '-e', script], check=True)
            except Exception as e:
                print(f"Error focusing window: {e}")
            
            result = self.selection_dialog.exec()
            
            if result == QDialog.DialogCode.Rejected:
                self.add_log("Region selection canceled")
                
        except Exception as e:
            self.add_log(f"Error in region selection: {e}")
            import traceback
            self.add_log(traceback.format_exc())
            QMessageBox.critical(
                self,
                "Screen Capture Error",
                f"Failed to create screen selection overlay.\nError: {str(e)}\n\n"
                "This may be due to permission issues or system constraints."
            )
            
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
        self.status_label.setStyleSheet(f"color: {self.colors['primary']}; font-weight: 500; font-size: 12px;")
    
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
            self.status_label.setStyleSheet(f"color: {self.colors['primary']}; font-weight: 500; font-size: 12px;")
    
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
        self.status_label.setStyleSheet(f"color: {self.colors['primary_light']}; font-weight: 500; font-size: 12px;")
        
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
                self.status_label.setStyleSheet(f"color: {self.colors['primary_light']}; font-weight: 500; font-size: 12px;")
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
    
    def toggle_repair_detection(self, checked):
        """Toggle repair detection"""
        if self.detector:
            self.detector.enable_repair_detection = checked
            self.add_log(f"Repair detection {'enabled' if checked else 'disabled'}")
    
    def toggle_action_sequence(self, checked):
        """Toggle action sequence"""
        if self.detector:
            self.detector.enable_action_sequence = checked
            self.add_log(f"Action sequence {'enabled' if checked else 'disabled'}")
            
    def toggle_right_panel(self):
        """Toggle the right panel between collapsed and expanded states"""
        if self.right_panel_collapsed:
            self.expand_right_panel()
        else:
            # Save current sizes before collapsing
            self.original_sizes = self.main_splitter.sizes()
            
            # Hide the right panel
            self.right_panel.hide()
            
            # Show the expand button by adding it to the layout
            container_layout = self.container.layout()
            container_layout.addWidget(self.persistent_button_frame)
            self.expand_button.show()
            
            # Resize the window to be more compact
            current_width = self.width()
            new_width = self.left_panel.width() + 70  # Left panel + margins + expand button
            self.resize(new_width, self.height())
            
            # Update toggle button
            self.toggle_button.setText("▶ Show View")
            
            # Update state
            self.right_panel_collapsed = True
    
    def expand_right_panel(self):
        """Expand the previously collapsed right panel"""
        # Show the right panel
        self.right_panel.show()
        
        # Remove and hide the expand button
        self.persistent_button_frame.setParent(None)
        self.expand_button.hide()
        
        # Restore original window size
        self.resize(880, self.height())
        
        # Restore original panel sizes after a short delay to ensure layout is updated
        QTimer.singleShot(100, lambda: self.main_splitter.setSizes(self.original_sizes))
        
        # Update toggle button text
        self.toggle_button.setText("◀ Hide View")
        
        # Update state
        self.right_panel_collapsed = False 