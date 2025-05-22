import sys
import time
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QSlider, QFrame, QSplitter, QTextEdit,
    QGroupBox, QMessageBox, QDialog, QDialogButtonBox, QCheckBox,
    QApplication, QGridLayout
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from src.models.detector import PixelChangeDetector
from src.ui.components.monitoring_display import MonitoringDisplay
from src.ui.components.timeline_plot import TimelinePlot
from src.ui.components.region_selection import RegionSelectionOverlay
from src.utils.permissions import show_permissions_help, check_screen_recording_permission

class PixelChangeApp(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoFishing")
        # Set minimum width to match left panel - will be updated after panel creation
        self.setMinimumSize(320, 600)
        
        # Initialize detector
        self.detector = PixelChangeDetector()
        self.detector.log_signal.connect(self.add_log)
        self.detector.frame_updated.connect(self.update_visualization)
        self.detector.detection_signal.connect(self.handle_detection)
        
        # Add new properties for toggleable features
        self.detector.enable_repair_detection = True
        self.detector.enable_action_sequence = True
        
        # Define color scheme first
        self._define_colors()
        
        # Create UI
        self._init_ui()
        
        # Detection counter
        self.detection_count = 0
        
        # Add properties for right panel collapse/expand
        self.right_panel_collapsed = False
        self.original_sizes = [300, 460]  # Default sizes for left and right panels
        
    def _define_colors(self):
        """Define the color scheme for the application - Matcha Wood Theme"""
        # Define color scheme - Matcha Wood Theme
        self.colors = {
            # Base colors
            'bg_dark': '#2C2417',      # Dark oak wood for background
            'bg_panel': '#372D1C',     # Slightly lighter oak wood for panels
            'bg_card': '#43341F',      # Medium oak wood for cards/controls
            'bg_accent': '#4E3C22',    # Lighter oak wood for accents
            
            # Text colors
            'text': '#F8F4E3',         # Cream text
            'text_dim': '#E6DFC8',     # Light cream for secondary text
            'text_muted': '#BDB59A',   # Muted cream for tertiary text
            'text_dark': '#2C2417',    # Dark text for light backgrounds
            
            # Accent colors
            'primary': '#8DC370',      # Matcha green primary
            'primary_light': '#A7CF90', # Light matcha green
            'primary_dark': '#6B9E4F',  # Dark matcha green
            'secondary': '#5D7052',    # Dark grass green secondary accent
            'highlight': '#B9C784',    # Light grass green highlight
            
            # Status colors
            'success': '#8DC370',      # Success - matcha green
            'alert': '#D95F4E',        # Error - burnt sienna 
            'warning': '#E6A948',      # Warning - golden oak
            'border': '#43341F',       # Border color - medium oak
        }
        
    def _init_ui(self):
        """Initialize the user interface - macOS-style theme"""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)
        
        # Set application-wide stylesheet - macOS style, using system fonts
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ 
                background-color: {self.colors['bg_dark']}; 
                color: {self.colors['text']}; 
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', 'Helvetica Neue', Helvetica, Arial, sans-serif;
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
                padding-bottom: 8px;
            }}
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                left: 12px; 
                padding: 0 8px 0 8px;
                color: {self.colors['text']};
                font-weight: 600;
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
                border-radius: 6px;
                padding: 8px 16px; 
                font-size: 13px;
                font-weight: 500;
                min-height: 18px;
                margin: 3px;
            }}
            QPushButton:hover {{ 
                background-color: {self.colors['primary_dark']}; 
                color: white;
            }}
            QPushButton:pressed {{ 
                background-color: {self.colors['primary']}; 
                color: white;
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
                border-radius: 6px;
                font-family: 'SF Mono', Menlo, Monaco, 'Courier New', monospace;
                font-size: 12px;
                padding: 8px;
                selection-background-color: {self.colors['primary']};
                selection-color: white;
            }}
            
            QSlider::groove:horizontal {{
                border: none;
                height: 4px;
                background: {self.colors['bg_accent']};
                margin: 2px 0;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {self.colors['primary']};
                border: none;
                width: 16px;
                height: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {self.colors['primary_light']};
            }}
            
            QCheckBox {{
                color: {self.colors['text']};
                font-size: 13px;
                spacing: 8px;
                min-height: 20px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 3px;
                border: 1px solid {self.colors['border']};
                background-color: {self.colors['bg_card']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {self.colors['primary']};
                border: 1px solid {self.colors['primary']};
                image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxNCIgaGVpZ2h0PSIxNCIgdmlld0JveD0iMCAwIDE0IDE0Ij48cGF0aCBmaWxsPSIjRkZGRkZGIiBkPSJNNS43MzMgMTBMMTIgMy43MzMgMTAuMjY3IDIgNS43MzMgNi41MzMgMy43MzMgNC41MzMgMiA2LjI2N3oiLz48L3N2Zz4=);
            }}
            QCheckBox::indicator:hover {{
                border: 1px solid {self.colors['primary']};
            }}
            
            QSplitter::handle {{
                background-color: {self.colors['border']};
                width: 1px;
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
        container_layout.addWidget(self.main_splitter)
        
        # Create left panel (controls)
        self.left_panel = QWidget()
        self.left_panel.setFixedWidth(300)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(12)
        self.main_splitter.addWidget(self.left_panel)
        
        # Update minimum width based on the left panel
        self.LEFT_PANEL_WIDTH = 300  # Store this for use in resize operations
        
        # Create right panel (visualization)
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)
        right_layout.setSpacing(12)
        self.main_splitter.addWidget(self.right_panel)
        
        # Create a persistent button frame that stays visible when right panel is collapsed
        self.persistent_button_frame = QFrame()
        self.persistent_button_frame.setFixedWidth(32)
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
        self.expand_button.setFixedSize(32, 70)
        self.expand_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['primary']};
                color: white;
                border-radius: 0px 6px 6px 0px;
                padding: 2px;
                font-size: 12px;
                font-weight: bold;
                margin: 0px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['primary_light']};
            }}
        """)
        self.expand_button.clicked.connect(self.expand_right_panel)
        persistent_layout.addWidget(self.expand_button)
        persistent_layout.addStretch()
        
        # Initially hide the expand button
        self.expand_button.hide()
        
        # Don't add this to main layout yet - will add only when needed
        self.persistent_button_widget = self.persistent_button_frame
        
        # No title for controls panel anymore
        
        # Create toggle button
        self.toggle_button = QPushButton("◀")
        self.toggle_button.setToolTip("Hide View Panel")
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_accent']};
                border-radius: 4px;
                padding: 4px;
                font-size: 10px;
                max-width: 24px;
                max-height: 24px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['primary']};
                color: white;
            }}
        """)
        self.toggle_button.clicked.connect(self.toggle_right_panel)
        
        # Add collapse button without header
        right_header_layout = QHBoxLayout()
        right_header_layout.setContentsMargins(0, 0, 0, 8)
        
        right_header_layout.addStretch()
        right_header_layout.addWidget(self.toggle_button)
        right_layout.addLayout(right_header_layout)
        
        # Store the original sizes for later restoration
        self.original_sizes = [300, 460]  # Default sizes for left and right panels
        self.right_panel_collapsed = False
        
        # === LEFT PANEL COMPONENTS ===
        
        # 1. Detection Parameters panel (first panel)
        parameters_group = QGroupBox("Detection Parameters")
        parameters_layout = QVBoxLayout(parameters_group)
        parameters_layout.setContentsMargins(16, 24, 16, 16)
        parameters_layout.setSpacing(16)
        left_layout.addWidget(parameters_group)
        
        # Threshold control with improved grid layout
        settings_grid = QGridLayout()
        settings_grid.setColumnStretch(1, 1)  # Make slider column stretch
        settings_grid.setVerticalSpacing(16)
        settings_grid.setHorizontalSpacing(12)
        
        # Threshold label with description
        threshold_label = QLabel("Sensitivity:")
        threshold_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 13px;")
        threshold_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        settings_grid.addWidget(threshold_label, 0, 0)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setFixedHeight(24)
        self.threshold_slider.setRange(1, 50)  # 0.01 to 0.50
        self.threshold_slider.setValue(5)      # Default 0.05
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        settings_grid.addWidget(self.threshold_slider, 0, 1)
        
        self.threshold_value_label = QLabel("0.05")
        self.threshold_value_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-size: 13px;")
        self.threshold_value_label.setFixedWidth(45)
        self.threshold_value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        settings_grid.addWidget(self.threshold_value_label, 0, 2)
        
        # Add a small description label for threshold
        threshold_desc = QLabel("Detection sensitivity threshold")
        threshold_desc.setStyleSheet(f"color: {self.colors['text_muted']}; font-size: 11px; font-style: italic;")
        threshold_desc.setAlignment(Qt.AlignmentFlag.AlignLeft)
        settings_grid.addWidget(threshold_desc, 1, 1, 1, 2)
        
        # Region size control with better description
        size_label = QLabel("Region Size:")
        size_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 13px;")
        size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        settings_grid.addWidget(size_label, 2, 0)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setFixedHeight(24)
        self.size_slider.setRange(20, 200)  # 20 to 200 pixels
        self.size_slider.setValue(50)      # Default 50
        self.size_slider.valueChanged.connect(self.update_size_label)
        settings_grid.addWidget(self.size_slider, 2, 1)
        
        self.size_value_label = QLabel("50 px")
        self.size_value_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-size: 13px;")
        self.size_value_label.setFixedWidth(45)
        self.size_value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        settings_grid.addWidget(self.size_value_label, 2, 2)
        
        # Add a small description label for size
        size_desc = QLabel("Default selection box size")
        size_desc.setStyleSheet(f"color: {self.colors['text_muted']}; font-size: 11px; font-style: italic;")
        size_desc.setAlignment(Qt.AlignmentFlag.AlignLeft)
        settings_grid.addWidget(size_desc, 3, 1, 1, 2)
        
        parameters_layout.addLayout(settings_grid)
        
        # 2. Detection Features panel (second panel, separate)
        features_group = QGroupBox("Detection Features")
        features_layout = QVBoxLayout(features_group)
        features_layout.setContentsMargins(16, 24, 16, 16)
        features_layout.setSpacing(16)
        left_layout.addWidget(features_group)
        
        # Checkboxes layout with better organization - first row
        checkbox_layout = QHBoxLayout()
        checkbox_layout.setSpacing(20)
        checkbox_layout.setContentsMargins(0, 8, 0, 8)
        
        # Noise reduction checkbox with icon-like alignment
        self.noise_checkbox = QCheckBox("Noise Reduction")
        self.noise_checkbox.setStyleSheet(f"""
            font-size: 13px;
            padding: 4px 0px;
            color: {self.colors['text']};
        """)
        self.noise_checkbox.setChecked(True)
        self.noise_checkbox.toggled.connect(self.toggle_noise_reduction)
        checkbox_layout.addWidget(self.noise_checkbox)
        
        # Bright background detection checkbox
        self.bright_checkbox = QCheckBox("Bright Detection")
        self.bright_checkbox.setStyleSheet(f"""
            font-size: 13px;
            padding: 4px 0px;
            color: {self.colors['text']};
        """)
        self.bright_checkbox.setChecked(True)
        self.bright_checkbox.toggled.connect(self.toggle_bright_detection)
        checkbox_layout.addWidget(self.bright_checkbox)
        
        features_layout.addLayout(checkbox_layout)
        
        # Second row of checkboxes with better spacing and alignment
        checkbox_layout2 = QHBoxLayout()
        checkbox_layout2.setSpacing(20)
        checkbox_layout2.setContentsMargins(0, 8, 0, 8)
        
        # Repair detection checkbox
        self.repair_checkbox = QCheckBox("Repair Detection")
        self.repair_checkbox.setStyleSheet(f"""
            font-size: 13px;
            padding: 4px 0px;
            color: {self.colors['text']};
        """)
        self.repair_checkbox.setChecked(True)
        self.repair_checkbox.toggled.connect(self.toggle_repair_detection)
        checkbox_layout2.addWidget(self.repair_checkbox)
        
        # Action sequence checkbox
        self.action_checkbox = QCheckBox("Action Sequence")
        self.action_checkbox.setStyleSheet(f"""
            font-size: 13px;
            padding: 4px 0px;
            color: {self.colors['text']};
        """)
        self.action_checkbox.setChecked(True)
        self.action_checkbox.toggled.connect(self.toggle_action_sequence)
        checkbox_layout2.addWidget(self.action_checkbox)
        
        features_layout.addLayout(checkbox_layout2)
        
        # 2. Monitoring group
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
                color: white;
                font-weight: 600;
                padding: 8px 16px;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['primary_light']};
            }}
        """)
        self.region_button.setMinimumHeight(32)
        self.region_button.clicked.connect(self.select_region)
        monitoring_layout.addWidget(self.region_button)
        
        # Region info display
        region_info_layout = QHBoxLayout()
        region_info_layout.setSpacing(8)
        region_info_layout.setContentsMargins(4, 4, 4, 4)
        status_label = QLabel("Status:")
        status_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 13px;")
        region_info_layout.addWidget(status_label)
        
        self.region_info_label = QLabel("No region selected")
        self.region_info_label.setStyleSheet("font-size: 13px;")
        region_info_layout.addWidget(self.region_info_label)
        monitoring_layout.addLayout(region_info_layout)
        
        # 3. Control group
        control_group = QGroupBox("Control")
        control_layout = QVBoxLayout(control_group)
        control_layout.setContentsMargins(8, 8, 8, 8)
        control_layout.setSpacing(8)
        left_layout.addWidget(control_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        self.start_button = QPushButton("Start")
        self.start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['success']};
                color: white;
                font-weight: 600;
                font-size: 13px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #40D168;
            }}
        """)
        self.start_button.setMinimumHeight(32)
        self.start_button.clicked.connect(self.start_detection)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['alert']};
                color: white;
                font-weight: 600;
                font-size: 13px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #FF594E;
            }}
        """)
        self.stop_button.setMinimumHeight(32)
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['warning']};
                color: white;
                font-weight: 600;
                font-size: 13px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: #FFAF3F;
            }}
        """)
        self.pause_button.setMinimumHeight(32)
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
                background-color: {self.colors['secondary']};
                color: white;
                font-size: 13px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: #6E6CF6;
            }}
        """)
        self.reference_button.setMinimumHeight(28)
        self.reference_button.clicked.connect(self.capture_reference)
        button_layout2.addWidget(self.reference_button)
        
        self.clear_button = QPushButton("Clear Logs")
        self.clear_button.setMinimumHeight(28)
        self.clear_button.setStyleSheet(f"""
            font-size: 13px; 
            padding: 6px 12px;
            background-color: {self.colors['bg_accent']};
        """)
        self.clear_button.clicked.connect(self.clear_logs)
        button_layout2.addWidget(self.clear_button)
        
        control_layout.addLayout(button_layout2)
        
        # Add permissions help button
        permissions_button = QPushButton("Fix Permissions")
        permissions_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_accent']};
                color: {self.colors['text']};
                font-size: 13px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['primary']};
                color: white;
            }}
        """)
        permissions_button.setMinimumHeight(28)
        permissions_button.clicked.connect(lambda: show_permissions_help(self))
        control_layout.addWidget(permissions_button)
        
        # === RIGHT PANEL COMPONENTS ===
        
        # 1. Monitoring display
        monitor_group = QGroupBox("Live Monitor")
        monitor_layout = QVBoxLayout(monitor_group)
        monitor_layout.setContentsMargins(16, 24, 16, 16)
        monitor_layout.setSpacing(8)
        
        self.monitor_display = MonitoringDisplay()
        self.monitor_display.setStyleSheet(f"""
            QLabel {{ 
                background-color: {self.colors['bg_card']}; 
                border: none; 
                border-radius: 6px;
                font-size: 13px;
            }}
        """)
        monitor_layout.addWidget(self.monitor_display)
        right_layout.addWidget(monitor_group, stretch=3)
        
        # 2. Log display (moved from left panel)
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(16, 24, 16, 16)
        log_layout.setSpacing(8)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMinimumHeight(120)
        self.log_display.setStyleSheet(f"""
            font-family: 'SF Mono', Menlo, Monaco, 'Courier New', monospace;
            font-size: 12px;
            background-color: {self.colors['bg_card']};
            color: {self.colors['text']};
            border: none;
            border-radius: 6px;
            padding: 8px;
        """)
        log_layout.addWidget(self.log_display)
        right_layout.addWidget(log_group, stretch=2)
        
        # 3. Timeline plot in its own group
        timeline_group = QGroupBox("Activity Timeline")
        timeline_layout = QVBoxLayout(timeline_group)
        timeline_layout.setContentsMargins(16, 24, 16, 16)
        
        self.timeline_plot = TimelinePlot(width=5, height=1.5)
        timeline_layout.addWidget(self.timeline_plot)
        
        right_layout.addWidget(timeline_group, stretch=1)
        
        # 3. Status and count display
        status_frame = QFrame()
        status_frame.setMinimumHeight(32)
        status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {self.colors['bg_panel']};
                border-radius: 6px;
                padding: 0px;
            }}
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(16, 0, 16, 0)
        status_layout.setSpacing(8)
        
        self.status_label = QLabel("Status: Waiting")
        self.status_label.setStyleSheet(f"color: {self.colors['text']}; font-weight: 500; font-size: 13px;")
        status_layout.addWidget(self.status_label)
        
        self.count_label = QLabel("Detections: 0")
        self.count_label.setStyleSheet(f"color: {self.colors['text']}; font-weight: 500; font-size: 13px;")
        status_layout.addWidget(self.count_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        right_layout.addWidget(status_frame)
        
        # Add a welcome log message
        self.add_log("AutoFishing initialized")
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
        self.size_value_label.setText(f"{value} px")
    
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
            # Save current sizes and width before collapsing
            self.original_sizes = self.main_splitter.sizes()
            self.original_width = self.width()
            
            # Hide the right panel
            self.right_panel.hide()
            
            # Show the expand button by adding it to the layout
            container_layout = self.container.layout()
            container_layout.addWidget(self.persistent_button_frame)
            self.expand_button.show()
            
            # Resize the window to exactly match the left panel width
            # Account for the expand button (32px) and small buffer
            new_width = self.LEFT_PANEL_WIDTH + 40  # Left panel + expand button + minimal buffer
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
        
        # Restore original window size if available, otherwise use default
        if hasattr(self, 'original_width'):
            self.resize(self.original_width, self.height())
        else:
            self.resize(800, self.height())
        
        # Restore original panel sizes after a short delay to ensure layout is updated
        QTimer.singleShot(100, lambda: self.main_splitter.setSizes(self.original_sizes))
        
        # Update toggle button text
        self.toggle_button.setText("◀ Hide View")
        
        # Update state
        self.right_panel_collapsed = False 