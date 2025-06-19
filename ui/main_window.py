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
    QFrame, QSplitter, QGroupBox, QSlider, QSpinBox, QDoubleSpinBox,
    QApplication, QScrollArea, QSizePolicy, QTextBrowser, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint
from PyQt6.QtGui import QColor
import qtawesome as qta

from core import PixelChangeDetector, FishingActionSequence
from ui.visualization import MatplotlibCanvas, ActivityGraphCanvas
from ui.selection import RegionSelectionOverlay, TkRegionSelector
from ui.components import CollapsibleSidebar, PopupSection, CollapsibleSection, ActivityGraphSection
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
        
        # Set fixed window size
        self.setFixedSize(380, 780)
        
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
            /* Hide all scrollbars */
            QScrollBar {{
                width: 0px;
                height: 0px;
                background: transparent;
            }}
            QScrollBar::handle {{
                background: transparent;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{
                height: 0px;
                background: transparent;
            }}
            QScrollArea {{
                border: none;
                background: transparent;
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
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(8, 8, 8, 4)
        top_layout.setSpacing(6)
        
        # Add visualization panel to top panel with improved styling
        visualization_section = QFrame()
        visualization_section.setStyleSheet(f"background-color: {UI_PANEL_BG}; border-radius: 6px;")
        visualization_layout = QVBoxLayout(visualization_section)
        visualization_layout.setContentsMargins(2, 2, 2, 2)
        visualization_layout.setSpacing(8)
        
        # Create a frame to contain the canvas with improved styling
        viz_frame = QFrame()
        viz_frame.setStyleSheet(f"background-color: {UI_DARK_BG}; border-radius: 6px;")
        viz_frame_layout = QVBoxLayout(viz_frame)
        viz_frame_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create MatplotlibCanvas for visualization
        self.viz_canvas = MatplotlibCanvas(parent=viz_frame)
        viz_frame_layout.addWidget(self.viz_canvas)
        
        # Add to visualization layout
        visualization_layout.addWidget(viz_frame)
        
        # Status panel with compact styling
        status_panel = QFrame()
        status_panel.setStyleSheet(f"background-color: {UI_PANEL_BG}; border-radius: 4px;")
        status_layout = QHBoxLayout(status_panel)
        status_layout.setContentsMargins(6, 4, 6, 4)
        status_layout.setSpacing(4)
        
        # Use smaller font for all status indicators
        status_font_size = "8pt"
        
        # Add status indicator with smaller font
        status_label = QLabel("Status:")
        status_label.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: {status_font_size}; font-weight: normal;")
        status_layout.addWidget(status_label)
        
        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet(f"color: white; font-weight: bold; font-size: {status_font_size};")
        status_layout.addWidget(self.status_label)
        
        # Add separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.VLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        separator1.setStyleSheet("background-color: transparent; max-width: 1px;")
        status_layout.addWidget(separator1)
        
        # Add threshold indicator with improved styling
        threshold_label = QLabel("Threshold:")
        threshold_label.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: {status_font_size}; font-weight: normal;")
        status_layout.addWidget(threshold_label)
        
        self.monitor_threshold = QLabel("0.05")
        self.monitor_threshold.setStyleSheet(f"color: {UI_WARNING_COLOR}; font-weight: bold; font-size: {status_font_size};")
        status_layout.addWidget(self.monitor_threshold)
        
        # Add separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.VLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        separator2.setStyleSheet("background-color: transparent; max-width: 1px;")
        status_layout.addWidget(separator2)
        
        # Add FPS indicator with improved styling
        fps_label = QLabel("FPS:")
        fps_label.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: {status_font_size}; font-weight: normal;")
        status_layout.addWidget(fps_label)
        
        self.monitor_fps = QLabel("0")
        self.monitor_fps.setStyleSheet(f"color: {UI_ACCENT_COLOR}; font-weight: bold; font-size: {status_font_size};")
        status_layout.addWidget(self.monitor_fps)
        
        # Add separator for sidebar toggle
        separator3 = QFrame()
        separator3.setFrameShape(QFrame.Shape.VLine)
        separator3.setFrameShadow(QFrame.Shadow.Sunken)
        separator3.setStyleSheet("background-color: transparent; max-width: 1px;")
        status_layout.addWidget(separator3)
        
        # # Add menu label
        # sidebar_label = QLabel("Menu:")
        # sidebar_label.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: {status_font_size}; font-weight: normal;")
        # status_layout.addWidget(sidebar_label)
        
        # Add menu button
        # menu_toggle = QPushButton()
        # menu_toggle.setIcon(qta.icon('fa5s.bars', color='white', scale_factor=0.9))
        # menu_toggle.setStyleSheet(f"""
        #     QPushButton {{
        #         background-color: transparent;
        #         border: none;
        #         padding: 1px;
        #         min-width: 16px;
        #         max-width: 16px;
        #         min-height: 16px;
        #         max-height: 16px;
        #     }}
        #     QPushButton:hover {{
        #         background-color: {UI_WOOD_DARK};
        #         border-radius: 2px;
        #     }}
        # """)
        # menu_toggle.setToolTip("Show Settings Tab")
        # menu_toggle.clicked.connect(lambda: self.tab_widget.setCurrentIndex(2))  # Switch to Settings tab
        # status_layout.addWidget(menu_toggle)
        
        # Add stretch to push everything to the left
        status_layout.addStretch()
        
        # Add the status panel to the viz layout
        visualization_layout.addWidget(status_panel)
        
        # Control bar with cleaner styling
        control_bar = QFrame()
        control_bar.setStyleSheet(f"background-color: {UI_PANEL_BG}; border-radius: 8px; margin-top: 8px; margin-bottom: 4px;")
        
        # Use horizontal layout for single row of controls
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(8, 6, 8, 6)
        control_layout.setSpacing(8)
        
        # Define button styles for different actions
        button_base_style = """
            QPushButton {
                border-radius: 3px;
                padding: 4px;
                margin: 0px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }
            QPushButton:disabled {
                background-color: %s;
                color: %s;
                border: 1px solid %s;
            }
        """
        
        # Different button styles by function
        region_style = button_base_style % (UI_DARK_BG, UI_SECONDARY_TEXT, UI_WOOD_DARK) + f"""
            QPushButton {{
                background-color: {UI_WOOD_MEDIUM};
                color: {UI_LIGHT_TEXT};
                border: 1px solid {UI_WOOD_LIGHT};
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_LIGHT};
                border: 1px solid {UI_ACCENT_COLOR};
            }}
            QPushButton:pressed {{
                background-color: {UI_ACCENT_DARK};
            }}
        """
        
        play_style = button_base_style % (UI_DARK_BG, UI_SECONDARY_TEXT, UI_WOOD_DARK) + f"""
            QPushButton {{
                background-color: {UI_ACCENT_DARK};
                color: {UI_LIGHT_TEXT};
                border: 1px solid {UI_ACCENT_COLOR};
            }}
            QPushButton:hover {{
                background-color: {UI_ACCENT_COLOR};
                border: 1px solid {UI_LIGHT_TEXT};
            }}
            QPushButton:pressed {{
                background-color: {UI_ACCENT_DARK};
            }}
        """
        
        pause_style = button_base_style % (UI_DARK_BG, UI_SECONDARY_TEXT, UI_WOOD_DARK) + f"""
            QPushButton {{
                background-color: {UI_WOOD_DARK};
                color: {UI_LIGHT_TEXT};
                border: 1px solid {UI_WOOD_MEDIUM};
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
                border: 1px solid {UI_ACCENT_COLOR};
            }}
            QPushButton:pressed {{
                background-color: {UI_ACCENT_DARK};
            }}
        """
        
        stop_style = button_base_style % (UI_DARK_BG, UI_SECONDARY_TEXT, UI_WOOD_DARK) + f"""
            QPushButton {{
                background-color: {UI_WARNING_COLOR};
                color: {UI_LIGHT_TEXT};
                border: 1px solid #c75146;
            }}
            QPushButton:hover {{
                background-color: #c75146;
                border: 1px solid {UI_LIGHT_TEXT};
            }}
            QPushButton:pressed {{
                background-color: {UI_WARNING_COLOR};
            }}
        """
        
        tool_style = button_base_style % (UI_DARK_BG, UI_SECONDARY_TEXT, UI_WOOD_DARK) + f"""
            QPushButton {{
                background-color: {UI_PANEL_BG};
                color: {UI_LIGHT_TEXT};
                border: 1px solid {UI_WOOD_DARK};
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_DARK};
                border: 1px solid {UI_ACCENT_COLOR};
            }}
            QPushButton:pressed {{
                background-color: {UI_ACCENT_DARK};
            }}
        """
        
        # Select region button
        self.region_button = QPushButton()
        self.region_button.setIcon(qta.icon('fa5s.crop', color='white', scale_factor=1.0))
        self.region_button.clicked.connect(self.select_region)
        self.region_button.setStyleSheet(region_style)
        self.region_button.setToolTip("Select Region")
        control_layout.addWidget(self.region_button)
        
        # Start button
        self.start_button = QPushButton()
        self.start_button.setIcon(qta.icon('fa5s.play', color='white', scale_factor=1.0))
        self.start_button.clicked.connect(self.start_detection)
        self.start_button.setStyleSheet(play_style)
        self.start_button.setEnabled(False)  # Initially disabled until region is selected
        self.start_button.setToolTip("Start Detection")
        control_layout.addWidget(self.start_button)
        
        # Pause/Resume button
        self.pause_button = QPushButton()
        self.pause_button.setIcon(qta.icon('fa5s.pause', color='white', scale_factor=1.0))
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setStyleSheet(pause_style)
        self.pause_button.setToolTip("Pause/Resume")
        control_layout.addWidget(self.pause_button)
        
        # Stop button
        self.stop_button = QPushButton()
        self.stop_button.setIcon(qta.icon('fa5s.stop', color='white', scale_factor=1.0))
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setStyleSheet(stop_style)
        self.stop_button.setToolTip("Stop Detection")
        control_layout.addWidget(self.stop_button)
        
        # Add spacer between main controls and tools
        control_layout.addSpacing(16)
        
        # Capture reference button
        self.ref_button = QPushButton()
        self.ref_button.setIcon(qta.icon('fa5s.camera', color='white', scale_factor=1.0))
        self.ref_button.clicked.connect(self.capture_reference)
        self.ref_button.setStyleSheet(tool_style)
        self.ref_button.setEnabled(False)  # Initially disabled until region is selected
        self.ref_button.setToolTip("Capture Reference Frame")
        control_layout.addWidget(self.ref_button)
        
        # Settings button
        settings_button = QPushButton()
        settings_button.setIcon(qta.icon('fa5s.cog', color='white', scale_factor=1.0))
        settings_button.setStyleSheet(tool_style)
        settings_button.setToolTip("Settings")
        settings_button.clicked.connect(lambda: self.tab_widget.setCurrentIndex(2))  # Switch to Settings tab
        control_layout.addWidget(settings_button)
        
        # Stats button
        stats_button = QPushButton()
        stats_button.setIcon(qta.icon('fa5s.chart-bar', color='white', scale_factor=1.0))
        stats_button.setStyleSheet(tool_style)
        stats_button.setToolTip("Statistics")
        stats_button.clicked.connect(lambda: self.tab_widget.setCurrentIndex(3))  # Switch to Statistics tab
        control_layout.addWidget(stats_button)
        
        # Add the control bar to the viz layout
        visualization_layout.addWidget(control_bar)
        
        # Add to main top panel
        top_layout.addWidget(visualization_section)
        
        # Create the activity graph visualization here instead of in the sidebar
        self.activity_graph_canvas = ActivityGraphCanvas()

        # Bottom container for logs and tabs
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(8, 6, 8, 6)
        bottom_layout.setSpacing(6)
        
        # Create tab widget for console and sidebar sections
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 6px;
                background-color: {UI_PANEL_BG};
                top: -1px;
            }}
            QTabWidget::tab-bar {{
                alignment: left;
                left: 0px;
                right: 0px;
            }}
            QTabBar::tab {{
                background-color: {UI_DARK_BG};
                color: {UI_SECONDARY_TEXT};
                border: 1px solid {UI_WOOD_DARK};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 5px 10px;
                margin-right: 0px;
                min-width: 0;
            }}
            QTabBar::tab:selected {{
                background-color: {UI_PANEL_BG};
                color: {UI_LIGHT_TEXT};
                border-bottom: none;
            }}
            QTabBar::tab:hover {{
                background-color: {UI_WOOD_DARK};
            }}
        """)
        
        # Set tab bar to expand tabs to fill width
        self.tab_widget.tabBar().setExpanding(True)
        
        # Create clear log button for the tab widget corner
        clear_button = QPushButton()
        clear_button.setIcon(qta.icon('fa5s.eraser', color='#aaaaaa', scale_factor=0.8))
        clear_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_PANEL_BG};
                border: none;
                border-radius: 3px;
                padding: 2px;
                margin: 2px 5px 0px 0px;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_DARK};
            }}
        """)
        clear_button.setToolTip("Clear Console")
        clear_button.clicked.connect(self.clear_logs)
        
        # Add clear button to the right corner of the tab widget
        self.tab_widget.setCornerWidget(clear_button, Qt.Corner.TopRightCorner)
        
        # 1. Console Tab
        console_tab = QWidget()
        console_layout = QVBoxLayout(console_tab)
        console_layout.setContentsMargins(6, 12, 6, 6)
        console_layout.setSpacing(4)
        
        # Create the text console for logs with focused styling
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {UI_DARK_BG};
                color: {UI_SECONDARY_TEXT};
                border: none;
                border-radius: 4px;
                padding: 6px;
                font-family: "Consolas", monospace;
                font-size: 8pt;
            }}
        """)
        
        # Customize font for logs - use monospace for better readability
        mono_font = self.log_console.font()
        mono_font.setFamily("Consolas")
        mono_font.setPointSize(8)
        self.log_console.setFont(mono_font)
        
        # Set fixed maximum document size to prevent memory issues
        document = self.log_console.document()
        document.setMaximumBlockCount(200)  # Limit to 200 lines of logs
        
        # Remove the old clear button and header layout
        # Add log console directly to the layout
        console_layout.addWidget(self.log_console)
        
        # 2. Activity Graph Tab
        activity_tab = QWidget()
        activity_layout = QVBoxLayout(activity_tab)
        activity_layout.setContentsMargins(6, 6, 6, 6)
        activity_layout.setSpacing(4)
        activity_layout.addWidget(self.activity_graph_canvas)
        
        # 3. Settings Tab - Create from the sidebar settings section
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setContentsMargins(6, 6, 6, 6)
        settings_layout.setSpacing(6)
        
        # Threshold
        threshold_widget = QWidget()
        threshold_layout = QGridLayout(threshold_widget)
        threshold_layout.setContentsMargins(0, 0, 0, 0)
        
        threshold_label = QLabel("Detection Threshold:")
        threshold_layout.addWidget(threshold_label, 0, 0)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(1)
        self.threshold_slider.setMaximum(50)
        self.threshold_slider.setValue(int(DEFAULT_THRESHOLD * 100))
        self.threshold_slider.setTracking(True)
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        threshold_layout.addWidget(self.threshold_slider, 0, 1)
        
        self.threshold_value = QLabel(f"{DEFAULT_THRESHOLD:.2f}")
        self.threshold_value.setMinimumWidth(36)
        self.threshold_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        threshold_layout.addWidget(self.threshold_value, 0, 2)
        
        settings_layout.addWidget(threshold_widget)
        
        # Cooldown time
        cooldown_widget = QWidget()
        cooldown_layout = QGridLayout(cooldown_widget)
        cooldown_layout.setContentsMargins(0, 0, 0, 0)
        
        cooldown_label = QLabel("Detection Cooldown (s):")
        cooldown_layout.addWidget(cooldown_label, 0, 0)
        
        self.cooldown_entry = QLineEdit(str(DEFAULT_DETECTION_COOLDOWN))
        self.cooldown_entry.setFixedWidth(50)
        cooldown_layout.addWidget(self.cooldown_entry, 0, 1)
        
        settings_layout.addWidget(cooldown_widget)
        
        # Fishing key
        key_widget = QWidget()
        key_layout = QGridLayout(key_widget)
        key_layout.setContentsMargins(0, 0, 0, 0)
        
        key_label = QLabel("Fishing Key:")
        key_layout.addWidget(key_label, 0, 0)
        
        self.fishing_key_entry = QLineEdit(DEFAULT_FISHING_KEY)
        self.fishing_key_entry.setFixedWidth(50)
        key_layout.addWidget(self.fishing_key_entry, 0, 1)
        
        settings_layout.addWidget(key_widget)
        
        # Region size
        size_widget = QWidget()
        size_layout = QGridLayout(size_widget)
        size_layout.setContentsMargins(0, 0, 0, 0)
        
        size_label = QLabel("Region Size (px):")
        size_layout.addWidget(size_label, 0, 0)
        
        self.size_entry = QLineEdit("50")
        self.size_entry.setFixedWidth(50)
        size_layout.addWidget(self.size_entry, 0, 1)
        
        settings_layout.addWidget(size_widget)
        
        # Checkboxes
        checkboxes_widget = QWidget()
        checkboxes_layout = QVBoxLayout(checkboxes_widget)
        checkboxes_layout.setContentsMargins(0, 0, 0, 0)
        checkboxes_layout.setSpacing(6)
        
        self.high_performance_checkbox = QCheckBox("High Performance Mode")
        self.high_performance_checkbox.setChecked(DEFAULT_HIGH_PERFORMANCE)
        self.high_performance_checkbox.stateChanged.connect(self.update_high_performance)
        checkboxes_layout.addWidget(self.high_performance_checkbox)
        
        self.respect_fullscreen_checkbox = QCheckBox("Respect Fullscreen Apps")
        self.respect_fullscreen_checkbox.setChecked(DEFAULT_RESPECT_FULLSCREEN)
        self.respect_fullscreen_checkbox.stateChanged.connect(self.update_respect_fullscreen)
        checkboxes_layout.addWidget(self.respect_fullscreen_checkbox)
        
        self.direct_control_checkbox = QCheckBox("Direct Control Mode")
        self.direct_control_checkbox.setChecked(DEFAULT_DIRECT_CONTROL)
        self.direct_control_checkbox.stateChanged.connect(self.update_direct_control)
        checkboxes_layout.addWidget(self.direct_control_checkbox)
        
        settings_layout.addWidget(checkboxes_widget)
        
        # Apply settings button
        apply_button = QPushButton("Apply Settings")
        apply_button.clicked.connect(self.apply_settings)
        settings_layout.addWidget(apply_button)
        
        settings_layout.addStretch()
        
        # 4. Statistics Tab
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)
        stats_layout.setContentsMargins(6, 6, 6, 6)
        stats_layout.setSpacing(3)
        
        # Add descriptive header
        header_text = "Real-time monitoring statistics:"
        header_label = QLabel(header_text)
        header_label.setStyleSheet(f"color: {UI_LIGHT_TEXT}; font-size: 9pt;")
        header_label.setWordWrap(True)
        stats_layout.addWidget(header_label)
        
        # Create 2-column layout for statistics
        stats_columns = QHBoxLayout()
        stats_layout.addLayout(stats_columns)
        
        # Left column for activity and performance stats
        left_column = QWidget()
        left_column_layout = QVBoxLayout(left_column)
        left_column_layout.setContentsMargins(3, 3, 3, 3)
        left_column_layout.setSpacing(3)
        
        # Activity Statistics
        activity_group = QGroupBox("Activity")
        activity_group.setStyleSheet(f"color: {UI_ACCENT_COLOR}; font-weight: bold;")
        activity_layout = QGridLayout(activity_group)
        activity_layout.setContentsMargins(6, 12, 6, 6)
        activity_layout.setSpacing(3)
        
        activity_layout.addWidget(QLabel("Detections:"), 0, 0)
        self.detections_label = QLabel("0")
        activity_layout.addWidget(self.detections_label, 0, 1)
        
        activity_layout.addWidget(QLabel("Runtime:"), 1, 0)
        self.runtime_label = QLabel("00:00:00")
        activity_layout.addWidget(self.runtime_label, 1, 1)
        
        activity_layout.addWidget(QLabel("Rate:"), 2, 0)
        self.rate_label = QLabel("0.0/min")
        activity_layout.addWidget(self.rate_label, 2, 1)
        
        activity_layout.addWidget(QLabel("Avg Interval:"), 3, 0)
        self.interval_label = QLabel("0.0s")
        activity_layout.addWidget(self.interval_label, 3, 1)
        
        activity_layout.addWidget(QLabel("Last Detection:"), 4, 0)
        self.last_detection_label = QLabel("None")
        activity_layout.addWidget(self.last_detection_label, 4, 1)
        
        activity_layout.addWidget(QLabel("Success Rate:"), 5, 0)
        self.success_rate_label = QLabel("0%")
        activity_layout.addWidget(self.success_rate_label, 5, 1)
        
        left_column_layout.addWidget(activity_group)
        
        # Performance Metrics
        performance_group = QGroupBox("Performance")
        performance_group.setStyleSheet(f"color: {UI_ACCENT_COLOR}; font-weight: bold;")
        performance_layout = QGridLayout(performance_group)
        performance_layout.setContentsMargins(6, 12, 6, 6)
        performance_layout.setSpacing(3)
        
        performance_layout.addWidget(QLabel("FPS:"), 0, 0)
        self.fps_label = QLabel("0")
        performance_layout.addWidget(self.fps_label, 0, 1)
        
        performance_layout.addWidget(QLabel("CPU Usage:"), 1, 0)
        self.cpu_usage_label = QLabel("0%")
        performance_layout.addWidget(self.cpu_usage_label, 1, 1)
        
        performance_layout.addWidget(QLabel("Latency:"), 2, 0)
        self.latency_label = QLabel("0ms")
        performance_layout.addWidget(self.latency_label, 2, 1)
        
        left_column_layout.addWidget(performance_group)
        left_column_layout.addStretch()
        
        # Right column for settings and system info
        right_column = QWidget()
        right_column_layout = QVBoxLayout(right_column)
        right_column_layout.setContentsMargins(3, 3, 3, 3)
        right_column_layout.setSpacing(3)
        
        # Current Settings
        settings_group = QGroupBox("Current Settings")
        settings_group.setStyleSheet(f"color: {UI_ACCENT_COLOR}; font-weight: bold;")
        settings_layout = QGridLayout(settings_group)
        settings_layout.setContentsMargins(6, 12, 6, 6)
        settings_layout.setSpacing(3)
        
        settings_layout.addWidget(QLabel("Threshold:"), 0, 0)
        self.monitor_threshold = QLabel(f"{DEFAULT_THRESHOLD:.2f}")
        settings_layout.addWidget(self.monitor_threshold, 0, 1)
        
        settings_layout.addWidget(QLabel("Cooldown:"), 1, 0)
        self.monitor_cooldown = QLabel(f"{DEFAULT_DETECTION_COOLDOWN}s")
        settings_layout.addWidget(self.monitor_cooldown, 1, 1)
        
        settings_layout.addWidget(QLabel("Key:"), 2, 0)
        self.monitor_key = QLabel(DEFAULT_FISHING_KEY)
        settings_layout.addWidget(self.monitor_key, 2, 1)
        
        settings_layout.addWidget(QLabel("Mode:"), 3, 0)
        self.monitor_mode = QLabel("High Perf" if DEFAULT_HIGH_PERFORMANCE else "Standard")
        settings_layout.addWidget(self.monitor_mode, 3, 1)
        
        right_column_layout.addWidget(settings_group)
        
        # System Info
        system_group = QGroupBox("System")
        system_group.setStyleSheet(f"color: {UI_ACCENT_COLOR}; font-weight: bold;")
        system_layout = QGridLayout(system_group)
        system_layout.setContentsMargins(6, 12, 6, 6)
        system_layout.setSpacing(3)
        
        system_layout.addWidget(QLabel("Region:"), 0, 0)
        self.region_size_label = QLabel("None")
        system_layout.addWidget(self.region_size_label, 0, 1)
        
        system_layout.addWidget(QLabel("Status:"), 1, 0)
        self.monitor_status = QLabel("Idle")
        system_layout.addWidget(self.monitor_status, 1, 1)
        
        right_column_layout.addWidget(system_group)
        right_column_layout.addStretch()
        
        # Add columns to layout
        stats_columns.addWidget(left_column)
        stats_columns.addWidget(right_column)
        
        stats_layout.addStretch()
        
        # 5. Region Info Tab
        region_tab = QWidget()
        region_layout = QVBoxLayout(region_tab)
        region_layout.setContentsMargins(6, 6, 6, 6)
        region_layout.setSpacing(4)
        
        self.region_info_label = QLabel("No region selected")
        self.region_info_label.setWordWrap(True)
        self.region_info_label.setStyleSheet(f"color: {UI_LIGHT_TEXT}; padding: 2px;")
        region_layout.addWidget(self.region_info_label)
        region_layout.addStretch()
        
        # Add all tabs to the tab widget
        self.tab_widget.addTab(console_tab, "Console")
        self.tab_widget.addTab(activity_tab, "Activity")
        self.tab_widget.addTab(settings_tab, "Settings")
        self.tab_widget.addTab(stats_tab, "Statistics")
        self.tab_widget.addTab(region_tab, "Info")
        
        # Add tab widget to bottom layout
        bottom_layout.addWidget(self.tab_widget)
        
        # Add containers to splitter
        self.main_splitter.addWidget(top_container)
        self.main_splitter.addWidget(bottom_container)
        self.main_splitter.setSizes([3, 2])  # 60% top, 40% bottom
        
    def log(self, message):
        """Add message to log queue without timestamp"""
        self.log_queue.put(message)
        
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
            
    def update_threshold(self, value):
        """Update threshold label when slider is moved"""
        threshold_value = value / 100.0
        self.threshold_value.setText(f"{threshold_value:.2f}")
            
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
                    
                if self.detector.detection_cooldown != cooldown_value:
                    self.log(f"Cooldown changed: {self.detector.detection_cooldown}s -> {cooldown_value}s")
                
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
        
        # Using the new TkRegionSelector which follows the autofisher.py implementation
        selector = TkRegionSelector(self, size)
        
        # Get selected region
        region = selector.capture_preview_and_select()
        if region:
            self.set_region(region)
            return True
        else:
            self.log("Region selection cancelled or failed")
            return False
            
    def restore_window(self, was_maximized, geometry_before):
        """Restore window after region selection"""
        self.log("Restoring main window...")
        if was_maximized:
            self.showMaximized()
        else:
            self.showNormal()
            self.setGeometry(geometry_before)
            
        self.log("Window restored")
            
    def set_region(self, region):
        """Set the region to monitor"""
        if not region:
            self.log("No region selected")
            return False
            
        if not self.detector:
            self.detector = PixelChangeDetector(self)
            
        # Set the region in the detector
        self.detector.region = region
        
        # Get region dimensions
        left, top, right, bottom = region
        width = right - left
        height = bottom - top
        
        self.log(f"Region selected: ({left},{top}) to ({right},{bottom}), size: {width}×{height}")
        
        # Update UI
        self.region_info_label.setText(
            f"Selected Region:\n"
            f"Position: ({left}, {top}) to ({right}, {bottom})\n"
            f"Size: {width}×{height} pixels\n"
            f"Aspect Ratio: {width / height if height > 0 else 0:.2f}"
        )
        
        # Update UI state
        if not self.detection_running:
            # Enable start button now that we have a valid region
            self.start_button.setEnabled(True)
            self.ref_button.setEnabled(True)
            
            self.log(f"Region selection completed at: {left},{top} to {right},{bottom}")
            
        # Start live preview automatically
        self.start_live_preview()
        
        return True
        
    def start_live_preview(self):
        """Start a live preview of the selected region"""
        if not self.detector or not self.detector.region:
            self.log("No region selected for preview")
            return False
            
        self.log("Starting live preview of selected region...")
        
        # Create preview thread if it doesn't exist
        if not hasattr(self, 'preview_thread') or not self.preview_thread.isRunning():
            from PyQt6.QtCore import QThread, pyqtSignal
            
            # Create a worker thread for preview
            class PreviewThread(QThread):
                preview_ready = pyqtSignal(object)
                
                def __init__(self, detector, parent=None):
                    super().__init__(parent)
                    self.detector = detector
                    self.running = True
                    
                def run(self):
                    import time
                    while self.running:
                        try:
                            # Capture frame from selected region
                            frame = self.detector.capture_screen()
                            if frame is not None:
                                # Emit signal with the frame
                                self.preview_ready.emit(frame)
                            time.sleep(0.1)  # 10 FPS preview
                        except Exception as e:
                            print(f"Preview error: {e}")
                            time.sleep(0.5)
                            
                def stop(self):
                    self.running = False
                    
            # Create and start the thread
            self.preview_thread = PreviewThread(self.detector, self)
            self.preview_thread.preview_ready.connect(self.update_preview)
            self.preview_thread.start()
            
            # Update UI to show we're in preview mode
            self.status_label.setText("Status: Live Preview")
            self.log("Live preview started. Click 'start' to begin detection.")
            
            return True
        else:
            self.log("Preview already running")
            return False
            
    def update_preview(self, frame):
        """Update the visualization with the preview frame"""
        if frame is not None:
            # Update the visualization with the current frame - use raw frame without modifications
            if hasattr(self, 'viz_canvas'):
                # Store the raw frame in the detector for reference
                if self.detector:
                    self.detector.color_frame = frame
                
                # Display the raw frame
                self.viz_canvas.update_image(frame, None)
            
            # If we have a detector with difference calculation capability, use it
            if self.detector and hasattr(self.detector, 'reference_frame') and self.detector.reference_frame is not None:
                try:
                    # Calculate difference from reference frame
                    diff_frame, change_percent = self.detector.calculate_frame_difference(frame, self.detector.reference_frame)
                    
                    # Store the diff frame in the detector
                    self.detector.diff_frame = diff_frame
                    
                    # Update the visualization with the difference frame
                    if hasattr(self, 'viz_canvas'):
                        self.viz_canvas.update_diff(diff_frame)
                    
                    # Add to activity history
                    if hasattr(self.detector, 'change_history'):
                        self.detector.change_history.append(change_percent)
                        if len(self.detector.change_history) > 1000:
                            self.detector.change_history = self.detector.change_history[-1000:]
                            
                    # Update activity graph
                    if hasattr(self, 'activity_graph_canvas'):
                        self.activity_graph_canvas.update(self.detector.change_history, self.detector.THRESHOLD)
                        
                    # Show current change percentage and debug info
                    debug_info = (
                        f"Status: Live Preview | "
                        f"Change: {change_percent:.4f} | "
                        f"Threshold: {self.detector.THRESHOLD:.4f} | "
                        f"Frame Size: {frame.shape[1]}x{frame.shape[0]}"
                    )
                    self.status_label.setText(debug_info)
                    
                    # Check for threshold crossing for debugging
                    if change_percent > self.detector.THRESHOLD:
                        self.log(f"Threshold crossed: {change_percent:.4f} > {self.detector.THRESHOLD:.4f}")
                    
                except Exception as e:
                    print(f"Error in preview update: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                # No reference frame yet, capture one
                if self.detector:
                    self.log("Capturing initial reference frame...")
                    self.detector.reference_frame = frame.copy()
                    if hasattr(frame, 'copy'):
                        self.detector.reference_color_frame = frame.copy()
                    self.log("Initial reference frame captured")
        
    def stop_live_preview(self):
        """Stop the live preview"""
        if hasattr(self, 'preview_thread') and self.preview_thread.isRunning():
            self.preview_thread.stop()
            self.log("Stopping live preview...")
            # Wait a bit for the thread to finish
            self.preview_thread.wait(1000)  # Wait up to 1 second for thread to finish
            self.log("Live preview stopped")
            self.status_label.setText("Status: Ready")
            return True
        return False
        
    def start_detection(self):
        """Start the detection process"""
        # Stop any running preview first
        self.stop_live_preview()
        
        # Continue with normal detection start
        if not self.detector or not self.detector.region:
            self.log("No region selected for detection")
            return False
            
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
            
        # Update the activity graph in its own tab
        if hasattr(self.detector, 'change_history') and self.detector.change_history:
            self.activity_graph_canvas.update(self.detector.change_history, self.detector.THRESHOLD)
            
    def increment_detection_count(self):
        """Increment detection count when signal is received"""
        self.total_detections += 1
        
        # Update UI immediately
        self.detections_label.setText(str(self.total_detections))
        
        # Log the detection
        self.log(f"Detection #{self.total_detections} triggered!")
        
    def update_statistics(self):
        """Update statistics labels"""
        # Only update if detector exists
        if not self.detector:
            return
            
        # Update run time
        elapsed = time.time() - self.start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        self.runtime_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # Update detection count and rate
        self.detections_label.setText(str(self.total_detections))
        
        if elapsed > 0:
            rate_per_min = (self.total_detections / elapsed) * 60
            self.rate_label.setText(f"{rate_per_min:.1f}/min")
            
            # Calculate average interval if we have detections
            if self.total_detections > 1:
                avg_interval = elapsed / self.total_detections
                self.interval_label.setText(f"{avg_interval:.1f}s")
        
        # Update Last Detection time
        if hasattr(self.detector, 'last_detection_time') and self.detector.last_detection_time > 0:
            time_since = time.time() - self.detector.last_detection_time
            if time_since < 60:
                self.last_detection_label.setText(f"{time_since:.1f}s ago")
            elif time_since < 3600:
                self.last_detection_label.setText(f"{time_since/60:.1f}m ago")
            else:
                self.last_detection_label.setText(f"{time_since/3600:.1f}h ago")
        else:
            self.last_detection_label.setText("None")
        
        # Update Success Rate (if available)
        success_attempts = getattr(self.detector, 'successful_detections', 0)
        total_attempts = max(1, getattr(self.detector, 'total_detection_attempts', 0))
        if total_attempts > 0:
            success_rate = (success_attempts / total_attempts) * 100
            self.success_rate_label.setText(f"{success_rate:.1f}%")
        else:
            self.success_rate_label.setText("0%")
        
        # Update Performance Metrics
        if hasattr(self.detector, 'current_fps'):
            fps_value = self.detector.current_fps
            self.fps_label.setText(f"{fps_value:.1f}")
            
            # Also update the status bar FPS if it exists
            if hasattr(self, 'monitor_fps'):
                self.monitor_fps.setText(f"{int(fps_value)}")
        else:
            # Estimate FPS based on high performance mode
            estimated_fps = 10.0 if self.detector.high_performance_mode else 5.0
            self.fps_label.setText(f"~{estimated_fps:.1f}")
            
            # Also update the status bar FPS if it exists
            if hasattr(self, 'monitor_fps'):
                self.monitor_fps.setText(f"{int(estimated_fps)}")
            
        # Get CPU usage if available
        try:
            import psutil
            cpu_percent = psutil.cpu_percent(interval=None)
            self.cpu_usage_label.setText(f"{cpu_percent:.1f}%")
        except (ImportError, AttributeError):
            self.cpu_usage_label.setText("N/A")
            
        # Update processing latency if available
        if hasattr(self.detector, 'avg_process_time'):
            latency_ms = self.detector.avg_process_time * 1000
            self.latency_label.setText(f"{latency_ms:.1f}ms")
        else:
            self.latency_label.setText("N/A")
            
        # Update Current Settings
        self.monitor_threshold.setText(f"{self.detector.THRESHOLD:.2f}")
        self.monitor_cooldown.setText(f"{self.detector.detection_cooldown:.1f}s")
        self.monitor_key.setText(self.detector.fishing_key)
        self.monitor_mode.setText("High Perf" if self.detector.high_performance_mode else "Standard")
        
        # Update System Info
        if self.detector.region:
            left, top, right, bottom = self.detector.region
            width = right - left
            height = bottom - top
            self.region_size_label.setText(f"{width}×{height}")
        else:
            self.region_size_label.setText("None")
            
        # Update Status
        if self.detection_running:
            if getattr(self.detector, 'paused', False):
                self.monitor_status.setText("Paused")
            else:
                self.monitor_status.setText("Running")
        else:
            self.monitor_status.setText("Idle")

    def closeEvent(self, event):
        """Handle application close event"""
        # Stop any running threads
        self.stop_live_preview()
        if hasattr(self, 'detector') and self.detector:
            self.detector.stop_detection()
        
        # Call the parent class closeEvent
        super().closeEvent(event)