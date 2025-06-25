import sys
import os
import time
import math
import threading
import datetime
from typing import Callable, Optional, List, Tuple
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, 
                            QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, 
                            QScrollArea, QSlider, QLineEdit, QTextEdit, QGroupBox)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, pyqtSignal, QPropertyAnimation, QEasingCurve, QSize, QObject
from PyQt6.QtGui import QFont, QColor, QPalette, QPixmap, QFontMetrics, QCursor, QMouseEvent
from PyQt6.QtGui import QMoveEvent, QScreen

# For Windows specific functionality - only import if on Windows
if sys.platform == 'win32':
    try:
        import win32gui
        import win32con
        import win32process
        import win32api
        WINDOWS_SUPPORT = True
    except ImportError:
        WINDOWS_SUPPORT = False
else:
    WINDOWS_SUPPORT = False

# Let the OS handle high DPI scaling, but we'll make our own adjustments
# for element sizing and positioning

class DraggableFrame(QFrame):
    """Custom QFrame that can be dragged"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drag_start_position = None
        # Using function references with proper type annotations
        self.start_drag_func: Optional[Callable] = None
        self.stop_drag_func: Optional[Callable] = None
        self.on_drag_func: Optional[Callable] = None
        
    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        if self.start_drag_func is not None:
            self.start_drag_func(a0)
        super().mousePressEvent(a0)
        
    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        if self.stop_drag_func is not None:
            self.stop_drag_func(a0)
        super().mouseReleaseEvent(a0)
        
    def mouseMoveEvent(self, a0: QMouseEvent | None) -> None:
        if self.on_drag_func is not None:
            self.on_drag_func(a0)
        super().mouseMoveEvent(a0)

class OverlayAutoFisher(QMainWindow):
    def __init__(self, parent=None):
        # Create main window
        super().__init__(parent)
        self.is_toplevel = parent is not None
            
        # Configure the window
        self.setWindowTitle("AutoFisher v0.0.01a")
        self.setGeometry(100, 100, 380, 580)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Colors and style
        self.colors = {
            'bg_dark': '#181914',         # Oak wood dark
            'bg_term': '#23281e',         # Slightly lighter for panels
            'bg_lighter': '#2e3324',      # Lighter panel
            'bg_alt': '#3e3c2f',          # Alternative dark
            'text': '#F8F5E3',            # Warm off-white
            'text_bright': '#FFFFFF',
            'text_dim': '#A3A08C',        # Dimmed text
            'accent': '#A3D977',          # Matcha green
            'accent_alt': '#7CB518',      # Deeper matcha
            'accent_bright': '#C4E6B5',   # Bright matcha
            'accent_special': '#E6CBA5',  # Oak highlight
            'green': '#A3D977',           # Matcha green
            'green_alt': '#BCD9B4',
            'border': '#6B6E58',
            'border_light': '#A3A08C',
            'cursor': '#A3D977',
            'alert': '#FF4D4D',
            'warning': '#FFB940',
            'selection': '#A3D977'
        }
        
        # Track if window is minimized
        self.is_minimized = False
        self.minimized_width = 50
        self.minimized_height = 50
        self.expanded_width = 380
        self.expanded_height = 580
        
        # Game window tracking
        self.last_move_target = None
        self.game_window = None
        self.game_window_name = "Play Together"
        self.offset_x = 16  # Offset from game window left edge
        self.offset_y = 36  # Offset from game window top edge
        self.tracking_active = False
        self.tracking_thread = None
        
        # Smooth movement variables
        self.target_x = 0
        self.target_y = 0
        self.current_x = 0
        self.current_y = 0
        self.is_animating = False
        self.animation_speed = 0.15  # Lower = faster animation (0-1)
        self.animation_min_step = 1  # Minimum pixel step for small movements
        self.animation_timer = None  # Animation timer
        
        # Track mouse position for dragging
        self.drag_start_position = None
        
        # Create the UI (expanded state by default)
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.central_widget.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: 2px solid {self.colors['border']};")
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.main_frame = None
        self.minimized_frame = None
        self.create_widgets()
        
        self.hwnd = self.winId().__int__()

        # Only start game window tracking on Windows
        if WINDOWS_SUPPORT:
            if self.find_game_window():
                # If game window found, position directly on it
                self.start_tracking()
                self.add_log("Game window found - overlay positioned on game")
            else:
                # If no game window found, use default position
                self.position_default()
                self.add_log("No game window found - using default position")
        else:
            self.position_default()
            self.add_log("Game window tracking is only available on Windows.")
    
    def create_widgets(self):
        # Create expanded view
        self.create_expanded_view()
        
        # Create minimized view (but don't show it yet)
        self.create_minimized_view()     
    
    def create_expanded_view(self):
        """Create the expanded view with AutoFisher UI"""
        # Adjust for DPI scaling
        dpi_scale = self.get_dpi_scale()
        
        # Main frame
        self.main_frame = QFrame(self.central_widget)
        self.main_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        self.main_layout.addWidget(self.main_frame)
        
        # Main frame layout
        self.expanded_layout = QVBoxLayout(self.main_frame)
        self.expanded_layout.setContentsMargins(0, 0, 0, 0)
        self.expanded_layout.setSpacing(0)
        
        # Title bar with controls
        self.title_bar = DraggableFrame()
        self.title_bar.start_drag_func = self.start_drag
        self.title_bar.stop_drag_func = self.stop_drag
        self.title_bar.on_drag_func = self.on_drag
        title_height = int(30 / dpi_scale)  # Adjust for scaling
        self.title_bar.setStyleSheet(f"background-color: {self.colors['bg_term']}; height: {title_height}px;")
        
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 0, 0, 0)
        title_layout.setSpacing(0)
        
        # Title label with adjusted font size for DPI
        font_size = int(10 / dpi_scale) if dpi_scale > 1.0 else 10
        self.title_label = QLabel("AutoFisher v0.0.01a")
        self.title_label.setStyleSheet(f"color: {self.colors['accent']}; font-weight: bold; font-size: {font_size}pt;")
        title_layout.addWidget(self.title_label)
        
        # Control buttons
        btn_frame = QFrame()
        btn_frame.setStyleSheet(f"background-color: {self.colors['bg_term']};")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(0)
        
        # Minimize/Expand toggle button
        self.toggle_button = QPushButton("−")
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_term']};
                color: {self.colors['text']};
                border: none;
                font-weight: bold;
                font-size: 10pt;
                width: 30px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_lighter']};
            }}
        """)
        self.toggle_button.clicked.connect(self.toggle_minimize)
        btn_layout.addWidget(self.toggle_button)
        
        # Close button
        self.close_button = QPushButton("×")
        self.close_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_term']};
                color: {self.colors['alert']};
                border: none;
                font-weight: bold;
                font-size: 10pt;
                width: 30px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_lighter']};
            }}
        """)
        self.close_button.clicked.connect(self.close)
        btn_layout.addWidget(self.close_button)
        
        title_layout.addWidget(btn_frame, alignment=Qt.AlignmentFlag.AlignRight)
        self.expanded_layout.addWidget(self.title_bar)
        
        # Content area
        self.content_frame = QFrame()
        self.content_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; margin: 5px;")
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(5, 5, 5, 5)
        content_layout.setSpacing(0)
        
        # Create AutoFisher UI sections
        self.create_settings_section(content_layout)
        self.create_monitoring_section(content_layout)
        self.create_control_section(content_layout)
        self.create_status_section(content_layout)
        self.create_log_section(content_layout)
        
        self.expanded_layout.addWidget(self.content_frame)
    
    def create_settings_section(self, parent_layout):
        """Create settings section similar to AutoFisher"""
        settings_frame = QGroupBox("SETTINGS")
        settings_frame.setStyleSheet(f"""
            QGroupBox {{
                font-size: 9pt;
                color: {self.colors['accent']};
                background-color: {self.colors['bg_dark']};
                border: 1px solid {self.colors['border']};
                margin-top: 8px;
                padding: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 5px;
                top: 0px;
                padding: 0px 5px 0px 5px;
            }}
        """)
        settings_layout = QGridLayout(settings_frame)
        settings_layout.setContentsMargins(4, 15, 4, 4)
        settings_layout.setSpacing(2)

        # Threshold (row 0)
        threshold_label = QLabel("Threshold")
        threshold_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 10pt;")
        settings_layout.addWidget(threshold_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        
        threshold_frame = QFrame()
        threshold_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        threshold_layout = QHBoxLayout(threshold_frame)
        threshold_layout.setContentsMargins(0, 0, 0, 0)
        
        self.threshold_var = 0.05
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(1, 50)  # 0.01 to 0.50
        self.threshold_slider.setValue(int(self.threshold_var * 100))
        self.threshold_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {self.colors['bg_lighter']};
                height: 8px;
                border-radius: 4px;
            }}
            QSlider::handle:horizontal {{
                background: {self.colors['accent']};
                width: 12px;
                margin: -2px 0;
                border-radius: 6px;
            }}
        """)
        self.threshold_slider.valueChanged.connect(self.on_threshold_changed)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_label = QLabel("0.05")
        self.threshold_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 10pt; min-width: 40px;")
        threshold_layout.addWidget(self.threshold_label)
        
        settings_layout.addWidget(threshold_frame, 0, 1)

        # Region Size (row 1)
        region_label = QLabel("Region Size")
        region_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 10pt;")
        settings_layout.addWidget(region_label, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        
        region_size_frame = QFrame()
        region_size_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        region_layout = QHBoxLayout(region_size_frame)
        region_layout.setContentsMargins(0, 0, 0, 0)
        
        self.size_var = "50"
        self.size_entry = QLineEdit(self.size_var)
        self.size_entry.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['text']};
                selection-background-color: {self.colors['selection']};
                selection-color: {self.colors['text_bright']};
                border: 1px solid {self.colors['border']};
                padding: 2px;
                border-radius: 0px;
                font-size: 10pt;
                max-width: 60px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors['accent']};
            }}
        """)
        region_layout.addWidget(self.size_entry)
        
        px_label = QLabel("px")
        px_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 10pt;")
        region_layout.addWidget(px_label)
        region_layout.addStretch()
        
        settings_layout.addWidget(region_size_frame, 1, 1)

        # Cooldown (row 2)
        cooldown_label = QLabel("Cooldown")
        cooldown_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 10pt;")
        settings_layout.addWidget(cooldown_label, 2, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        
        cooldown_frame = QFrame()
        cooldown_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        cooldown_layout = QHBoxLayout(cooldown_frame)
        cooldown_layout.setContentsMargins(0, 0, 0, 0)
        
        self.cooldown_var = "5.0"
        self.cooldown_entry = QLineEdit(self.cooldown_var)
        self.cooldown_entry.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['text']};
                selection-background-color: {self.colors['selection']};
                selection-color: {self.colors['text_bright']};
                border: 1px solid {self.colors['border']};
                padding: 2px;
                border-radius: 0px;
                font-size: 10pt;
                max-width: 60px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors['accent']};
            }}
        """)
        cooldown_layout.addWidget(self.cooldown_entry)
        
        sec_label = QLabel("sec")
        sec_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 10pt;")
        cooldown_layout.addWidget(sec_label)
        cooldown_layout.addStretch()
        
        settings_layout.addWidget(cooldown_frame, 2, 1)

        # Fishing Key (row 3)
        fishing_key_label = QLabel("Fishing Key")
        fishing_key_label.setStyleSheet(f"color: {self.colors['text']}; font-size: 10pt;")
        settings_layout.addWidget(fishing_key_label, 3, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        
        fishing_key_frame = QFrame()
        fishing_key_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        fishing_key_layout = QHBoxLayout(fishing_key_frame)
        fishing_key_layout.setContentsMargins(0, 0, 0, 0)
        
        self.fishing_key_var = "f"
        self.fishing_key_entry = QLineEdit(self.fishing_key_var)
        self.fishing_key_entry.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['text']};
                selection-background-color: {self.colors['selection']};
                selection-color: {self.colors['text_bright']};
                border: 1px solid {self.colors['border']};
                padding: 2px;
                border-radius: 0px;
                font-size: 10pt;
                max-width: 40px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors['accent']};
            }}
        """)
        fishing_key_layout.addWidget(self.fishing_key_entry)
        fishing_key_layout.addStretch()
        
        settings_layout.addWidget(fishing_key_frame, 3, 1)
        
        # Apply Settings button
        apply_button_frame = QFrame()
        apply_button_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        apply_layout = QHBoxLayout(apply_button_frame)
        apply_layout.setContentsMargins(0, 8, 0, 0)
        apply_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['accent']};
                border: 1px solid {self.colors['border']};
                padding: 6px 10px;
                font-size: 10pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['accent_bright']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['accent_alt']};
            }}
        """)
        self.apply_button.clicked.connect(self.dummy_apply_settings)
        apply_layout.addWidget(self.apply_button)
        
        settings_layout.addWidget(apply_button_frame, 4, 0, 1, 2)
        
        parent_layout.addWidget(settings_frame)
    
    def on_threshold_changed(self, value):
        """Handle threshold slider change"""
        self.threshold_var = value / 100.0
        self.threshold_label.setText(f"{self.threshold_var:.2f}")
    
    def create_monitoring_section(self, parent_layout):
        """Create monitoring section similar to AutoFisher"""
        monitoring_frame = QGroupBox("MONITORING")
        monitoring_frame.setStyleSheet(f"""
            QGroupBox {{
                font-size: 9pt;
                color: {self.colors['accent']};
                background-color: {self.colors['bg_dark']};
                border: 1px solid {self.colors['border']};
                margin-top: 8px;
                padding: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 5px;
                top: 0px;
                padding: 0px 5px 0px 5px;
            }}
        """)
        
        monitoring_layout = QVBoxLayout(monitoring_frame)
        monitoring_layout.setContentsMargins(4, 15, 4, 4)
        
        # Stats details in two columns
        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        
        stats_layout = QGridLayout(stats_frame)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(1)
        
        self.stats_labels = {}
        stats_keys = [
            ("Detections", "total_detections"),
            ("Session Runtime", "session_runtime"),
            ("Detection Rate", "detections_per_hour"),
            ("Avg. Interval", "avg_interval"),
            ("Threshold", "current_threshold"),
            ("Cooldown", "cooldown"),
            ("Key Mapping", "key_mapping"),
            ("Processing FPS", "processing_fps")
        ]
        
        # Arrange in two columns
        for i, (label, key) in enumerate(stats_keys):
            row = i // 2
            col = i % 2
            l = QLabel(f"{label}: ...")
            l.setStyleSheet(f"color: {self.colors['text']}; font-size: 10pt;")
            stats_layout.addWidget(l, row, col, 1, 1, Qt.AlignmentFlag.AlignLeft)
            stats_layout.setColumnStretch(col, 1)
            self.stats_labels[key] = l
        
        monitoring_layout.addWidget(stats_frame)
        
        # Initialize with dummy values
        self.update_stats_display()
        
        parent_layout.addWidget(monitoring_frame)
    
    def create_control_section(self, parent_layout):
        """Create control section similar to AutoFisher"""
        control_frame = QGroupBox("CONTROL")
        control_frame.setStyleSheet(f"""
            QGroupBox {{
                font-size: 9pt;
                color: {self.colors['accent']};
                background-color: {self.colors['bg_dark']};
                border: 1px solid {self.colors['border']};
                margin-top: 8px;
                padding: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 5px;
                top: 0px;
                padding: 0px 5px 0px 5px;
            }}
        """)
        
        control_layout = QVBoxLayout(control_frame)
        control_layout.setContentsMargins(4, 15, 4, 4)
        
        # First row of buttons
        button_frame = QFrame()
        button_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(5, 4, 5, 4)
        button_layout.setSpacing(5)
        
        self.start_button = QPushButton("start")
        self.start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['green']};
                border: 1px solid {self.colors['border']};
                padding: 5px 10px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['green_alt']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['green']};
            }}
            QPushButton:disabled {{
                color: grey;
            }}
        """)
        self.start_button.clicked.connect(self.dummy_start)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("stop")
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['alert']};
                border: 1px solid {self.colors['border']};
                padding: 5px 10px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['alert']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['alert']};
            }}
            QPushButton:disabled {{
                color: grey;
            }}
        """)
        self.stop_button.clicked.connect(self.dummy_stop)
        button_layout.addWidget(self.stop_button)
        
        self.pause_button = QPushButton("pause")
        self.pause_button.setEnabled(False)
        self.pause_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['warning']};
                border: 1px solid {self.colors['border']};
                padding: 5px 10px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['warning']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['warning']};
            }}
            QPushButton:disabled {{
                color: grey;
            }}
        """)
        self.pause_button.clicked.connect(self.dummy_pause)
        button_layout.addWidget(self.pause_button)
        
        self.clear_button = QPushButton("clear-logs")
        self.clear_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['text_dim']};
                border: 1px solid {self.colors['border']};
                padding: 5px 10px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['text']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['text']};
            }}
        """)
        self.clear_button.clicked.connect(self.clear_logs)
        button_layout.addWidget(self.clear_button)
        
        control_layout.addWidget(button_frame)
        
        # Second row of buttons
        button_frame2 = QFrame()
        button_frame2.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        
        button_layout2 = QHBoxLayout(button_frame2)
        button_layout2.setContentsMargins(5, 4, 5, 4)
        button_layout2.setSpacing(5)
        
        self.ref_button = QPushButton("capture-reference")
        self.ref_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['accent']};
                border: 1px solid {self.colors['border']};
                padding: 5px 15px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['accent_alt']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['accent']};
            }}
        """)
        self.ref_button.clicked.connect(self.dummy_capture_reference)
        button_layout2.addWidget(self.ref_button)
        
        self.region_button = QPushButton("select-region")
        self.region_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['green']};
                border: 1px solid {self.colors['border']};
                padding: 5px 10px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['green_alt']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['green']};
            }}
        """)
        self.region_button.clicked.connect(self.dummy_select_region)
        button_layout2.addWidget(self.region_button)
        
        # Add a "Log Position" button
        self.log_pos_button = QPushButton("log-position")
        self.log_pos_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['text_dim']};
                border: 1px solid {self.colors['border']};
                padding: 5px 10px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['text']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['text']};
            }}
        """)

        button_layout2.addWidget(self.log_pos_button)
        
        control_layout.addWidget(button_frame2)
        
        parent_layout.addWidget(control_frame)
    
    def create_status_section(self, parent_layout):
        """Create status section similar to AutoFisher"""
        status_frame = QGroupBox("STATUS")
        status_frame.setStyleSheet(f"""
            QGroupBox {{
                font-size: 9pt;
                color: {self.colors['accent']};
                background-color: {self.colors['bg_dark']};
                border: 1px solid {self.colors['border']};
                margin-top: 8px;
                padding: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 5px;
                top: 0px;
                padding: 0px 5px 0px 5px;
            }}
        """)
        
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(4, 15, 4, 4)
        
        # System status
        self.status_label = QLabel("System: monitor.idle")
        self.status_label.setStyleSheet(f"""
            color: {self.colors['text_dim']};
            font-size: 16pt;
            padding: 2px;
        """)
        status_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignLeft)
        
        parent_layout.addWidget(status_frame)
    
    def create_log_section(self, parent_layout):
        """Create log section similar to AutoFisher"""
        log_frame = QGroupBox("LOGS")
        log_frame.setStyleSheet(f"""
            QGroupBox {{
                font-size: 9pt;
                color: {self.colors['accent']};
                background-color: {self.colors['bg_dark']};
                border: 1px solid {self.colors['border']};
                margin-top: 8px;
                padding: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 5px;
                top: 0px;
                padding: 0px 5px 0px 5px;
            }}
        """)
        
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(4, 15, 4, 4)
        
        self.log_console = QTextEdit()
        self.log_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['text']};
                border: none;
                font-family: 'Consolas', monospace;
                font-size: 9pt;
                padding: 8px;
            }}
        """)
        self.log_console.setReadOnly(True)
        
        log_layout.addWidget(self.log_console)
        
        # Add initial log messages
        self.add_log("AutoFisher initialized!")
        
        parent_layout.addWidget(log_frame)
    
    def create_minimized_view(self):
        """Create the minimized view (just the expand button)"""
        self.minimized_frame = QFrame(self.central_widget)
        self.minimized_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        self.minimized_frame.hide()  # Hide initially
        
        minimized_layout = QVBoxLayout(self.minimized_frame)
        minimized_layout.setContentsMargins(2, 2, 2, 2)
        
        # Minimized content with rounded appearance
        self.minimized_content = DraggableFrame()
        # Set drag function callbacks
        self.minimized_content.start_drag_func = self.start_drag
        self.minimized_content.stop_drag_func = self.stop_drag
        self.minimized_content.on_drag_func = self.on_drag
        self.minimized_content.setStyleSheet(f"""
            background-color: {self.colors['bg_term']};
            border-radius: 5px;
        """)
        
        minimized_content_layout = QVBoxLayout(self.minimized_content)
        minimized_content_layout.setContentsMargins(0, 0, 0, 0)
        minimized_content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Expand button
        self.expand_button = QPushButton("+")
        self.expand_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {self.colors['accent']};
                border: none;
                font-weight: bold;
                font-size: 12pt;
            }}
            QPushButton:hover {{
                color: {self.colors['accent_bright']};
            }}
        """)
        self.expand_button.clicked.connect(self.toggle_minimize)
        minimized_content_layout.addWidget(self.expand_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        minimized_layout.addWidget(self.minimized_content)
        self.main_layout.addWidget(self.minimized_frame)

    def update_stats_display(self):
        """Update the stats display with dummy values"""
        stats_data = {
            "total_detections": "0",
            "session_runtime": "00:00:00",
            "detections_per_hour": "0.0",
            "avg_interval": "N/A",
            "current_threshold": f"{self.threshold_var:.3f}",
            "cooldown": f"{self.cooldown_var}s",
            "key_mapping": self.fishing_key_var.upper(),
            "processing_fps": "30"
        }
        
        for key, label in self.stats_labels.items():
            label.setText(f"{label.text().split(':')[0]}: {stats_data.get(key, '...')}")
    
    def dummy_apply_settings(self):
        """Dummy function for apply settings button"""
        self.add_log(f"Settings applied: threshold={self.threshold_var:.2f}, cooldown={self.cooldown_var}s, key={self.fishing_key_var}")
        self.update_stats_display()
    
    def dummy_start(self):
        """Dummy function for start button"""
        self.add_log("Starting detection...")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.status_label.setText("System: monitor.active")
        self.status_label.setStyleSheet(f"color: {self.colors['green']}; font-size: 16pt; padding: 2px;")
    
    def dummy_stop(self):
        """Dummy function for stop button"""
        self.add_log("Detection stopped")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.status_label.setText("System: monitor.stopped")
        self.status_label.setStyleSheet(f"color: {self.colors['alert']}; font-size: 16pt; padding: 2px;")
    
    def dummy_pause(self):
        """Dummy function for pause button"""
        if self.pause_button.text() == "pause":
            self.add_log("Detection paused")
            self.pause_button.setText("resume")
            self.status_label.setText("System: monitor.paused")
            self.status_label.setStyleSheet(f"color: {self.colors['warning']}; font-size: 16pt; padding: 2px;")
        else:
            self.add_log("Detection resumed")
            self.pause_button.setText("pause")
            self.status_label.setText("System: monitor.active")
            self.status_label.setStyleSheet(f"color: {self.colors['green']}; font-size: 16pt; padding: 2px;")
    
    def dummy_capture_reference(self):
        """Dummy function for capture reference button"""
        self.add_log("Reference frame captured")
    
    def dummy_select_region(self):
        """Dummy function for select region button"""
        self.add_log("Please select a region on the screen...")
    
    def add_log(self, message):
        """Add a message to the log console, write to file, and print to console"""
        log_entry = f"{message}"
        
        # Add to UI console
        self.log_console.append(log_entry)
        
        # Print to standard output for immediate feedback
        print(log_entry)
        
        # # Also write to log file
        # try:
        #     with open('autofisher_debug.log', 'a', encoding='utf-8') as f:
        #         f.write(log_entry + '\n')
        # except Exception:
        #     # Silently ignore file writing errors
        #     pass
    
    def clear_logs(self):
        """Clear the log console"""
        self.log_console.clear()
        self.add_log("Logs cleared")
    
    def toggle_minimize(self):
        """Toggle between minimized and expanded states with animation"""
        if self.is_minimized:
            # Expand
            if self.main_frame and self.minimized_frame:
                self.main_frame.show()
                self.minimized_frame.hide()
                # Animate size change
                self._animate_size(self.minimized_width, self.minimized_height,
                                self.expanded_width, self.expanded_height)
        else:
            # Minimize
            if self.main_frame and self.minimized_frame:
                self.main_frame.hide()
                self.minimized_frame.show()
                # Animate size change
                self._animate_size(self.expanded_width, self.expanded_height,
                                self.minimized_width, self.minimized_height)
        
        self.is_minimized = not self.is_minimized
        
        # Reposition for multi-monitor support
        self.ensure_on_screen()
    
    def _animate_size(self, start_width, start_height, end_width, end_height):
        """Animate window size change with proper multi-monitor awareness"""
        try:
            # Use QPropertyAnimation for smooth animation
            animation = QPropertyAnimation(self, b"size")
            animation.setDuration(200)  # Duration in milliseconds
            animation.setStartValue(QSize(start_width, start_height))
            animation.setEndValue(QSize(end_width, end_height))
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.start()
            
            # Store a reference to prevent garbage collection
            self.size_animation = animation
        except Exception:
            # Fallback to instant resize
            self.resize(end_width, end_height)
    
    def ensure_on_screen(self):
        """Ensure the window is visible on at least one screen"""
        screens = QApplication.screens()
        if not screens:
            return
            
        # Get window geometry
        window_rect = self.geometry()
        
        # Check if window is at least partially visible on any screen
        visible_on_screen = False
        for screen in screens:
            screen_geometry = screen.geometry()
            if window_rect.intersects(screen_geometry):
                visible_on_screen = True
                break
        
        # If not visible, reposition to the primary screen
        if not visible_on_screen:
            primary_screen = QApplication.primaryScreen()
            if primary_screen:
                screen_geometry = primary_screen.geometry()
                # Center window on primary screen
                x = screen_geometry.x() + (screen_geometry.width() - window_rect.width()) // 2
                y = screen_geometry.y() + (screen_geometry.height() - window_rect.height()) // 2
                self.move(x, y)
    
    def find_game_window(self):
        """Find the Play Together game window or any window if not found"""
        if not WINDOWS_SUPPORT:
            return False
            
        # Reset game window handle
        self.game_window = None
            
        try:
            # First try to find the game window by name
            game_windows = []
            visible_windows = []
            
            def enum_window_callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    try:
                        window_text = win32gui.GetWindowText(hwnd)
                        # Skip empty windows or Windows system windows
                        if window_text and len(window_text) > 0 and not window_text.startswith("Windows"):
                            visible_windows.append((hwnd, window_text))
                            
                            if self.game_window_name.lower() in window_text.lower():
                                game_windows.append((hwnd, window_text))
                    except Exception:
                        pass
                return True
                
            win32gui.EnumWindows(enum_window_callback, None)
            
            # First priority: Find window with exact name
            if game_windows:
                self.game_window = game_windows[0][0]
                window_title = game_windows[0][1]
                self.add_log(f"Found game window: '{window_title}'")
                return True
                
            # Second priority: Use any visible non-system window
            if visible_windows:
                # Sort by window title length to find likely main windows (usually have shorter names)
                visible_windows.sort(key=lambda x: len(x[1]))
                for hwnd, title in visible_windows:
                    # Skip tiny windows and system tray windows
                    rect = win32gui.GetWindowRect(hwnd)
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    
                    if width > 200 and height > 200:
                        self.game_window = hwnd
                        self.add_log(f"No game window found, using window: '{title}' ({width}x{height})")
                        return True
                
            # Last resort: Use the first window we found
            if visible_windows:
                self.game_window = visible_windows[0][0]
                self.add_log(f"Using fallback window: '{visible_windows[0][1]}'")
                return True
                
            self.add_log("No suitable window found")
        except Exception as e:
            self.add_log(f"Error finding game window: {e}")
        
        return False    
    
    def moveEvent(self, event):
        """Handle move events for the window (including those from the tracking thread)"""
        super().moveEvent(event)
        # Update our stored position
        self.current_x = self.x()
        self.current_y = self.y()
    
    def start_tracking(self):
        """Start a thread to track the game window position"""
        if not WINDOWS_SUPPORT:
            # On non-Windows platforms, we can't track game window
            return
            
        try:
            self.tracking_active = True
            self.tracking_thread = threading.Thread(target=self._tracking_loop)
            self.tracking_thread.daemon = True  # Thread will exit when main thread exits
            self.tracking_thread.start()
        except Exception as e:
            self.add_log(f"Error starting tracking thread: {e}")
    
    def _tracking_loop(self):
        """Loop that monitors game window position and updates overlay position"""
        if not WINDOWS_SUPPORT:
            return

        while self.tracking_active:
            try:
                # Update internal position tracking
                actual_x, actual_y = self.x(), self.y()
                self.last_move_target = (actual_x, actual_y)

                # If game_window is not set or invalid, try to find it
                if not hasattr(self, 'game_window') or not self.game_window:
                    self.find_game_window()
                    time.sleep(0.015)
                    continue

                if not win32gui.IsWindow(self.game_window):
                    self.game_window = None  # Window closed or changed
                    time.sleep(0.015)
                    continue

                try:
                    # Get window position
                    win_left, win_top, _, _ = win32gui.GetWindowRect(self.game_window)

                    # Move overlay window to track game window
                    win32gui.SetWindowPos(
                        self.hwnd,
                        0,  # No z-order change
                        win_left + 20, win_top + 40,  # Offset position
                        0, 0,  # Size (unchanged)
                        win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
                    )
                except Exception as e:
                    self.add_log(f"Error positioning relative to game: {e}")
                    self.position_default()

            except Exception:
                # Prevent thread from crashing silently
                pass

            # Small sleep to reduce CPU usage
            time.sleep(0.015)

    def start_drag(self, event):
        """Begin dragging the window"""
        if isinstance(event, QMouseEvent):
            self.drag_start_position = event.position().toPoint()
        else:
            self.drag_start_position = event.pos()
    
    def stop_drag(self, event):
        """End dragging the window"""
        self.drag_start_position = None
        
        # Update current position after drag
        self.current_x = self.x()
        self.current_y = self.y()
    
    def on_drag(self, event):
        """Handle window dragging"""
        if self.drag_start_position is None:
            return
            
        if isinstance(event, QMouseEvent):
            delta = event.position().toPoint() - self.drag_start_position
            self.move(self.x() + delta.x(), self.y() + delta.y())
            
            # Update current position for animation system
            self.current_x = self.x()
            self.current_y = self.y()
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop tracking thread
        self.tracking_active = False
        if self.tracking_thread and self.tracking_thread.is_alive():
            self.tracking_thread.join(0.1)  # Wait briefly for thread to terminate
        
        # Accept the event to close the window
        event.accept() 

    def position_default(self):
        """Position the window on the primary screen"""
        # Get the primary screen
        target_screen = QApplication.primaryScreen()
        if not target_screen:
            # Fallback if no screen found
            self.move(100, 100)
            return
        
        # Log basic screen information
        self.add_log(f"Using screen: {target_screen.name()}")
        
        # Get the dimensions and scale factor of the target screen
        screen_geometry = target_screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        # Get the device pixel ratio for proper scaling on high-DPI displays
        device_pixel_ratio = target_screen.devicePixelRatio()
        
        # Adjust size for the current DPI scaling
        window_width = int(self.expanded_width / device_pixel_ratio)
        window_height = int(self.expanded_height / device_pixel_ratio)
        self.minimized_width = int(50 / device_pixel_ratio)
        self.minimized_height = int(50 / device_pixel_ratio)
        
        # Position in the center of the screen
        x = screen_geometry.x() + (screen_width - window_width) // 2
        y = screen_geometry.y() + (screen_height - window_height) // 2
        
        # Resize and position
        self.resize(window_width, window_height)
        self.move(x, y)
        
        self.add_log(f"Positioned at ({x},{y}) with size {window_width}x{window_height}")

    def get_dpi_scale(self):
        """Get the current screen's DPI scaling factor"""
        screen = self.get_current_screen()
        if screen:
            return screen.devicePixelRatio()
        return 1.0
    
    def get_current_screen(self):
        """Get the screen containing this window"""
        pos = self.geometry().center()
        for screen in QApplication.screens():
            if screen.geometry().contains(pos):
                return screen
        return QApplication.primaryScreen()
        
    def move(self, x, y):
        """Override move to store the target position and optionally validate"""
        # Store the target position
        self.last_move_target = (x, y)
        
        # Call the parent implementation
        super().move(x, y)
        
        # No need to verify every move as that would cause recursion issues
        # The verification will be handled by dedicated verification calls

# Run the overlay if executed directly
if __name__ == "__main__":
    app = QApplication(sys.argv)
   
    # Create and show the overlay
    overlay = OverlayAutoFisher()
    overlay.show()
    
    # Start the event loop
    sys.exit(app.exec()) 