import sys
import time
import threading
import queue
import datetime
import numpy as np
import pyautogui
import mss
import cv2  # For efficient image processing
from PIL import Image
import matplotlib.pyplot as plt
import subprocess  # For running AppleScript to focus on windows
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QSlider, QFrame, QSplitter, QTextEdit,
    QGroupBox, QMessageBox, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRect, QPoint, QSize, QThread, QObject
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QImage, QFont


class PixelChangeDetector(QObject):
    """Core detector class for monitoring pixel changes in a screen region"""
    detection_signal = pyqtSignal()
    log_signal = pyqtSignal(str)
    frame_updated = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.THRESHOLD = 0.05  # Default threshold for pixel change detection
        self.is_running = False
        self.is_paused = False
        
        # Screen capture region
        self.region = None  # (left, top, right, bottom)
        
        # Frames for comparison
        self.current_frame = None
        self.previous_frame = None
        self.reference_frame = None
        self.diff_frame = None
        self.color_frame = None
        
        # Change history
        self.change_history = []
        
        # Last detection time for cooldown
        self.last_detection_time = 0
        self.detection_cooldown = 0.5  # Seconds between detections
        
        # Thread control
        self.detection_thread = None
        self.stop_requested = False
        
    def log(self, message):
        """Log a message"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_signal.emit(formatted_message)
        
    def capture_screen(self):
        """Capture the defined region of the screen"""
        try:
            if not self.region:
                self.log("No region selected")
                return None
                
            left, top, right, bottom = self.region
            width = right - left
            height = bottom - top
            
            with mss.mss() as sct:
                monitor = {"top": top, "left": left, "width": width, "height": height}
                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)
                
                # Store color frame for visualization
                self.color_frame = frame.copy()
                
                # Convert to grayscale for processing
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
                
                return frame
                
        except Exception as e:
            self.log(f"Error capturing screen: {e}")
            return None
            
    def calculate_frame_difference(self, frame1, frame2):
        """Calculate the difference between two frames"""
        if frame1 is None or frame2 is None:
            return None, 0
            
        # Ensure frames have same dimensions
        if frame1.shape != frame2.shape:
            # Resize to match
            frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
            
        # Calculate absolute difference
        diff_frame = cv2.absdiff(frame1, frame2)
        
        # Calculate percentage of pixels that changed significantly
        changed_pixels = np.sum(diff_frame > 30)  # Threshold for significant change
        total_pixels = frame1.shape[0] * frame1.shape[1]
        change_percent = changed_pixels / total_pixels
        
        return diff_frame, change_percent
        
    def capture_reference(self):
        """Capture a reference frame for comparison"""
        frame = self.capture_screen()
        if frame is not None:
            self.reference_frame = frame
            self.log(f"Reference frame captured")
            return True
        return False
    
    def start_detection(self):
        """Start the detection process"""
        if self.is_running:
            return
            
        self.is_running = True
        self.is_paused = False
        self.stop_requested = False
        self.change_history = []
        
        # Capture initial reference frame if none exists
        if self.reference_frame is None:
            self.capture_reference()
            
        self.previous_frame = self.reference_frame
        
        # Start detection thread
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        self.log("Detection started")
        
    def stop_detection(self):
        """Stop the detection process"""
        self.stop_requested = True
        self.is_running = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=1.0)
            
        self.log("Detection stopped")
        
    def toggle_pause(self):
        """Pause or resume detection"""
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.log("Detection paused")
        else:
            self.log("Detection resumed")
            
    def _detection_loop(self):
        """Main detection loop"""
        while self.is_running and not self.stop_requested:
            try:
                # Skip if paused
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                    
                # Capture current frame
                self.current_frame = self.capture_screen()
                
                if self.current_frame is None:
                    time.sleep(0.1)
                    continue
                    
                # Determine which frame to compare against
                compare_frame = self.reference_frame if self.reference_frame is not None else self.previous_frame
                
                if compare_frame is None:
                    self.capture_reference()
                    time.sleep(0.1)
                    continue
                
                # Calculate difference
                self.diff_frame, change_percent = self.calculate_frame_difference(
                    self.current_frame, compare_frame
                )
                
                # Store in history
                self.change_history.append(change_percent)
                if len(self.change_history) > 100:
                    self.change_history = self.change_history[-100:]
                    
                # Emit signal for UI update
                self.frame_updated.emit()
                
                # Check for detection with cooldown
                current_time = time.time()
                if (change_percent > self.THRESHOLD and 
                        (current_time - self.last_detection_time) > self.detection_cooldown):
                    self.log(f"Change detected! {change_percent:.2%}")
                    self.last_detection_time = current_time
                    
                    # Emit signal to trigger action
                    self.detection_signal.emit()
                    
                    # Brief pause after detection
                    time.sleep(1.0)
                
                # Store current frame as previous
                self.previous_frame = self.current_frame
                
                # Control capture rate
                time.sleep(0.05)
                
            except Exception as e:
                self.log(f"Error in detection loop: {e}")
                time.sleep(0.1)
                
        self.log("Detection thread exiting")


class RegionSelectionOverlay(QDialog):
    """Overlay for selecting a screen region"""
    region_selected = pyqtSignal(tuple)
    
    def __init__(self, parent=None, default_size=100):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        
        # Save screen dimensions
        self.screen_width = QApplication.primaryScreen().size().width()
        self.screen_height = QApplication.primaryScreen().size().height()
        
        # Box dimensions (1.5:1 ratio)
        self.box_height = default_size
        self.box_width = int(default_size * 1.5)
        
        # For tracking mouse position
        self.mouse_pos = QPoint(self.screen_width // 2, self.screen_height // 2)
        
        # Initialize UI
        self._init_ui()
        
    def _init_ui(self):
        """Initialize the UI components"""
        # Add label with instructions
        self.instructions = QLabel("Click to place the region box (ESC to cancel)", self)
        self.instructions.setStyleSheet("color: white; background-color: rgba(0, 0, 0, 150); padding: 10px;")
        self.instructions.setGeometry(0, 30, self.screen_width, 30)
        self.instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
    def paintEvent(self, event):
        """Draw the selection overlay"""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))  # Semi-transparent background
        
        # Draw crosshairs
        painter.setPen(QPen(QColor(100, 200, 255), 1, Qt.PenStyle.DashLine))
        painter.drawLine(0, self.mouse_pos.y(), self.screen_width, self.mouse_pos.y())
        painter.drawLine(self.mouse_pos.x(), 0, self.mouse_pos.x(), self.screen_height)
        
        # Calculate box position (centered on mouse)
        left = self.mouse_pos.x() - self.box_width // 2
        top = self.mouse_pos.y() - self.box_height // 2
        
        # Ensure box stays within screen bounds
        if left < 0:
            left = 0
        elif left + self.box_width > self.screen_width:
            left = self.screen_width - self.box_width
            
        if top < 0:
            top = 0
        elif top + self.box_height > self.screen_height:
            top = self.screen_height - self.box_height
        
        # Draw selection box
        box_rect = QRect(left, top, self.box_width, self.box_height)
        
        # Draw outer border
        painter.setPen(QPen(QColor(100, 200, 255), 2))
        painter.drawRect(box_rect)
        
        # Draw semi-transparent fill
        painter.fillRect(box_rect, QColor(100, 200, 255, 40))
        
        # Draw grid lines
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1, Qt.PenStyle.DashLine))
        # Vertical grid lines
        cell_width = self.box_width // 3
        for i in range(1, 3):
            painter.drawLine(
                left + i * cell_width, top,
                left + i * cell_width, top + self.box_height
            )
        # Horizontal grid lines
        cell_height = self.box_height // 3
        for i in range(1, 3):
            painter.drawLine(
                left, top + i * cell_height,
                left + self.box_width, top + i * cell_height
            )
        
        # Draw coordinates
        coord_text = f"Position: ({left},{top}) • Size: {self.box_width}×{self.box_height}"
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Menlo", 10))
        painter.drawText(
            0, self.screen_height - 40, self.screen_width, 30,
            Qt.AlignmentFlag.AlignCenter, coord_text
        )
        
    def mouseMoveEvent(self, event):
        """Track mouse movement"""
        self.mouse_pos = event.pos()
        self.update()  # Redraw
        
    def mousePressEvent(self, event):
        """Handle mouse clicks"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Calculate box position
            left = self.mouse_pos.x() - self.box_width // 2
            top = self.mouse_pos.y() - self.box_height // 2
            
            # Ensure box stays within screen bounds
            if left < 0:
                left = 0
            elif left + self.box_width > self.screen_width:
                left = self.screen_width - self.box_width
                
            if top < 0:
                top = 0
            elif top + self.box_height > self.screen_height:
                top = self.screen_height - self.box_height
                
            # Calculate region bounds
            right = left + self.box_width
            bottom = top + self.box_height
            
            # Emit signal with selected region
            self.region_selected.emit((left, top, right, bottom))
            self.accept()
            
    def keyPressEvent(self, event):
        """Handle key presses"""
        if event.key() == Qt.Key.Key_Escape:
            self.reject()


class TimelinePlot(FigureCanvas):
    """Timeline plot for visualizing change history"""
    def __init__(self, parent=None, width=6, height=1, dpi=100):
        # Create figure and axes
        self.fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        self.fig.set_facecolor('#1A1A1A')
        self.ax.set_facecolor('#1A1A1A')
        
        # Initialize with empty data
        self.x_data = np.arange(100)
        self.y_data = np.zeros(100)
        
        # Create the plot
        self.activity_line, = self.ax.plot(self.x_data, self.y_data, color='#A280FF', linewidth=1)
        self.threshold_line = self.ax.axhline(y=0.05, color='#FF4D4D', linestyle='--', alpha=0.6, linewidth=1)
        
        # Configure appearance
        self.ax.set_xlim(0, 99)
        self.ax.set_ylim(0, 1)
        self.ax.set_xticks([])
        self.ax.grid(True, alpha=0.1)
        self.ax.set_title("Activity Timeline", color='#C4E6B5', fontsize=9)
        
        # Set text color for axis labels and ticks
        self.ax.tick_params(axis='y', colors='#999999')
        self.ax.yaxis.label.set_color('#F8F5FF')
        
        # Remove spines
        for spine in self.ax.spines.values():
            spine.set_color('#333333')
        
        # Initialize the canvas
        super().__init__(self.fig)
        self.setParent(parent)
        
    def update_plot(self, history, threshold):
        """Update the plot with new data"""
        if not history:
            return
            
        # Create data array, padded with zeros if necessary
        data = history[-100:].copy()
        if len(data) < 100:
            data = [0] * (100 - len(data)) + data
            
        # Update the plot
        self.activity_line.set_ydata(data)
        self.threshold_line.set_ydata([threshold, threshold])
        
        # Redraw the canvas
        self.draw()


class MonitoringDisplay(QWidget):
    """Widget for displaying the captured region and difference visualization"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Image display label
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #0E0E0E; border: 1px solid #333333;")
        layout.addWidget(self.image_label)
        
        # Status indicators
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("color: #999999;")
        status_layout.addWidget(self.status_label)
        
        self.change_label = QLabel("Change: 0.00%")
        self.change_label.setStyleSheet("color: #999999;")
        status_layout.addWidget(self.change_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addLayout(status_layout)
        
    def update_display(self, color_frame, diff_frame, change_percent):
        """Update the display with current frames"""
        if color_frame is None:
            return
            
        try:
            # Create overlay of original frame with difference highlights
            display_frame = color_frame.copy()
            
            if diff_frame is not None:
                # Create a mask where differences are significant
                mask = diff_frame > 30
                
                # Apply red highlighting to areas with significant change
                display_frame[mask, 0] = 255  # Max out red channel
                
            # Convert to QImage for display
            height, width, channels = display_frame.shape
            bytes_per_line = channels * width
            
            # Convert BGR to RGB for proper display
            display_frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            q_img = QImage(display_frame_rgb.data, width, height, 
                          bytes_per_line, QImage.Format.Format_RGB888)
            
            # Scale image to fit label while maintaining aspect ratio
            pixmap = QPixmap.fromImage(q_img)
            self.image_label.setPixmap(pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
            
            # Update change percentage display
            self.change_label.setText(f"Change: {change_percent:.2%}")
            
        except Exception as e:
            print(f"Error updating display: {e}")
    
    def set_status(self, status):
        """Update the status display"""
        if status == "running":
            self.status_label.setText("Status: Running")
            self.status_label.setStyleSheet("color: #47D068;")  # Green
        elif status == "stopped":
            self.status_label.setText("Status: Stopped")
            self.status_label.setStyleSheet("color: #FF4D4D;")  # Red
        elif status == "paused":
            self.status_label.setText("Status: Paused")
            self.status_label.setStyleSheet("color: #FFB940;")  # Yellow
        else:
            self.status_label.setText(f"Status: {status}")
            self.status_label.setStyleSheet("color: #999999;")  # Gray


class PixelChangeApp(QMainWindow):
    """Main application window"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pixel Change Detector")
        self.setMinimumSize(800, 600)
        
        # Initialize detector
        self.detector = PixelChangeDetector()
        self.detector.log_signal.connect(self.add_log)
        self.detector.frame_updated.connect(self.update_visualization)
        self.detector.detection_signal.connect(self.handle_detection)
        
        # Create UI
        self._init_ui()
        
        # Configure colors and styles
        self._setup_styles()
        
        # Detection counter
        self.detection_count = 0
        
    def _init_ui(self):
        """Initialize the user interface"""
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create left panel (controls)
        left_panel = QWidget()
        left_panel.setFixedWidth(280)
        left_layout = QVBoxLayout(left_panel)
        main_layout.addWidget(left_panel)
        
        # Create right panel (visualization)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        main_layout.addWidget(right_panel)
        
        # === LEFT PANEL COMPONENTS ===
        
        # 1. Settings group
        settings_group = QGroupBox("SETTINGS")
        settings_layout = QVBoxLayout(settings_group)
        left_layout.addWidget(settings_group)
        
        # Threshold control
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("threshold:")
        threshold_layout.addWidget(threshold_label)
        
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(1, 50)  # 0.01 to 0.50
        self.threshold_slider.setValue(5)      # Default 0.05
        self.threshold_slider.valueChanged.connect(self.update_threshold)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_value_label = QLabel("0.05")
        threshold_layout.addWidget(self.threshold_value_label)
        settings_layout.addLayout(threshold_layout)
        
        # Region size control
        size_layout = QHBoxLayout()
        size_label = QLabel("region_size:")
        size_layout.addWidget(size_label)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(20, 200)  # 20 to 200 pixels
        self.size_slider.setValue(100)      # Default 100
        self.size_slider.valueChanged.connect(self.update_size_label)
        size_layout.addWidget(self.size_slider)
        
        self.size_value_label = QLabel("100")
        size_layout.addWidget(self.size_value_label)
        settings_layout.addLayout(size_layout)
        
        # 2. Monitoring group
        monitoring_group = QGroupBox("MONITORING")
        monitoring_layout = QVBoxLayout(monitoring_group)
        left_layout.addWidget(monitoring_group)
        
        # Region selection button
        self.region_button = QPushButton("select-region")
        self.region_button.clicked.connect(self.select_region)
        monitoring_layout.addWidget(self.region_button)
        
        # Region info display
        region_info_layout = QHBoxLayout()
        region_info_layout.addWidget(QLabel("status:"))
        self.region_info_label = QLabel("waiting_for_region_selection")
        region_info_layout.addWidget(self.region_info_label)
        monitoring_layout.addLayout(region_info_layout)
        
        # 3. Control group
        control_group = QGroupBox("CONTROL")
        control_layout = QVBoxLayout(control_group)
        left_layout.addWidget(control_group)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("start")
        self.start_button.clicked.connect(self.start_detection)
        button_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("stop")
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        self.pause_button = QPushButton("pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        button_layout.addWidget(self.pause_button)
        
        control_layout.addLayout(button_layout)
        
        # Second row of buttons
        button_layout2 = QHBoxLayout()
        
        self.reference_button = QPushButton("capture-reference")
        self.reference_button.clicked.connect(self.capture_reference)
        button_layout2.addWidget(self.reference_button)
        
        self.clear_button = QPushButton("clear-logs")
        self.clear_button.clicked.connect(self.clear_logs)
        button_layout2.addWidget(self.clear_button)
        
        control_layout.addLayout(button_layout2)
        
        # 4. Log display
        log_group = QGroupBox("LOGS")
        log_layout = QVBoxLayout(log_group)
        left_layout.addWidget(log_group, stretch=1)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        log_layout.addWidget(self.log_display)
        
        # === RIGHT PANEL COMPONENTS ===
        
        # 1. Monitoring display
        self.monitor_display = MonitoringDisplay()
        right_layout.addWidget(self.monitor_display, stretch=3)
        
        # 2. Timeline plot
        self.timeline_plot = TimelinePlot(width=5, height=1.5)
        timeline_container = QWidget()
        timeline_layout = QVBoxLayout(timeline_container)
        timeline_layout.addWidget(self.timeline_plot)
        right_layout.addWidget(timeline_container, stretch=1)
        
        # 3. Status and count display
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("system:monitor.idle")
        status_layout.addWidget(self.status_label)
        
        self.count_label = QLabel("detections: 0")
        status_layout.addWidget(self.count_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        right_layout.addLayout(status_layout)
        
        # Add a welcome log message
        self.add_log("Pixel Change Detector initialized")
        self.add_log("Click 'select-region' to begin")
        
    def _setup_styles(self):
        """Configure application styling"""
        # Define color scheme
        self.colors = {
            'bg_dark': '#050505',      
            'bg_term': '#0E0E0E',     
            'bg_lighter': '#1A1A1A',   
            'bg_alt': '#191919',      
            'text': '#F8F5FF',         
            'text_dim': '#999999',     
            'accent': '#A280FF',       
            'green': '#C4E6B5',        
            'success': '#47D068',      
            'alert': '#FF4D4D',        
            'warning': '#FFB940',      
            'border': '#2A2A2A',       
        }
        
        # Set application-wide stylesheet
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background-color: {self.colors['bg_dark']}; color: {self.colors['text']}; }}
            
            QGroupBox {{ 
                background-color: {self.colors['bg_dark']}; 
                color: {self.colors['green']}; 
                border: 1px solid {self.colors['border']}; 
                border-radius: 3px; 
                margin-top: 0.5em;
                font-weight: bold;
            }}
            QGroupBox::title {{ 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 3px;
            }}
            
            QLabel {{ color: {self.colors['text']}; }}
            
            QPushButton {{ 
                background-color: {self.colors['bg_dark']}; 
                color: {self.colors['green']}; 
                border: 1px solid {self.colors['border']}; 
                padding: 5px; 
                border-radius: 2px;
            }}
            QPushButton:hover {{ background-color: {self.colors['bg_lighter']}; }}
            QPushButton:pressed {{ background-color: {self.colors['bg_alt']}; }}
            QPushButton:disabled {{ color: {self.colors['text_dim']}; }}
            
            QTextEdit {{ 
                background-color: {self.colors['bg_term']}; 
                color: {self.colors['text']}; 
                border: 1px solid {self.colors['border']}; 
                font-family: Menlo, Consolas, monospace;
                font-size: 10pt;
            }}
            
            QSlider::groove:horizontal {{
                border: 1px solid {self.colors['border']};
                height: 4px;
                background: {self.colors['bg_term']};
                margin: 0px;
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {self.colors['accent']};
                border: 1px solid {self.colors['accent']};
                width: 10px;
                margin: -5px 0;
                border-radius: 5px;
            }}
        """)
        
        # Set specific button styles
        self.start_button.setStyleSheet(f"""
            QPushButton {{ color: {self.colors['green']}; }}
            QPushButton:hover {{ color: {self.colors['success']}; }}
        """)
        
        self.stop_button.setStyleSheet(f"""
            QPushButton {{ color: {self.colors['alert']}; }}
            QPushButton:hover {{ color: {self.colors['alert']}; }}
        """)
        
        self.pause_button.setStyleSheet(f"""
            QPushButton {{ color: {self.colors['warning']}; }}
            QPushButton:hover {{ color: {self.colors['warning']}; }}
        """)
    
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
        # Hide main window temporarily
        self.hide()
        time.sleep(0.2)  # Short delay for window transition
        
        # Create and show region selection dialog
        region_size = self.size_slider.value()
        selection_dialog = RegionSelectionOverlay(None, region_size)
        selection_dialog.region_selected.connect(self.set_region)
        
        if selection_dialog.exec() == QDialog.DialogCode.Rejected:
            self.add_log("Region selection canceled")
            
        # Show main window again
        self.show()
    
    def set_region(self, region):
        """Set the selected region"""
        self.detector.region = region
        left, top, right, bottom = region
        width = right - left
        height = bottom - top
        
        # Update UI
        self.region_info_label.setText(f"region({left},{top},{width}×{height})")
        self.add_log(f"Region selected: ({left},{top}) {width}×{height}")
    
    def start_detection(self):
        """Start the detection process"""
        if not self.detector.region:
            self.add_log("You must select a region first")
            return
            
        # Update threshold from UI
        self.detector.THRESHOLD = self.threshold_slider.value() / 100.0
        
        # Start detection
        self.detector.start_detection()
        
        # Update UI
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.monitor_display.set_status("running")
        self.status_label.setText("system:monitor.active")
        self.status_label.setStyleSheet(f"color: {self.colors['success']};")
    
    def stop_detection(self):
        """Stop the detection process"""
        self.detector.stop_detection()
        
        # Update UI
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("pause")
        self.monitor_display.set_status("stopped")
        self.status_label.setText("system:monitor.stopped")
        self.status_label.setStyleSheet(f"color: {self.colors['alert']};")
    
    def toggle_pause(self):
        """Pause or resume detection"""
        self.detector.toggle_pause()
        
        if self.detector.is_paused:
            self.pause_button.setText("resume")
            self.monitor_display.set_status("paused")
            self.status_label.setText("system:monitor.paused")
            self.status_label.setStyleSheet(f"color: {self.colors['warning']};")
        else:
            self.pause_button.setText("pause")
            self.monitor_display.set_status("running")
            self.status_label.setText("system:monitor.active")
            self.status_label.setStyleSheet(f"color: {self.colors['success']};")
    
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
        self.count_label.setText(f"detections: {self.detection_count}")
        
        # Run AppleScript to press 'f' key in the active application
        try:
            # AppleScript to press 'f' key
            script = '''
            tell application "System Events"
                keystroke "f"
            end tell
            '''
            subprocess.run(['osascript', '-e', script], check=True)
            self.add_log("Triggered 'f' key press")
            
            # After a delay, also send ESC key
            def delayed_esc():
                time.sleep(3)
                esc_script = '''
                tell application "System Events"
                    keystroke (ASCII character 27)  # ESC key
                    delay 0.5
                    keystroke "f"
                end tell
                '''
                subprocess.run(['osascript', '-e', esc_script], check=True)
                
            threading.Thread(target=delayed_esc, daemon=True).start()
            
        except subprocess.SubprocessError as e:
            self.add_log(f"Error triggering key press: {e}")
    
    def update_visualization(self):
        """Update visualization components"""
        if not self.detector:
            return
            
        # Get latest data from detector
        current_frame = self.detector.color_frame
        diff_frame = self.detector.diff_frame
        
        # Calculate current change percentage
        current_change = self.detector.change_history[-1] if self.detector.change_history else 0
        
        # Update display components
        self.monitor_display.update_display(current_frame, diff_frame, current_change)
        self.timeline_plot.update_plot(self.detector.change_history, self.detector.THRESHOLD)


def main():
    app = QApplication(sys.argv)
    window = PixelChangeApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()