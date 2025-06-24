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
    QLabel, QComboBox, QSystemTrayIcon, QMenu, QMessageBox, QDialog
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
    UI_ACCENT_HOVER, UI_ACCENT_ACTIVE,
    DEFAULT_DETECTION_ZONES, UI_CONFIG
)

def enhance_visualization(frame):
    """Enhance a frame for better visualization"""
    if frame is None:
        return None
        
    try:
        # Make a copy to avoid modifying the original
        enhanced = frame.copy()
        
        # Ensure the frame is RGB
        if len(enhanced.shape) == 2:  # Grayscale
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
        elif enhanced.shape[2] == 4:  # RGBA
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_RGBA2RGB)
            
        # Apply simple brightness/contrast enhancement
        enhanced = cv2.convertScaleAbs(enhanced, alpha=1.2, beta=10)
        
        return enhanced
    except Exception:
        return frame  # Return original frame if enhancement fails

class OverlayWindow(QWidget):
    """Clean overlay window with all features in one interface"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Track window dragging
        self.dragging = False
        self.offset = QPoint()
        
        # Zone indicators
        self.zone_indicators = {}
        
        # Initialize UI
        self.init_ui()
        
        # Set initial size
        self.setMinimumWidth(300)
        # Calculate initial size based on visible sections
        self.adjust_window_size()
        
    def init_ui(self):
        """Initialize the overlay UI"""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(5)
        self.main_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinAndMaxSize)
        
        # Track section visibility
        self.sections_visible = {
            'settings': False,
            'visualization': False
        }
        
        # Create header (title bar) with all controls
        self.header = QWidget()
        self.header.setStyleSheet(f"""
            background-color: {UI_DARK_BG};
            border-radius: 4px;
        """)
        self.header.setFixedHeight(36)  # Fixed height for header
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(5)
        
        # Status indicator
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 14pt;")
        header_layout.addWidget(self.status_indicator)
        
        # Title
        title_label = QLabel(f"AutoFisher v{VERSION}")
        title_label.setStyleSheet(f"color: {UI_ACCENT_COLOR}; font-weight: bold;")
        header_layout.addWidget(title_label)
        
        # Add spacer
        header_layout.addStretch()
        
        # Start/Stop button in title bar
        self.start_stop_button = QPushButton()
        self.start_stop_button.setIcon(qta.icon('fa5s.play', color=UI_SUCCESS_COLOR))
        self.start_stop_button.setToolTip("Start Fishing")
        self.start_stop_button.setFixedSize(24, 24)
        self.start_stop_button.setStyleSheet("background: transparent; border: none;")
        self.start_stop_button.clicked.connect(self.toggle_detection)
        header_layout.addWidget(self.start_stop_button)
        
        # Region selection button in title bar
        self.region_button = QPushButton()
        self.region_button.setIcon(qta.icon('fa5s.crop-alt', color=UI_LIGHT_TEXT))
        self.region_button.setToolTip("Select Region")
        self.region_button.setFixedSize(24, 24)
        self.region_button.setStyleSheet("background: transparent; border: none;")
        self.region_button.clicked.connect(self.select_region)
        header_layout.addWidget(self.region_button)
        
        # Settings button in title bar
        self.settings_button = QPushButton()
        self.settings_button.setIcon(qta.icon('fa5s.cog', color=UI_LIGHT_TEXT))
        self.settings_button.setToolTip("Settings")
        self.settings_button.setFixedSize(24, 24)
        self.settings_button.setStyleSheet("background: transparent; border: none;")
        self.settings_button.clicked.connect(self.toggle_settings)
        header_layout.addWidget(self.settings_button)
        
        # FPS monitor button in title bar
        self.fps_button = QPushButton()
        self.fps_button.setIcon(qta.icon('fa5s.tachometer-alt', color=UI_LIGHT_TEXT))
        self.fps_button.setToolTip("FPS: 0")
        self.fps_button.setFixedSize(24, 24)
        self.fps_button.setStyleSheet("background: transparent; border: none;")
        header_layout.addWidget(self.fps_button)
        
        # Minimize button
        self.minimize_button = QPushButton()
        self.minimize_button.setIcon(qta.icon('fa5s.window-minimize', color=UI_LIGHT_TEXT))
        self.minimize_button.setToolTip("Minimize")
        self.minimize_button.setFixedSize(24, 24)
        self.minimize_button.setStyleSheet("background: transparent; border: none;")
        self.minimize_button.clicked.connect(self.toggle_content)
        header_layout.addWidget(self.minimize_button)
        
        # Exit button
        exit_button = QPushButton()
        exit_button.setIcon(qta.icon('fa5s.times', color=UI_ERROR_COLOR))
        exit_button.setToolTip("Exit")
        exit_button.setFixedSize(24, 24)
        exit_button.setStyleSheet("background: transparent; border: none;")
        exit_button.clicked.connect(lambda: QApplication.quit())
        header_layout.addWidget(exit_button)
        
        # Add header to main layout
        self.main_layout.addWidget(self.header)
        
        # Content area
        self.content = QWidget()
        self.content.setStyleSheet(f"""
            background-color: {UI_DARK_BG};
            border: 1px solid {UI_WOOD_DARK};
            border-radius: 4px;
        """)
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(5)
        
        # Stats group
        stats_group = QGroupBox("Statistics")
        stats_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 3px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                color: {UI_ACCENT_COLOR};
                subcontrol-origin: margin;
                left: 7px;
                padding: 0 3px;
            }}
        """)
        stats_layout = QGridLayout(stats_group)
        stats_layout.setContentsMargins(8, 10, 8, 8)
        stats_layout.setSpacing(5)
        
        # Add statistics
        stats_layout.addWidget(QLabel("Detections:"), 0, 0)
        self.count_label = QLabel("0")
        self.count_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.count_label, 0, 1)
        
        stats_layout.addWidget(QLabel("Runtime:"), 1, 0)
        self.runtime_label = QLabel("00:00:00")
        self.runtime_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.runtime_label, 1, 1)
        
        stats_layout.addWidget(QLabel("Status:"), 2, 0)
        self.status_label = QLabel("Idle")
        self.status_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.status_label, 2, 1)
        
        # Add FPS and threshold
        stats_layout.addWidget(QLabel("FPS:"), 3, 0)
        self.fps_label = QLabel("0")
        self.fps_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.fps_label, 3, 1)
        
        stats_layout.addWidget(QLabel("Threshold:"), 4, 0)
        self.threshold_label = QLabel("0.045")
        self.threshold_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self.threshold_label, 4, 1)
        
        content_layout.addWidget(stats_group)
        
        # Settings section (initially hidden)
        self.settings_section = QGroupBox("Settings")
        self.settings_section.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 3px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                color: {UI_ACCENT_COLOR};
                subcontrol-origin: margin;
                left: 7px;
                padding: 0 3px;
            }}
            QLabel {{
                font-size: 8pt;
            }}
            QSlider {{
                max-height: 15px;
            }}
        """)
        settings_layout = QVBoxLayout(self.settings_section)
        settings_layout.setContentsMargins(6, 10, 6, 6)
        settings_layout.setSpacing(3)
        
        # Threshold setting
        threshold_layout = QHBoxLayout()
        threshold_layout.setContentsMargins(0, 0, 0, 0)
        threshold_layout.setSpacing(5)
        
        threshold_label = QLabel("Threshold:")
        threshold_label.setFixedWidth(60)
        threshold_layout.addWidget(threshold_label)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(10)
        self.threshold_slider.setMaximum(100)
        self.threshold_slider.setValue(45)
        self.threshold_slider.setFixedHeight(15)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_value = QLabel("0.045")
        self.threshold_value.setFixedWidth(35)
        self.threshold_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        threshold_layout.addWidget(self.threshold_value)
        
        self.threshold_slider.valueChanged.connect(
            lambda v: self.threshold_value.setText(f"{v/1000:.3f}")
        )
        
        settings_layout.addLayout(threshold_layout)
        
        # Cooldown setting
        cooldown_layout = QHBoxLayout()
        cooldown_layout.setContentsMargins(0, 0, 0, 0)
        cooldown_layout.setSpacing(5)
        
        cooldown_label = QLabel("Cooldown:")
        cooldown_label.setFixedWidth(60)
        cooldown_layout.addWidget(cooldown_label)
        
        self.cooldown_slider = QSlider(Qt.Orientation.Horizontal)
        self.cooldown_slider.setMinimum(10)
        self.cooldown_slider.setMaximum(100)
        self.cooldown_slider.setValue(50)
        self.cooldown_slider.setFixedHeight(15)
        cooldown_layout.addWidget(self.cooldown_slider)
        
        self.cooldown_value = QLabel("5.0s")
        self.cooldown_value.setFixedWidth(35)
        self.cooldown_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        cooldown_layout.addWidget(self.cooldown_value)
        
        self.cooldown_slider.valueChanged.connect(
            lambda v: self.cooldown_value.setText(f"{v/10:.1f}s")
        )
        
        settings_layout.addLayout(cooldown_layout)
        
        # Create a grid for more compact settings
        options_grid = QGridLayout()
        options_grid.setContentsMargins(0, 0, 0, 0)
        options_grid.setSpacing(5)
        
        # Fishing key
        key_label = QLabel("Fishing Key:")
        key_label.setFixedWidth(60)
        options_grid.addWidget(key_label, 0, 0)
        
        self.fishing_key = QLineEdit("f")
        self.fishing_key.setMaxLength(1)
        self.fishing_key.setFixedWidth(30)
        options_grid.addWidget(self.fishing_key, 0, 1)
        
        # High performance mode
        perf_label = QLabel("High Perf:")
        perf_label.setFixedWidth(60)
        options_grid.addWidget(perf_label, 1, 0)
        
        self.high_perf = QCheckBox()
        self.high_perf.setChecked(True)
        options_grid.addWidget(self.high_perf, 1, 1)
        
        # Display options
        viz_label = QLabel("Show Viz:")
        viz_label.setFixedWidth(60)
        options_grid.addWidget(viz_label, 2, 0)
        
        self.show_viz = QCheckBox()
        self.show_viz.setChecked(False)
        self.show_viz.stateChanged.connect(
            lambda state: self.update_visualization_visibility(state == 2)
        )
        options_grid.addWidget(self.show_viz, 2, 1)
        
        settings_layout.addLayout(options_grid)
        
        # Apply button
        apply_layout = QHBoxLayout()
        apply_layout.addStretch()
        
        apply_button = QPushButton("Apply")
        apply_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_WOOD_DARK};
                color: {UI_LIGHT_TEXT};
                border: none;
                border-radius: 3px;
                padding: 3px 8px;
                font-size: 8pt;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
        """)
        apply_button.clicked.connect(self.apply_settings)
        apply_layout.addWidget(apply_button)
        
        settings_layout.addLayout(apply_layout)
        
        # Add settings section to content
        content_layout.addWidget(self.settings_section)
        self.settings_section.setVisible(False)  # Initially hidden
        
        # Zone indicators section
        zone_group = QGroupBox("Detection Zones")
        zone_group.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 3px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                color: {UI_ACCENT_COLOR};
                subcontrol-origin: margin;
                left: 7px;
                padding: 0 3px;
            }}
        """)
        zone_layout = QVBoxLayout(zone_group)
        zone_layout.setContentsMargins(8, 10, 8, 8)
        zone_layout.setSpacing(5)
        
        # Create simple zone indicators
        for zone_id, zone_config in DEFAULT_DETECTION_ZONES.items():
            zone_color = UI_CONFIG['zone_colors'].get(zone_id, UI_ACCENT_COLOR)
            
            zone_row = QHBoxLayout()
            
            # Zone indicator
            indicator = QLabel("○")
            indicator.setStyleSheet(f"color: {zone_color}; font-size: 12pt; font-weight: bold;")
            zone_row.addWidget(indicator)
            
            # Store reference to indicator
            self.zone_indicators[zone_id] = indicator
            
            # Zone name
            name_label = QLabel(zone_config["name"])
            name_label.setStyleSheet(f"color: {UI_LIGHT_TEXT}; font-weight: bold;")
            zone_row.addWidget(name_label)
            
            zone_layout.addLayout(zone_row)
            
        content_layout.addWidget(zone_group)
        
        # Add visualization section (initially hidden)
        self.viz_section = QGroupBox("Visualization")
        self.viz_section.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 3px;
                margin-top: 8px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                color: {UI_ACCENT_COLOR};
                subcontrol-origin: margin;
                left: 7px;
                padding: 0 3px;
            }}
        """)
        viz_layout = QVBoxLayout(self.viz_section)
        viz_layout.setContentsMargins(4, 10, 4, 4)
        
        # Create a frame to contain the visualization
        viz_frame = QFrame()
        viz_frame.setStyleSheet(f"background-color: {UI_DARK_BG}; border: none;")
        viz_frame.setMinimumHeight(120)
        viz_frame.setMaximumHeight(160)
        viz_frame_layout = QVBoxLayout(viz_frame)
        viz_frame_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add placeholder for visualization
        self.viz_placeholder = QLabel("No visualization")
        self.viz_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viz_placeholder.setStyleSheet(f"color: {UI_SECONDARY_TEXT};")
        viz_frame_layout.addWidget(self.viz_placeholder)
        
        viz_layout.addWidget(viz_frame)
        
        # Add visualization section to content
        content_layout.addWidget(self.viz_section)
        self.viz_section.setVisible(False)  # Initially hidden
        
        # Add content to main layout
        self.main_layout.addWidget(self.content)
        
    def toggle_content(self):
        """Toggle content visibility"""
        # Toggle main content visibility
        is_visible = not self.content.isVisible()
        self.content.setVisible(is_visible)
        
        # If hiding content, make sure all sections are also hidden
        if not is_visible:
            # Hide all sections
            self.settings_section.setVisible(False)
            self.viz_section.setVisible(False)
            
            # Update tracking
            self.sections_visible['settings'] = False
            self.sections_visible['visualization'] = False
            
            # Reset UI elements
            self.settings_button.setIcon(qta.icon('fa5s.cog', color=UI_LIGHT_TEXT))
            self.show_viz.setChecked(False)
        
        # Update minimize button icon
        if is_visible:
            self.minimize_button.setIcon(qta.icon('fa5s.window-minimize', color=UI_LIGHT_TEXT))
        else:
            self.minimize_button.setIcon(qta.icon('fa5s.window-maximize', color=UI_LIGHT_TEXT))
            
        # Calculate and apply the appropriate window size
        self.adjust_window_size()
        
    def toggle_settings(self):
        """Toggle settings section visibility"""
        # Toggle visibility state
        self.sections_visible['settings'] = not self.sections_visible['settings']
        
        # Update visibility
        self.settings_section.setVisible(self.sections_visible['settings'])
        
        # Update the settings icon to indicate state
        if self.sections_visible['settings']:
            self.settings_button.setIcon(qta.icon('fa5s.cog', color=UI_ACCENT_COLOR))
        else:
            self.settings_button.setIcon(qta.icon('fa5s.cog', color=UI_LIGHT_TEXT))
            
        # Calculate and apply new size
        self.adjust_window_size()
        
    def update_visualization_visibility(self, visible):
        """Update visualization section visibility"""
        # Update tracking
        self.sections_visible['visualization'] = visible
        
        # Update visibility
        self.viz_section.setVisible(visible)
        
        # Calculate and apply new size
        self.adjust_window_size()
        
    def toggle_visualization(self):
        """Toggle visualization section visibility"""
        # Toggle visibility state
        self.sections_visible['visualization'] = not self.sections_visible['visualization']
        
        # Update visibility
        self.viz_section.setVisible(self.sections_visible['visualization'])
        
        # Update checkbox to match
        self.show_viz.setChecked(self.sections_visible['visualization'])
        
        # Calculate and apply new size
        self.adjust_window_size()
        
    def adjust_window_size(self):
        """Calculate and apply the appropriate window size based on visible sections"""
        from utils.constants import SECTION_SIZES
        
        # Store current position
        current_pos = self.pos()
        
        # If content is not visible, just show the header
        if not self.content.isVisible():
            new_height = self.header.height() + 10
            self.resize(self.width(), new_height)
            self.move(current_pos)
            return
            
        # Start with base height (header + basic margins)
        height = SECTION_SIZES["base_height"]
        width = max(SECTION_SIZES["base_width"], self.width())
        
        # Add height for each visible section
        if self.sections_visible['settings']:
            height += SECTION_SIZES["settings_panel"]
        
        if self.sections_visible['visualization']:
            height += SECTION_SIZES["visualization_panel"]
            
        # Add margins
        height += SECTION_SIZES["margins"]
        
        # Apply new size
        self.resize(width, height)
        
        # Restore position to prevent window jumping
        self.move(current_pos)
        
    def update_visualization(self, frame=None):
        """Update the visualization with the current frame"""
        if frame is None or not self.viz_section.isVisible():
            return
            
        # Convert frame to QPixmap for display
        height, width = frame.shape[:2]
        
        # Resize frame to fit the visualization area
        max_height = 150
        max_width = 250
        
        # Calculate aspect ratio
        aspect_ratio = width / height
        
        # Determine new size while maintaining aspect ratio
        if width > height:
            new_width = min(max_width, width)
            new_height = int(new_width / aspect_ratio)
            if new_height > max_height:
                new_height = max_height
                new_width = int(new_height * aspect_ratio)
        else:
            new_height = min(max_height, height)
            new_width = int(new_height * aspect_ratio)
            if new_width > max_width:
                new_width = max_width
                new_height = int(new_width / aspect_ratio)
        
        # Resize frame and convert to RGB
        resized_frame = cv2.resize(frame, (new_width, new_height))
        rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
        
        # Convert to QImage and QPixmap
        height, width, channel = rgb_frame.shape
        bytes_per_line = 3 * width
        q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)
        
        # Update the visualization widget
        viz_frame = self.viz_section.layout().itemAt(0).widget()
        viz_layout = viz_frame.layout()
        
        # Remove old placeholder
        for i in reversed(range(viz_layout.count())): 
            widget = viz_layout.itemAt(i).widget()
            if widget:
                widget.hide()
                viz_layout.removeWidget(widget)
        
        # Create new label with pixmap
        viz_label = QLabel()
        viz_label.setPixmap(pixmap)
        viz_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        viz_label.setStyleSheet("border: none;")
        viz_layout.addWidget(viz_label)
        
    def mousePressEvent(self, event):
        """Handle mouse press events for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            if self.header.geometry().contains(event.pos()):
                # Store press time for double-click detection
                self.press_time = time.time()
                self.press_pos = event.pos()
                
                # Start dragging
                self.dragging = True
                self.offset = event.pos()
            
    def mouseMoveEvent(self, event):
        """Handle mouse move events for dragging"""
        if self.dragging and event.buttons() & Qt.MouseButton.LeftButton:
            # Only drag if we've moved more than a few pixels
            delta = (event.pos() - self.press_pos).manhattanLength()
            if delta > 3:
                self.move(self.mapToGlobal(event.pos() - self.offset))
            
    def mouseReleaseEvent(self, event):
        """Handle mouse release events for dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check for double-click (quick click without much movement)
            if hasattr(self, 'press_time'):
                delta_time = time.time() - self.press_time
                delta_pos = (event.pos() - self.press_pos).manhattanLength()
                
                # If quick click without much movement, toggle content
                if delta_time < 0.3 and delta_pos < 5 and self.header.geometry().contains(event.pos()):
                    self.toggle_content()
            
            # End dragging
            self.dragging = False
            
    def update_status(self, is_running, detection_count):
        """Update the overlay status"""
        # Update status indicator
        if is_running:
            self.status_indicator.setStyleSheet(f"color: {UI_SUCCESS_COLOR}; font-size: 14pt;")
            self.status_label.setText("Running")
            
            # Update start/stop button
            self.start_stop_button.setIcon(qta.icon('fa5s.stop', color=UI_ERROR_COLOR))
            self.start_stop_button.setToolTip("Stop Fishing")
        else:
            self.status_indicator.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 14pt;")
            self.status_label.setText("Idle")
            
            # Update start/stop button
            self.start_stop_button.setIcon(qta.icon('fa5s.play', color=UI_SUCCESS_COLOR))
            self.start_stop_button.setToolTip("Start Fishing")
            
        # Update count
        self.count_label.setText(str(detection_count))
            
    def update_zone_status(self, zone_id, active):
        """Update the status of a specific zone"""
        if zone_id not in self.zone_indicators:
            return
            
        indicator = self.zone_indicators[zone_id]
        
        if active:
            color = UI_SUCCESS_COLOR
            text = "●"
        else:
            color = UI_CONFIG['zone_colors'].get(zone_id, UI_SECONDARY_TEXT)
            text = "○"
            
        indicator.setText(text)
        indicator.setStyleSheet(f"color: {color}; font-size: 12pt; font-weight: bold;")
        
    def update_runtime(self, elapsed_time):
        """Update runtime display"""
        hours, remainder = divmod(int(elapsed_time), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.runtime_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
    def update_fps(self, fps):
        """Update FPS display"""
        if hasattr(self, 'fps_label'):
            self.fps_label.setText(str(int(fps)))
        if hasattr(self, 'fps_button'):
            self.fps_button.setToolTip(f"FPS: {int(fps)}")
            
    def update_threshold(self, threshold):
        """Update threshold display"""
        if hasattr(self, 'threshold_label'):
            self.threshold_label.setText(f"{threshold:.3f}")
            
        # Also update the slider if it doesn't match
        if hasattr(self, 'threshold_slider') and hasattr(self, 'threshold_value'):
            slider_value = int(threshold * 1000)
            if self.threshold_slider.value() != slider_value:
                self.threshold_slider.setValue(slider_value)
                self.threshold_value.setText(f"{threshold:.3f}")
        
    def toggle_detection(self):
        """Toggle detection on/off"""
        if self.parent():
            # Use handle_tray_start_stop which is the correct method
            if hasattr(self.parent(), 'handle_tray_start_stop'):
                self.parent().handle_tray_start_stop()
            # Fallbacks if that's not available
            elif hasattr(self.parent(), 'start_detection') and hasattr(self.parent(), 'stop_detection'):
                parent = self.parent()
                if hasattr(parent, 'detection_running') and parent.detection_running:
                    parent.stop_detection()
                else:
                    parent.start_detection()
                    
    def select_region(self):
        """Open region selection dialog"""
        if self.parent():
            # Check if we're in overlay-only mode
            if hasattr(self.parent(), 'select_region'):
                self.parent().select_region()
                
    def apply_settings(self):
        """Apply settings to parent detector"""
        if not self.parent() or not hasattr(self.parent(), 'detector'):
            return
            
        parent = self.parent()
        detector = parent.detector
        
        # Get current settings
        threshold = self.threshold_slider.value() / 1000.0
        cooldown = self.cooldown_slider.value() / 10.0
        fishing_key = self.fishing_key.text()
        high_perf = self.high_perf.isChecked()
        
        # Apply settings to detector
        if detector:
            # Update threshold for all zones
            for zone in detector.zones.values():
                zone.threshold = threshold
                
            # Update cooldown
            detector.detection_cooldown = cooldown
            
            # Update fishing key
            detector.fishing_key = fishing_key
            
            # Update performance mode
            detector.high_performance_mode = high_perf
            
            # Update threshold display
            self.update_threshold(threshold)
            
        # Update visualization visibility based on checkbox
        show_viz = self.show_viz.isChecked()
        self.sections_visible['visualization'] = show_viz
        self.viz_section.setVisible(show_viz)
        
        # Update settings section state after applying
        # Don't force hide it - let the toggle_settings method handle visibility
        if self.sections_visible['settings']:
            # If settings are currently visible, keep them visible
            self.settings_button.setIcon(qta.icon('fa5s.cog', color=UI_ACCENT_COLOR))
        else:
            # If settings are hidden, keep the icon in normal state
            self.settings_button.setIcon(qta.icon('fa5s.cog', color=UI_LIGHT_TEXT))
        
        # Calculate and apply new size
        self.adjust_window_size()
            
        # Log changes
        if hasattr(parent, 'log'):
            parent.log(f"Applied settings: threshold={threshold:.3f}, cooldown={cooldown:.1f}s, key={fishing_key}, high_perf={high_perf}")

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
                
            except Exception:
                # Sleep and continue on any error
                time.sleep(1.0)
                
    def stop(self):
        self.running = False

class AutoFisherMainWindow(QMainWindow):
    """Main window for the AutoFisher Qt application"""
    
    def __init__(self, overlay_only=False):
        """Initialize the main window"""
        super().__init__()
        self.setWindowTitle(f"AutoFisher Qt v{VERSION} - {VERSION_NAME}")
        
        # Set overlay-only mode
        self.overlay_only = overlay_only
        
        # Set fixed window size
        self.setFixedSize(380, 780)
        
        # Initialize instance variables
        self.detector = None
        self.live_preview_running = False
        self.detection_running = False
        self.start_time = time.time()  # Initialize start time
        self.detection_count = 0
        self.vis_frame = None
        self.selected_region = None
        self.region_selector = None
        self.vis_timer = None
        
        # Create message queue for logging
        self.log_queue = queue.Queue()
        
        # Overlay functionality
        self.overlay_mode = False
        self.overlay_window = None
        self.full_overlay_window = None
        self.game_tracker = None
        self.original_geometry = None
        self.use_full_overlay = True  # Default to using the full overlay
        
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
                margin-top: 6px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0px 5px 0px 5px;
                color: {UI_ACCENT_COLOR};
            }}
        """)
        
        # Initialize detector for both modes
        self.try_initialize_detector()
        
        # Don't initialize the UI in overlay-only mode
        if not overlay_only:
            self.init_ui()
        
        # Configure logs update timer
        self.log_timer = QTimer()
        self.log_timer.setInterval(100)  # 10 times per second
        self.log_timer.timeout.connect(self.update_logs)
        self.log_timer.start()  # Start the log timer immediately
        
        # Setup timer for statistics updates
        self.stats_timer = QTimer()
        self.stats_timer.setInterval(1000)  # Update every second
        self.stats_timer.timeout.connect(self.update_statistics)
        self.stats_timer.start()
        
        # Log initialization
        self.log("AutoFisher Qt initialized")
        self.log("Select a region to begin")
        
        # Start in overlay mode if requested
        if overlay_only:
            QTimer.singleShot(100, self.minimize_to_overlay)
    
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
        """Update the log display with messages from the queue"""
        if self.overlay_only:
            # Just consume logs without displaying in overlay-only mode
            while not self.log_queue.empty():
                self.log_queue.get()
            return
            
        # Skip if no log queue or widget available
        if not hasattr(self, 'log_queue') or not hasattr(self, 'log_text'):
            return
            
        # Process all waiting messages
        new_logs = False
        while not self.log_queue.empty():
            try:
                message = self.log_queue.get(block=False)
                self.log_text.append(message)
                new_logs = True
            except queue.Empty:
                break
                
        # Scroll to bottom if we added new logs
        if new_logs:
            self.log_text.verticalScrollBar().setValue(
                self.log_text.verticalScrollBar().maximum()
            )
    
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
            high_perf = self.high_perf.isChecked()
            respect_fullscreen = self.respect_fullscreen_checkbox.isChecked()
            direct_control = self.direct_control_checkbox.isChecked()
            
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
                self.detector.high_performance_mode = high_perf
                self.detector.respect_fullscreen = respect_fullscreen
                self.detector.direct_control = direct_control
                
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
        """Open region selection dialog"""
        if self.overlay_only:
            # Use a simpler approach for overlay-only mode
            try:
                from ui.selection import TkRegionSelector
                selector = TkRegionSelector(self)
                
                # Get game window handle if we have a detector
                game_window = None
                if self.detector:
                    game_window = self.detector.get_game_window_handle()
                    
                # Select region
                region = selector.select_region(game_window)
                
                if region:
                    self.set_region(region)
                    self.log(f"Selected region: {region}")
            except Exception as e:
                self.log(f"Error selecting region: {e}")
            return
            
        # Regular implementation for non-overlay mode
        # This part would normally use UI elements like size_entry
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
        """Update visualization with the latest frame"""
        if not self.detector:
            return
            
        # Get the latest frame
        if hasattr(self.detector, 'current_frame') and self.detector.current_frame is not None:
            # Enhance visualization for better clarity
            enhanced_frame = enhance_visualization(self.detector.current_frame.copy())
            
            # Update canvas display
            self.viz_canvas.update_image(enhanced_frame)
            
            # Update overlay visualization if in overlay mode
            if self.overlay_mode and self.use_full_overlay and self.full_overlay_window:
                self.full_overlay_window.update_visualization(enhanced_frame)
                
    def handle_zone_detection(self, zone_id):
        """Handle a detection event from a specific zone"""
        self.log(f"Detection in zone: {zone_id}")
        self.increment_detection_count()
        
        # Update overlay if active
        self.update_overlay()
        
        # Also update visualization in overlay
        if self.overlay_mode and self.use_full_overlay and self.full_overlay_window:
            self.full_overlay_window.update_visualization()
            
    def increment_detection_count(self):
        """Increment detection counter and update UI"""
        self.detection_count += 1
        self.update_statistics()
        
        # Update overlay if active
        self.update_overlay()
    
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
        
    def toggle_detection(self):
        """Toggle detection on/off - called from tray menu"""
        if self.detection_running:
            self.stop_detection()
        else:
            self.start_detection()
            
    def setup_system_tray(self):
        """Set up system tray icon"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.log("System tray not available")
            return
            
        # Create tray icon using qtawesome
        icon = qta.icon('fa5s.fish', color=UI_ACCENT_COLOR)
        self.system_tray = QSystemTrayIcon(icon, self)
        self.system_tray.setToolTip(f"AutoFisher {VERSION}")
        
        # Create tray menu
        tray_menu = QMenu()
        
        # Add start/stop action
        self.tray_start_stop_action = QAction("Start Fishing", self)
        
        # Connect to a method that checks state and calls appropriate method
        self.tray_start_stop_action.triggered.connect(self.toggle_detection)
        tray_menu.addAction(self.tray_start_stop_action)
        
        # Add overlay mode toggle
        self.tray_overlay_mode_action = QAction("Use Simple Overlay", self)
        self.tray_overlay_mode_action.triggered.connect(self.toggle_overlay_mode)
        tray_menu.addAction(self.tray_overlay_mode_action)
        
        # Add minimize to overlay action
        minimize_action = QAction("Minimize to Overlay", self)
        minimize_action.triggered.connect(self.minimize_to_overlay)
        tray_menu.addAction(minimize_action)
        
        # Add restore action
        restore_action = QAction("Restore Window", self)
        restore_action.triggered.connect(self.restore_from_overlay)
        tray_menu.addAction(restore_action)
        
        # Add separator
        tray_menu.addSeparator()
        
        # Add quit action
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        tray_menu.addAction(quit_action)
        
        # Set the menu
        self.system_tray.setContextMenu(tray_menu)
        
        # Connect activated signal
        self.system_tray.activated.connect(self.on_tray_activated)
        
        # Show the tray icon
        self.system_tray.show()
        
    def handle_tray_start_stop(self):
        """Handle start/stop action from the system tray"""
        # Call toggle_detection to handle the actual toggling
        self.toggle_detection()
        
        # Update the tray menu text based on the new state
        if self.detection_running:
            self.tray_start_stop_action.setText("Stop Fishing")
        else:
            self.tray_start_stop_action.setText("Start Fishing")
            
        # Update overlay if active
        self.update_overlay()
        
    def on_tray_activated(self, reason):
        """Handle tray icon activation"""
        # Left click or double click to toggle window visibility
        if reason == QSystemTrayIcon.ActivationReason.Trigger or reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                if self.overlay_mode:
                    self.restore_from_overlay()
                else:
                    self.show()
                    self.activateWindow()
                    
    def toggle_overlay_mode(self):
        """Toggle between simple and full overlay modes"""
        self.use_full_overlay = not self.use_full_overlay
        
        # Update tray menu text
        if hasattr(self, 'tray_overlay_mode_action'):
            self.tray_overlay_mode_action.setText("Use Simple Overlay" if self.use_full_overlay else "Use Full Overlay")
        
        # If currently in overlay mode, switch the overlay type
        if self.overlay_mode:
            # Hide current overlay
            if self.overlay_window:
                self.overlay_window.hide()
            if self.full_overlay_window:
                self.full_overlay_window.hide()
                
            # Go back to minimize_to_overlay which will use the new setting
            self.minimize_to_overlay()
        
        overlay_type = "full" if self.use_full_overlay else "simple"
        self.log(f"Switched to {overlay_type} overlay mode")

    def closeEvent(self, event):
        """Handle application close event"""
        # Stop detection if running
        if self.detection_running:
            self.stop_detection()
            
        # Stop live preview if running
        if hasattr(self, 'preview_thread') and self.preview_thread and self.preview_thread.isRunning():
            self.preview_thread.stop()
            self.preview_thread.wait(1000)  # Wait up to 1 second
            
        # Stop zone preview threads if running
        if hasattr(self, 'zone_preview_threads'):
            for thread in self.zone_preview_threads.values():
                if thread and thread.isRunning():
                    thread.stop()
                    thread.wait(1000)  # Wait up to 1 second
            
        # Stop game tracker
        if self.game_tracker:
            self.game_tracker.stop()
            self.game_tracker.wait(1000)  # Wait up to 1 second
            self.game_tracker = None
            
        # Stop any other threads
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, QThread) and attr.isRunning():
                try:
                    attr.stop()  # Try to stop if it has a stop method
                except:
                    pass
                attr.wait(1000)  # Wait up to 1 second
            
        # Hide overlays
        if self.overlay_window:
            self.overlay_window.hide()
            self.overlay_window.deleteLater()
        if self.full_overlay_window:
            self.full_overlay_window.hide()
            self.full_overlay_window.deleteLater()
            
        # Hide system tray
        if self.system_tray:
            self.system_tray.hide()
            
        # Process events to ensure cleanup happens
        QApplication.processEvents()
            
        # Call parent close event
        super().closeEvent(event)

    def minimize_to_overlay(self):
        """Minimize the main window to an overlay"""
        self.overlay_mode = True
        
        if self.use_full_overlay:
            # Use full overlay window with all controls
            if not self.full_overlay_window:
                # Create the full overlay window
                from ui.main_window import FullOverlayWindow
                self.full_overlay_window = FullOverlayWindow(self)
                
            # Position it on screen
            screen_geometry = QApplication.primaryScreen().geometry()
            self.full_overlay_window.move(
                screen_geometry.width() - self.full_overlay_window.width() - 20, 
                100
            )
            
            # Show the overlay window
            self.full_overlay_window.show()
            # Calculate proper size based on visible sections
            self.full_overlay_window.adjust_size()
        else:
            # Use simple overlay window
            if not self.overlay_window:
                # Create the overlay window
                from ui.main_window import OverlayWindow
                self.overlay_window = OverlayWindow(self)
            
            # Position it on screen
            screen_geometry = QApplication.primaryScreen().geometry()
            self.overlay_window.move(
                screen_geometry.width() - self.overlay_window.width() - 20,
                100
            )
            
            # Show the overlay window
            self.overlay_window.show()
            # Calculate proper size based on visible sections
            self.overlay_window.adjust_window_size()
        
        # Start game window tracking if we have a window
        if self.detector and self.detector.get_game_window_handle():
            self.start_game_window_tracking(self.detector.get_game_window_handle())
            
        # Hide the main window
        self.hide()
        
        # Update the overlay
        self.update_overlay()
        
    def update_overlay(self):
        """Update the overlay window with current status"""
        # Check if we have an overlay to update
        if not self.overlay_mode:
            return
            
        # Get detection status
        is_running = self.is_detector_running()
        
        # Get elapsed time
        elapsed_time = 0
        if self.start_time:
            elapsed_time = time.time() - self.start_time
            
        # Get FPS if available
        fps = 0
        if self.detector and hasattr(self.detector, "stats"):
            fps = self.detector.stats.get("fps", 0)
            
        # Get threshold if available
        threshold = 0.045  # Default value
        if self.detector:
            threshold = getattr(self.detector, "THRESHOLD", 0.045)
            
        # Update the appropriate overlay
        if self.use_full_overlay and self.full_overlay_window:
            try:
                self.full_overlay_window.update_status(is_running, self.detection_count, elapsed_time)
                
                # Update visualization if available
                if hasattr(self.detector, "current_frame") and self.detector.current_frame is not None:
                    self.full_overlay_window.update_visualization(self.detector.current_frame)
            except Exception as e:
                print(f"Error updating full overlay: {e}")
        elif self.overlay_window:
            try:
                # Update status and detection count
                self.overlay_window.update_status(is_running, self.detection_count)
                
                # Update runtime
                self.overlay_window.update_runtime(elapsed_time)
                
                # Update FPS and threshold
                self.overlay_window.update_fps(fps)
                self.overlay_window.update_threshold(threshold)
                
                # Update zone indicators if we have a detector with zones
                if self.detector and hasattr(self.detector, "zones"):
                    for zone_id in self.detector.zones:
                        zone = self.detector.zones[zone_id]
                        # Active if enabled and has a region
                        is_active = zone.enabled and zone.region is not None
                        self.overlay_window.update_zone_status(zone_id, is_active)
                        
                # Update visualization if available
                if hasattr(self.detector, "current_frame") and self.detector.current_frame is not None:
                    self.overlay_window.update_visualization(self.detector.current_frame)
            except Exception as e:
                print(f"Error updating overlay: {e}")

    def restore_from_overlay(self):
        """Restore the main window from overlay mode"""
        # If in overlay-only mode, don't restore the main window
        if self.overlay_only:
            return
            
        # Hide overlays
        if self.overlay_window:
            self.overlay_window.hide()
        if self.full_overlay_window:
            self.full_overlay_window.hide()
            
        # Stop game window tracking
        if self.game_tracker:
            self.game_tracker.stop()
            self.game_tracker.wait()
            self.game_tracker = None
            
        # Restore main window
        if self.original_geometry:
            self.setGeometry(self.original_geometry)
        self.show()
        self.activateWindow()
        self.overlay_mode = False
        
        self.log("Restored from overlay mode")
        
    def start_game_window_tracking(self, game_window_hwnd):
        """Start tracking the game window position"""
        if not game_window_hwnd:
            return False
            
        # Create and start the tracker
        self.game_tracker = GameWindowTracker(game_window_hwnd, self)
        self.game_tracker.position_changed.connect(self.update_overlay_position)
        self.game_tracker.window_lost.connect(self.handle_game_window_lost)
        self.game_tracker.start()
        return True
        
    def update_overlay_position(self, x, y, width, height):
        """Update overlay position based on game window position"""
        if self.overlay_mode:
            if self.use_full_overlay and self.full_overlay_window:
                # Position the full overlay near the game window
                # Place it on the right side of the game window
                overlay_x = x + width + 10  # 10px offset from right edge
                overlay_y = y + 50  # 50px from top
                
                # Ensure it stays on screen
                screen = QApplication.primaryScreen().geometry()
                if overlay_x + self.full_overlay_window.width() > screen.width():
                    # If it would go off-screen to the right, place it on the left instead
                    overlay_x = x - self.full_overlay_window.width() - 10
                    
                    # If that would go off-screen to the left, place it on top
                    if overlay_x < 0:
                        overlay_x = x + (width - self.full_overlay_window.width()) // 2
                        overlay_y = y - self.full_overlay_window.height() - 10
                        
                        # If that would go off-screen to the top, place it inside the game window
                        if overlay_y < 0:
                            overlay_x = x + 20
                            overlay_y = y + 20
                
                self.full_overlay_window.move(overlay_x, overlay_y)
                
            elif self.overlay_window:
                # Position the simple overlay at top-right corner of game window
                overlay_x = x + width - 60  # 60px from right edge
                overlay_y = y + 10  # 10px from top
                
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
        """Handle when the game window is closed or lost"""
        if self.overlay_mode:
            # Show dialog asking user what to do
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Game Window Closed")
            msg_box.setText("The Play Together game window was closed or minimized!")
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
                    
                # Try to find the game window again
                if self.detector:
                    self.detector.find_play_together_process()
                    if self.detector.play_together_window:
                        self.start_game_window_tracking(self.detector.play_together_window)
        
    def handle_detector_error(self, error):
        """Handle detector error"""
        self.log(f"Detector error: {error}")
        # Add any additional error handling logic you want to execute

    def try_initialize_detector(self):
        """Initialize the detector with error handling"""
        try:
            from core.detector import MultiZoneDetector
            
            # Create detector instance
            self.detector = MultiZoneDetector(self)
            
            # Connect signals only if we're not in overlay-only mode
            if not self.overlay_only:
                # Connect detection signal to handle detections
                self.detector.detection_signal.connect(self.handle_zone_detection)
                
                # Connect zone status signal
                if hasattr(self, 'update_zone_status'):
                    self.detector.zone_status_signal.connect(self.update_zone_status)
                
                # Connect performance metrics signal
                if hasattr(self, 'update_performance_metrics'):
                    self.detector.performance_signal.connect(self.update_performance_metrics)
                
                # Connect error signal
                if hasattr(self, 'handle_detector_error'):
                    self.detector.error_signal.connect(self.handle_detector_error)
            
            return True
        except Exception as e:
            print(f"Error initializing detector: {e}")
            return False
            
    def update_zone_status(self, zone_id, status):
        """Handle zone status updates"""
        if self.overlay_only:
            return
            
        # This is a stub method for when we're in overlay-only mode
        # The actual implementation would update UI elements

    def update_statistics(self):
        """Update statistics for display"""
        # Skip if detector doesn't exist
        if not self.detector:
            return
            
        # Calculate elapsed time
        if self.start_time:
            elapsed_time = time.time() - self.start_time
        else:
            elapsed_time = 0
            
        # Update overlay if in overlay mode
        if self.overlay_mode and self.use_full_overlay and self.full_overlay_window:
            self.full_overlay_window.update_status(self.is_detector_running(), self.detection_count, elapsed_time)
            
        # Skip UI updates in overlay-only mode
        if self.overlay_only:
            return
            
        # Update UI elements in standard mode
        # (This part would contain all the UI update code for the main window)

    def update_performance_metrics(self, metrics):
        """Update performance metrics display"""
        if self.overlay_only:
            return
            
        # This is a stub method for when we're in overlay-only mode
        # The actual implementation would update UI elements

class FullOverlayWindow(QWidget):
    """Full-featured overlay window for AutoFisher that stays on top of the game"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Track if overlay is collapsed to minimal mode
        self.is_collapsed = False
        self.is_dragging = False
        self.drag_offset = QPoint()
        
        # Create detector instance if no parent provided
        self.parent_window = parent
        self.detector = None
        self.detection_running = False
        self.start_time = None
        self.detection_count = 0
        
        # If no parent, initialize our own detector
        if parent is None:
            self.detector = MultiZoneDetector()
            self.detector.detection_signal.connect(self.handle_zone_detection)
        
        # Initialize UI
        self.init_ui()
        
        # Setup timer for statistics updates
        self.stats_timer = QTimer()
        self.stats_timer.setInterval(1000)  # Update every second
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start()
        
    def init_ui(self):
        """Initialize the overlay UI"""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        # Create header with controls - styled like the original app
        self.header_widget = QWidget()
        self.header_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {UI_DARK_BG};
                border: 1px solid {UI_ACCENT_COLOR};
                border-radius: 6px;
            }}
        """)
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(10, 5, 10, 5)
        self.header_layout.setSpacing(8)
        
        # Title with logo
        self.title_label = QLabel(f"AutoFisher v{VERSION}")
        self.title_label.setStyleSheet(f"""
            color: {UI_ACCENT_COLOR};
            font-size: 14pt;
            font-weight: bold;
        """)
        self.header_layout.addWidget(self.title_label)
        
        # Add spacer
        self.header_layout.addStretch()
        
        # Control buttons
        self.start_stop_button = QPushButton()
        self.start_stop_button.setIcon(qta.icon('fa5s.play', color=UI_SUCCESS_COLOR))
        self.start_stop_button.setToolTip("Start fishing")
        self.start_stop_button.setFixedSize(24, 24)
        self.start_stop_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
        """)
        self.start_stop_button.clicked.connect(self.toggle_detection)
        self.header_layout.addWidget(self.start_stop_button)
        
        # Visualization button
        self.viz_button = QPushButton()
        self.viz_button.setIcon(qta.icon('fa5s.chart-line', color=UI_LIGHT_TEXT))
        self.viz_button.setToolTip("Show visualization")
        self.viz_button.setFixedSize(24, 24)
        self.viz_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
        """)
        self.viz_button.clicked.connect(self.toggle_visualization_panel)
        self.header_layout.addWidget(self.viz_button)
        
        # Region selection button
        self.region_button = QPushButton()
        self.region_button.setIcon(qta.icon('fa5s.crop-alt', color=UI_LIGHT_TEXT))
        self.region_button.setToolTip("Select region")
        self.region_button.setFixedSize(24, 24)
        self.region_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
        """)
        self.region_button.clicked.connect(self.select_region)
        self.header_layout.addWidget(self.region_button)
        
        # Multi-zone button
        self.zones_button = QPushButton()
        self.zones_button.setIcon(qta.icon('fa5s.th', color=UI_LIGHT_TEXT))
        self.zones_button.setToolTip("Configure detection zones")
        self.zones_button.setFixedSize(24, 24)
        self.zones_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
        """)
        self.zones_button.clicked.connect(self.toggle_zones_panel)
        self.header_layout.addWidget(self.zones_button)
        
        # Settings button
        self.settings_button = QPushButton()
        self.settings_button.setIcon(qta.icon('fa5s.cog', color=UI_LIGHT_TEXT))
        self.settings_button.setToolTip("Settings")
        self.settings_button.setFixedSize(24, 24)
        self.settings_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
        """)
        self.settings_button.clicked.connect(self.toggle_settings_panel)
        self.header_layout.addWidget(self.settings_button)
        
        # Collapse/expand button
        self.collapse_button = QPushButton()
        self.collapse_button.setIcon(qta.icon('fa5s.chevron-up', color=UI_LIGHT_TEXT))
        self.collapse_button.setToolTip("Collapse overlay")
        self.collapse_button.setFixedSize(24, 24)
        self.collapse_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
        """)
        self.collapse_button.clicked.connect(self.toggle_collapse)
        self.header_layout.addWidget(self.collapse_button)
        
        # Exit button (replacing restore main window button)
        self.exit_button = QPushButton()
        self.exit_button.setIcon(qta.icon('fa5s.power-off', color=UI_ERROR_COLOR))
        self.exit_button.setToolTip("Exit application")
        self.exit_button.setFixedSize(24, 24)
        self.exit_button.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {UI_WOOD_MEDIUM};
            }}
        """)
        self.exit_button.clicked.connect(self.exit_application)
        self.header_layout.addWidget(self.exit_button)
        
        # Add header to main layout
        self.main_layout.addWidget(self.header_widget)
        
        # Content area (expandable)
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {UI_DARK_BG};
                border: 1px solid {UI_ACCENT_COLOR};
                border-radius: 5px;
            }}
        """)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(5)
        
        # Stats display
        self.stats_label = QLabel("Detections: 0 | Runtime: 00:00:00")
        self.stats_label.setStyleSheet(f"color: {UI_LIGHT_TEXT}; font-size: 9pt;")
        self.content_layout.addWidget(self.stats_label)
        
        # Zone status grid
        self.zone_grid = QGridLayout()
        self.zone_grid.setSpacing(5)
        
        # Create zone indicators
        self.zone_indicators = {}
        row = 0
        for zone_id, zone_config in DEFAULT_DETECTION_ZONES.items():
            # Zone name label
            name_label = QLabel(zone_config["name"])
            name_label.setStyleSheet(f"color: {UI_LIGHT_TEXT}; font-size: 8pt;")
            
            # Zone status indicator
            status_indicator = QLabel("○")
            status_indicator.setStyleSheet(f"""
                color: {UI_CONFIG['zone_colors'].get(zone_id, UI_SECONDARY_TEXT)};
                font-size: 12pt;
            """)
            
            # Store reference to indicator
            self.zone_indicators[zone_id] = status_indicator
            
            # Add to grid
            self.zone_grid.addWidget(status_indicator, row, 0)
            self.zone_grid.addWidget(name_label, row, 1)
            row += 1
        
        self.content_layout.addLayout(self.zone_grid)
        
        # Visualization panel (hidden by default)
        self.visualization_panel = QWidget()
        self.visualization_panel.setVisible(False)
        self.visualization_layout = QVBoxLayout(self.visualization_panel)
        self.visualization_layout.setContentsMargins(5, 5, 5, 5)
        self.visualization_layout.setSpacing(5)
        
        # Create a frame to contain the visualization
        viz_frame = QFrame()
        viz_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {UI_PANEL_BG};
                border: 1px solid {UI_WOOD_DARK};
                border-radius: 3px;
            }}
        """)
        viz_frame_layout = QVBoxLayout(viz_frame)
        viz_frame_layout.setContentsMargins(5, 5, 5, 5)
        viz_frame_layout.setSpacing(2)
        
        # Create the visualization canvas
        from ui.visualization import ActivityGraphCanvas
        self.activity_graph = ActivityGraphCanvas(self, width=5, height=2, dpi=80)
        self.activity_graph.setMinimumHeight(80)
        viz_frame_layout.addWidget(self.activity_graph)
        
        # Create the image preview
        self.preview_label = QLabel("No preview available")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(f"""
            color: {UI_SECONDARY_TEXT};
            background-color: {UI_DARK_BG};
            border: 1px solid {UI_WOOD_DARK};
            border-radius: 3px;
            padding: 4px;
        """)
        self.preview_label.setMinimumHeight(100)
        self.preview_label.setMaximumHeight(150)
        viz_frame_layout.addWidget(self.preview_label)
        
        # Add to visualization layout
        self.visualization_layout.addWidget(viz_frame)
        
        # Add visualization panel to content
        self.content_layout.addWidget(self.visualization_panel)
        
        # Settings panel (hidden by default)
        self.settings_panel = QWidget()
        self.settings_panel.setVisible(False)
        self.settings_layout = QVBoxLayout(self.settings_panel)
        self.settings_layout.setContentsMargins(5, 5, 5, 5)
        self.settings_layout.setSpacing(5)
        
        # Add threshold slider
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Threshold:")
        threshold_label.setStyleSheet(f"color: {UI_LIGHT_TEXT}; font-size: 8pt;")
        threshold_layout.addWidget(threshold_label)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(1)
        self.threshold_slider.setMaximum(100)
        self.threshold_slider.setValue(int(DEFAULT_THRESHOLD * 1000))
        self.threshold_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {UI_WOOD_DARK};
                height: 4px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {UI_ACCENT_COLOR};
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }}
        """)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_value = QLabel(f"{DEFAULT_THRESHOLD:.3f}")
        self.threshold_value.setStyleSheet(f"color: {UI_LIGHT_TEXT}; font-size: 8pt;")
        threshold_layout.addWidget(self.threshold_value)
        
        self.settings_layout.addLayout(threshold_layout)
        
        # Add cooldown spinner
        cooldown_layout = QHBoxLayout()
        cooldown_label = QLabel("Cooldown:")
        cooldown_label.setStyleSheet(f"color: {UI_LIGHT_TEXT}; font-size: 8pt;")
        cooldown_layout.addWidget(cooldown_label)
        
        self.cooldown_spinner = QDoubleSpinBox()
        self.cooldown_spinner.setMinimum(0.5)
        self.cooldown_spinner.setMaximum(10.0)
        self.cooldown_spinner.setSingleStep(0.5)
        self.cooldown_spinner.setValue(DEFAULT_DETECTION_COOLDOWN)
        self.cooldown_spinner.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {UI_WOOD_DARK};
                color: {UI_LIGHT_TEXT};
                border: 1px solid {UI_WOOD_LIGHT};
                border-radius: 3px;
                padding: 1px 3px;
            }}
        """)
        cooldown_layout.addWidget(self.cooldown_spinner)
        
        self.settings_layout.addLayout(cooldown_layout)
        
        # Add fishing key input
        key_layout = QHBoxLayout()
        key_label = QLabel("Fishing Key:")
        key_label.setStyleSheet(f"color: {UI_LIGHT_TEXT}; font-size: 8pt;")
        key_layout.addWidget(key_label)
        
        self.key_input = QLineEdit(DEFAULT_FISHING_KEY)
        self.key_input.setMaximumWidth(30)
        self.key_input.setMaxLength(1)
        self.key_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {UI_WOOD_DARK};
                color: {UI_LIGHT_TEXT};
                border: 1px solid {UI_WOOD_LIGHT};
                border-radius: 3px;
                padding: 1px 3px;
            }}
        """)
        key_layout.addWidget(self.key_input)
        key_layout.addStretch()
        
        self.settings_layout.addLayout(key_layout)
        
        # Add checkboxes for options
        self.high_performance_cb = QCheckBox("High Performance")
        self.high_performance_cb.setChecked(DEFAULT_HIGH_PERFORMANCE)
        self.high_performance_cb.setStyleSheet(f"""
            QCheckBox {{
                color: {UI_LIGHT_TEXT};
                font-size: 8pt;
            }}
            QCheckBox::indicator:checked {{
                background-color: {UI_ACCENT_COLOR};
                border: 1px solid {UI_ACCENT_DARK};
                border-radius: 2px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: {UI_WOOD_DARK};
                border: 1px solid {UI_WOOD_LIGHT};
                border-radius: 2px;
            }}
        """)
        self.settings_layout.addWidget(self.high_performance_cb)
        
        self.respect_fullscreen_cb = QCheckBox("Respect Fullscreen Apps")
        self.respect_fullscreen_cb.setChecked(DEFAULT_RESPECT_FULLSCREEN)
        self.respect_fullscreen_cb.setStyleSheet(f"""
            QCheckBox {{
                color: {UI_LIGHT_TEXT};
                font-size: 8pt;
            }}
            QCheckBox::indicator:checked {{
                background-color: {UI_ACCENT_COLOR};
                border: 1px solid {UI_ACCENT_DARK};
                border-radius: 2px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: {UI_WOOD_DARK};
                border: 1px solid {UI_WOOD_LIGHT};
                border-radius: 2px;
            }}
        """)
        self.settings_layout.addWidget(self.respect_fullscreen_cb)
        
        self.direct_control_cb = QCheckBox("Direct Control Mode")
        self.direct_control_cb.setChecked(DEFAULT_DIRECT_CONTROL)
        self.direct_control_cb.setStyleSheet(f"""
            QCheckBox {{
                color: {UI_LIGHT_TEXT};
                font-size: 8pt;
            }}
            QCheckBox::indicator:checked {{
                background-color: {UI_ACCENT_COLOR};
                border: 1px solid {UI_ACCENT_DARK};
                border-radius: 2px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: {UI_WOOD_DARK};
                border: 1px solid {UI_WOOD_LIGHT};
                border-radius: 2px;
            }}
        """)
        self.settings_layout.addWidget(self.direct_control_cb)
        
        # Apply settings button
        self.apply_settings_btn = QPushButton("Apply Settings")
        self.apply_settings_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_ACCENT_COLOR};
                color: {UI_DARK_BG};
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {UI_ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {UI_ACCENT_ACTIVE};
            }}
        """)
        self.apply_settings_btn.clicked.connect(self.apply_settings)
        self.settings_layout.addWidget(self.apply_settings_btn)
        
        # Add settings panel to content
        self.content_layout.addWidget(self.settings_panel)
        
        # Zones panel (hidden by default)
        self.zones_panel = QWidget()
        self.zones_panel.setVisible(False)
        self.zones_layout = QVBoxLayout(self.zones_panel)
        self.zones_layout.setContentsMargins(5, 5, 5, 5)
        self.zones_layout.setSpacing(5)
        
        # Add title for zones panel
        zones_title = QLabel("Detection Zones")
        zones_title.setStyleSheet(f"color: {UI_LIGHT_TEXT}; font-size: 9pt; font-weight: bold;")
        zones_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zones_layout.addWidget(zones_title)
        
        # Create zone controls for each zone
        self.zone_controls = {}
        for zone_id, zone_config in DEFAULT_DETECTION_ZONES.items():
            # Zone frame
            zone_frame = QFrame()
            zone_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {UI_PANEL_BG};
                    border: 1px solid {UI_WOOD_DARK};
                    border-radius: 3px;
                }}
            """)
            zone_frame_layout = QVBoxLayout(zone_frame)
            zone_frame_layout.setContentsMargins(5, 5, 5, 5)
            zone_frame_layout.setSpacing(3)
            
            # Zone header
            zone_header = QHBoxLayout()
            
            # Zone name and checkbox
            zone_checkbox = QCheckBox(zone_config["name"])
            zone_checkbox.setChecked(zone_config["enabled"])
            zone_checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: {UI_LIGHT_TEXT};
                    font-size: 8pt;
                    font-weight: bold;
                }}
                QCheckBox::indicator:checked {{
                    background-color: {UI_CONFIG['zone_colors'].get(zone_id, UI_ACCENT_COLOR)};
                    border: 1px solid {UI_ACCENT_DARK};
                    border-radius: 2px;
                }}
                QCheckBox::indicator:unchecked {{
                    background-color: {UI_WOOD_DARK};
                    border: 1px solid {UI_WOOD_LIGHT};
                    border-radius: 2px;
                }}
            """)
            zone_checkbox.clicked.connect(lambda state, zid=zone_id: self.toggle_zone_enable(zid, state))
            zone_header.addWidget(zone_checkbox)
            
            # Add spacer
            zone_header.addStretch()
            
            # Select region button
            zone_region_btn = QPushButton()
            zone_region_btn.setIcon(qta.icon('fa5s.crop-alt', color=UI_LIGHT_TEXT))
            zone_region_btn.setToolTip(f"Select region for {zone_config['name']}")
            zone_region_btn.setFixedSize(20, 20)
            zone_region_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 3px;
                }}
                QPushButton:hover {{
                    background-color: {UI_WOOD_MEDIUM};
                }}
            """)
            zone_region_btn.clicked.connect(lambda _, zid=zone_id: self.select_zone_region(zid))
            zone_header.addWidget(zone_region_btn)
            
            # Clear region button
            zone_clear_btn = QPushButton()
            zone_clear_btn.setIcon(qta.icon('fa5s.times', color=UI_ERROR_COLOR))
            zone_clear_btn.setToolTip(f"Clear region for {zone_config['name']}")
            zone_clear_btn.setFixedSize(20, 20)
            zone_clear_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 3px;
                }}
                QPushButton:hover {{
                    background-color: {UI_WOOD_MEDIUM};
                }}
            """)
            zone_clear_btn.clicked.connect(lambda _, zid=zone_id: self.clear_zone_region(zid))
            zone_header.addWidget(zone_clear_btn)
            
            # Add header to frame
            zone_frame_layout.addLayout(zone_header)
            
            # Sensitivity slider
            sensitivity_layout = QHBoxLayout()
            sensitivity_label = QLabel("Sensitivity:")
            sensitivity_label.setStyleSheet(f"color: {UI_LIGHT_TEXT}; font-size: 8pt;")
            sensitivity_layout.addWidget(sensitivity_label)
            
            sensitivity_slider = QSlider(Qt.Orientation.Horizontal)
            sensitivity_slider.setMinimum(50)
            sensitivity_slider.setMaximum(200)
            sensitivity_slider.setValue(int(zone_config["sensitivity"] * 100))
            sensitivity_slider.setStyleSheet(f"""
                QSlider::groove:horizontal {{
                    background: {UI_WOOD_DARK};
                    height: 3px;
                    border-radius: 1px;
                }}
                QSlider::handle:horizontal {{
                    background: {UI_CONFIG['zone_colors'].get(zone_id, UI_ACCENT_COLOR)};
                    width: 10px;
                    margin: -3px 0;
                    border-radius: 5px;
                }}
            """)
            sensitivity_layout.addWidget(sensitivity_slider)
            
            sensitivity_value = QLabel(f"{zone_config['sensitivity']:.1f}x")
            sensitivity_value.setStyleSheet(f"color: {UI_LIGHT_TEXT}; font-size: 8pt;")
            sensitivity_layout.addWidget(sensitivity_value)
            
            # Connect slider to update value label
            sensitivity_slider.valueChanged.connect(
                lambda value, label=sensitivity_value: label.setText(f"{value/100:.1f}x")
            )
            
            zone_frame_layout.addLayout(sensitivity_layout)
            
            # Store controls for later access
            self.zone_controls[zone_id] = {
                'checkbox': zone_checkbox,
                'sensitivity_slider': sensitivity_slider,
                'sensitivity_value': sensitivity_value,
                'region_btn': zone_region_btn,
                'clear_btn': zone_clear_btn
            }
            
            # Add zone frame to zones panel
            self.zones_layout.addWidget(zone_frame)
        
        # Apply zones button
        self.apply_zones_btn = QPushButton("Apply Zone Settings")
        self.apply_zones_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {UI_ACCENT_COLOR};
                color: {UI_DARK_BG};
                border: none;
                border-radius: 3px;
                padding: 4px 8px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {UI_ACCENT_HOVER};
            }}
            QPushButton:pressed {{
                background-color: {UI_ACCENT_ACTIVE};
            }}
        """)
        self.apply_zones_btn.clicked.connect(self.apply_zone_settings)
        self.zones_layout.addWidget(self.apply_zones_btn)
        
        # Add zones panel to content
        self.content_layout.addWidget(self.zones_panel)
        
        # Add content widget to main layout
        self.main_layout.addWidget(self.content_widget)
        
        # Set initial size
        self.setMinimumWidth(250)
        self.adjust_size()
        
    def toggle_zones_panel(self):
        """Show or hide zones panel"""
        # Hide settings panel if open
        if self.settings_panel.isVisible():
            self.settings_panel.setVisible(False)
            
        # Toggle zones panel
        self.zones_panel.setVisible(not self.zones_panel.isVisible())
        self.adjust_size()
        
    def select_zone_region(self, zone_id):
        """Select region for a specific zone"""
        if self.parent_window:
            # Hide the overlay temporarily
            self.hide()
            
            # Call parent's select_zone_region method
            if hasattr(self.parent_window, 'select_zone_region'):
                self.parent_window.select_zone_region(zone_id)
                
            # Show the overlay again after a short delay
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self.show)
            
    def clear_zone_region(self, zone_id):
        """Clear region for a specific zone"""
        if self.parent_window and hasattr(self.parent_window, 'clear_zone_region'):
            self.parent_window.clear_zone_region(zone_id)
            
    def toggle_zone_enable(self, zone_id, state):
        """Enable or disable a detection zone"""
        if self.parent_window and hasattr(self.parent_window, 'toggle_zone_enable'):
            self.parent_window.toggle_zone_enable(zone_id, state)
            
    def apply_zone_settings(self):
        """Apply zone settings from the UI to the parent detector"""
        if self.parent_window and hasattr(self.parent_window, 'detector') and self.parent_window.detector:
            for zone_id, controls in self.zone_controls.items():
                if zone_id in self.parent_window.detector.zones:
                    zone = self.parent_window.detector.zones[zone_id]
                    
                    # Update zone configuration
                    zone.enabled = controls['checkbox'].isChecked()
                    zone.sensitivity = controls['sensitivity_slider'].value() / 100.0
                    
                    # Log the change
                    if hasattr(self.parent_window, 'log'):
                        self.parent_window.log(f"Updated {zone_id} settings: enabled={zone.enabled}, sensitivity={zone.sensitivity:.1f}x")
                        
            # Update parent UI
            if hasattr(self.parent_window, 'update_zone_statistics'):
                self.parent_window.update_zone_statistics()
        
    def toggle_detection(self):
        """Toggle detection on/off"""
        if self.detection_running:
            self.stop_detection()
        else:
            self.start_detection()
            
        # Update overlay if active
        self.update_overlay()
        
    def toggle_settings_panel(self):
        """Show or hide settings panel"""
        self.settings_panel.setVisible(not self.settings_panel.isVisible())
        self.adjust_size()
        
    def toggle_collapse(self):
        """Collapse or expand the overlay"""
        self.is_collapsed = not self.is_collapsed
        
        if self.is_collapsed:
            self.content_widget.setVisible(False)
            self.collapse_button.setIcon(qta.icon('fa5s.chevron-down', color=UI_LIGHT_TEXT))
            self.collapse_button.setToolTip("Expand overlay")
        else:
            self.content_widget.setVisible(True)
            self.collapse_button.setIcon(qta.icon('fa5s.chevron-up', color=UI_LIGHT_TEXT))
            self.collapse_button.setToolTip("Collapse overlay")
            
        self.adjust_size()
        
    def adjust_size(self):
        """Adjust size based on visible sections"""
        new_size = self.calculate_window_size()
        self.setFixedWidth(new_size.width())
        self.setFixedHeight(new_size.height())
        
    def calculate_window_size(self):
        """Calculate the window size based on which sections are visible
        
        Returns:
            QSize: The calculated size of the window
        """
        from PyQt6.QtCore import QSize
        from utils.constants import SECTION_SIZES
        
        # Start with base dimensions
        width = SECTION_SIZES["base_width"]
        
        # If collapsed, only use header height
        if self.is_collapsed:
            height = self.header_widget.height() + SECTION_SIZES["margins"]
            return QSize(width, height)
            
        # Start with base height
        height = SECTION_SIZES["base_height"]
        
        # Add height for each visible section
        if hasattr(self, 'settings_panel') and self.settings_panel.isVisible():
            height += SECTION_SIZES["settings_panel"] + SECTION_SIZES["section_padding"]
            
        if hasattr(self, 'visualization_panel') and self.visualization_panel.isVisible():
            height += SECTION_SIZES["visualization_panel"] + SECTION_SIZES["section_padding"]
            
        if hasattr(self, 'zones_panel') and self.zones_panel.isVisible():
            height += SECTION_SIZES["zones_panel"] + SECTION_SIZES["section_padding"]
            
        if hasattr(self, 'stats_panel') and self.stats_panel.isVisible():
            height += SECTION_SIZES["statistics_panel"] + SECTION_SIZES["section_padding"]
            
        # Add margins
        height += SECTION_SIZES["margins"]
        
        return QSize(width, height)
            
    def exit_application(self):
        """Exit the application"""
        # Ask for confirmation
        from PyQt6.QtWidgets import QMessageBox
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Exit AutoFisher")
        msg_box.setText("Are you sure you want to exit AutoFisher?")
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        # Make sure message box appears on top
        msg_box.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Dialog | 
            Qt.WindowType.CustomizeWindowHint | 
            Qt.WindowType.WindowTitleHint
        )
        
        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            # Stop detection if running
            if self.detection_running and self.detector:
                self.stop_detection()
                
            # Close the parent application if it exists
            if self.parent_window:
                self.parent_window.close()
            
            # Quit the application
            QApplication.quit()
        
    def update_status(self, is_running, detection_count, elapsed_time):
        """Update overlay status indicators with error checking"""
        try:
            # Update status indicator color if it exists
            if hasattr(self, 'status_indicator'):
                if is_running:
                    self.status_indicator.setStyleSheet(f"color: {UI_SUCCESS_COLOR}; font-size: 16pt; font-weight: bold;")
                else:
                    self.status_indicator.setStyleSheet(f"color: {UI_SECONDARY_TEXT}; font-size: 16pt; font-weight: bold;")
            
            # Update start/stop button if it exists
            if hasattr(self, 'start_stop_button'):
                if is_running:
                    self.start_stop_button.setIcon(qta.icon('fa5s.stop', color=UI_ERROR_COLOR))
                    self.start_stop_button.setToolTip("Stop fishing")
                else:
                    self.start_stop_button.setIcon(qta.icon('fa5s.play', color=UI_SUCCESS_COLOR))
                    self.start_stop_button.setToolTip("Start fishing")
            
            # Format elapsed time
            hours, remainder = divmod(int(elapsed_time), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # Update stats label if it exists
            if hasattr(self, 'stats_label'):
                self.stats_label.setText(f"Detections: {detection_count} | Runtime: {time_str}")
        except Exception as e:
            # Silently handle errors in the UI update
            print(f"Error updating overlay status: {e}")

    def update_zone_status(self, zone_id, is_active):
        """Update zone status indicators"""
        if zone_id in self.zone_indicators:
            indicator = self.zone_indicators[zone_id]
            if is_active:
                indicator.setText("●")  # Filled circle for active
            else:
                indicator.setText("○")  # Empty circle for inactive
                
    def apply_settings(self):
        """Apply settings from the UI to the parent detector"""
        if self.parent_window:
            # Get values from UI
            threshold = self.threshold_slider.value() / 1000.0
            cooldown = self.cooldown_spinner.value()
            fishing_key = self.key_input.text()
            high_performance = self.high_performance_cb.isChecked()
            respect_fullscreen = self.respect_fullscreen_cb.isChecked()
            direct_control = self.direct_control_cb.isChecked()
            
            # Update threshold value label
            self.threshold_value.setText(f"{threshold:.3f}")
            
            # Apply to parent
            if hasattr(self.parent_window, 'apply_settings'):
                self.parent_window.apply_settings({
                    'threshold': threshold,
                    'cooldown': cooldown,
                    'fishing_key': fishing_key,
                    'high_performance': high_performance,
                    'respect_fullscreen': respect_fullscreen,
                    'direct_control': direct_control
                })
                
            # Note: We don't hide the settings panel here - let the toggle_settings_panel handle visibility
    
    def mousePressEvent(self, event):
        """Handle mouse press for dragging the overlay"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Only start drag if clicking in header area
            if self.header_widget.geometry().contains(event.pos()):
                self.is_dragging = True
                self.drag_offset = event.pos()
    
    def mouseMoveEvent(self, event):
        """Handle mouse movement for dragging the overlay"""
        if self.is_dragging:
            self.move(self.mapToParent(event.pos() - self.drag_offset))
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to end dragging"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = False
    
    def select_region(self):
        """Open region selection dialog"""
        if self.parent_window:
            # Hide the overlay temporarily
            self.hide()
            
            # Call parent's select_region method
            if hasattr(self.parent_window, 'select_region'):
                self.parent_window.select_region()
                
            # Show the overlay again after a short delay
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self.show)
        elif self.detector:
            # Handle region selection ourselves
            self.hide()
            
            # Use TkRegionSelector for consistency
            from ui.selection import TkRegionSelector
            selector = TkRegionSelector(self)
            region = selector.select_region(self.detector.play_together_window)
            
            if region:
                # Set the region in the detector
                self.detector.set_zone_region('main_fishing', region)
                print(f"Selected region: {region}")
                
                # Instead of calling capture_reference, just grab a frame for preview
                if hasattr(self.detector, 'capture_zone_frame'):
                    frame = self.detector.capture_zone_frame('main_fishing')
                    if frame is not None and hasattr(self, 'preview_label'):
                        # Convert to QImage and display
                        import cv2
                        from PyQt6.QtGui import QImage, QPixmap
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgb_frame.shape
                        q_img = QImage(rgb_frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
                        pixmap = QPixmap.fromImage(q_img)
                        self.preview_label.setPixmap(pixmap.scaled(
                            self.preview_label.width(), 
                            self.preview_label.height(),
                            Qt.AspectRatioMode.KeepAspectRatio
                        ))
            
            # Show overlay again after selection
            self.show()
        
    def toggle_detection(self):
        """Toggle detection on/off"""
        if self.detection_running:
            self.stop_detection()
        else:
            self.start_detection()
        
    def toggle_visualization_panel(self):
        """Show or hide visualization panel"""
        # Hide other panels if open
        if self.settings_panel.isVisible():
            self.settings_panel.setVisible(False)
        if self.zones_panel.isVisible():
            self.zones_panel.setVisible(False)
            
        # Toggle visualization panel
        self.visualization_panel.setVisible(not self.visualization_panel.isVisible())
        self.adjust_size()
        
    def update_visualization(self, frame=None):
        """Update visualization with new frame data"""
        if not self.visualization_panel.isVisible():
            return
            
        # Update activity graph if we have a parent with detector
        if self.parent_window and hasattr(self.parent_window, 'detector') and self.parent_window.detector:
            detector = self.parent_window.detector
            
            # Update graph with detection history if available
            if hasattr(detector, 'frame_history'):
                threshold = detector.zones.get('main_fishing', DetectionZone('main', {})).threshold
                self.activity_graph.update(detector.frame_history, threshold)
                
        # Update preview image if provided
        if frame is not None and isinstance(frame, np.ndarray):
            # Convert frame to QImage for display
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_img)
            
            # Scale pixmap to fit the label while maintaining aspect ratio
            scaled_pixmap = pixmap.scaled(
                self.preview_label.width(), 
                self.preview_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio
            )
            
            # Update preview label
            self.preview_label.setPixmap(scaled_pixmap)
        
    def toggle_settings_panel(self):
        """Show or hide settings panel"""
        # Hide other panels if open
        if self.visualization_panel.isVisible():
            self.visualization_panel.setVisible(False)
        if self.zones_panel.isVisible():
            self.zones_panel.setVisible(False)
            
        # Toggle settings panel
        is_visible = not self.settings_panel.isVisible()
        self.settings_panel.setVisible(is_visible)
        
        # Update button appearance to indicate state
        if is_visible:
            self.settings_button.setIcon(qta.icon('fa5s.cog', color=UI_ACCENT_COLOR))
        else:
            self.settings_button.setIcon(qta.icon('fa5s.cog', color=UI_LIGHT_TEXT))
            
        self.adjust_size()
        
    def toggle_zones_panel(self):
        """Show or hide zones panel"""
        # Hide other panels if open
        if self.settings_panel.isVisible():
            self.settings_panel.setVisible(False)
        if self.visualization_panel.isVisible():
            self.visualization_panel.setVisible(False)
            
        # Toggle zones panel
        self.zones_panel.setVisible(not self.zones_panel.isVisible())
        self.adjust_size()
        
    def start_detection(self):
        """Start the detection process"""
        if not self.detector:
            return
            
        # Start detection
        self.detector.start_detection()
        self.detection_running = True
        self.start_time = time.time()
        
        # Update UI
        self.update_status(True, self.detection_count, 0)
        
    def stop_detection(self):
        """Stop the detection process"""
        if not self.detector:
            return
            
        # Stop detection
        self.detector.stop_detection()
        self.detection_running = False
        
        # Update UI
        elapsed_time = 0
        if self.start_time:
            elapsed_time = time.time() - self.start_time
        self.update_status(False, self.detection_count, elapsed_time)
        
    def handle_zone_detection(self, zone_id):
        """Handle a detection event from a specific zone"""
        # Increment detection count
        self.detection_count += 1
        
        # Update zone status
        self.update_zone_status(zone_id, True)
        
        # Update stats
        elapsed_time = 0
        if self.start_time:
            elapsed_time = time.time() - self.start_time
        self.update_status(self.detection_running, self.detection_count, elapsed_time)
        
        # Schedule reset of zone status after a short delay
        QTimer.singleShot(1000, lambda: self.update_zone_status(zone_id, False))
                
    def update_stats(self):
        """Update statistics display"""
        elapsed_time = 0
        if self.start_time:
            elapsed_time = time.time() - self.start_time
            
        # Update status display
        self.update_status(self.detection_running, self.detection_count, elapsed_time)
        
    def select_region(self):
        """Open region selection dialog"""
        if self.parent_window:
            # Hide the overlay temporarily
            self.hide()
            
            # Call parent's select_region method
            if hasattr(self.parent_window, 'select_region'):
                self.parent_window.select_region()
                
            # Show the overlay again after a short delay
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self.show)
        elif self.detector:
            # Handle region selection ourselves
            self.hide()
            
            # Use TkRegionSelector for consistency
            from ui.selection import TkRegionSelector
            selector = TkRegionSelector(self)
            region = selector.select_region(self.detector.play_together_window)
            
            if region:
                # Set the region in the detector
                self.detector.set_zone_region('main_fishing', region)
                print(f"Selected region: {region}")
                
                # Instead of calling capture_reference, just grab a frame for preview
                if hasattr(self.detector, 'capture_zone_frame'):
                    frame = self.detector.capture_zone_frame('main_fishing')
                    if frame is not None and hasattr(self, 'preview_label'):
                        # Convert to QImage and display
                        import cv2
                        from PyQt6.QtGui import QImage, QPixmap
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgb_frame.shape
                        q_img = QImage(rgb_frame.data, w, h, ch * w, QImage.Format.Format_RGB888)
                        pixmap = QPixmap.fromImage(q_img)
                        self.preview_label.setPixmap(pixmap.scaled(
                            self.preview_label.width(), 
                            self.preview_label.height(),
                            Qt.AspectRatioMode.KeepAspectRatio
                        ))
            
            # Show overlay again after selection
            self.show()