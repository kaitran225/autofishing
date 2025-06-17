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
    QFrame, QSplitter, QGroupBox, QSlider, QSpinBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint
from PyQt6.QtGui import QColor

from core import PixelChangeDetector, FishingActionSequence
from ui.visualization import MatplotlibCanvas
from ui.selection import RegionSelectionOverlay
from ui.components import CollapsibleSidebar, PopupSection, CollapsibleSection
from utils.constants import (
    VERSION, VERSION_NAME, 
    DEFAULT_THRESHOLD, DEFAULT_DETECTION_COOLDOWN, DEFAULT_FISHING_KEY,
    DEFAULT_HIGH_PERFORMANCE, DEFAULT_RESPECT_FULLSCREEN, DEFAULT_DIRECT_CONTROL,
    UI_DARK_BG, UI_PANEL_BG, UI_LIGHT_TEXT, UI_SECONDARY_TEXT,
    UI_ACCENT_COLOR, UI_ACCENT_DARK, UI_ACCENT_LIGHT,
    UI_WOOD_DARK, UI_WOOD_MEDIUM, UI_WOOD_LIGHT,
    UI_WARNING_COLOR, UI_ALERT_COLOR, UI_SUCCESS_COLOR
)

class AutoFisherMainWindow(QMainWindow):
    """Main window for the AutoFisher Qt application"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"AutoFisher Qt v{VERSION} - {VERSION_NAME}")
        self.setMinimumSize(400, 600)
        self.setMaximumWidth(900)
        
        # Set application-wide theme
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {UI_DARK_BG};
                color: {UI_LIGHT_TEXT};
            }}
            QGroupBox {{
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
                background-color: {UI_PANEL_BG};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 8px;
                color: {UI_ACCENT_COLOR};
                font-size: 11pt;
            }}
            QPushButton {{
                background-color: {UI_WOOD_DARK};
                color: {UI_LIGHT_TEXT};
                border: none;
                border-radius: 5px;
                padding: 8px;
                margin: 3px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
            QPushButton:pressed {{
                background-color: {UI_ACCENT_DARK};
            }}
            QLineEdit, QSpinBox, QDoubleSpinBox {{
                background-color: {UI_PANEL_BG};
                color: {UI_LIGHT_TEXT};
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 4px;
                padding: 5px;
                margin: 2px;
            }}
            QCheckBox {{
                color: {UI_LIGHT_TEXT};
                spacing: 6px;
                padding: 2px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
            }}
            QCheckBox::indicator:unchecked {{
                border: 1px solid {UI_WOOD_MEDIUM};
                background-color: {UI_PANEL_BG};
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                border: 1px solid {UI_ACCENT_COLOR};
                background-color: {UI_ACCENT_DARK};
                border-radius: 3px;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwLjE5OTggMi42OTMzNEwzLjk5OTgxIDguODkzMzRMMSA1Ljg5MzM0IiBzdHJva2U9IiNFOEU4RTAiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
            }}
            QLabel {{
                padding: 2px;
            }}
            QSlider::groove:horizontal {{
                height: 8px;
                background-color: {UI_PANEL_BG};
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background-color: {UI_ACCENT_COLOR};
                border: none;
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }}
            QSlider::sub-page:horizontal {{
                background-color: {UI_ACCENT_DARK};
                border-radius: 4px;
            }}
            QFrame[frameShape="4"], QFrame[frameShape="5"] {{
                color: {UI_WOOD_DARK};
            }}
            QSplitter::handle {{
                background-color: {UI_WOOD_DARK};
                height: 1px;
            }}
        """)
        
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
        
        # Main layout using splitter for top and bottom sections
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create splitter for top and bottom sections
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(self.main_splitter)
        
        # Top container
        top_container = QWidget()
        top_layout = QHBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        
        # Left panel for visualization - use less margins for more space
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 4, 4)
        left_layout.setSpacing(6)
        
        # Right panel for collapsible sidebar
        self.sidebar = CollapsibleSidebar()
        
        # Connect sidebar expand/collapse to window width adjustment
        self.sidebar.collapsed_changed.connect(self.adjust_window_width)
        
        # Add panels to top container
        top_layout.addWidget(left_panel, 1)  # Main content stretches
        top_layout.addWidget(self.sidebar, 0)  # Sidebar doesn't stretch
        
        # Bottom container for logs with improved styling
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(8, 6, 8, 6)
        bottom_layout.setSpacing(6)
        
        # Add containers to splitter
        self.main_splitter.addWidget(top_container)
        self.main_splitter.addWidget(bottom_container)
        self.main_splitter.setSizes([4, 1])  # 80% top, 20% bottom
        
        # Add visualization panel to left panel with improved styling
        visualization_section = QFrame()
        visualization_section.setStyleSheet(f"background-color: {UI_PANEL_BG}; border-radius: 6px;")
        visualization_layout = QVBoxLayout(visualization_section)
        visualization_layout.setContentsMargins(10, 10, 10, 10)
        visualization_layout.setSpacing(8)
        
        # Add title for visualization area with cleaner styling
        viz_header = QLabel("Bobber Monitoring")
        viz_header.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {UI_ACCENT_COLOR}; padding: 0 0 5px 0;")
        visualization_layout.addWidget(viz_header)
        
        # Create a frame to contain the canvas with improved styling
        viz_frame = QFrame()
        viz_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        viz_frame.setLineWidth(1)
        viz_frame.setStyleSheet(f"background-color: {UI_DARK_BG}; border: 1px solid {UI_WOOD_DARK}; border-radius: 6px;")
        
        # Use a layout that maintains the aspect ratio with better spacing
        viz_frame_layout = QVBoxLayout(viz_frame)
        viz_frame_layout.setContentsMargins(6, 6, 6, 6)
        
        # Create matplotlib canvas for visualization with the correct aspect ratio (1.5:1)
        self.viz_canvas = MatplotlibCanvas(self, width=6, height=4, dpi=100, bg_color=UI_DARK_BG)
        
        # Add the canvas to the frame
        viz_frame_layout.addWidget(self.viz_canvas)
        
        # Add the frame to the main viz layout
        visualization_layout.addWidget(viz_frame)
        
        # Add monitoring status indicators with better styling
        status_panel = QFrame()
        status_panel.setStyleSheet(f"background-color: {UI_DARK_BG}; border-radius: 4px; padding: 2px;")
        status_layout = QHBoxLayout(status_panel)
        status_layout.setContentsMargins(8, 6, 8, 6)
        
        # Add threshold indicator with improved styling
        threshold_label = QLabel("Threshold:")
        threshold_label.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 10pt;")
        status_layout.addWidget(threshold_label)
        
        self.monitor_threshold = QLabel("0.05")
        self.monitor_threshold.setStyleSheet(f"color: {UI_WARNING_COLOR}; font-weight: bold; font-size: 10pt;")
        status_layout.addWidget(self.monitor_threshold)
        
        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet(f"color: {UI_WOOD_MEDIUM}; margin: 0 10px;")
        status_layout.addWidget(separator)
        
        # Add FPS indicator with improved styling
        fps_label = QLabel("FPS:")
        fps_label.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 10pt;")
        status_layout.addWidget(fps_label)
        
        self.monitor_fps = QLabel("0")
        self.monitor_fps.setStyleSheet(f"color: {UI_ACCENT_COLOR}; font-weight: bold; font-size: 10pt;")
        status_layout.addWidget(self.monitor_fps)
        
        status_layout.addStretch()
        
        # Add the status panel to the viz layout
        visualization_layout.addWidget(status_panel)
        
        # Status bar with current state - improved styling
        status_bar = QFrame()
        status_bar.setStyleSheet(f"background-color: {UI_WOOD_DARK}; border-radius: 8px; margin-top: 12px; margin-bottom: 6px;")
        status_bar_layout = QHBoxLayout(status_bar)
        status_bar_layout.setContentsMargins(15, 10, 15, 10)
        status_bar_layout.setSpacing(15)
        
        status_label = QLabel("Status:")
        status_label.setStyleSheet("color: #CCC; font-weight: bold; font-size: 11pt;")
        status_bar_layout.addWidget(status_label)
        
        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("color: white; font-weight: bold; font-size: 11pt;")
        status_bar_layout.addWidget(self.status_label)
        
        # Add extra spacing between status and controls
        status_bar_layout.addSpacing(20)
        status_bar_layout.addStretch()
        
        # Add quick control buttons to status bar
        # Import qtawesome for better looking buttons
        import qtawesome as qta
        
        # Create button with icon
        self.region_button = QPushButton("  Select Region  ")
        self.region_button.setIcon(qta.icon('fa5s.vector-square', color='white'))
        self.region_button.clicked.connect(self.select_region)
        self.region_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_ACCENT_DARK};
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 6px;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: {UI_ACCENT_COLOR};
            }}
        """)
        status_bar_layout.addWidget(self.region_button)
        
        self.start_button = QPushButton("  Start  ")
        self.start_button.setIcon(qta.icon('fa5s.play', color='white'))
        self.start_button.clicked.connect(self.start_detection)
        self.start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_ACCENT_DARK};
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 6px;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: {UI_ACCENT_COLOR};
            }}
        """)
        status_bar_layout.addWidget(self.start_button)
        
        self.pause_button = QPushButton("  Pause  ")
        self.pause_button.setIcon(qta.icon('fa5s.pause', color='white'))
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_WOOD_MEDIUM};
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 6px;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_LIGHT};
            }}
        """)
        status_bar_layout.addWidget(self.pause_button)
        
        self.stop_button = QPushButton("  Stop  ")
        self.stop_button.setIcon(qta.icon('fa5s.stop', color='white'))
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_WARNING_COLOR};
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 6px;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: #C06A5A;
            }}
        """)
        status_bar_layout.addWidget(self.stop_button)
        
        visualization_layout.addWidget(status_bar)
        
        # Add to main left panel
        left_layout.addWidget(visualization_section)
        
        # Create collapsible sections for the sidebar
        # 1. Settings section
        settings_section = PopupSection("Settings")
        settings_content = QWidget()
        settings_layout = QVBoxLayout(settings_content)
        settings_layout.setContentsMargins(5, 5, 5, 5)
        settings_layout.setSpacing(8)
        
        # Threshold
        threshold_widget = QWidget()
        threshold_layout = QGridLayout(threshold_widget)
        threshold_layout.setContentsMargins(0, 0, 0, 0)
        threshold_layout.setSpacing(5)
        
        threshold_layout.addWidget(QLabel("Detection Threshold:"), 0, 0)
        threshold_slider_widget = QWidget()
        threshold_slider_layout = QHBoxLayout(threshold_slider_widget)
        threshold_slider_layout.setContentsMargins(0, 0, 0, 0)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(1)
        self.threshold_slider.setMaximum(50)
        self.threshold_slider.setValue(int(DEFAULT_THRESHOLD * 100))
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        threshold_slider_layout.addWidget(self.threshold_slider)
        
        self.threshold_label = QLabel(f"{DEFAULT_THRESHOLD:.2f}")
        threshold_slider_layout.addWidget(self.threshold_label)
        
        threshold_layout.addWidget(threshold_slider_widget, 0, 1)
        
        # Add description
        threshold_desc = QLabel("Lower values = more sensitive detection")
        threshold_desc.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 9pt; font-style: italic;")
        threshold_layout.addWidget(threshold_desc, 1, 0, 1, 2)
        
        settings_layout.addWidget(threshold_widget)
        
        # Cooldown
        cooldown_widget = QWidget()
        cooldown_layout = QGridLayout(cooldown_widget)
        cooldown_layout.setContentsMargins(0, 0, 0, 0)
        
        cooldown_layout.addWidget(QLabel("Cooldown:"), 0, 0)
        self.cooldown_entry = QDoubleSpinBox()
        self.cooldown_entry.setRange(0.5, 30.0)
        self.cooldown_entry.setSingleStep(0.5)
        self.cooldown_entry.setValue(DEFAULT_DETECTION_COOLDOWN)
        self.cooldown_entry.setSuffix(" seconds")
        cooldown_layout.addWidget(self.cooldown_entry, 0, 1)
        
        # Add description
        cooldown_desc = QLabel("Time between fishing attempts")
        cooldown_desc.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 9pt; font-style: italic;")
        cooldown_layout.addWidget(cooldown_desc, 1, 0, 1, 2)
        
        settings_layout.addWidget(cooldown_widget)
        
        # Fishing Key
        key_widget = QWidget()
        key_layout = QGridLayout(key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        
        key_layout.addWidget(QLabel("Fishing Key:"), 0, 0)
        self.fishing_key_entry = QLineEdit(DEFAULT_FISHING_KEY)
        self.fishing_key_entry.setMaximumWidth(40)
        key_layout.addWidget(self.fishing_key_entry, 0, 1)
        
        # Add description
        key_desc = QLabel("Key used for fishing in game (usually F)")
        key_desc.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 9pt; font-style: italic;")
        key_layout.addWidget(key_desc, 1, 0, 1, 2)
        
        settings_layout.addWidget(key_widget)
        
        # Region Size
        region_widget = QWidget()
        region_layout = QGridLayout(region_widget)
        region_layout.setContentsMargins(0, 0, 0, 0)
        
        region_layout.addWidget(QLabel("Selection Size:"), 0, 0)
        self.size_entry = QSpinBox()
        self.size_entry.setRange(10, 500)
        self.size_entry.setValue(50)
        self.size_entry.setSuffix(" px")
        region_layout.addWidget(self.size_entry, 0, 1)
        
        # Add description
        region_desc = QLabel("Default size when making a new selection")
        region_desc.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 9pt; font-style: italic;")
        region_layout.addWidget(region_desc, 1, 0, 1, 2)
        
        settings_layout.addWidget(region_widget)
        
        # Apply button
        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.clicked.connect(self.apply_settings)
        self.apply_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_ACCENT_DARK};
                font-weight: bold;
                padding: 6px;
            }}
            QPushButton:hover {{
                background-color: {UI_ACCENT_COLOR};
            }}
        """)
        settings_layout.addWidget(self.apply_button)
        
        # Add content to section
        settings_section.add_widget(settings_content)
        
        # 2. Advanced options section
        advanced_section = PopupSection("Advanced Options")
        advanced_content = QWidget()
        advanced_layout = QVBoxLayout(advanced_content)
        advanced_layout.setContentsMargins(5, 5, 5, 5)
        
        # High Performance Mode
        self.high_performance_checkbox = QCheckBox("High Performance Mode")
        self.high_performance_checkbox.setChecked(DEFAULT_HIGH_PERFORMANCE)
        self.high_performance_checkbox.stateChanged.connect(self.update_high_performance)
        advanced_layout.addWidget(self.high_performance_checkbox)
        
        # Add description
        hp_desc = QLabel("Increases reliability using more system resources")
        hp_desc.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 9pt; margin-left: 20px; margin-bottom: 10px;")
        advanced_layout.addWidget(hp_desc)
        
        # Respect Fullscreen Apps
        self.respect_fullscreen_checkbox = QCheckBox("Respect Fullscreen Apps")
        self.respect_fullscreen_checkbox.setChecked(DEFAULT_RESPECT_FULLSCREEN)
        self.respect_fullscreen_checkbox.stateChanged.connect(self.update_respect_fullscreen)
        advanced_layout.addWidget(self.respect_fullscreen_checkbox)
        
        # Add description
        fs_desc = QLabel("Prevents interruption when other fullscreen applications are active")
        fs_desc.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 9pt; margin-left: 20px; margin-bottom: 10px;")
        advanced_layout.addWidget(fs_desc)
        
        # Direct Control Mode
        self.direct_control_checkbox = QCheckBox("Direct Control Mode")
        self.direct_control_checkbox.setChecked(DEFAULT_DIRECT_CONTROL)
        self.direct_control_checkbox.stateChanged.connect(self.update_direct_control)
        advanced_layout.addWidget(self.direct_control_checkbox)
        
        # Add description
        dc_desc = QLabel("Uses direct input methods for maximum reliability")
        dc_desc.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 9pt; margin-left: 20px; margin-bottom: 10px;")
        advanced_layout.addWidget(dc_desc)
        
        # Add content to section
        advanced_section.add_widget(advanced_content)
        
        # 3. Region info section
        region_section = CollapsibleSection("Region Info")
        region_content = QWidget()
        region_layout = QVBoxLayout(region_content)
        
        self.region_info_label = QLabel("No region selected")
        self.region_info_label.setWordWrap(True)
        self.region_info_label.setStyleSheet(f"color: {UI_LIGHT_TEXT}; padding: 5px;")
        region_layout.addWidget(self.region_info_label)
        
        self.capture_ref_button = QPushButton("Capture Reference Frame")
        self.capture_ref_button.clicked.connect(self.capture_reference)
        region_layout.addWidget(self.capture_ref_button)
        
        # Add content to section
        region_section.add_widget(region_content)
        
        # 4. Statistics section
        stats_section = PopupSection("Statistics")
        stats_content = QWidget()
        stats_layout = QGridLayout(stats_content)
        stats_layout.setContentsMargins(5, 5, 5, 5)
        
        # Stats rows
        stats_layout.addWidget(QLabel("Total Detections:"), 0, 0)
        self.detections_label = QLabel("0")
        stats_layout.addWidget(self.detections_label, 0, 1)
        
        stats_layout.addWidget(QLabel("Runtime:"), 1, 0)
        self.runtime_label = QLabel("00:00:00")
        stats_layout.addWidget(self.runtime_label, 1, 1)
        
        stats_layout.addWidget(QLabel("Detection Rate:"), 2, 0)
        self.rate_label = QLabel("0.0/min")
        stats_layout.addWidget(self.rate_label, 2, 1)
        
        stats_layout.addWidget(QLabel("Average Interval:"), 3, 0)
        self.interval_label = QLabel("0.0s")
        stats_layout.addWidget(self.interval_label, 3, 1)
        
        # Add content to section
        stats_section.add_widget(stats_content)
        
        # Add all sections to sidebar
        self.sidebar.add_section(settings_section)
        self.sidebar.add_section(advanced_section)
        self.sidebar.add_section(region_section)
        self.sidebar.add_section(stats_section)
        
        # Connect popup sections to window resize handler
        settings_section.popup_state_changed.connect(self.adjust_window_for_popup)
        advanced_section.popup_state_changed.connect(self.adjust_window_for_popup)
        stats_section.popup_state_changed.connect(self.adjust_window_for_popup)
        
        # Log console in bottom container with cleaner styling
        log_group = QGroupBox("Activity Logs")
        log_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 6px;
                margin-top: 10px;
                padding: 12px;
                font-weight: bold;
                background-color: {UI_PANEL_BG};
                font-size: 12pt;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 8px;
                color: {UI_ACCENT_COLOR};
                font-size: 12pt;
            }}
        """)
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(8, 15, 8, 8)  # Extra top margin for the title
        log_layout.setSpacing(8)
        
        # Create log console with better styling
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {UI_DARK_BG};
                color: {UI_LIGHT_TEXT};
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10pt;
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 5px;
                padding: 8px;
            }}
        """)
        log_layout.addWidget(self.log_console)
        
        # Add log control panel with improved styling
        log_control_panel = QFrame()
        log_control_layout = QHBoxLayout(log_control_panel)
        log_control_layout.setContentsMargins(0, 5, 0, 0)
        
        # Add timestamp indicator
        timestamp_label = QLabel("Last updated: ")
        timestamp_label.setStyleSheet(f"color: {UI_SECONDARY_TEXT};")
        log_control_layout.addWidget(timestamp_label)
        
        self.timestamp = QLabel(datetime.datetime.now().strftime("%H:%M:%S"))
        self.timestamp.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-weight: bold;")
        log_control_layout.addWidget(self.timestamp)
        
        # Add spacer to push button to the right
        log_control_layout.addStretch()
        
        # Add clear button with icon
        clear_log_button = QPushButton(" Clear Logs")
        clear_log_button.setIcon(qta.icon('fa5s.trash-alt', color='white'))
        clear_log_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_WOOD_DARK};
                color: {UI_LIGHT_TEXT};
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
        """)
        clear_log_button.setMaximumWidth(120)
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
                
                # Update timestamp
                current_time = datetime.datetime.now().strftime("%H:%M:%S")
                self.timestamp.setText(current_time)
                
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
        
    def adjust_window_width(self, is_collapsed):
        """Adjust the window width when sidebar is expanded/collapsed"""
        # Get current window geometry
        current_geometry = self.geometry()
        
        # Calculate width difference based on sidebar state
        width_diff = 200  # Approximate difference between expanded and collapsed sidebar
        
        # Calculate new width based on collapsed state, respecting the max width
        if is_collapsed:
            # Sidebar is collapsing, reduce window width
            new_width = max(400, current_geometry.width() - width_diff)
        else:
            # Sidebar is expanding, increase width but respect maximum
            new_width = min(900, current_geometry.width() + width_diff)
        
        # Set new geometry
        self.setGeometry(
            current_geometry.x(),
            current_geometry.y(),
            new_width,
            current_geometry.height()
        )
    
    def adjust_window_for_popup(self, is_popped_out):
        """Adjust the window width when a section is popped out"""
        # Get current window geometry
        current_geometry = self.geometry()
        
        # Calculate width difference based on popup state
        width_diff = 350  # Width of the popup extension
        
        # Calculate new width based on popup state, respecting max width
        if is_popped_out:
            # Section is popping out, increase window width but respect the maximum
            new_width = min(900, current_geometry.width() + width_diff)
        else:
            # Section is popping in, reduce window width
            new_width = max(400, current_geometry.width() - width_diff)
        
        # Set new geometry
        self.setGeometry(
            current_geometry.x(),
            current_geometry.y(),
            new_width,
            current_geometry.height()
        ) 