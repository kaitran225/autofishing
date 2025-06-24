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
    QApplication, QScrollArea, QSizePolicy, QTextBrowser, QTabWidget, QFileDialog,
    QLabel, QComboBox, QSystemTrayIcon, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QRect, QPoint, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QIcon, QPixmap, QImage, QAction
import qtawesome as qta
import cv2
import numpy as np

from core.detector import MultiZoneDetector, DetectionZone
from core.action_sequence import FishingActionSequence
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
    UI_WARNING_COLOR, UI_ALERT_COLOR, UI_SUCCESS_COLOR,
    UI_SUCCESS_HOVER, UI_SUCCESS_ACTIVE,
    UI_ERROR_COLOR, UI_ERROR_HOVER, UI_ERROR_ACTIVE,
    UI_ACCENT_HOVER, UI_ACCENT_ACTIVE
)

class OverlayWindow(QWidget):
    """Small overlay window that follows the game window"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(50, 50)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create status indicator with restore button functionality
        self.status_label = QLabel("●")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {UI_ACCENT_COLOR};
                font-size: 24pt;
                font-weight: bold;
                background-color: {UI_DARK_BG};
                border: 2px solid {UI_ACCENT_COLOR};
                border-radius: 25px;
                padding: 0px;
            }}
        """)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.status_label)
        
        # Detection count
        self.count_label = QLabel("0")
        self.count_label.setStyleSheet(f"""
            QLabel {{
                color: {UI_LIGHT_TEXT};
                font-size: 8pt;
                font-weight: bold;
                background-color: transparent;
            }}
        """)
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.count_label)
        
        # Mouse tracking for drag
        self.setMouseTracking(True)
        self.dragging = False
        self.drag_offset = QPoint()
        
        # Tooltip for user guidance
        self.setToolTip("Double-click to restore main window\nDrag to move overlay")
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_offset = event.pos()
            
    def mouseMoveEvent(self, event):
        if self.dragging:
            new_pos = self.mapToParent(event.pos() - self.drag_offset)
            self.move(new_pos)
            
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Emit signal to restore main window
            if hasattr(self.parent(), 'restore_from_overlay'):
                self.parent().restore_from_overlay()
                
    def update_status(self, is_running, detection_count):
        """Update overlay status"""
        if is_running:
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {UI_SUCCESS_COLOR};
                    font-size: 24pt;
                    font-weight: bold;
                    background-color: {UI_DARK_BG};
                    border: 2px solid {UI_SUCCESS_COLOR};
                    border-radius: 25px;
                    padding: 0px;
                }}
            """)
        else:
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    color: {UI_SECONDARY_TEXT};
                    font-size: 24pt;
                    font-weight: bold;
                    background-color: {UI_DARK_BG};
                    border: 2px solid {UI_SECONDARY_TEXT};
                    border-radius: 25px;
                    padding: 0px;
                }}
            """)
            
        self.count_label.setText(str(detection_count))

class GameWindowTracker(QThread):
    """Thread to track game window position"""
    position_changed = pyqtSignal(int, int, int, int)  # x, y, width, height
    window_lost = pyqtSignal()  # Emitted when game window is lost
    
    def __init__(self, game_window_hwnd, parent=None):
        super().__init__(parent)
        self.game_window_hwnd = game_window_hwnd
        self.running = True
        self.last_rect = None
        
    def run(self):
        import win32gui
        import time
        
        # Validate handle before starting
        if not self.game_window_hwnd:
            self.window_lost.emit()
            return
            
        try:
            if not win32gui.IsWindow(self.game_window_hwnd):
                self.window_lost.emit()
                return
        except Exception:
            self.window_lost.emit()
            return
        
        while self.running:
            try:
                # Check if window still exists
                if not self.game_window_hwnd or not win32gui.IsWindow(self.game_window_hwnd):
                    # Try to find the window again
                    if hasattr(self.parent(), 'detector'):
                        new_hwnd = self.parent().detector.get_game_window_handle()
                        if new_hwnd:
                            self.game_window_hwnd = new_hwnd
                        else:
                            # Window lost
                            self.window_lost.emit()
                            time.sleep(1.0)
                            continue
                    else:
                        time.sleep(1.0)
                        continue
                
                # Get current window position
                rect = win32gui.GetWindowRect(self.game_window_hwnd)
                if rect != self.last_rect:
                    x, y, right, bottom = rect
                    width = right - x
                    height = bottom - y
                    self.position_changed.emit(x, y, width, height)
                    self.last_rect = rect
                    
                time.sleep(0.1)  # Check every 100ms
                
            except Exception as e:
                # Only log if it's not a common "invalid handle" error
                if "Invalid window handle" not in str(e):
                    print(f"Game window tracking error: {e}")
                time.sleep(1.0)
                
    def stop(self):
        self.running = False

class AutoFisherMainWindow(QMainWindow):
    """Main window for the AutoFisher Qt application"""
    
    def __init__(self):
        """Initialize the main window"""
        super().__init__()
        self.setWindowTitle(f"AutoFisher Qt v{VERSION} - {VERSION_NAME}")
        
        # Set fixed window size
        self.setFixedSize(380, 780)
        
        # Initialize instance variables
        self.detector = None
        self.live_preview_running = False
        self.detection_running = False
        self.start_time = None
        self.detection_count = 0
        self.vis_frame = None
        self.selected_region = None
        self.region_selector = None
        self.vis_timer = None
        
        # Overlay functionality
        self.overlay_mode = False
        self.overlay_window = None
        self.game_tracker = None
        self.original_geometry = None
        
        # System tray
        self.system_tray = None
        self.setup_system_tray()
        
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
        
        # Create MultiZoneDetector for advanced detection
        self.detector = MultiZoneDetector(self)
        # Connect zone-based detection signal
        self.detector.detection_signal.connect(self.handle_zone_detection)
        
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
        
        self.try_start_overlay_on_launch()
    
    def try_start_overlay_on_launch(self):
        """Try up to 10 times to find the game window and start overlay. Exit if not found."""
        import time
        found = False
        for attempt in range(10):
            game_hwnd = self.detector.get_game_window_handle()
            if game_hwnd:
                found = True
                break
            time.sleep(0.5)
        if found:
            self.minimize_to_overlay()
        else:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Game Not Found")
            msg_box.setText("Play Together game window not found after 10 attempts!")
            msg_box.setInformativeText("Please make sure the game is running and restart AutoFisher.")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            QApplication.quit()
    
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
        self.start_button.clicked.connect(self.toggle_detection)
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
        
        # Minimize to overlay button
        self.minimize_button = QPushButton()
        self.minimize_button.setIcon(qta.icon('fa5s.compress', color='white', scale_factor=1.0))
        self.minimize_button.clicked.connect(self.minimize_to_overlay)
        self.minimize_button.setStyleSheet(tool_style)
        self.minimize_button.setToolTip("Minimize to Overlay")
        control_layout.addWidget(self.minimize_button)
        
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
        
        # 6. Zone Management Tab
        zones_tab = QWidget()
        zones_layout = QVBoxLayout(zones_tab)
        zones_layout.setContentsMargins(6, 6, 6, 6)
        zones_layout.setSpacing(8)
        
        # Zone management header
        zones_header = QLabel("Multi-Zone Detection Management")
        zones_header.setStyleSheet(f"color: {UI_ACCENT_COLOR}; font-weight: bold; font-size: 10pt; padding: 4px;")
        zones_layout.addWidget(zones_header)
        
        # Create zone controls for each detection zone
        self.zone_controls = {}
        zone_configs = {
            "main_fishing": {"name": "Main Fishing Zone", "color": "#4CAF50", "description": "Primary fish bite detection"},
            "fish_name": {"name": "Fish Name Zone", "color": "#2196F3", "description": "Fish name/catch notification detection"},
            "fishing_rod": {"name": "Fishing Rod Zone", "color": "#FF9800", "description": "Fishing rod movement detection"},
            "bounce_shadow": {"name": "Shadow Bounce Zone", "color": "#9C27B0", "description": "Fish shadow movement detection"}
        }
        
        for zone_id, config in zone_configs.items():
            # Create zone group
            zone_group = QGroupBox(config["name"])
            zone_group.setStyleSheet(f"""
                QGroupBox {{
                    border: 2px solid {config["color"]};
                    border-radius: 6px;
                    margin-top: 8px;
                    padding-top: 8px;
                    font-weight: bold;
                    background-color: {UI_PANEL_BG};
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top center;
                    padding: 0 8px;
                    color: {config["color"]};
                    font-size: 9pt;
                }}
            """)
            
            zone_layout = QVBoxLayout(zone_group)
            zone_layout.setContentsMargins(8, 12, 8, 8)
            zone_layout.setSpacing(6)
            
            # Zone description
            desc_label = QLabel(config["description"])
            desc_label.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 8pt; font-weight: normal;")
            zone_layout.addWidget(desc_label)
            
            # Zone status and controls row
            status_row = QHBoxLayout()
            
            # Zone status indicator
            status_indicator = QLabel("●")
            status_indicator.setStyleSheet(f"color: {config['color']}; font-size: 12pt; font-weight: bold;")
            status_indicator.setFixedWidth(20)
            status_row.addWidget(status_indicator)
            
            # Zone status text
            status_text = QLabel("Disabled")
            status_text.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 8pt;")
            status_text.setFixedWidth(60)
            status_row.addWidget(status_text)
            
            # Region info
            region_info = QLabel("No region")
            region_info.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 8pt;")
            region_info.setFixedWidth(80)
            status_row.addWidget(region_info)
            
            # Detection count
            detection_count = QLabel("0 detections")
            detection_count.setStyleSheet(f"color: {UI_ACCENT_COLOR}; font-size: 8pt; font-weight: bold;")
            detection_count.setFixedWidth(70)
            status_row.addWidget(detection_count)
            
            status_row.addStretch()
            
            # Enable/disable checkbox
            enable_checkbox = QCheckBox("Enable")
            enable_checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: {UI_LIGHT_TEXT};
                    font-size: 8pt;
                }}
                QCheckBox::indicator {{
                    width: 14px;
                    height: 14px;
                }}
                QCheckBox::indicator:checked {{
                    background-color: {config["color"]};
                    border: 1px solid {config["color"]};
                    border-radius: 2px;
                }}
            """)
            enable_checkbox.setChecked(True)  # Default enabled
            status_row.addWidget(enable_checkbox)
            
            zone_layout.addLayout(status_row)
            
            # Zone controls row
            controls_row = QHBoxLayout()
            
            # Select region button
            select_btn = QPushButton("Select Region")
            select_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {config["color"]};
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 8pt;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {config["color"]}dd;
                }}
                QPushButton:pressed {{
                    background-color: {config["color"]}aa;
                }}
            """)
            controls_row.addWidget(select_btn)
            
            # Clear region button
            clear_btn = QPushButton("Clear")
            clear_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {UI_WOOD_DARK};
                    color: {UI_LIGHT_TEXT};
                    border: 1px solid {UI_WOOD_MEDIUM};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 8pt;
                }}
                QPushButton:hover {{
                    background-color: {UI_WOOD_MEDIUM};
                }}
            """)
            controls_row.addWidget(clear_btn)
            
            # Preview button
            preview_btn = QPushButton("Preview")
            preview_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {UI_ACCENT_DARK};
                    color: {UI_LIGHT_TEXT};
                    border: 1px solid {UI_ACCENT_COLOR};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 8pt;
                }}
                QPushButton:hover {{
                    background-color: {UI_ACCENT_COLOR};
                }}
            """)
            controls_row.addWidget(preview_btn)
            
            controls_row.addStretch()
            
            zone_layout.addLayout(controls_row)
            
            # Zone preview area (small)
            preview_frame = QFrame()
            preview_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {UI_DARK_BG};
                    border: 1px solid {UI_WOOD_DARK};
                    border-radius: 4px;
                }}
            """)
            preview_frame.setFixedHeight(60)
            preview_layout = QVBoxLayout(preview_frame)
            preview_layout.setContentsMargins(4, 4, 4, 4)
            
            preview_label = QLabel("No preview")
            preview_label.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 8pt;")
            preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_layout.addWidget(preview_label)
            
            zone_layout.addWidget(preview_frame)
            
            # Store zone controls
            self.zone_controls[zone_id] = {
                "group": zone_group,
                "status_indicator": status_indicator,
                "status_text": status_text,
                "region_info": region_info,
                "detection_count": detection_count,
                "enable_checkbox": enable_checkbox,
                "select_btn": select_btn,
                "clear_btn": clear_btn,
                "preview_btn": preview_btn,
                "preview_frame": preview_frame,
                "preview_label": preview_label,
                "color": config["color"]
            }
            
            # Connect button signals
            select_btn.clicked.connect(lambda checked, zid=zone_id: self.select_zone_region(zid))
            clear_btn.clicked.connect(lambda checked, zid=zone_id: self.clear_zone_region(zid))
            preview_btn.clicked.connect(lambda checked, zid=zone_id: self.toggle_zone_preview(zid))
            enable_checkbox.stateChanged.connect(lambda state, zid=zone_id: self.toggle_zone_enable(zid, state))
            
            zones_layout.addWidget(zone_group)
        
        # Add stretch to push everything to the top
        zones_layout.addStretch()
        
        # Add all tabs to the tab widget
        self.tab_widget.addTab(console_tab, "Console")
        self.tab_widget.addTab(activity_tab, "Activity")
        self.tab_widget.addTab(settings_tab, "Settings")
        self.tab_widget.addTab(stats_tab, "Statistics")
        self.tab_widget.addTab(region_tab, "Info")
        self.tab_widget.addTab(zones_tab, "Zones")
        
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
            self.detector = MultiZoneDetector(self)
        
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
            
    def set_region(self, region):
        """Set the region to monitor"""
        if not region:
            self.log("No region selected")
            return False
            
        if not self.detector:
            self.detector = MultiZoneDetector(self)
            
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
            self.status_label.setText("Live Preview")
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
            self.status_label.setText("Ready")
            return True
        return False
        
    def start_detection(self):
        """Start detection with proper error handling"""
        try:
            if self.is_detector_running():
                self.log("Detection already running")
                return
                
            if not self.detector:
                self.log("Detector not initialized")
                return
                
            # Check if region is selected
            if not self.detector.region:
                self.log("No region selected. Please select a region first.")
                return
            
            # Start detection
            success = self.detector.start_detection()
            
            if success:
                self.log("Detection started")
                self.update_ui_elements(True)  # Update UI to show detection is running
            else:
                self.log("Failed to start detection")
                
        except Exception as e:
            self.log(f"Error starting detection: {str(e)}")
            # Make sure UI reflects detection is not running
            self.update_ui_elements(False)
    
    def stop_detection(self):
        """Stop detection with proper UI updates"""
        if not self.detector:
            return
        
        try:
            # Stop detection in the detector
            self.detector.stop_detection()
            
            # Update UI immediately
            self.update_ui_elements(False)
            
            self.log("Detection stopped")
        except Exception as e:
            self.log(f"Error stopping detection: {str(e)}")
            # Make sure UI reflects detection is not running anyway
            self.update_ui_elements(False)
        
    def toggle_pause(self):
        """Toggle pause state"""
        if not self.detector:
            return
            
        # Use the detector's toggle_pause method instead of direct manipulation
        self.detector.toggle_pause()
        
        # Update UI based on the detector's state
        if self.detector.thread_control["paused"]:
            self.pause_button.setText("Resume")
            self.status_label.setText("Paused")
            self.log("Detection paused")
        else:
            self.pause_button.setText("Pause")
            self.status_label.setText("Running - Monitoring for changes")
            self.log("Detection resumed")
            
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
            
    def handle_zone_detection(self, zone_id):
        """Handle detection event from a specific zone"""
        self.increment_detection_count()
        # Update zone detection count
        if zone_id in self.zone_controls:
            current_count = int(self.zone_controls[zone_id]["detection_count"].text().split()[0])
            self.zone_controls[zone_id]["detection_count"].setText(f"{current_count + 1} detections")
        # Optionally, update UI to highlight which zone triggered
        print(f"Detection triggered by zone: {zone_id}")
        
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
            high_perf_mode = getattr(self.detector, 'high_performance_mode', True)
            estimated_fps = 10.0 if high_perf_mode else 5.0
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
        self.monitor_threshold.setText(f"{getattr(self.detector, 'THRESHOLD', 0.045):.2f}")
        self.monitor_cooldown.setText(f"{getattr(self.detector, 'detection_cooldown', 5.0):.1f}s")
        self.monitor_key.setText(getattr(self.detector, 'fishing_key', 'f'))
        high_perf_mode = getattr(self.detector, 'high_performance_mode', True)
        self.monitor_mode.setText("High Perf" if high_perf_mode else "Standard")
        
        # Update System Info
        region = getattr(self.detector, 'region', None)
        if region:
            left, top, right, bottom = region
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
            
        # Update zone statistics
        self.update_zone_statistics()
    
    def reset_detection_stats(self):
        """Reset all detection statistics"""
        self.detection_count = 0
        self.start_time = time.time()
        if self.detector:
            # Reset detector statistics
            self.detector.stats["total_detections"] = 0
            self.detector.stats["session_start_time"] = time.time()
            self.detector.stats["last_detection_time"] = 0
            self.detector.stats["avg_detection_interval"] = 0
    
    def closeEvent(self, event):
        """Handle window close event"""
        # Stop detection if running
        if self.detector and self.detection_running:
            self.log("Stopping detection before exit...")
            self.detector.stop_detection()
            
            # Wait a moment for threads to clean up
            for _ in range(10):
                QApplication.processEvents()
                time.sleep(0.1)
        
        # Accept the close event
        event.accept()

    def update_ui_elements(self, is_running):
        """Update UI elements based on detection state"""
        if is_running:
            # Update state variables
            self.detection_running = True
            self.start_time = time.time()
            
            # Update UI controls
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            self.pause_button.setText("Pause")  # Ensure button shows correct state
            self.status_label.setText("Running - Monitoring for changes")
            
            # Start visualization timer
            self.vis_timer.start()
        else:
            # Update state variables
            self.detection_running = False
            
            # Update UI controls
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.pause_button.setEnabled(False)
            self.pause_button.setText("Pause")  # Reset to default state
            self.status_label.setText("Ready - Detection stopped")
            
            # Stop visualization timer
            self.vis_timer.stop()
    
    def is_detector_running(self):
        """Check if detector is currently running"""
        if not self.detector:
            return False
        return self.detector.running

    def select_zone_region(self, zone_id):
        """Select region for a specific zone"""
        try:
            # Get the size from the input field (use default if not available)
            try:
                size = int(self.size_entry.text())
            except (ValueError, AttributeError):
                size = 50  # Default size
                
            # First find the Play Together window
            if not self.detector:
                self.detector = MultiZoneDetector(self)
                
            # Using the new TkRegionSelector which follows the autofisher.py implementation
            self.region_selector = TkRegionSelector(
                size=size,
                callback=lambda region: self.set_zone_region(zone_id, region)
            )
            
            self.log(f"Selecting region for {zone_id} zone...")
            
        except Exception as e:
            self.log(f"Error selecting zone region: {e}")
            
    def set_zone_region(self, zone_id, region):
        """Set region for a specific zone"""
        try:
            if not self.detector:
                self.detector = MultiZoneDetector(self)
                
            # Set the region in the detector
            self.detector.set_zone_region(zone_id, region)
            
            # Update UI
            if zone_id in self.zone_controls:
                left, top, right, bottom = region
                width = right - left
                height = bottom - top
                region_text = f"{width}x{height}"
                self.zone_controls[zone_id]["region_info"].setText(region_text)
                enabled = self.zone_controls[zone_id]["enable_checkbox"].isChecked()
                if enabled:
                    self.zone_controls[zone_id]["status_text"].setText("Ready")
                    self.zone_controls[zone_id]["status_indicator"].setText("●")
                else:
                    self.zone_controls[zone_id]["status_text"].setText("Disabled")
                    self.zone_controls[zone_id]["status_indicator"].setText("○")
            self.log(f"Zone {zone_id} region set: {region}")
        except Exception as e:
            self.log(f"Error setting zone region: {e}")

    def clear_zone_region(self, zone_id):
        """Clear region for a specific zone"""
        try:
            if self.detector and zone_id in self.detector.zones:
                self.detector.zones[zone_id].region = None
            # Update UI
            if zone_id in self.zone_controls:
                self.zone_controls[zone_id]["region_info"].setText("No region")
                enabled = self.zone_controls[zone_id]["enable_checkbox"].isChecked()
                if enabled:
                    self.zone_controls[zone_id]["status_text"].setText("Waiting")
                    self.zone_controls[zone_id]["status_indicator"].setText("●")
                else:
                    self.zone_controls[zone_id]["status_text"].setText("Disabled")
                    self.zone_controls[zone_id]["status_indicator"].setText("○")
            self.log(f"Zone {zone_id} region cleared")
        except Exception as e:
            self.log(f"Error clearing zone region: {e}")

    def toggle_zone_enable(self, zone_id, state):
        """Enable or disable a zone"""
        try:
            if self.detector:
                enabled = state == 2  # Qt.Checked = 2
                self.detector.enable_zone(zone_id, enabled)
                # Update UI
                if zone_id in self.zone_controls:
                    region = self.zone_controls[zone_id]["region_info"].text()
                    if enabled:
                        if region == "No region":
                            self.zone_controls[zone_id]["status_text"].setText("Waiting")
                            self.zone_controls[zone_id]["status_indicator"].setText("●")
                        else:
                            self.zone_controls[zone_id]["status_text"].setText("Ready")
                            self.zone_controls[zone_id]["status_indicator"].setText("●")
                    else:
                        self.zone_controls[zone_id]["status_text"].setText("Disabled")
                        self.zone_controls[zone_id]["status_indicator"].setText("○")
            self.log(f"Zone {zone_id} {'enabled' if enabled else 'disabled'}")
        except Exception as e:
            self.log(f"Error toggling zone enable: {e}")

    def toggle_zone_preview(self, zone_id):
        """Toggle live preview for a specific zone"""
        try:
            if zone_id not in self.zone_controls:
                return
                
            preview_btn = self.zone_controls[zone_id]["preview_btn"]
            preview_label = self.zone_controls[zone_id]["preview_label"]
            
            if preview_btn.text() == "Preview":
                # Start preview
                preview_btn.setText("Stop")
                preview_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {UI_WARNING_COLOR};
                        color: {UI_LIGHT_TEXT};
                        border: 1px solid {UI_WARNING_COLOR};
                        border-radius: 4px;
                        padding: 4px 8px;
                        font-size: 8pt;
                    }}
                    QPushButton:hover {{
                        background-color: {UI_WARNING_COLOR}dd;
                    }}
                """)
                
                # Start preview thread for this zone
                self.start_zone_preview(zone_id)
                
            else:
                # Stop preview
                preview_btn.setText("Preview")
                preview_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {UI_ACCENT_DARK};
                        color: {UI_LIGHT_TEXT};
                        border: 1px solid {UI_ACCENT_COLOR};
                        border-radius: 4px;
                        padding: 4px 8px;
                        font-size: 8pt;
                    }}
                    QPushButton:hover {{
                        background-color: {UI_ACCENT_COLOR};
                    }}
                """)
                
                preview_label.setText("No preview")
                self.stop_zone_preview(zone_id)
                
        except Exception as e:
            self.log(f"Error toggling zone preview: {e}")
            
    def start_zone_preview(self, zone_id):
        """Start live preview for a specific zone"""
        try:
            if not self.detector or zone_id not in self.detector.zones:
                return
                
            zone = self.detector.zones[zone_id]
            if not zone.region:
                self.log(f"Zone {zone_id} has no region set")
                return
                
            # Create preview thread for this zone
            class ZonePreviewThread(QThread):
                preview_ready = pyqtSignal(str, object)  # zone_id, frame
                
                def __init__(self, detector, zone_id, parent=None):
                    super().__init__(parent)
                    self.detector = detector
                    self.zone_id = zone_id
                    self.running = False
                    
                def run(self):
                    self.running = True
                    while self.running:
                        try:
                            frame = self.detector.capture_zone_frame(self.zone_id)
                            if frame is not None:
                                self.preview_ready.emit(self.zone_id, frame)
                            time.sleep(0.1)  # 10 FPS
                        except Exception as e:
                            print(f"Zone preview error: {e}")
                            break
                            
                def stop(self):
                    self.running = False
                    
            # Store the thread
            if not hasattr(self, 'zone_preview_threads'):
                self.zone_preview_threads = {}
                
            self.zone_preview_threads[zone_id] = ZonePreviewThread(self.detector, zone_id, self)
            self.zone_preview_threads[zone_id].preview_ready.connect(self.update_zone_preview)
            self.zone_preview_threads[zone_id].start()
            
        except Exception as e:
            self.log(f"Error starting zone preview: {e}")
            
    def stop_zone_preview(self, zone_id):
        """Stop live preview for a specific zone"""
        try:
            if hasattr(self, 'zone_preview_threads') and zone_id in self.zone_preview_threads:
                self.zone_preview_threads[zone_id].stop()
                self.zone_preview_threads[zone_id].wait(1000)  # Wait up to 1 second
                del self.zone_preview_threads[zone_id]
                
        except Exception as e:
            self.log(f"Error stopping zone preview: {e}")
            
    def update_zone_preview(self, zone_id, frame):
        """Update preview for a specific zone"""
        try:
            if zone_id not in self.zone_controls:
                return
                
            preview_label = self.zone_controls[zone_id]["preview_label"]
            
            # Convert frame to QPixmap for display
            if frame is not None:
                # Resize frame to fit preview area
                height, width = frame.shape[:2]
                preview_height = 50  # Match the fixed height of preview frame
                preview_width = int(width * preview_height / height)
                
                # Resize frame
                resized_frame = cv2.resize(frame, (preview_width, preview_height))
                
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
                
                # Convert to QImage
                height, width, channel = rgb_frame.shape
                bytes_per_line = 3 * width
                q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
                
                # Convert to QPixmap
                pixmap = QPixmap.fromImage(q_image)
                
                # Clear the preview frame and add the pixmap
                preview_frame = self.zone_controls[zone_id]["preview_frame"]
                preview_layout = preview_frame.layout()
                
                # Remove old preview label
                preview_layout.removeWidget(preview_label)
                preview_label.hide()
                
                # Create new preview label with pixmap
                new_preview_label = QLabel()
                new_preview_label.setPixmap(pixmap)
                new_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                new_preview_label.setStyleSheet("border: none;")
                preview_layout.addWidget(new_preview_label)
                
                # Update the stored reference
                self.zone_controls[zone_id]["preview_label"] = new_preview_label
                
        except Exception as e:
            self.log(f"Error updating zone preview: {e}")
            
    def update_zone_statistics(self):
        """Update zone statistics from detector"""
        try:
            if not self.detector:
                return
            zone_stats = self.detector.get_zone_stats()
            for zone_id, stats in zone_stats.items():
                if zone_id in self.zone_controls:
                    # Update detection count
                    count = stats.get("detection_count", 0)
                    self.zone_controls[zone_id]["detection_count"].setText(f"{count} detections")
                    # Update status
                    enabled = stats.get("enabled", False)
                    region = self.zone_controls[zone_id]["region_info"].text()
                    if enabled:
                        if region == "No region":
                            status = "Waiting"
                            indicator = "●"
                        else:
                            status = "Ready"
                            indicator = "●"
                    else:
                        status = "Disabled"
                        indicator = "○"
                    self.zone_controls[zone_id]["status_text"].setText(status)
                    self.zone_controls[zone_id]["status_indicator"].setText(indicator)
                    # Update enable checkbox
                    self.zone_controls[zone_id]["enable_checkbox"].setChecked(enabled)
        except Exception as e:
            self.log(f"Error updating zone statistics: {e}")
            
    def closeEvent(self, event):
        """Handle application close event"""
        try:
            # Stop all zone previews
            if hasattr(self, 'zone_preview_threads'):
                for zone_id, thread in self.zone_preview_threads.items():
                    thread.stop()
                    thread.wait(1000)
                    
            # Stop detection if running
            if self.detection_running:
                self.stop_detection()
                
            # Stop live preview if running
            if self.live_preview_running:
                self.stop_live_preview()
                
            event.accept()
            
        except Exception as e:
            self.log(f"Error during close: {e}")
            event.accept()
        
    def setup_system_tray(self):
        """Setup system tray icon and menu"""
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.system_tray = QSystemTrayIcon(self)
            self.system_tray.setIcon(qta.icon('fa5s.fish', color=UI_ACCENT_COLOR))
            
            # Create tray menu
            tray_menu = QMenu()
            
            # Restore action
            restore_action = QAction("Restore Main Window", self)
            restore_action.triggered.connect(self.restore_from_overlay)
            tray_menu.addAction(restore_action)
            
            # Minimize to overlay action
            minimize_action = QAction("Minimize to Overlay", self)
            minimize_action.triggered.connect(self.minimize_to_overlay)
            tray_menu.addAction(minimize_action)
            
            tray_menu.addSeparator()
            
            # Start/Stop action
            self.tray_start_stop_action = QAction("Start Detection", self)
            self.tray_start_stop_action.triggered.connect(self.toggle_detection)
            tray_menu.addAction(self.tray_start_stop_action)
            
            tray_menu.addSeparator()
            
            # Exit action
            exit_action = QAction("Exit", self)
            exit_action.triggered.connect(self.close)
            tray_menu.addAction(exit_action)
            
            self.system_tray.setContextMenu(tray_menu)
            
            # Connect double-click to restore
            self.system_tray.activated.connect(self.on_tray_activated)
            
            self.system_tray.show()
            
    def on_tray_activated(self, reason):
        """Handle system tray activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.overlay_mode:
                self.restore_from_overlay()
            else:
                self.show()
                self.raise_()
                self.activateWindow()
        
    def minimize_to_overlay(self):
        """Minimize the main window and show overlay"""
        if self.overlay_mode:
            return
            
        # First check if game window exists
        game_hwnd = self.detector.get_game_window_handle()
        if not game_hwnd:
            # Show dialog informing user that no game window was found
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Game Not Found")
            msg_box.setText("Play Together game window not found!")
            msg_box.setInformativeText("Please make sure the game is running before using overlay mode.")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            return
            
        # Store original geometry
        self.original_geometry = self.geometry()
        
        # Create overlay window
        self.overlay_window = OverlayWindow(self)
        
        # Start game window tracking
        self.game_tracker = GameWindowTracker(game_hwnd, self)
        self.game_tracker.position_changed.connect(self.update_overlay_position)
        self.game_tracker.window_lost.connect(self.handle_game_window_lost)
        self.game_tracker.start()
        
        # Get initial game window position
        try:
            import win32gui
            if win32gui.IsWindow(game_hwnd):
                rect = win32gui.GetWindowRect(game_hwnd)
                x, y, right, bottom = rect
                width = right - x
                height = bottom - y
                # Position overlay at top-left corner of game window
                self.update_overlay_position(x, y, width, height)
            else:
                # Fallback position if window not found
                self.overlay_window.move(10, 10)
        except Exception as e:
            print(f"Error getting game window position: {e}")
            # Fallback position
            self.overlay_window.move(10, 10)
            
        # Show overlay
        self.overlay_window.show()
        
        # Hide main window
        self.hide()
        
        # Update overlay status
        self.overlay_window.update_status(self.detection_running, self.detection_count)
        
        # Update system tray
        if self.system_tray:
            self.tray_start_stop_action.setText("Stop Detection" if self.detection_running else "Start Detection")
            
        self.overlay_mode = True
        
        # Log the action
        self.log("Minimized to overlay mode")
        
    def restore_from_overlay(self):
        """Restore the main window from overlay"""
        if not self.overlay_mode:
            return
            
        # Stop game tracker
        if self.game_tracker:
            self.game_tracker.stop()
            self.game_tracker.wait()
            self.game_tracker = None
            
        # Hide overlay
        if self.overlay_window:
            self.overlay_window.hide()
            self.overlay_window.deleteLater()
            self.overlay_window = None
            
        # Show main window
        if self.original_geometry:
            self.setGeometry(self.original_geometry)
        self.show()
        self.raise_()
        self.activateWindow()
        
        # Update system tray
        if self.system_tray:
            self.tray_start_stop_action.setText("Start Detection" if not self.detection_running else "Stop Detection")
            
        self.overlay_mode = False
        
        # Log the action
        self.log("Restored from overlay mode")
        
    def update_overlay_position(self, x, y, width, height):
        """Update overlay position based on game window position"""
        if self.overlay_window and self.overlay_mode:
            # Position overlay at top-left corner of game window with small offset
            overlay_x = x + 5  # 5px offset from left
            overlay_y = y + 5  # 5px offset from top
            
            # Ensure overlay stays within screen bounds
            screen = QApplication.primaryScreen().geometry()
            if overlay_x < 0:
                overlay_x = 5
            if overlay_y < 0:
                overlay_y = 5
            if overlay_x + 50 > screen.width():
                overlay_x = screen.width() - 55
            if overlay_y + 50 > screen.height():
                overlay_y = screen.height() - 55
                
            self.overlay_window.move(overlay_x, overlay_y)
            
    def handle_game_window_lost(self):
        """Handle when the game window is closed"""
        if self.overlay_mode:
            # Show dialog asking user what to do
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Game Window Closed")
            msg_box.setText("The Play Together game window was closed!")
            msg_box.setInformativeText("Would you like to restore the main AutoFisher window?")
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
            
            result = msg_box.exec()
            if result == QMessageBox.StandardButton.Yes:
                self.restore_from_overlay()
            else:
                # Keep overlay but stop tracking
                if self.game_tracker:
                    self.game_tracker.stop()
                    self.game_tracker.wait()
                    self.game_tracker = None
        
    def toggle_detection(self):
        """Toggle detection on/off"""
        if self.detection_running:
            self.stop_detection()
        else:
            self.start_detection()
            
        # Update overlay status
        if self.overlay_window and self.overlay_mode:
            self.overlay_window.update_status(self.detection_running, self.detection_count)
            
        # Update system tray
        if self.system_tray:
            self.tray_start_stop_action.setText("Stop Detection" if self.detection_running else "Start Detection")
            
    def handle_zone_detection(self, zone_id):
        """Handle zone detection and update overlay"""
        self.increment_detection_count()
        
        # Update overlay if in overlay mode
        if self.overlay_window and self.overlay_mode:
            self.overlay_window.update_status(self.detection_running, self.detection_count)
            
    def closeEvent(self, event):
        """Handle application close event"""
        # Stop detection if running
        if self.detection_running:
            self.stop_detection()
            
        # Stop game tracker
        if self.game_tracker:
            self.game_tracker.stop()
            self.game_tracker.wait()
            
        # Hide overlay
        if self.overlay_window:
            self.overlay_window.hide()
            self.overlay_window.deleteLater()
            
        # Hide system tray
        if self.system_tray:
            self.system_tray.hide()
            
        # Call parent close event
        super().closeEvent(event)