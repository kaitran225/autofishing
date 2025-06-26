import sys
import os
import time
import math
import threading
import datetime
from typing import Callable, Optional, List, Tuple
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel, 
                            QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, 
                            QScrollArea, QSlider, QLineEdit, QTextEdit, QGroupBox, QTabWidget)
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
        
        # Initialize log buffer for early logging before UI is created
        self.log_buffer = []
        self.log_console = None
            
        # Configure the window
        self.setWindowTitle("AutoFisher v0.0.01a")
        
        # Default fallback size if no game window is found
        self.default_width = 350
        self.default_height = 550
        
        # Dynamic sizing parameters - more compact
        self.game_width_percentage = 0.25  # Reduced from 0.25 to 20% of game width
        self.game_height_percentage = 0.60  # Reduced from 0.60 to 50% of game height
        
        # Set initial size - will be recalculated if game window is found
        self.expanded_width = int(self.default_width * self.game_width_percentage)  # Make default size more compact
        self.expanded_height = int(self.default_height * self.game_height_percentage)
        
        # Calculate initial UI scaling factors - more compact
        self.ui_scale = {
            'base': 0.7,           # Reduced base scaling factor
            'margins': 2,           # Reduced margin size
            'spacing': 4,           # Reduced spacing
            'button_height': 28,    # Reduced button height
            'title_height': 30,     # Reduced title bar height
            'font_size': 9,         # Reduced font size
            'small_font_size': 8,   # Reduced smaller font size
            'large_font_size': 14,  # Reduced larger font size
            'border_radius': 6,     # Reduced border radius
            'button_radius': 5      # Reduced button border radius
        }
        
        # Set initial window position and flags
        self.move(100, 100)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Colors and style
        self.colors = {
            'bg_dark': '#121212',         # Charcoal black
            'bg_term': '#1A1A1A',         # Slightly lighter charcoal
            'bg_lighter': '#232323',      # Lighter panel
            'bg_alt': '#2C2C2C',          # Alternative dark
            'text': '#E8E3D9',            # Warm off-white
            'text_bright': '#FFFFFF',     # Bright white text
            'text_dim': '#A3A08C',        # Dimmed text
            'accent': '#A3D977',          # Matcha green
            'accent_alt': '#7CB518',      # Deeper matcha
            'accent_bright': '#C4E6B5',   # Bright matcha
            'accent_special': '#8B5A2B',  # Dark oak wood
            'green': '#A3D977',           # Matcha green
            'green_alt': '#7CB518',       # Alternative matcha
            'border': '#3A3A3A',          # Dark border
            'border_light': '#4D4D4D',    # Light border
            'cursor': '#A3D977',          # Cursor color (matcha)
            'alert': '#FF6B6B',           # Alert/Error color
            'warning': '#FFD166',         # Warning color
            'selection': '#A3D977'        # Selection color (matcha)
        }
        
        # Track if window is minimized
        self.is_minimized = False
        self.minimized_width = 50
        self.minimized_height = 50
        
        # Game window tracking
        self.last_move_target = None
        self.last_game_window_position = (0, 0)
        self.game_window = None
        self.game_window_name = "Play Together"
        self.offset_x = 10
        self.offset_y = 40
        self.tracking_active = False
        self.tracking_thread = None
        self.game_window_size = (0, 0)
        
        # Smooth movement variables
        self.target_x = 0
        self.target_y = 0
        self.current_x = 0
        self.current_y = 0
        self.is_animating = False
        self.animation_speed = 0.15
        self.animation_min_step = 1
        self.animation_timer = None
        
        # Track mouse position for dragging
        self.drag_start_position = None
        
        # Find game window and calculate initial size
        if WINDOWS_SUPPORT:
            if self.find_game_window():
                # If game window found, calculate size based on it
                self.calculate_size_from_game_window()
        
        # Set the initial size
        self.setGeometry(100, 100, self.expanded_width, self.expanded_height)
        
        # Calculate UI scaling factors based on initial size
        self.calculate_ui_scaling()
        
        # Create the UI (expanded state by default)
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.central_widget.setStyleSheet(f"""
            background-color: {self.colors['bg_dark']};
            border: 1px solid {self.colors['border']};
            border-radius: {self.ui_scale['border_radius']}px;
        """)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.main_frame = None
        self.minimized_frame = None
        self.create_widgets()
        
        self.hwnd = self.winId().__int__()
        
        # Only start game window tracking on Windows
        if WINDOWS_SUPPORT:
            if self.game_window:
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
            
        # Process any buffered logs
        self.flush_log_buffer()
    
    def calculate_ui_scaling(self):
        """Calculate UI scaling factors based on window size"""
        # Base the scaling on the window width
        width = self.expanded_width
        height = self.expanded_height
        
        # Determine base scaling factor (more compact)
        base_scale = 0.7  # Reduced from 0.7 for more compact UI
        
        # Calculate scaled values - more compact
        self.ui_scale = {
            'base': base_scale,
            'margins': max(1, int(4 * base_scale)),  # Reduced margins
            'spacing': max(1, int(2 * base_scale)),  # Reduced spacing
            'button_height': max(18, int(28 * base_scale)),  # Reduced button height
            'title_height': max(18, int(30 * base_scale)),  # Reduced title bar height
            'font_size': max(8, int(9 * base_scale)),  # Reduced font size
            'small_font_size': max(5, int(6 * base_scale)),  # Reduced small font
            'large_font_size': max(10, int(12 * base_scale)),  # Reduced large font
            'border_radius': max(3, int(6 * base_scale)),  # Reduced border radius
            'button_radius': max(2, int(5 * base_scale))  # Reduced button radius
        }
        
        return self.ui_scale
    
    def calculate_size_from_game_window(self):
        """Calculate overlay size based on game window dimensions"""
        if not WINDOWS_SUPPORT or not self.game_window:
            return False
            
        try:
            # Get game window size
            left, top, right, bottom = win32gui.GetWindowRect(self.game_window)
            game_width = right - left
            game_height = bottom - top
            
            # Store game window size
            self.game_window_size = (game_width, game_height)
            
            # Calculate new dimensions
            new_width = int(game_width * self.game_width_percentage)
            new_height = int(game_height * self.game_height_percentage)
            
            # Update expanded size
            self.expanded_width = new_width
            self.expanded_height = new_height
            
            return True
        except Exception as e:
            print(f"Error calculating size from game window: {e}")
            return False
    
    def create_widgets(self):
        # Create expanded view
        self.create_expanded_view()
        
        # Create minimized view (but don't show it yet)
        self.create_minimized_view()     
    
    def create_expanded_view(self):
        """Create the expanded view with AutoFisher UI"""
        # Get DPI scale for additional adjustments if needed
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
        title_height = self.ui_scale['title_height']
        border_radius = self.ui_scale['border_radius']
        self.title_bar.setStyleSheet(f"""
            background-color: {self.colors['bg_term']};
            height: {title_height}px;
            border-top-left-radius: {border_radius}px;
            border-top-right-radius: {border_radius}px;
        """)
        
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(self.ui_scale['margins'], 0, self.ui_scale['margins'], 0)
        title_layout.setSpacing(0)
        
        # Title label with adjusted font size
        font_size = self.ui_scale['font_size']
        self.title_label = QLabel("AutoFisher v0.0.01a")
        self.title_label.setStyleSheet(f"""
            color: {self.colors['accent']};
            font-weight: bold;
            font-size: {font_size}pt;
        """)
        title_layout.addWidget(self.title_label)
        
        # Control buttons
        btn_frame = QFrame()
        btn_frame.setStyleSheet(f"background-color: transparent;")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(self.ui_scale['spacing'])
        
        # Minimize/Expand toggle button
        button_width = int(self.ui_scale['button_height'] * 0.8)
        button_radius = button_width // 2  # Make it circular
        self.toggle_button = QPushButton("−")
        self.toggle_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['text']};
                border: none;
                font-weight: bold;
                font-size: {font_size}pt;
                width: {button_width}px;
                height: {button_width}px;
                border-radius: {button_radius}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['text_bright']};
            }}
        """)
        self.toggle_button.clicked.connect(self.toggle_minimize)
        btn_layout.addWidget(self.toggle_button)
        
        # Close button
        self.close_button = QPushButton("×")
        self.close_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['alert']};
                border: none;
                font-weight: bold;
                font-size: {font_size}pt;
                width: {button_width}px;
                height: {button_width}px;
                border-radius: {button_radius}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['alert']};
                color: {self.colors['text_bright']};
            }}
        """)
        self.close_button.clicked.connect(self.close)
        btn_layout.addWidget(self.close_button)
        
        title_layout.addWidget(btn_frame, alignment=Qt.AlignmentFlag.AlignRight)
        self.expanded_layout.addWidget(self.title_bar)
        
        # Content area
        self.content_frame = QFrame()
        content_margin = self.ui_scale['margins']
        self.content_frame.setStyleSheet(f"""
            background-color: {self.colors['bg_dark']};
            margin: {content_margin}px;
            border-radius: {self.ui_scale['border_radius']}px;
        """)
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(content_margin, content_margin, content_margin, content_margin)
        content_layout.setSpacing(self.ui_scale['spacing'] * 2)
        
        # Create AutoFisher UI sections
        self.create_tabs_section(content_layout)
        self.create_status_section(content_layout)
        self.create_monitoring_section(content_layout)
        self.create_control_section(content_layout)
        self.create_log_section(content_layout)
        
        self.expanded_layout.addWidget(self.content_frame)
    
    def create_tabs_section(self, parent_layout):
        """Create settings section with tabs for settings and monitoring preview"""
        small_font = self.ui_scale['small_font_size']
        normal_font = self.ui_scale['font_size']
        margin = self.ui_scale['margins']
        spacing = max(1, self.ui_scale['spacing'] - 1)  # Reduced spacing
        border_radius = self.ui_scale['border_radius']
        
        # Create main container frame
        tab_frame = QGroupBox("")
        tab_frame.setStyleSheet(f"""
            QGroupBox {{
                font-size: {small_font}pt;
                color: {self.colors['accent']};
                background-color: {self.colors['bg_dark']};
                border: 1px solid {self.colors['border']};
                border-radius: {border_radius}px;
                margin-top: {margin}px;
                padding: {margin}px;
            }}
        """)
        
        # Create tab widget
        tab_layout = QVBoxLayout(tab_frame)
        tab_layout.setContentsMargins(margin, margin, margin, margin)
        
        tab_widget = QTabWidget()
        tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {self.colors['border']};
                border-radius: {border_radius}px;
                background-color: {self.colors['bg_dark']};
            }}
            QTabBar::tab {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['text']};
                padding: {spacing}px {spacing*3}px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {self.colors['bg_dark']};
                color: {self.colors['accent']};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {self.colors['bg_alt']};
            }}
        """)
        
        # Create Settings tab
        settings_tab = QWidget()
        settings_tab_layout = QGridLayout(settings_tab)
        settings_tab_layout.setContentsMargins(margin, margin, margin, margin)
        settings_tab_layout.setSpacing(spacing)
        settings_tab_layout.setVerticalSpacing(int(spacing / 2))
        
        # Threshold (row 0)
        threshold_label = QLabel("Threshold")
        threshold_label.setStyleSheet(f"color: {self.colors['text']}; font-size: {normal_font}pt;")
        settings_tab_layout.addWidget(threshold_label, 0, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        
        threshold_frame = QFrame()
        threshold_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        threshold_layout = QHBoxLayout(threshold_frame)
        threshold_layout.setContentsMargins(0, 0, 0, 0)
        
        self.threshold_var = 0.05
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(1, 50)  # 0.01 to 0.50
        self.threshold_slider.setValue(int(self.threshold_var * 100))
        slider_height = max(6, int(6 * self.ui_scale['base']))
        handle_width = max(12, int(12 * self.ui_scale['base']))
        handle_radius = handle_width // 2
        self.threshold_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {self.colors['bg_alt']};
                height: {slider_height}px;
                border-radius: {slider_height//2}px;
            }}
            QSlider::sub-page:horizontal {{
                background: {self.colors['accent']};
                height: {slider_height}px;
                border-radius: {slider_height//2}px;
            }}
            QSlider::handle:horizontal {{
                background: {self.colors['text_bright']};
                width: {handle_width}px;
                height: {handle_width}px;
                margin: {(handle_width-slider_height)//2}px 0;
                border-radius: {handle_radius}px;
            }}
            QSlider::handle:horizontal:hover {{
                background: {self.colors['accent_bright']};
            }}
        """)
        self.threshold_slider.valueChanged.connect(self.on_threshold_changed)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_label = QLabel("0.05")
        self.threshold_label.setStyleSheet(f"color: {self.colors['text']}; font-size: {normal_font}pt; min-width: {40*self.ui_scale['base']}px;")
        threshold_layout.addWidget(self.threshold_label)
        
        settings_tab_layout.addWidget(threshold_frame, 0, 1)

        # Region Size (row 1)
        region_label = QLabel("Region Size")
        region_label.setStyleSheet(f"color: {self.colors['text']}; font-size: {normal_font}pt;")
        settings_tab_layout.addWidget(region_label, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        
        region_size_frame = QFrame()
        region_size_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        region_layout = QHBoxLayout(region_size_frame)
        region_layout.setContentsMargins(0, 0, 0, 0)
        
        self.size_var = "50"
        self.size_entry = QLineEdit(self.size_var)
        entry_padding = max(4, int(4 * self.ui_scale['base']))
        entry_width = max(60, int(60 * self.ui_scale['base']))
        entry_radius = self.ui_scale['button_radius']
        self.size_entry.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['text']};
                selection-background-color: {self.colors['selection']};
                selection-color: {self.colors['text_bright']};
                border: none;
                padding: {entry_padding / 2}px;
                border-radius: {entry_radius}px;
                font-size: {normal_font}pt;
                max-width: {entry_width}px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors['accent']};
            }}
        """)
        region_layout.addWidget(self.size_entry)
        
        px_label = QLabel("px")
        px_label.setStyleSheet(f"color: {self.colors['text']}; font-size: {normal_font}pt;")
        region_layout.addWidget(px_label)
        region_layout.addStretch()
        
        settings_tab_layout.addWidget(region_size_frame, 1, 1)

        # Cooldown (row 2)
        cooldown_label = QLabel("Cooldown")
        cooldown_label.setStyleSheet(f"color: {self.colors['text']}; font-size: {normal_font}pt;")
        settings_tab_layout.addWidget(cooldown_label, 2, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        
        cooldown_frame = QFrame()
        cooldown_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        cooldown_layout = QHBoxLayout(cooldown_frame)
        cooldown_layout.setContentsMargins(0, 0, 0, 0)
        
        self.cooldown_var = "5.0"
        self.cooldown_entry = QLineEdit(self.cooldown_var)
        self.cooldown_entry.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['text']};
                selection-background-color: {self.colors['selection']};
                selection-color: {self.colors['text_bright']};
                border: none;
                padding: {entry_padding / 2}px;
                border-radius: {entry_radius}px;
                font-size: {normal_font}pt;
                max-width: {entry_width}px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors['accent']};
            }}
        """)
        cooldown_layout.addWidget(self.cooldown_entry)
        
        sec_label = QLabel("sec")
        sec_label.setStyleSheet(f"color: {self.colors['text']}; font-size: {normal_font}pt;")
        cooldown_layout.addWidget(sec_label)
        cooldown_layout.addStretch()
        
        settings_tab_layout.addWidget(cooldown_frame, 2, 1)

        # Fishing Key (row 3)
        fishing_key_label = QLabel("Fishing Key")
        fishing_key_label.setStyleSheet(f"color: {self.colors['text']}; font-size: {normal_font}pt;")
        settings_tab_layout.addWidget(fishing_key_label, 3, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        
        fishing_key_frame = QFrame()
        fishing_key_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        fishing_key_layout = QHBoxLayout(fishing_key_frame)
        fishing_key_layout.setContentsMargins(0, 0, 0, 0)
        
        self.fishing_key_var = "f"
        small_entry_width = max(40, int(40 * self.ui_scale['base']))
        self.fishing_key_entry = QLineEdit(self.fishing_key_var)
        self.fishing_key_entry.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['text']};
                selection-background-color: {self.colors['selection']};
                selection-color: {self.colors['text_bright']};
                border: none;
                padding: {entry_padding / 2}px;
                border-radius: {entry_radius}px;
                font-size: {normal_font}pt;
                max-width: {small_entry_width}px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.colors['accent']};
            }}
        """)
        fishing_key_layout.addWidget(self.fishing_key_entry)
        fishing_key_layout.addStretch()
        
        settings_tab_layout.addWidget(fishing_key_frame, 3, 1)

        # Apply Settings button
        button_padding_v = max(8, int(8 * self.ui_scale['base']))
        button_padding_h = max(12, int(12 * self.ui_scale['base']))
        
        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['accent']};
                color: {self.colors['bg_dark']};
                border: none;
                padding: {button_padding_v}px {button_padding_h}px;
                font-size: {normal_font}pt;
                font-weight: bold;
                border-radius: {self.ui_scale['button_radius']}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['accent_bright']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['accent_alt']};
            }}
        """)
        self.apply_button.clicked.connect(self.dummy_apply_settings)
        settings_tab_layout.addWidget(self.apply_button, 4, 1, alignment=Qt.AlignmentFlag.AlignRight)
        
        # Create Monitoring Preview tab
        preview_tab = QWidget()
        preview_tab_layout = QVBoxLayout(preview_tab)
        preview_tab_layout.setContentsMargins(margin, margin, margin, margin)
        preview_tab_layout.setSpacing(spacing)
        
        preview_tab.setStyleSheet(f"""
            background-color: {self.colors['bg_lighter']};
        """)

        # Placeholder for preview image
        self.preview_label = QLabel("No preview available\nSelect a region first")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(f"""
            color: {self.colors['text_dim']};
            font-size: {normal_font}pt;
            background-color: {self.colors['bg_dark']};
            border-radius: {border_radius-2}px;
            padding: 0px;
        """)
        self.preview_label.setMinimumHeight(150)
        preview_tab_layout.addWidget(self.preview_label)

        # Add tabs to the tab widget
        tab_widget.addTab(preview_tab, "Live Preview")
        tab_widget.addTab(settings_tab, "Settings")
        
        # Add tab widget to main layout
        tab_layout.addWidget(tab_widget)
        
        parent_layout.addWidget(tab_frame)

    def on_threshold_changed(self, value):
        """Handle threshold slider change - with feedback like in autofisher.py"""
        self.threshold_var = value / 100.0
        self.threshold_label.setText(f"{self.threshold_var:.2f}")

        # Add threshold guidance messages like in autofisher.py
        if self.threshold_var < 0.5:
            self.add_log("Current threshold is very sensitive - may cause false positives")
          
        elif self.threshold_var > 0.25:
            self.add_log("Current threshold: {self.threshold_var} is not very sensitive - may miss subtle changes")
    
    def create_status_section(self, parent_layout):
        """Create monitoring section similar to AutoFisher - more compact"""
        small_font = self.ui_scale['small_font_size']
        normal_font = self.ui_scale['font_size']
        margin = self.ui_scale['margins']
        border_radius = self.ui_scale['border_radius']
        
        status_frame = QGroupBox("")
        status_frame.setStyleSheet(f"""
            QGroupBox {{
                font-size: {small_font}pt;
                color: {self.colors['accent']};
                background-color: {self.colors['bg_dark']};
                border: 1px solid {self.colors['border']};
                border-radius: {border_radius}px;
                margin-top: {margin }px;
                padding: {margin / 2}px;
            }}
        """)
        
        monitoring_layout = QVBoxLayout(status_frame)
        monitoring_layout.setContentsMargins(margin-1, margin, margin-1, margin-1)  # Reduced margins
        monitoring_layout.setSpacing(max(1, self.ui_scale['spacing'] - 1))  # Reduced spacing
    
        # System status - more compact
        self.status_label = QLabel("System: monitor.idle")
        self.status_label.setStyleSheet(f"""
            color: {self.colors['text_dim']};
            font-size: {normal_font}pt;
            padding: {max(1, self.ui_scale['spacing']-1)}px;  /* Reduced padding */
            background-color: {self.colors['bg_dark']};
            border-radius: {border_radius/2}px;
            min-height: {max(15, int(20 * self.ui_scale['base']))}px;  /* Fixed smaller height */
        """)
        monitoring_layout.addWidget(self.status_label)
        
        parent_layout.addWidget(status_frame)

    def create_monitoring_section(self, parent_layout):
        """Create monitoring section similar to AutoFisher - more compact"""
        small_font = self.ui_scale['small_font_size']
        normal_font = self.ui_scale['font_size']
        margin = self.ui_scale['margins']
        border_radius = self.ui_scale['border_radius']
        
        monitoring_frame = QGroupBox("")
        monitoring_frame.setStyleSheet(f"""
            QGroupBox {{
                font-size: {small_font}pt;
                color: {self.colors['accent']};
                background-color: {self.colors['bg_dark']};
                border: 1px solid {self.colors['border']};
                border-radius: {border_radius}px;
                margin-top: {margin }px;
                padding: {margin}px;
            }}
        """)
        
        monitoring_layout = QVBoxLayout(monitoring_frame)
        monitoring_layout.setContentsMargins(margin-1, margin, margin-1, margin-1)  # Reduced margins
        monitoring_layout.setSpacing(max(1, self.ui_scale['spacing'] - 1))  # Reduced spacing

        # Stats details in two columns - more compact
        stats_frame = QFrame()
        stats_frame.setStyleSheet(f"""
            background-color: {self.colors['bg_dark']};
            border: none;
            border-radius: {border_radius/2}px;
        """)
        
        stats_layout = QGridLayout(stats_frame)
        stats_layout.setContentsMargins(margin-1, margin-1, margin-1, margin-1)  # Reduced margins
        stats_layout.setSpacing(max(1, self.ui_scale['spacing'] - 1))  # Reduced spacing
        stats_layout.setVerticalSpacing(max(1, (self.ui_scale['spacing'] - 1) // 2))  # Even smaller vertical spacing
        
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
            l.setStyleSheet(f"""
                color: {self.colors['text']};
                font-size: {normal_font}pt;
                padding: {max(1, self.ui_scale['spacing']-1)}px;  /* Reduced padding */
            """)
            stats_layout.addWidget(l, row, col, 1, 1, Qt.AlignmentFlag.AlignLeft)
            stats_layout.setColumnStretch(col, 1)
            self.stats_labels[key] = l
        
        monitoring_layout.addWidget(stats_frame)

        # Initialize with dummy values
        self.update_stats_display()
        
        parent_layout.addWidget(monitoring_frame)
    
    def create_control_section(self, parent_layout):
        """Create control section similar to AutoFisher - more compact"""
        small_font = self.ui_scale['small_font_size']
        normal_font = self.ui_scale['font_size']
        margin = self.ui_scale['margins']
        spacing = max(1, self.ui_scale['spacing'] - 1)  # Reduced spacing
        button_padding_v = max(4, int(6 * self.ui_scale['base']))  # Reduced vertical padding
        button_padding_h = max(8, int(8 * self.ui_scale['base']))  # Reduced horizontal padding
        button_radius = self.ui_scale['button_radius']
        
        control_frame = QGroupBox("")
        control_frame.setStyleSheet(f"""
            QGroupBox {{
                font-size: {small_font}pt;
                color: {self.colors['accent']};
                background-color: {self.colors['bg_dark']};
                border: 1px solid {self.colors['border']};
                border-radius: {self.ui_scale['border_radius']}px;
                margin-top: {margin }px;
                padding: {margin}px;
            }}
        """)
        
        control_layout = QVBoxLayout(control_frame)
        control_layout.setContentsMargins(margin-1, margin, margin-1, margin-1)  # Reduced top margin
        control_layout.setSpacing(spacing // 2)  # Smaller spacing between rows
        
        # First row of buttons - more compact
        button_frame = QFrame()
        button_frame.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        
        button_layout = QHBoxLayout(button_frame)
        button_layout.setContentsMargins(spacing//2, spacing//2, spacing//2, spacing//2)  # Reduced margins
        button_layout.setSpacing(spacing)  # Keep horizontal spacing between buttons
        
        self.start_button = QPushButton("Start")
        self.start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['green']};
                color: {self.colors['bg_dark']};
                border: none;
                padding: {button_padding_v}px {button_padding_h}px;
                font-size: {normal_font}pt;
                font-weight: bold;
                border-radius: {button_radius}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['green_alt']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['accent']};
            }}
            QPushButton:disabled {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['text_dim']};
            }}
        """)
        self.start_button.clicked.connect(self.dummy_start)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['alert']};
                color: {self.colors['bg_dark']};
                border: none;
                padding: {button_padding_v}px {button_padding_h}px;
                font-size: {normal_font}pt;
                font-weight: bold;
                border-radius: {button_radius}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['accent_special']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['accent']};
            }}
            QPushButton:disabled {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['text_dim']};
            }}
        """)
        self.stop_button.clicked.connect(self.dummy_stop)
        button_layout.addWidget(self.stop_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.setEnabled(False)
        self.pause_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['warning']};
                color: {self.colors['bg_dark']};
                border: none;
                padding: {button_padding_v}px {button_padding_h}px;
                font-size: {normal_font}pt;
                font-weight: bold;
                border-radius: {button_radius}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['accent_special']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['accent']};
            }}
            QPushButton:disabled {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['text_dim']};
            }}
        """)
        self.pause_button.clicked.connect(self.dummy_pause)
        button_layout.addWidget(self.pause_button)
        
        self.clear_button = QPushButton("Clear Logs")
        self.clear_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['text']};
                border: none;
                padding: {button_padding_v}px {button_padding_h}px;
                font-size: {normal_font}pt;
                font-weight: bold;
                border-radius: {button_radius}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['text_bright']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['accent']};
                color: {self.colors['bg_dark']};
            }}
        """)
        self.clear_button.clicked.connect(self.clear_logs)
        button_layout.addWidget(self.clear_button)
        
        control_layout.addWidget(button_frame)
        
        # Second row of buttons - more compact
        button_frame2 = QFrame()
        button_frame2.setStyleSheet(f"background-color: {self.colors['bg_dark']}; border: none;")
        
        button_layout2 = QHBoxLayout(button_frame2)
        button_layout2.setContentsMargins(spacing//2, spacing//2, spacing//2, spacing//2)  # Reduced margins
        button_layout2.setSpacing(spacing)  # Keep horizontal spacing between buttons
        
        # Adjust padding for the wider button - reduced
        ref_padding_h = max(8, int(10 * self.ui_scale['base']))  # Smaller padding
        
        self.ref_button = QPushButton("Capture Reference")
        self.ref_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['accent']};
                border: none;
                padding: {button_padding_v}px {button_padding_h}px;
                font-size: {normal_font}pt;
                font-weight: bold;
                border-radius: {button_radius}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['accent_bright']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['accent']};
                color: {self.colors['bg_dark']};
            }}
        """)
        self.ref_button.clicked.connect(self.dummy_capture_reference)
        button_layout2.addWidget(self.ref_button)
        
        self.region_button = QPushButton("Select Region")
        self.region_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['green']};
                border: none;
                padding: {button_padding_v}px {button_padding_h}px;
                font-size: {normal_font}pt;
                font-weight: bold;
                border-radius: {button_radius}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['bg_alt']};
                color: {self.colors['green_alt']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['green']};
                color: {self.colors['bg_dark']};
            }}
        """)
        self.region_button.clicked.connect(self.dummy_select_region)
        button_layout2.addWidget(self.region_button)

        control_layout.addWidget(button_frame2)

        parent_layout.addWidget(control_frame)
    
    def create_log_section(self, parent_layout):
        """Create log section similar to AutoFisher - more compact"""
        small_font = self.ui_scale['small_font_size']
        normal_font = self.ui_scale['font_size']
        margin = self.ui_scale['margins']
        border_radius = self.ui_scale['border_radius']
        console_font_size = max(8, int(8 * self.ui_scale['base']))  # Reduced font size
        
        log_frame = QGroupBox("")
        log_frame.setStyleSheet(f"""
            QGroupBox {{
                font-size: {small_font}pt;
                color: {self.colors['accent']};
                background-color: {self.colors['bg_dark']};
                border: 1px solid {self.colors['border']};
                border-radius: {border_radius}px;
                margin-top: {margin }px;
                padding: {margin}px;
            }}
        """)
        
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(margin,margin, margin, margin)  # Reduced top margin
        log_layout.setSpacing(self.ui_scale['spacing'])
        
        self.log_console = QTextEdit()
        self.log_console.setStyleSheet(f"""
            QTextEdit {{
                background-color: {self.colors['bg_lighter']};
                color: {self.colors['text']};
                border: none;
                border-radius: {border_radius/2}px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: {console_font_size}pt;
                padding: {margin}px;
            }}
            QScrollBar:vertical {{
                background-color: {self.colors['bg_lighter']};
                width: {margin}px;
                border-radius: {margin/2}px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {self.colors['border']};
                border-radius: {margin/2}px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {self.colors['accent']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        self.log_console.setReadOnly(True)
        
        log_layout.addWidget(self.log_console)
        
        # Add initial log messages
        self.add_log("AutoFisher initialized!")
        
        parent_layout.addWidget(log_frame)
    
    def create_minimized_view(self):
        """Create the minimized view (just the expand button)"""
        margin = self.ui_scale['margins']
        normal_font = self.ui_scale['font_size']
        large_font = self.ui_scale['large_font_size']
        border_radius = self.ui_scale['border_radius']
        
        self.minimized_frame = QFrame(self.central_widget)
        self.minimized_frame.setStyleSheet(f"background-color: transparent; border: none;")
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
            border: 1px solid {self.colors['border']};
            border-radius: {border_radius}px;
        """)
        
        minimized_content_layout = QVBoxLayout(self.minimized_content)
        half_margin = int(margin/2)
        minimized_content_layout.setContentsMargins(half_margin, half_margin, half_margin, half_margin)
        minimized_content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Expand button
        button_size = max(32, int(32 * self.ui_scale['base']))
        self.expand_button = QPushButton("+")
        self.expand_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['accent']};
                color: {self.colors['bg_dark']};
                border: none;
                border-radius: {button_size/2}px;
                font-weight: bold;
                font-size: {large_font}pt;
                min-width: {button_size}px;
                min-height: {button_size}px;
                max-width: {button_size}px;
                max-height: {button_size}px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['accent_bright']};
            }}
            QPushButton:pressed {{
                background-color: {self.colors['accent_alt']};
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
        self.status_label.setText("System: ACTIVE")
        self.status_label.setStyleSheet(f"""
            color: {self.colors['green']};
            font-size: {self.ui_scale['large_font_size']}pt;
            font-weight: bold;
            padding: {self.ui_scale['spacing']}px;
            background-color: {self.colors['bg_lighter']};
            border-radius: {self.ui_scale['border_radius']/2}px;
        """)
    
    def dummy_stop(self):
        """Dummy function for stop button"""
        self.add_log("Detection stopped")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.status_label.setText("System: STOPPED")
        self.status_label.setStyleSheet(f"""
            color: {self.colors['alert']};
            font-size: {self.ui_scale['large_font_size']}pt;
            font-weight: bold;
            padding: {self.ui_scale['spacing']}px;
            background-color: {self.colors['bg_lighter']};
            border-radius: {self.ui_scale['border_radius']/2}px;
        """)
    
    def dummy_pause(self):
        """Dummy function for pause button"""
        if self.pause_button.text() == "Pause":
            self.add_log("Detection paused")
            self.pause_button.setText("Resume")
            self.status_label.setText("System: PAUSED")
            self.status_label.setStyleSheet(f"""
                color: {self.colors['warning']};
                font-size: {self.ui_scale['large_font_size']}pt;
                font-weight: bold;
                padding: {self.ui_scale['spacing']}px;
                background-color: {self.colors['bg_lighter']};
                border-radius: {self.ui_scale['border_radius']/2}px;
            """)
        else:
            self.add_log("Detection resumed")
            self.pause_button.setText("Pause")
            self.status_label.setText("System: ACTIVE")
            self.status_label.setStyleSheet(f"""
                color: {self.colors['green']};
                font-size: {self.ui_scale['large_font_size']}pt;
                font-weight: bold;
                padding: {self.ui_scale['spacing']}px;
                background-color: {self.colors['bg_lighter']};
                border-radius: {self.ui_scale['border_radius']/2}px;
            """)
    
    def dummy_capture_reference(self):
        """Dummy function for capture reference button"""
        self.add_log("Reference frame captured")
    
    def dummy_select_region(self):
        """Dummy function for select region button"""
        self.add_log("Please select a region on the screen...")
        # This would be connected to actual region selection code
        # For now, update the region info label with dummy data to demonstrate
        self.update_region_info((100, 200, 250, 300))
        
    def update_region_info(self, region=None):
        """Update the region info label similar to autofisher.py"""
        if region and hasattr(self, 'region_info_label'):
            left, top, right, bottom = region
            width = right - left
            height = bottom - top
    
    def add_log(self, message):
        """Add a message to the log console, write to file, and print to console"""
        log_entry = f"{message}"
        
        # Print to standard output for immediate feedback
        print(log_entry)
        
        # If log_console exists, add to UI
        if hasattr(self, 'log_console') and self.log_console is not None:
            self.log_console.append(log_entry)
        else:
            # Otherwise buffer the log for later
            self.log_buffer.append(log_entry)
    
    def flush_log_buffer(self):
        """Flush any buffered log messages to the log console"""
        if hasattr(self, 'log_console') and self.log_console is not None and self.log_buffer:
            for log_entry in self.log_buffer:
                self.log_console.append(log_entry)
            self.log_buffer.clear()
    
    def clear_logs(self):
        """Clear the log console"""
        if hasattr(self, 'log_console') and self.log_console is not None:
            self.log_console.clear()
            self.add_log("Logs cleared")
        else:
            # If log console doesn't exist yet, just clear the buffer
            self.log_buffer.clear()
    
    def toggle_minimize(self):
        """Toggle between minimized and expanded states with animation"""
        if self.is_minimized:
            # Calculate the correct expanded size before expanding
            if self.game_window and WINDOWS_SUPPORT:
                try:
                    # Get current game window size
                    left, top, right, bottom = win32gui.GetWindowRect(self.game_window)
                    game_width = right - left
                    game_height = bottom - top
                    
                    # Update the expanded dimensions based on current game window size
                    self.expanded_width = int(game_width * self.game_width_percentage)
                    self.expanded_height = int(game_height * self.game_height_percentage)
                except Exception as e:
                    print(f"Error calculating expanded size: {e}")
            
            # Expand
            if self.main_frame and self.minimized_frame:
                # First update the size target
                self.main_frame.show()
                self.minimized_frame.hide()
                
                # Small delay to ensure frame visibility changes are processed
                QApplication.processEvents()
                
                # Animate size change
                self._animate_size(self.minimized_width, self.minimized_height,
                                self.expanded_width, self.expanded_height)
        else:
            # Minimize
            if self.main_frame and self.minimized_frame:
                self.main_frame.hide()
                self.minimized_frame.show()
                
                # Small delay to ensure frame visibility changes are processed
                QApplication.processEvents()
                
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
                
                # Get window size for dynamic sizing
                left, top, right, bottom = win32gui.GetWindowRect(self.game_window)
                game_width = right - left
                game_height = bottom - top
                self.game_window_size = (game_width, game_height)
                
                self.add_log(f"Found game window: '{window_title}' ({game_width}x{game_height})")
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
                        self.game_window_size = (width, height)
                        self.add_log(f"No game window found, using window: '{title}' ({width}x{height})")
                        return True
                
            # Last resort: Use the first window we found
            if visible_windows:
                self.game_window = visible_windows[0][0]
                rect = win32gui.GetWindowRect(self.game_window)
                width = rect[2] - rect[0]
                height = rect[3] - rect[1]
                self.game_window_size = (width, height)
                self.add_log(f"Using fallback window: '{visible_windows[0][1]}' ({width}x{height})")
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

        last_position_update_time = 0
        position_update_interval = 0.015  # Update position every 0.1 seconds
        
        # Precalculate offsets
        offset_x = self.offset_x
        offset_y = self.offset_y

        while self.tracking_active:
            try:
                current_time = time.time()
                
                # If game_window is not set or invalid, try to find it
                if not hasattr(self, 'game_window') or not self.game_window:
                    self.find_game_window()
                    time.sleep(position_update_interval)
                    continue

                if not win32gui.IsWindow(self.game_window):
                    self.game_window = None  # Window closed or changed
                    time.sleep(position_update_interval)
                    continue

                try:
                    # Get window position and size
                    win_left, win_top, win_right, win_bottom = win32gui.GetWindowRect(self.game_window)

                    if(win_left == self.last_game_window_position[0] and win_top == self.last_game_window_position[1]):
                        continue

                    win32gui.SetWindowPos(
                            self.hwnd,
                            0,  # No z-order change
                            win_left + offset_x, win_top + offset_y,  # Offset position
                            0, 0,  # Size (unchanged)
                            win32con.SWP_NOSIZE | win32con.SWP_NOZORDER
                        )
                    self.last_game_window_position = (win_left, win_top)
                    time.sleep(position_update_interval)
                        
                except Exception as e:
                    print(f"Error in tracking loop: {e}")
                    time.sleep(position_update_interval)  # Longer sleep on error

            except Exception as e:
                print(f"Tracking loop exception: {e}")
                time.sleep(position_update_interval)  # Longer sleep on exception

            # Small sleep to reduce CPU usage
            time.sleep(position_update_interval)

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
        
        # If we have a game window size, use it for dynamic sizing
        if self.game_window_size[0] > 0 and self.game_window_size[1] > 0:
            game_width, game_height = self.game_window_size
            window_width = int(game_width * self.game_width_percentage)
            window_height = int(game_height * self.game_height_percentage)
            
            # Update expanded dimensions
            self.expanded_width = window_width
            self.expanded_height = window_height
        else:
            # Otherwise use default size adjusted for DPI
            window_width = int(self.default_width / device_pixel_ratio)
            window_height = int(self.default_height / device_pixel_ratio)
            
            # Update expanded dimensions
            self.expanded_width = window_width
            self.expanded_height = window_height
        
        # Update minimized dimensions
        self.minimized_width = int(50 / device_pixel_ratio)
        self.minimized_height = int(50 / device_pixel_ratio)
        
        # Position in the center of the screen
        x = screen_geometry.x() + (screen_width - window_width) // 2
        y = screen_geometry.y() + (screen_height - window_height) // 2
        
        # Resize and position - only if not minimized
        if not self.is_minimized:
            self.resize(window_width, window_height)
        else:
            self.resize(self.minimized_width, self.minimized_height)
            
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