"""
Main application UI using PyQt6 for cross-platform compatibility
"""
import sys
import time
import datetime
import numpy as np
import cv2
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QSlider, QFrame, QSplitter, QTextEdit,
    QGroupBox, QMessageBox, QDialog, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect, QPoint, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QImage, QFont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from autofisher.backends.factory import create_detector

class TimelinePlot(FigureCanvas):
    """Timeline plot for visualizing detection events"""
    
    def __init__(self, parent=None, width=6, height=1, dpi=100):
        # Define colors for plot
        self.colors = {
            'background': '#1E1E1E',
            'grid': '#333333',
            'text': '#E0E0E0',
            'timeline': '#4CAF50',
            'threshold': '#FF5722'
        }
        
        # Create figure with dark theme
        self.fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        self.fig.patch.set_facecolor(self.colors['background'])
        
        super().__init__(self.fig)
        self.setParent(parent)
        
        # Configure axis appearance
        self.ax.set_facecolor(self.colors['background'])
        self.ax.tick_params(colors=self.colors['text'], which='both')
        self.ax.spines['bottom'].set_color(self.colors['grid'])
        self.ax.spines['top'].set_color(self.colors['grid'])
        self.ax.spines['left'].set_color(self.colors['grid'])
        self.ax.spines['right'].set_color(self.colors['grid'])
        self.ax.grid(True, color=self.colors['grid'], linestyle='-', linewidth=0.5, alpha=0.7)
        
        # Initial empty plot
        self.timeline, = self.ax.plot([], [], '-', color=self.colors['timeline'], linewidth=2, label='Pixel Change')
        self.threshold_line = None
        
        # Setup legend
        self.ax.legend(facecolor=self.colors['background'], edgecolor=self.colors['grid'], 
                      labelcolor=self.colors['text'], loc='upper right')
        
        # Title and labels with theme colors
        self.ax.set_title('Pixel Change History', color=self.colors['text'])
        self.ax.set_xlabel('Time (s)', color=self.colors['text'])
        self.ax.set_ylabel('Change %', color=self.colors['text'])
        
        self.fig.tight_layout()
        
    def update_plot(self, history, threshold):
        """Update the plot with new history data"""
        if not history:
            return
            
        # Clear previous data
        self.ax.clear()
        
        # Extract data
        timestamps, values = zip(*history) if history else ([], [])
        
        # Normalize time to seconds from first detection
        if timestamps:
            base_time = timestamps[0]
            norm_times = [(t - base_time) for t in timestamps]
            
            # Plot the data
            self.ax.plot(norm_times, [v * 100 for v in values], '-', 
                        color=self.colors['timeline'], linewidth=2, label='Pixel Change')
                        
            # Add threshold line
            self.ax.axhline(y=threshold * 100, color=self.colors['threshold'], 
                           linestyle='--', linewidth=1.5, label=f'Threshold ({threshold:.1%})')
                           
            # Set y-axis limits with some padding
            max_val = max(max(values) * 100, threshold * 100) * 1.2
            self.ax.set_ylim(0, max_val)
            
            # Format x-axis to show seconds
            self.ax.set_xlim(0, max(norm_times) + 1)
            
        # Restore theme settings
        self.ax.set_facecolor(self.colors['background'])
        self.ax.tick_params(colors=self.colors['text'], which='both')
        self.ax.spines['bottom'].set_color(self.colors['grid'])
        self.ax.spines['top'].set_color(self.colors['grid'])
        self.ax.spines['left'].set_color(self.colors['grid'])
        self.ax.spines['right'].set_color(self.colors['grid'])
        self.ax.grid(True, color=self.colors['grid'], linestyle='-', linewidth=0.5, alpha=0.7)
        
        # Restore labels
        self.ax.set_title('Pixel Change History', color=self.colors['text'])
        self.ax.set_xlabel('Time (s)', color=self.colors['text'])
        self.ax.set_ylabel('Change %', color=self.colors['text'])
        
        # Update legend
        self.ax.legend(facecolor=self.colors['background'], edgecolor=self.colors['grid'], 
                      labelcolor=self.colors['text'], loc='upper right')
        
        # Redraw canvas
        self.fig.tight_layout()
        self.draw()

class MonitoringDisplay(QWidget):
    """Widget for displaying captured frames and detection visualization"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        
        # Define colors
        self.colors = {
            'background': '#1E1E1E',
            'outline': '#3E3E3E',
            'text': '#E0E0E0',
            'highlight': '#4CAF50',
            'status_running': '#4CAF50',  # Green
            'status_stopped': '#FF5722',  # Red-orange
            'status_paused': '#FFC107'    # Amber
        }
        
        # Setup widget
        self.setAutoFillBackground(True)
        self.set_background_color(self.colors['background'])
        
        # Setup layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # Display frames and status
        self.display_label = QLabel("No image captured")
        self.display_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display_label.setStyleSheet(f"color: {self.colors['text']}; background-color: {self.colors['background']};")
        self.display_label.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
        
        # Status indicator
        self.status_layout = QHBoxLayout()
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(16, 16)
        self.status_indicator.setStyleSheet(
            f"background-color: {self.colors['status_stopped']}; border-radius: 8px;")
        
        self.status_text = QLabel("Stopped")
        self.status_text.setStyleSheet(f"color: {self.colors['text']};")
        
        self.status_layout.addWidget(self.status_indicator)
        self.status_layout.addWidget(self.status_text)
        self.status_layout.addStretch()
        
        self.layout.addWidget(self.display_label)
        self.layout.addLayout(self.status_layout)
        
        # Properties
        self.current_frame = None
        self.diff_frame = None
        self.detection_overlay = False
        
    def set_background_color(self, color):
        """Set widget background color"""
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(color))
        self.setPalette(palette)
        
    def update_display(self, color_frame, diff_frame, change_percent):
        """Update the display with the current frames"""
        if color_frame is None:
            return
            
        # Store frames
        self.current_frame = color_frame
        self.diff_frame = diff_frame
        
        try:
            # Convert numpy array to QImage for display
            height, width, channels = color_frame.shape
            bytes_per_line = channels * width
            
            # Convert BGR to RGB for QImage (OpenCV uses BGR)
            if channels == 3:  # BGR format
                rgb_frame = cv2.cvtColor(color_frame, cv2.COLOR_BGR2RGB)
            elif channels == 4:  # BGRA format
                rgb_frame = cv2.cvtColor(color_frame, cv2.COLOR_BGRA2RGBA)
            else:
                rgb_frame = color_frame
                
            # Create QImage from numpy array
            q_img = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            
            # Create pixmap from QImage
            pixmap = QPixmap.fromImage(q_img)
            
            # Resize pixmap to fit in the label while maintaining aspect ratio
            pixmap = pixmap.scaled(self.display_label.width(), self.display_label.height(), 
                                  Qt.AspectRatioMode.KeepAspectRatio)
                                  
            # Display the image
            self.display_label.setPixmap(pixmap)
            
            # Update status text with change percentage if we have a diff frame
            if diff_frame is not None:
                self.status_text.setText(f"Change: {change_percent:.2%}")
        except Exception as e:
            print(f"Error updating display: {e}")
    
    def set_status(self, status):
        """Set the status indicator color and text"""
        if status == "running":
            color = self.colors['status_running']
            text = "Running"
        elif status == "paused":
            color = self.colors['status_paused']
            text = "Paused"
        else:  # stopped
            color = self.colors['status_stopped']
            text = "Stopped"
            
        self.status_indicator.setStyleSheet(
            f"background-color: {color}; border-radius: 8px;")
        self.status_text.setText(text)

class RegionSelectionOverlay(QDialog):
    """Overlay for selecting a screen region"""
    
    region_selected = pyqtSignal(tuple)
    
    def __init__(self, parent=None, default_size=100):
        super().__init__(parent)
        
        self.setWindowTitle("Select Screen Region")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Full screen overlay
        screen_geometry = QApplication.primaryScreen().geometry()
        self.setGeometry(screen_geometry)
        
        # Selection properties
        self.selection_start = QPoint()
        self.selection_end = QPoint()
        self.is_selecting = False
        
        # Default selection box (centered with default size)
        center = screen_geometry.center()
        half_size = default_size // 2
        self.selection_start = QPoint(center.x() - half_size, center.y() - half_size)
        self.selection_end = QPoint(center.x() + half_size, center.y() + half_size)
        
        # Colors
        self.colors = {
            "overlay": QColor(0, 0, 0, 150),
            "selection": QColor(76, 175, 80, 50),  # Semi-transparent green
            "border": QColor(76, 175, 80),
            "text": QColor(255, 255, 255)
        }
        
        # Keyboard instructions
        self.instructions = [
            "Click and drag to select a region",
            "Press Enter to confirm",
            "Press Esc to cancel",
        ]
        
    def paintEvent(self, event):
        """Paint the overlay with selection box"""
        painter = QPainter(self)
        
        # Draw semi-transparent overlay
        painter.fillRect(self.rect(), self.colors["overlay"])
        
        # Calculate selection rectangle (normalized)
        selection_rect = QRect(self.selection_start, self.selection_end).normalized()
        
        # Draw selected region (less dark)
        painter.fillRect(selection_rect, self.colors["selection"])
        
        # Draw border around selection
        pen = QPen(self.colors["border"])
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(selection_rect)
        
        # Draw instructions
        font = painter.font()
        font.setPointSize(12)
        painter.setFont(font)
        painter.setPen(self.colors["text"])
        
        y_offset = 30
        for instruction in self.instructions:
            painter.drawText(20, y_offset, instruction)
            y_offset += 25
            
        # Draw selection size
        size_text = f"Selection: {selection_rect.width()} x {selection_rect.height()}"
        painter.drawText(20, y_offset, size_text)
        
    def mousePressEvent(self, event):
        """Handle mouse press for starting selection"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.selection_start = event.position().toPoint()
            self.selection_end = self.selection_start
            self.is_selecting = True
            self.update()
            
    def mouseMoveEvent(self, event):
        """Handle mouse move for updating selection"""
        if self.is_selecting:
            self.selection_end = event.position().toPoint()
            self.update()
            
    def mouseReleaseEvent(self, event):
        """Handle mouse release for completing selection"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.selection_end = event.position().toPoint()
            self.is_selecting = False
            self.update()
            
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # Confirm selection
            selection_rect = QRect(self.selection_start, self.selection_end).normalized()
            region = (selection_rect.left(), selection_rect.top(), 
                     selection_rect.right(), selection_rect.bottom())
            self.region_selected.emit(region)
            self.accept()
        elif event.key() == Qt.Key.Key_Escape:
            # Cancel selection
            self.reject()
        else:
            super().keyPressEvent(event)

class AutoFisherApp(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        # Main properties
        self.detector = None
        self.detection_count = 0
        
        # Define theme colors
        self._define_colors()
        
        # Setup UI
        self._init_ui()
        
        # Setup timers
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_visualization)
        self.update_timer.start(100)  # Update at 10 Hz
        
        # Create backend detector
        try:
            self.detector = create_detector()
            self.detector.on_detection = self.handle_detection
            self.detector.on_log = self.add_log
            self.detector.on_frame_updated = self.update_visualization
        except NotImplementedError as e:
            QMessageBox.critical(self, "Unsupported Platform", str(e))
            sys.exit(1)
        
    def _define_colors(self):
        """Define color theme for the application"""
        self.colors = {
            'bg_dark': '#1E1E1E',           # Dark background
            'bg_medium': '#252526',          # Medium background
            'bg_light': '#2D2D30',           # Light background
            'text': '#E0E0E0',               # Text color
            'highlight': '#4CAF50',          # Highlight color (green)
            'warning': '#FFC107',            # Warning color (amber)
            'error': '#FF5722',              # Error color (red-orange)
            'button_bg': '#3E3E3E',          # Button background
            'button_hover': '#4E4E4E',       # Button hover
            'button_text': '#E0E0E0',        # Button text
            'border': '#555555',             # Border color
            'disabled': '#666666',           # Disabled element color
            'slider_handle': '#4CAF50',      # Slider handle
            'slider_groove': '#3E3E3E',      # Slider groove
        }
        
    def _init_ui(self):
        """Initialize the user interface"""
        # Window setup
        self.setWindowTitle("AutoFisher")
        self.resize(1000, 700)
        self.setMinimumSize(800, 600)
        
        # Apply dark theme
        self.setStyleSheet(f"""
            QMainWindow, QDialog {{ background-color: {self.colors['bg_dark']}; }}
            QWidget {{ color: {self.colors['text']}; }}
            QLabel {{ color: {self.colors['text']}; }}
            QPushButton {{ 
                background-color: {self.colors['button_bg']}; 
                color: {self.colors['button_text']}; 
                border: 1px solid {self.colors['border']};
                padding: 5px;
                border-radius: 3px;
            }}
            QPushButton:hover {{ background-color: {self.colors['button_hover']}; }}
            QPushButton:disabled {{ 
                background-color: {self.colors['bg_medium']}; 
                color: {self.colors['disabled']}; 
            }}
            QSlider::handle {{ 
                background-color: {self.colors['slider_handle']}; 
                border-radius: 7px;
            }}
            QSlider::groove:horizontal {{ 
                background-color: {self.colors['slider_groove']}; 
                height: 3px;
            }}
            QTextEdit {{ 
                background-color: {self.colors['bg_medium']}; 
                color: {self.colors['text']}; 
                border: 1px solid {self.colors['border']};
            }}
            QGroupBox {{ 
                border: 1px solid {self.colors['border']}; 
                margin-top: 10px; 
                padding-top: 15px;
            }}
            QGroupBox::title {{ 
                color: {self.colors['text']}; 
                subcontrol-origin: margin; 
                left: 10px; 
            }}
        """)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)
        
        # Splitters for layout panels
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # === Control Panel ===
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        
        # Region selection
        region_group = QGroupBox("Region Selection")
        region_layout = QVBoxLayout(region_group)
        
        self.region_label = QLabel("No region selected")
        self.region_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        select_region_btn = QPushButton("Select Region")
        select_region_btn.clicked.connect(self.select_region)
        
        region_layout.addWidget(self.region_label)
        region_layout.addWidget(select_region_btn)
        
        # Threshold controls
        threshold_group = QGroupBox("Detection Settings")
        threshold_layout = QVBoxLayout(threshold_group)
        
        threshold_layout.addWidget(QLabel("Sensitivity:"))
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(1)
        self.threshold_slider.setMaximum(20)
        self.threshold_slider.setValue(5)  # Default 0.05 (5%)
        self.threshold_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.threshold_slider.setTickInterval(1)
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        
        self.threshold_label = QLabel("Threshold: 5%")
        self.threshold_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Enhancement settings
        self.noise_reduction_cb = QCheckBox("Noise Reduction")
        self.noise_reduction_cb.setChecked(True)
        self.noise_reduction_cb.toggled.connect(self.toggle_noise_reduction)
        
        self.bright_detection_cb = QCheckBox("Enhanced Bright Background Detection")
        self.bright_detection_cb.setChecked(True)
        self.bright_detection_cb.toggled.connect(self.toggle_bright_detection)
        
        threshold_layout.addWidget(self.threshold_slider)
        threshold_layout.addWidget(self.threshold_label)
        threshold_layout.addWidget(self.noise_reduction_cb)
        threshold_layout.addWidget(self.bright_detection_cb)
        
        # Action buttons
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        self.start_btn = QPushButton("Start Detection")
        self.start_btn.clicked.connect(self.start_detection)
        
        self.stop_btn = QPushButton("Stop Detection")
        self.stop_btn.clicked.connect(self.stop_detection)
        self.stop_btn.setEnabled(False)
        
        self.pause_btn = QPushButton("Pause Detection")
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.pause_btn.setEnabled(False)
        
        capture_ref_btn = QPushButton("Capture Reference Frame")
        capture_ref_btn.clicked.connect(self.capture_reference)
        
        actions_layout.addWidget(self.start_btn)
        actions_layout.addWidget(self.pause_btn)
        actions_layout.addWidget(self.stop_btn)
        actions_layout.addWidget(capture_ref_btn)
        
        # Stats display
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.detection_count_label = QLabel("Detections: 0")
        stats_layout.addWidget(self.detection_count_label)
        
        # Add all groups to control panel
        control_layout.addWidget(region_group)
        control_layout.addWidget(threshold_group)
        control_layout.addWidget(actions_group)
        control_layout.addWidget(stats_group)
        control_layout.addStretch()
        
        # === Monitoring Panel ===
        monitoring_panel = QWidget()
        monitoring_layout = QVBoxLayout(monitoring_panel)
        
        # Image display
        self.monitoring_display = MonitoringDisplay()
        
        # Timeline plot
        self.timeline_plot = TimelinePlot(width=5, height=2)
        
        monitoring_layout.addWidget(self.monitoring_display, 2)
        monitoring_layout.addWidget(self.timeline_plot, 1)
        
        # === Log Panel ===
        log_panel = QWidget()
        log_layout = QVBoxLayout(log_panel)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        
        clear_log_btn = QPushButton("Clear Logs")
        clear_log_btn.clicked.connect(self.clear_logs)
        
        log_layout.addWidget(self.log_text)
        log_layout.addWidget(clear_log_btn)
        
        # Add panels to splitters
        top_splitter.addWidget(control_panel)
        top_splitter.addWidget(monitoring_panel)
        top_splitter.setSizes([300, 700])
        
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(log_panel)
        main_splitter.setSizes([500, 200])
        
        # Add splitter to main layout
        main_layout.addWidget(main_splitter)
        
        # Initialize
        self.update_threshold()
        
    def update_threshold(self):
        """Update threshold from slider value"""
        value = self.threshold_slider.value()
        threshold = value / 100.0
        self.threshold_label.setText(f"Threshold: {value}%")
        
        if self.detector:
            self.detector.THRESHOLD = threshold
            self.timeline_plot.update_plot(self.detector.change_history, threshold)
        
    def select_region(self):
        """Open the region selection overlay"""
        overlay = RegionSelectionOverlay(self)
        overlay.region_selected.connect(self.set_region)
        overlay.exec()
        
    def set_region(self, region):
        """Set the selected region"""
        if not region:
            return
            
        left, top, right, bottom = region
        self.region_label.setText(f"Region: ({left}, {top}) to ({right}, {bottom})")
        
        if self.detector:
            self.detector.region = region
            self.detector.log(f"Region set to: {region}")
            
    def start_detection(self):
        """Start the detection process"""
        if not self.detector:
            return
            
        if not self.detector.region:
            QMessageBox.warning(self, "No Region Selected", 
                               "Please select a screen region first.")
            return
            
        self.detector.start_detection()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
        
        self.monitoring_display.set_status("running")
        
    def stop_detection(self):
        """Stop the detection process"""
        if not self.detector:
            return
            
        self.detector.stop_detection()
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause Detection")
        
        self.monitoring_display.set_status("stopped")
        
    def toggle_pause(self):
        """Pause or resume detection"""
        if not self.detector:
            return
            
        self.detector.toggle_pause()
        
        paused = self.detector.is_paused
        self.pause_btn.setText("Resume Detection" if paused else "Pause Detection")
        
        self.monitoring_display.set_status("paused" if paused else "running")
        
    def capture_reference(self):
        """Capture a reference frame"""
        if not self.detector:
            return
            
        if not self.detector.region:
            QMessageBox.warning(self, "No Region Selected", 
                               "Please select a screen region first.")
            return
            
        self.detector.capture_reference()
        
    def add_log(self, message):
        """Add a message to the log"""
        self.log_text.append(message)
        # Scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def clear_logs(self):
        """Clear the log text"""
        self.log_text.clear()
        
    def handle_detection(self):
        """Handle a detection event"""
        self.detection_count += 1
        self.detection_count_label.setText(f"Detections: {self.detection_count}")
        
    def update_visualization(self):
        """Update the visualization displays"""
        if not self.detector:
            return
            
        # Update the monitoring display
        if hasattr(self.detector, 'color_frame') and self.detector.color_frame is not None:
            change_percent = 0
            if hasattr(self.detector, 'change_history') and self.detector.change_history:
                # Get the latest change percentage
                change_percent = self.detector.change_history[-1][1] if self.detector.change_history else 0
                
            self.monitoring_display.update_display(
                self.detector.color_frame, 
                self.detector.diff_frame,
                change_percent
            )
            
        # Update the timeline plot
        if hasattr(self.detector, 'change_history'):
            self.timeline_plot.update_plot(
                self.detector.change_history, 
                self.detector.THRESHOLD
            )
            
    def toggle_noise_reduction(self, checked):
        """Toggle noise reduction"""
        if self.detector:
            self.detector.apply_blur = checked
            
    def toggle_bright_detection(self, checked):
        """Toggle enhanced bright background detection"""
        if self.detector:
            self.detector.enhanced_bright_detection = checked
            
    def run(self):
        """Run the application"""
        self.show()
        
    def closeEvent(self, event):
        """Handle window close event"""
        if self.detector and self.detector.is_running:
            self.detector.stop_detection()
        event.accept() 