import sys
import time
import threading
import datetime
import queue
import numpy as np
from typing import Callable, Optional, List, Tuple
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QTextEdit, QGroupBox, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, QSize,
)
from PyQt6.QtGui import (
    QFont, QColor, QPixmap, QCursor, QMouseEvent, QImage,
)

import cv2

from core.game_capture import GameCapture
from core.exclamation_preprocess import PreprocessConfig, PreprocessResult, load_config, run_preprocess
from utils.constants import ALERT_VERSION
from utils.coords import get_client_area_screen_rect
from ui.monitor_views import (
    crop_raw_zone_rgb,
    crop_zone_zoom_rgb,
    downscale_rgb_for_display,
    draw_detection_zone,
    numpy_to_pixmap,
    zoom_preprocess_bbox_rgb,
)
from utils.detection_zone import get_detection_zone

if sys.platform == "win32":
    try:
        import win32gui
        import win32con
        import mss
        import ctypes
        WINDOWS_SUPPORT = True
    except ImportError:
        WINDOWS_SUPPORT = False
else:
    WINDOWS_SUPPORT = False

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
        super().__init__(parent)
        self.is_toplevel = parent is not None

        self.log_buffer = []
        self.log_console = None
        self.log_queue = queue.Queue()
        self.capture = GameCapture(log_queue=self.log_queue)
        self.capture.gui = self  # type: ignore
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.poll_log_queue)
        self.log_timer.start(100)
            
        self.setWindowTitle(f"AutoFisher Alert v{ALERT_VERSION}")
        
        # Default fallback size if no game window is found
        self.default_width = 400
        self.default_height = 620
        
        self.game_width_percentage = 0.34
        self.game_height_percentage = 0.82
        
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
        self.game_window_name = "PLAY TOGETHER"
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
        
        self.preview_timer = None
        self.preview_interval = 80  # ms — smooth feed; detect is throttled separately
        self._preview_display_max_w = 720
        self._monitor_panel_w = 360
        self._monitor_panel_h = 200
        self.preview_active = False
        self._monitoring_view_active = False

        self._preprocess_cfg: PreprocessConfig = load_config()
        self._preprocess_result: Optional[PreprocessResult] = None
        self._preprocess_tick = 0
        self._preprocess_every = 3  # run preprocess every N preview ticks (~4Hz at 80ms)
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
            self._expert_width = max(440, int(new_width * 1.08))
            self._expert_height = max(800, int(new_height * 1.28))

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
        title_text = f"AutoFisher Alert · Expert v{ALERT_VERSION}"
        self.title_label = QLabel(title_text)
        self.title_label.setStyleSheet(f"""
            color: {self.colors['accent']};
            font-weight: bold;
            font-size: {font_size}pt;
            letter-spacing: 0.5px;
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
        
        self._expert_width = max(440, int(self.expanded_width * 1.08))
        self._expert_height = max(800, int(self.expanded_height * 1.28))
        self._monitoring_view_active = True

        self.create_unified_expert_dashboard(content_layout)

        self.expanded_layout.addWidget(self.content_frame)
    def create_unified_expert_dashboard(self, parent_layout):
        """Compact single-column UI: status, controls, monitors, log."""
        small_font = self.ui_scale["small_font_size"]
        margin = self.ui_scale["margins"]
        spacing = max(1, self.ui_scale["spacing"] - 1)
        border_radius = self.ui_scale["border_radius"]

        panel = QFrame()
        panel.setStyleSheet(
            f"background: {self.colors['bg_dark']}; border: none; border-radius: {border_radius}px;"
        )
        root = QVBoxLayout(panel)
        root.setContentsMargins(margin, margin, margin, margin)
        root.setSpacing(spacing)

        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet(
            f"color: {self.colors['text_dim']}; font-size: {small_font}pt;"
        )
        root.addWidget(self.status_label)

        self._create_primary_session_buttons()
        btn_row = QHBoxLayout()
        btn_row.setSpacing(spacing)
        for btn in (
            self.start_button,
            self.stop_button,
            self.pause_button,
            self.clear_button,
        ):
            btn_row.addWidget(btn)
        root.addLayout(btn_row)

        feed_col = QVBoxLayout()
        feed_col.setSpacing(spacing + 2)
        pw = getattr(self, "_monitor_panel_w", 320)
        ph = getattr(self, "_monitor_panel_h", 178)

        def _monitor_label(text: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setMinimumSize(pw, ph)
            lbl.setMaximumHeight(ph + 24)
            lbl.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Preferred,
            )
            lbl.setStyleSheet(self._monitor_label_style())
            return lbl

        self.monitor1_label = _monitor_label("Live game view\nOpen Play Together")
        feed_col.addWidget(self.monitor1_label, stretch=1)

        self.monitor_zone_label = _monitor_label("Preprocess preview")
        feed_col.addWidget(self.monitor_zone_label, stretch=1)

        self.monitor_zoom_label = _monitor_label("Mark zoom")
        feed_col.addWidget(self.monitor_zoom_label, stretch=1)

        root.addLayout(feed_col, stretch=3)
        self.preview_label = self.monitor1_label

        self.create_log_section(root)
        self.log_console.setMinimumHeight(165)
        self.log_console.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        root.setStretch(root.count() - 1, 2)

        parent_layout.addWidget(panel, stretch=1)

        QTimer.singleShot(0, self._activate_expert_dashboard)

    def _monitor_label_style(self) -> str:
        return f"""
            background-color: {self.colors['bg_dark']};
            color: {self.colors['text_dim']};
            border: 1px solid {self.colors['border']};
            border-radius: {self.ui_scale['border_radius']}px;
        """

    def _activate_expert_dashboard(self) -> None:
        if self.is_minimized:
            return
        self._monitoring_view_active = True
        if hasattr(self, "capture"):
            self.capture.find_play_together_process(force=True)
        if not self.preview_active:
            self.start_preview()
        if not self.is_minimized:
            self.resize(self._expert_width, self._expert_height)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self._activate_expert_dashboard)

    def update_monitor_dashboard(self):
        """Live capture preview — panel 1: live feed, panel 2: preprocess composite, panel 3: bbox zoom."""
        if not getattr(self, "_monitoring_view_active", False):
            return
        frame = self.capture.capture_screen()
        if frame is None:
            return

        if len(frame.shape) >= 3 and frame.shape[2] == 4:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
            bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        elif len(frame.shape) == 3:
            rgb = frame[:, :, :3]
            bgr = frame
        else:
            rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
            bgr = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        fh, fw = rgb.shape[:2]
        zone = get_detection_zone(fw, fh)

        # --- Panel 1: live game view with detection zone overlay ---
        disp_max_w = getattr(self, "_preview_display_max_w", 520)
        w1 = max(100, self.monitor1_label.width() - 8)
        h1 = max(100, self.monitor1_label.height() - 8)
        disp_scale = min(disp_max_w / max(fw, 1), w1 / max(fw, 1), h1 / max(fh, 1), 1.0)

        scaled_zone = zone
        if disp_scale < 0.999:
            zx, zy, zw, zh = zone
            scaled_zone = (
                int(zx * disp_scale),
                int(zy * disp_scale),
                max(1, int(zw * disp_scale)),
                max(1, int(zh * disp_scale)),
            )

        disp_rgb = downscale_rgb_for_display(rgb, w1, h1)
        live_rgb = draw_detection_zone(disp_rgb, scaled_zone)
        self.monitor1_label.setPixmap(numpy_to_pixmap(live_rgb, w1, h1))
        self.monitor1_label.setText("")

        # --- Throttled preprocess (~4Hz) ---
        self._preprocess_tick += 1
        if self._preprocess_tick >= self._preprocess_every:
            self._preprocess_tick = 0
            zx, zy, zw, zh = zone
            zone_bgr = bgr[zy : zy + zh, zx : zx + zw]
            if zone_bgr.size > 0:
                try:
                    self._preprocess_result = run_preprocess(zone_bgr, self._preprocess_cfg)
                except Exception:
                    self._preprocess_result = None

        # --- Panel 2: preprocess composite preview ---
        wz_panel = max(80, self.monitor_zone_label.width() - 8)
        hz_panel = max(80, self.monitor_zone_label.height() - 8)
        pp = self._preprocess_result
        if pp is not None and pp.preview_rgb is not None and pp.preview_rgb.size > 0:
            self.monitor_zone_label.setPixmap(numpy_to_pixmap(pp.preview_rgb, wz_panel, hz_panel))
            self.monitor_zone_label.setText("")
        else:
            zone_rgb = crop_raw_zone_rgb(bgr, zone)
            if zone_rgb is not None and zone_rgb.size > 0:
                self.monitor_zone_label.setPixmap(numpy_to_pixmap(zone_rgb, wz_panel, hz_panel))
                self.monitor_zone_label.setText("")
            else:
                self.monitor_zone_label.clear()
                self.monitor_zone_label.setText("detection\nzone")

        # --- Panel 3: zoom preprocess bbox when mask found, else zone zoom ---
        if not hasattr(self, "monitor_zoom_label"):
            return
        wz = max(80, self.monitor_zoom_label.width() - 8)
        hz = max(80, self.monitor_zoom_label.height() - 8)
        zoom_rgb = None
        if pp is not None and pp.bbox is not None and pp.preview_rgb is not None:
            zoom_rgb = zoom_preprocess_bbox_rgb(pp.preview_rgb, pp.bbox)
        if zoom_rgb is None:
            zoom_rgb = crop_zone_zoom_rgb(rgb, zone)
        if zoom_rgb is not None and zoom_rgb.size > 0:
            self.monitor_zoom_label.setPixmap(numpy_to_pixmap(zoom_rgb, wz, hz))
            self.monitor_zoom_label.setText("")
        else:
            self.monitor_zoom_label.clear()
            self.monitor_zoom_label.setText("zone zoom")

    def _session_button_metrics(self) -> tuple:
        normal_font = self.ui_scale["font_size"]
        spacing = max(1, self.ui_scale["spacing"] - 1)
        button_padding_v = max(4, int(6 * self.ui_scale["base"]))
        button_padding_h = max(8, int(8 * self.ui_scale["base"]))
        button_radius = self.ui_scale["button_radius"]
        return normal_font, spacing, button_padding_v, button_padding_h, button_radius

    def _create_primary_session_buttons(self) -> None:
        """Start / Stop / Pause / Clear — placed in Live session section."""
        if hasattr(self, "start_button"):
            return
        normal_font, _, button_padding_v, button_padding_h, button_radius = (
            self._session_button_metrics()
        )

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
        self.start_button.clicked.connect(self.start)

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
        self.stop_button.clicked.connect(self.stop)

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
        self.pause_button.clicked.connect(self.pause)

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

    def start(self):
        """Start detection"""
        if not self.game_window and not self.find_game_window():
            self.add_log("Cannot start: Game window not found")
            return
        self.capture.play_together_window = self.game_window
        self.add_log("Live session started...")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.status_label.setText("Active — live capture")
        self.status_label.setStyleSheet(
            f"color: {self.colors['green']}; font-size: {self.ui_scale['font_size']}pt; font-weight: bold;"
        )
        from utils.constants import (
            DEFAULT_DETECTION_COOLDOWN,
            DEFAULT_EXCLAMATION_MATCH,
            DEFAULT_FISHING_KEY,
        )

        self.capture.detection_cooldown = DEFAULT_DETECTION_COOLDOWN
        self.capture.fishing_key = DEFAULT_FISHING_KEY
        self.capture.match_threshold = DEFAULT_EXCLAMATION_MATCH
        self._paused = False
        if not self.capture.start_session():
            self.add_log("Failed to start session")
            self.stop()
            return
        if getattr(self, "_monitoring_view_active", False):
            self.start_preview()
        self.set_status_indicator("running")
    
    def stop(self):
        """Stop detection"""
        self.add_log("Detection stopped")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.status_label.setText("Stopped")
        self.status_label.setStyleSheet(
            f"color: {self.colors['text_dim']}; font-size: {self.ui_scale['font_size']}pt;"
        )
        self.capture.stop_session()
        if self.preview_timer:
            self.preview_timer.setInterval(self.preview_interval)
    
    def pause(self):
        """Pause/resume detection"""
        if not hasattr(self, '_paused'):
            self._paused = False
        self._paused = not self._paused
        if self._paused:
            self.add_log("Detection paused")
            self.pause_button.setText("Resume")
            self.status_label.setText("Paused")
            self.status_label.setStyleSheet(
                f"color: {self.colors['warning']}; font-size: {self.ui_scale['font_size']}pt; font-weight: bold;"
            )
        else:
            self.add_log("Detection resumed")
            self.pause_button.setText("Pause")
            self.status_label.setText("Active — live capture")
            self.status_label.setStyleSheet(
                f"color: {self.colors['green']}; font-size: {self.ui_scale['font_size']}pt; font-weight: bold;"
            )
        if hasattr(self.capture, "thread_control"):
            self.capture.thread_control["paused"] = self._paused
    
    def start_preview(self):
        """Start updating the preview image"""
        if self.preview_timer is None:
            self.preview_timer = QTimer(self)
            self.preview_timer.timeout.connect(self.update_preview)
        
        if not self.preview_active:
            self.preview_timer.start(self.preview_interval)
            self.preview_active = True
            self.add_log("Preview started")
    
    def stop_preview(self):
        """Stop updating the preview image"""
        if self.preview_timer is not None:
            self.preview_timer.stop()
            self.preview_active = False
            self.add_log("Preview stopped")
    
    def update_preview(self):
        """Refresh live game feed."""
        self.update_region_position()
        if getattr(self, "_monitoring_view_active", False):
            self.update_monitor_dashboard()

    def add_log(self, message):
        """Add a message to the log console, write to file, and print to console"""
        log_entry = f"{message}"
        
        # Print to standard output for immediate feedback
        print(log_entry)
        
        # If log_console exists, add to UI
        if hasattr(self, 'log_console') and self.log_console is not None:
            self.log_console.append(log_entry)
            
            # Check if scrollbar exists before accessing it
            scrollbar = self.log_console.verticalScrollBar()
            if scrollbar is not None:
                scrollbar.setValue(scrollbar.maximum())
        else:
            # Otherwise buffer the log for later
            self.log_buffer.append(log_entry)
    
    def flush_log_buffer(self):
        """Flush any buffered log messages to the log console"""
        if hasattr(self, 'log_console') and self.log_console is not None and self.log_buffer:
            for log_entry in self.log_buffer:
                self.log_console.append(log_entry)
                
            # After adding all buffered messages, scroll to the bottom
            scrollbar = self.log_console.verticalScrollBar()
            if scrollbar is not None:
                scrollbar.setValue(scrollbar.maximum())
            
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
        was_minimized = self.is_minimized
        
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
                    self._expert_width = max(520, int(self.expanded_width * 1.08))
                    self._expert_height = max(800, int(self.expanded_height * 1.28))
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
                tw, th = self._expert_width, self._expert_height
                self._animate_size(self.minimized_width, self.minimized_height, tw, th)
                QTimer.singleShot(100, self._activate_expert_dashboard)
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
        
        # Make sure region tracking continues to work correctly
        # after window state changes
        if was_minimized and not self.is_minimized:
            # We just expanded, update the region position
            self.update_region_position()
            
            # If we have a preview active, update it
            if hasattr(self, 'preview_active') and self.preview_active:
                self.update_preview()
    
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
        """Find Play Together using prototype window discovery."""
        if not WINDOWS_SUPPORT:
            return False

        from utils.win32_utils import find_play_together_window

        self.game_window = None
        try:
            hwnd, _pid = find_play_together_window()
            if not hwnd:
                self.add_log("No Play Together window found")
                return False

            self.game_window = hwnd
            if self.capture:
                self.capture.play_together_window = hwnd

            left, top, right, bottom = win32gui.GetWindowRect(self.game_window)
            self.game_window_size = (right - left, bottom - top)
            title = win32gui.GetWindowText(self.game_window)
            self.add_log(f"Found game window: '{title}' ({self.game_window_size[0]}x{self.game_window_size[1]})")
            return True
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

        position_update_interval = 0.015  # Update position every 15ms
        
        # Precalculate offsets
        offset_x = self.offset_x
        offset_y = self.offset_y

        while self.tracking_active:
            try:
                
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
                    win_left, win_top, _, _ = win32gui.GetWindowRect(self.game_window)

                    # Check if window has moved
                    if win_left != self.last_game_window_position[0] or win_top != self.last_game_window_position[1]:
                        # Move the overlay window
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
        # Stop preview timer
        self.stop_preview()
        
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
        
        window_width = getattr(self, "_expert_width", self.expanded_width)
        window_height = getattr(self, "_expert_height", self.expanded_height)

        if self.game_window_size[0] > 0 and self.game_window_size[1] > 0:
            game_width, game_height = self.game_window_size
            self.expanded_width = int(game_width * self.game_width_percentage)
            self.expanded_height = int(game_height * self.game_height_percentage)
            window_width = max(440, int(self.expanded_width * 1.08))
            window_height = max(800, int(self.expanded_height * 1.28))
            self._expert_width = window_width
            self._expert_height = window_height

        # Update minimized dimensions
        self.minimized_width = int(50)
        self.minimized_height = int(50)
        
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

    def update_region_position(self):
        """Refresh detector client rect when the game window moves."""
        if WINDOWS_SUPPORT and self.game_window and hasattr(self.capture, "_update_client_rect"):
            self.capture._update_client_rect()

    def set_status_indicator(self, state):
        """Update status label after bite handling (used by fishing_actions)."""
        if not hasattr(self, "status_label") or self.status_label is None:
            return
        styles = {
            "running": ("Active — watching for !", self.colors["green"], True),
            "paused": ("Paused", self.colors["warning"], True),
            "idle": ("Idle", self.colors["text_dim"], False),
        }
        text, color, bold = styles.get(
            state, (state.capitalize(), self.colors["text_dim"], False)
        )
        weight = "bold" if bold else "normal"
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {color}; font-size: {self.ui_scale['font_size']}pt; font-weight: {weight};"
        )

    def poll_log_queue(self):
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                self.add_log(msg)
            except Exception:
                break

    def increment_detection_count(self):
        self.add_log("Fish bite detected!")

    def log(self, message):
        """Wrapper for add_log to ensure compatibility with detector's calls"""
        self.add_log(message)

# Run the overlay if executed directly
if __name__ == "__main__":
    from program_alert import main

    sys.exit(main()) 