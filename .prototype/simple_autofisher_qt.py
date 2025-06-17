import sys
import os
import time
import threading
import numpy as np
import cv2
import traceback
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QGridLayout, QDoubleSpinBox, QSpinBox, QLineEdit, QComboBox,
    QCheckBox, QTextEdit, QFrame, QSplitter, QDialog, QFormLayout, QDialogButtonBox, 
    QSpinBox, QMessageBox, QGroupBox, QSlider
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot, QRect, QPoint, QObject, QRectF
from PyQt6.QtGui import QFont, QColor, QPalette, QPainter, QPen, QBrush, QScreen, QPixmap, QImage, QCursor, QPainterPath
import keyboard
import queue
import datetime
import win32gui
import win32con
import win32process
import win32api
import ctypes
import psutil
from PIL import ImageGrab
import mss
import mss.tools
# Add matplotlib imports for visualization
import matplotlib
# Set the backend to qt5agg (compatible with PyQt6)
matplotlib.use('qt5agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# Import the core functionality from the original file
from autofisher import (
    PixelChangeDetector, force_focus_window, direct_key_press, 
    MOUSEINPUT, KEYBDINPUT, HARDWAREINPUT, INPUT_UNION, INPUT,
    user32, kernel32, VK_F, KEYEVENTF_KEYUP, INPUT_KEYBOARD,
    HWND_TOPMOST, SWP_NOMOVE, SWP_NOSIZE, SWP_SHOWWINDOW
)

# Application version
VERSION = "1.6"
VERSION_NAME = "Direct Control Edition"

# Matplotlib canvas class for Qt integration
class MatplotlibCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=3.33, dpi=100, bg_color='#333333'):
        # Create figure with correct aspect ratio (1.5:1 width to height)
        # Add extra height for the timeline
        adjusted_height = height * 1.15  # Add 15% height for timeline
        self.fig = Figure(figsize=(width, adjusted_height), dpi=dpi, facecolor=bg_color)
        
        # Create properly spaced subplots - one for image, one for timeline
        gs = self.fig.add_gridspec(2, 1, height_ratios=[9, 1], hspace=0.15)
        
        # Main image display - top subplot
        self.current_ax = self.fig.add_subplot(gs[0, 0])
        self.current_ax.set_facecolor(bg_color)
        self.current_ax.axis('off')
        
        # Initialize empty image with correct aspect ratio (1.5:1)
        empty_img = np.zeros((100, 150, 3), dtype=np.uint8)  # 150x100 = 1.5:1 ratio
        self.current_image = self.current_ax.imshow(empty_img, aspect='equal', interpolation='none')
        self.diff_overlay = self.current_ax.imshow(np.zeros((100, 150, 4), dtype=np.uint8), 
                                                  alpha=0.5, interpolation='none')
        
        # Add rectangle border around image
        rect = plt.Rectangle((0, 0), 1, 1, fill=False, ec='#666', linewidth=1.5, 
                            transform=self.current_ax.transAxes, clip_on=False)
        self.current_ax.add_patch(rect)
        
        # Add timeline for activity monitoring in separate subplot
        self.timeline_ax = self.fig.add_subplot(gs[1, 0])
        self.timeline_ax.set_facecolor(bg_color)
        self.timeline_ax.set_xticks([])
        self.timeline_ax.set_yticks([])
        
        # Add border for timeline
        self.timeline_ax.spines['top'].set_visible(False)
        self.timeline_ax.spines['right'].set_visible(False)
        self.timeline_ax.spines['bottom'].set_visible(False)
        self.timeline_ax.spines['left'].set_visible(False)
        
        # Initialize timeline data
        x_data = np.arange(100)
        y_data = np.ones(100) * 0.5
        self.activity_line, = self.timeline_ax.plot(x_data, y_data, color='#77DD77', linewidth=1.5)
        self.threshold_line = self.timeline_ax.axhline(y=0.05, color='#FF6961', 
                                                      linestyle='--', alpha=0.7, linewidth=1)
        self.timeline_ax.set_ylim(0, 1)
        
        # Add title to timeline with threshold value
        self.timeline_ax.set_title("ACTIVITY", color='#77DD77', fontsize=8, fontweight='normal', pad=2)
        
        # Initialize the figure canvas
        super(MatplotlibCanvas, self).__init__(self.fig)
        self.setParent(parent)
        
        # Add placeholder text
        self.placeholder_text = self.fig.text(0.5, 0.45, "Awaiting data...", color='#999', 
                                             ha='center', va='center', fontsize=10)
        
        # Set min/fixed size to maintain aspect ratio
        self.setMinimumSize(300, 200)
        
    def resizeEvent(self, event):
        """Handle resize events to maintain proper aspect ratio"""
        super().resizeEvent(event)
        # Update aspect ratio by adjusting the axes
        self.current_ax.set_aspect('equal')
        self.current_ax.figure.canvas.draw_idle()

    def update_image(self, frame=None, diff_frame=None):
        """Update the displayed image maintaining aspect ratio"""
        if self.placeholder_text:
            self.placeholder_text.remove()
            self.placeholder_text = None
            
        if frame is not None:
            # If frame doesn't have the correct aspect ratio, resize it
            h, w = frame.shape[:2]
            target_ratio = 1.5
            actual_ratio = w / h
            
            if abs(actual_ratio - target_ratio) > 0.01:  # If ratio is off by more than 1%
                # Resize the image to match the target ratio
                new_w = w
                new_h = int(w / target_ratio)
                if new_h > h:
                    new_h = h
                    new_w = int(h * target_ratio)
                
                # Center crop to the new size
                y_start = (h - new_h) // 2
                x_start = (w - new_w) // 2
                frame = frame[y_start:y_start+new_h, x_start:x_start+new_w]
                
            self.current_image.set_data(frame)
            
        if diff_frame is not None:
            # Create a colored diff frame with alpha channel
            diff_display = cv2.convertScaleAbs(diff_frame, alpha=3)
            diff_colored = cv2.applyColorMap(diff_display, cv2.COLORMAP_INFERNO)
            colored_diff = cv2.cvtColor(diff_colored, cv2.COLOR_BGR2RGB)
            
            colored_diff_alpha = np.zeros((colored_diff.shape[0], colored_diff.shape[1], 4), dtype=np.uint8)
            colored_diff_alpha[..., :3] = colored_diff
            
            # Set alpha based on difference intensity
            alpha_threshold = 30
            for i in range(diff_display.shape[0]):
                for j in range(diff_display.shape[1]):
                    if diff_display[i, j] > alpha_threshold:
                        # Scale alpha with intensity
                        safe_value = min(127, diff_display[i, j])
                        colored_diff_alpha[i, j, 3] = min(255, int(safe_value * 2))
                    else:
                        colored_diff_alpha[i, j, 3] = 0
            
            self.diff_overlay.set_data(colored_diff_alpha)
        
        # Ensure display maintains correct aspect ratio
        self.current_ax.set_aspect('equal')
        self.current_ax.figure.canvas.draw_idle()
    
    def update_timeline(self, history=None, threshold=0.05):
        """Update the activity timeline"""
        if history and len(history) > 0:
            # Normalize values to 0-1 range for clean display
            max_val = max(history) if max(history) > 0 else 1
            normalized_history = [min(h / max_val, 1.0) for h in history]
            
            # Pad with zeros if needed
            if len(normalized_history) < 100:
                normalized_history = [0] * (100 - len(normalized_history)) + normalized_history
            elif len(normalized_history) > 100:
                normalized_history = normalized_history[-100:]
                
            # Update the line data
            self.activity_line.set_ydata(normalized_history)
            
            # Update threshold line position (normalized)
            threshold_value = min(threshold / max_val, 1.0)
            self.threshold_line.set_ydata([threshold_value, threshold_value])
        
        self.fig.canvas.draw_idle()

# Region Selection Overlay class for Qt
class RegionSelectionOverlay(QWidget):
    """Overlay widget for selecting a region of the screen"""
    
    region_selected = pyqtSignal(tuple)  # Signal emitted when region is selected
    selection_canceled = pyqtSignal()    # Signal emitted when selection is canceled
    
    def __init__(self, window_geometry, parent=None):
        super().__init__(parent)
        # Store the target window geometry
        self.window_x, self.window_y, self.window_width, self.window_height = window_geometry
        
        # Configure the overlay window properties
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        
        # Position and size the overlay to match the target window
        self.setGeometry(self.window_x, self.window_y, self.window_width, self.window_height)
        
        # Set fixed box size (height × width)
        self.box_height = 50
        self.box_width = 75
        
        # Track mouse position
        self.current_x = None
        self.current_y = None
        
        # Initialize box position
        self.box_x = 0
        self.box_y = 0
        self.current_box = None
        
        # Set up colors
        self.colors = {
            'background': QColor(0, 0, 0, 30),   # Very transparent black
            'selection': QColor(255, 255, 0, 230),  # Yellow with high opacity
            'selection_fill': QColor(255, 255, 0, 30),  # Yellow with low opacity
            'grid': QColor(255, 255, 0, 120),  # Yellow with medium opacity
            'text': QColor(255, 255, 255, 255),  # White
            'accent': QColor(255, 255, 0, 255),  # Bright yellow
            'border': QColor(0, 0, 0, 150),  # Dark border
            'text_bg': QColor(0, 0, 0, 180)  # Semi-transparent black for text backgrounds
        }
        
        # Selection result
        self.selection_complete = False
        self.selected_region = None
        
        # Preview image
        self.preview_pixmap = None
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(100)  # Update preview 10 times per second
        self.preview_timer.timeout.connect(self.update_preview)
        
        # Initialize mouse tracking
        self.setMouseTracking(True)
        
        # Center cursor on start
        cursor = QCursor()
        center_x = self.window_x + (self.window_width // 2)
        center_y = self.window_y + (self.window_height // 2)
        cursor.setPos(center_x, center_y)
        
        # Initial update for box position
        self.current_x = self.window_width // 2
        self.current_y = self.window_height // 2
        self.update_current_box()
        
        # Set up a timer to ensure we maintain proper positioning
        self.position_check_timer = QTimer(self)
        self.position_check_timer.setInterval(100)  # Check every 100ms
        self.position_check_timer.timeout.connect(self.check_position)
        self.position_check_timer.start()
        
        # Start preview timer
        self.preview_timer.start()
    
    def showEvent(self, event):
        """Ensure window is active when shown"""
        super().showEvent(event)
        self.raise_()
        self.activateWindow()
        
        # Make sure we're correctly positioned and visible
        self.check_position()
    
    def check_position(self):
        """Ensure the overlay stays correctly positioned and on top"""
        if not self.isVisible():
            return
        
        # Set position and size again to make sure overlay stays aligned
        self.setGeometry(self.window_x, self.window_y, self.window_width, self.window_height)
        
        # Make sure we're on top
        self.raise_()
        self.activateWindow()
        
        # Process events to ensure immediate updates
        QApplication.processEvents()
    
    def update_preview(self):
        """Update the preview image of the current selection"""
        if not self.current_box:
            return
            
        try:
            # Calculate absolute screen coordinates for capture
            left, top, right, bottom = self.current_box
            abs_left = self.window_x + left
            abs_top = self.window_y + top
            abs_right = abs_left + (right - left)
            abs_bottom = abs_top + (bottom - top)
            
            # Capture the current selection using QScreen
            screen = QApplication.primaryScreen()
            self.preview_pixmap = screen.grabWindow(
                0,  # Capture entire screen
                abs_left, abs_top,
                abs_right - abs_left, abs_bottom - abs_top
            )
            
            # Request a repaint to show the updated preview
            self.update()
            
        except Exception as e:
            print(f"Error updating preview: {e}")
        
    def update_current_box(self):
        """Update the current box position based on mouse position"""
        if self.current_x is None or self.current_y is None:
            return
            
        # Calculate box coordinates centered on cursor
        left = self.current_x - (self.box_width // 2)
        top = self.current_y - (self.box_height // 2)
        
        # Ensure box stays within overlay bounds
        if left < 0:
            left = 0
        elif left + self.box_width > self.window_width:
            left = self.window_width - self.box_width
            
        if top < 0:
            top = 0
        elif top + self.box_height > self.window_height:
            top = self.window_height - self.box_height
        
        # Store current box coordinates (left, top, right, bottom)
        right = left + self.box_width
        bottom = top + self.box_height
        self.box_x = left
        self.box_y = top
        self.current_box = (left, top, right, bottom)
        
        # Request a repaint
        self.update()
        
    def mouseMoveEvent(self, event):
        """Handle mouse movement to update selection box position"""
        self.current_x = int(event.position().x())
        self.current_y = int(event.position().y())
        self.update_current_box()
        
        # Process events to ensure smooth updates
        QApplication.processEvents()
    
    def mousePressEvent(self, event):
        """Handle mouse click to finalize selection"""
        if event.button() == Qt.MouseButton.LeftButton and self.current_box:
            # Calculate absolute screen coordinates
            left, top, right, bottom = self.current_box
            abs_left = self.window_x + left
            abs_top = self.window_y + top
            abs_right = abs_left + self.box_width
            abs_bottom = abs_top + self.box_height
            
            # Store selection
            self.selected_region = (abs_left, abs_top, abs_right, abs_bottom)
            self.selection_complete = True
            
            # Stop the timers
            self.position_check_timer.stop()
            self.preview_timer.stop()
            
            # Close the overlay
            self.close()
    
    def keyPressEvent(self, event):
        """Handle key presses"""
        if event.key() == Qt.Key.Key_Escape:
            # Cancel selection
            self.selection_complete = False
            self.selected_region = None
            
            # Stop the timers
            self.position_check_timer.stop()
            self.preview_timer.stop()
            
            # Close the overlay
            self.close()
    
    def paintEvent(self, event):
        """Draw the overlay UI"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw a very transparent background to allow clicking
        # but keep it almost completely transparent so game is visible
        painter.fillRect(self.rect(), self.colors['background'])
        
        # Draw guides (crosshair)
        painter.setPen(QPen(self.colors['grid'], 1, Qt.PenStyle.DashLine))
        
        if self.current_x is not None and self.current_y is not None:
            painter.drawLine(self.current_x, 0, self.current_x, self.height())
            painter.drawLine(0, self.current_y, self.width(), self.current_y)
        
        # Draw selection box
        if self.current_box:
            left, top, right, bottom = self.current_box
            
            # First draw semi-transparent fill
            painter.setBrush(QBrush(self.colors['selection_fill']))
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawRect(left, top, right - left, bottom - top)
            
            # Then draw border with thicker pen
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.setPen(QPen(self.colors['selection'], 2))
            painter.drawRect(left, top, right - left, bottom - top)
            
            # Draw outer glow effect
            painter.setPen(QPen(self.colors['border'], 1, Qt.PenStyle.DotLine))
            painter.drawRect(left-4, top-4, (right-left)+8, (bottom-top)+8)
            
            # Draw grid inside selection box
            cell_width = self.box_width // 3
            cell_height = self.box_height // 3
            
            painter.setPen(QPen(self.colors['grid'], 1, Qt.PenStyle.DotLine))
            
            # Vertical grid lines
            for i in range(1, 3):
                x = left + i * cell_width
                painter.drawLine(x, top, x, bottom)
            
            # Horizontal grid lines
            for i in range(1, 3):
                y = top + i * cell_height
                painter.drawLine(left, y, right, y)
            
            # Highlight center of the box (where bobber should be)
            center_x = left + self.box_width // 2
            center_y = top + self.box_height // 2
            center_size = min(self.box_width, self.box_height) // 6
            
            # Draw center target circle
            painter.setPen(QPen(self.colors['accent'], 2))
            painter.drawEllipse(center_x - center_size//2, center_y - center_size//2, center_size, center_size)
            
            # Draw center crosshair
            painter.drawLine(center_x - center_size, center_y, center_x + center_size, center_y)
            painter.drawLine(center_x, center_y - center_size, center_x, center_y + center_size)
            
            # Draw a small dot at the very center
            painter.setBrush(QBrush(self.colors['accent']))
            painter.drawEllipse(center_x-1, center_y-1, 2, 2)
            
            # Draw info text with fixed dimensions
            info_text = f"Selection box: {self.box_height}×{self.box_width} px • Position: ({left},{top})"
            
            # Draw text with better visibility
            text_bg_rect = QRect(0, self.height() - 30, self.width(), 25)
            painter.fillRect(text_bg_rect, self.colors['text_bg'])
            
            painter.setPen(QPen(self.colors['text']))
            font = painter.font()
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            
            painter.drawText(text_bg_rect, Qt.AlignmentFlag.AlignCenter, info_text)
            
            # Draw preview box in corner
            if self.preview_pixmap:
                preview_size = 150  # Preview size
                preview_scale = 2  # Scale factor for preview (2x larger)
                
                # Draw preview background and border
                preview_rect = QRect(
                    self.width() - preview_size - 10, 
                    10, 
                    preview_size, 
                    preview_size
                )
                
                # Draw background for preview
                painter.fillRect(preview_rect, self.colors['text_bg'])
                
                # Draw border
                painter.setPen(QPen(self.colors['accent'], 2))
                painter.drawRect(preview_rect)
                
                # Draw preview label
                label_rect = QRect(
                    self.width() - preview_size - 10,
                    10,
                    preview_size,
                    20
                )
                painter.setPen(QPen(self.colors['text']))
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, "LIVE PREVIEW")
                
                # Calculate scaled preview image
                scaled_pixmap = self.preview_pixmap.scaled(
                    preview_size - 10, 
                    preview_size - 30, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Draw the preview image
                painter.drawPixmap(
                    self.width() - scaled_pixmap.width() - 15,
                    35,
                    scaled_pixmap
                )
        
        # Draw instructions panel
        instructions = "POSITION OVER FISHING BOBBER • CLICK TO SELECT • ESC TO CANCEL"
        instructions_rect = QRect(0, 30, self.width(), 30)
        
        # Draw background for instructions
        bg_rect = instructions_rect.adjusted(-10, -5, 10, 5)
        painter.fillRect(bg_rect, self.colors['text_bg'])
        painter.setPen(QPen(self.colors['selection']))
        painter.drawRect(bg_rect)
        
        # Draw text
        painter.setPen(QPen(self.colors['text']))
        font = painter.font()
        font.setPointSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(instructions_rect, Qt.AlignmentFlag.AlignCenter, instructions)
        
        # Draw additional info
        detail_text = f"Fixed box size: {self.box_height}×{self.box_width} pixels (height × width) • Center the yellow target on the bobber"
        detail_rect = QRect(0, 60, self.width(), 20)
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(detail_rect, Qt.AlignmentFlag.AlignCenter, detail_text)

class PixelChangeDetector(QObject):
    # Define signals
    detection_signal = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__()
        # Store parent for callbacks
        self.parent = parent
        
        # Initialize logging
        self.log_history = []  # Store log messages locally
        
        # Initialize variables
        self.region = None
        self.reference_frame = None
        self.previous_frame = None
        self.current_frame = None
        self.color_frame = None  # For visualization
        self.diff_frame = None
        
        # Play Together window handling
        self.play_together_window = None
        
        # Detection parameters
        self.THRESHOLD = 0.05
        self.detection_cooldown = 5.0
        self.last_detection_time = 0
        self.change_history = []
        self.fishing_key = "f"
        
        # Options
        self.high_performance_mode = True
        self.respect_fullscreen = True
        self.direct_control = True
        
        # Thread handling
        self.thread_control = {"stop_requested": False}
        self.running = False
        self.paused = False
        self.capture_interval = 0.1  # 10 FPS default
        
        # Initialize stats
        self.stats = {
            "total_detections": 0,
            "last_detection_time": 0,
            "avg_detection_interval": 0
        }
        
        # Find Play Together window
        self.find_play_together_process()
        
        # Set up performance metrics
        self.performance = {
            "fps": 0,
            "processing_samples": 0
        }
        
        # Log initialization
        self.log("PixelChangeDetector initialized")
    
    def log(self, message):
        """Log a message to the parent application or print to console"""
        try:
            # Send to parent's log queue if available
            if self.parent:
                # Make sure we're using the parent's log method
                self.parent.log(message)
            else:
                # Otherwise print to console
                print(f"[Detector] {message}")
                
            # Add to local log history
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.log_history.append(f"[{timestamp}] {message}")
            while len(self.log_history) > 100:  # Limit history size
                self.log_history.pop(0)
        except Exception as e:
            # Emergency fallback
            print(f"[ERROR] Failed to log message: {e}")
            print(f"[DEBUG] Original message: {message}")
    
    def find_play_together_process(self):
        """Find Play Together process and window handle"""
        # List of possible name variations
        name_variations = [
            'play together',
            'playtogether',
            'play-together',
            'play_together',
            'playtogether.exe',
            'play together.exe',
            'play together game',
            'playtogether game'
        ]
        
        # Find window handle using EnumWindows
        def enum_window_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd).lower()
                
                # Skip our own detector window
                if 'autofisher' in window_text:
                    return True
                
                # Check by window title
                if any(variation in window_text for variation in name_variations):
                    self.play_together_window = hwnd
                    self.log(f"Found Play Together window: {window_text} (HWND: {hwnd})")
                    return False
            return True
            
        win32gui.EnumWindows(enum_window_callback, None)
        
        # If no Play Together window was found, log it clearly
        if not self.play_together_window:
            self.log("No Play Together window found. Please make sure the Play Together application is running.")
            return False
        
        return self.play_together_window is not None
    
    def capture_reference(self):
        """Capture a reference frame for comparison"""
        frame = self.capture_screen()
        if frame is not None:
            self.reference_frame = frame
            self.log(f"Reference frame captured: {self.reference_frame.shape}")
            
            # If we have a color frame, store it for visualization
            if hasattr(self, 'color_frame') and self.color_frame is not None:
                self.reference_color_frame = self.color_frame.copy()
                
            return True
        else:
            self.log("Failed to capture reference frame")
            return False
    
    def capture_screen(self):
        """Capture the region of interest using MSS"""
        try:
            if not self.region:
                self.log("No region selected. Please select a region first.")
                return None
                
            # Validate region size
            left, top, right, bottom = self.region
            width = right - left
            height = bottom - top
            
            if width < 10 or height < 10:
                self.log("Invalid region size detected. Please select a new region.")
                return None
                
            # Use mss library which has better performance and multi-monitor support
            with mss.mss() as sct:
                # Convert region format to mss format (left, top, width, height)
                mss_region = {
                    "left": left,
                    "top": top,
                    "width": width,
                    "height": height
                }
                
                # Capture the region
                screenshot = sct.grab(mss_region)
                
                # Convert to numpy array - sct.grab returns BGR
                frame = np.array(screenshot)
                
            # Store color frame for visualization (convert BGR to RGB)
            if len(frame.shape) >= 3:
                self.color_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                
            return frame
            
        except Exception as e:
            self.log(f"Error capturing screen: {e}")
            return None
    
    def validate_region(self):
        """Validate the selected region with a preview capture"""
        frame = self.capture_screen()
        if frame is not None:
            self.log(f"Region validation successful: captured {frame.shape}")
            return True
        else:
            self.log("Failed to validate region")
            return False
    
    def calculate_frame_difference(self, frame1, frame2):
        """Calculate the difference between two frames"""
        if frame1 is None or frame2 is None:
            return None, 0
            
        # Ensure frames have same dimensions
        if frame1.shape != frame2.shape:
            # Resize to match
            frame2 = cv2.resize(frame2, (frame1.shape[1], frame1.shape[0]))
        
        # Apply slight blur to reduce noise sensitivity
        frame1_blurred = cv2.GaussianBlur(frame1, (5, 5), 0)
        frame2_blurred = cv2.GaussianBlur(frame2, (5, 5), 0)
        
        # For color images - convert to HSV for better color sensitivity
        if len(frame1.shape) >= 3:
            frame1_hsv = cv2.cvtColor(frame1_blurred, cv2.COLOR_BGR2HSV)
            frame2_hsv = cv2.cvtColor(frame2_blurred, cv2.COLOR_BGR2HSV)
            
            # Calculate difference in HSV space
            h_diff = cv2.absdiff(frame1_hsv[:,:,0], frame2_hsv[:,:,0])
            s_diff = cv2.absdiff(frame1_hsv[:,:,1], frame2_hsv[:,:,1])
            v_diff = cv2.absdiff(frame1_hsv[:,:,2], frame2_hsv[:,:,2])
            
            # Weight hue differences more heavily for pastel colors
            h_weight = 2.0  # Increased weight for hue differences
            s_weight = 1.0
            v_weight = 1.0
            
            # Combine channels with weights
            diff_frame = cv2.addWeighted(h_diff, h_weight, s_diff, s_weight, 0)
            diff_frame = cv2.addWeighted(diff_frame, 1.0, v_diff, v_weight, 0)
        else:
            # For grayscale images
            diff_frame = cv2.absdiff(frame1_blurred, frame2_blurred)
        
        # Calculate percentage of pixels that changed significantly
        threshold = 20  # Lower threshold for more sensitivity
        
        # Apply morphological operations to highlight larger changes
        kernel = np.ones((3, 3), np.uint8)
        dilated_diff = cv2.dilate(diff_frame, kernel, iterations=1)
        
        # Count significant pixel changes
        changed_pixels = np.sum(dilated_diff > threshold)
        total_pixels = frame1.shape[0] * frame1.shape[1]
        change_percent = changed_pixels / total_pixels
        
        return dilated_diff, change_percent
    
    def start_detection(self):
        """Start detection thread"""
        if not self.find_play_together_process():
            self.log("Cannot start detection: Play Together window not found")
            return False
            
        self.running = True
        self.paused = False
        self.change_history = []
        
        # Capture initial frame as reference if none exists
        if self.reference_frame is None:
            self.capture_reference()
            
        self.previous_frame = self.reference_frame
        
        self.detection_thread = threading.Thread(target=self._detection_loop)
        self.detection_thread.daemon = True
        self.detection_thread.start()
        
        return True
    
    def stop_detection(self):
        """Stop detection thread"""
        self.running = False
        
    def _detection_loop(self):
        """Main detection loop"""
        self.log("Starting detection loop")
        
        # Initialize performance tracking
        frame_counter = 0
        fps_counter = 0
        fps_timer = time.time()
        
        # Track consecutive detections to filter false positives
        detection_intensity = 0  # Used to track detection confidence
        
        while self.running:
            try:
                # Check if paused
                if self.paused:
                    time.sleep(0.1)
                    continue
                    
                # Capture current frame
                self.current_frame = self.capture_screen()
                
                if self.current_frame is None:
                    time.sleep(0.1)
                    continue
                    
                # Use reference frame if available, otherwise use previous frame
                compare_frame = self.reference_frame if self.reference_frame is not None else self.previous_frame
                
                if compare_frame is None:
                    self.capture_reference()
                    time.sleep(0.1)
                    continue
                
                # Calculate difference
                self.diff_frame, change_percent = self.calculate_frame_difference(self.current_frame, compare_frame)
                
                # Store in history
                self.change_history.append(change_percent)
                if len(self.change_history) > 100:
                    self.change_history = self.change_history[-100:]
                
                # Check for detection with cooldown
                current_time = time.time()
                cooldown_passed = (current_time - self.last_detection_time) > self.detection_cooldown
                
                # Calculate triggering threshold with hysteresis
                # Use higher threshold for isolated frames to avoid false positives
                # Use lower threshold for consecutive detections
                trigger_threshold = self.THRESHOLD * (1.0 - min(detection_intensity / 10.0, 0.5))
                
                if change_percent > trigger_threshold:
                    # Increase detection confidence
                    detection_intensity = min(detection_intensity + 1, 10)
                    
                    # Check if we should trigger action sequence
                    if detection_intensity >= 3 and cooldown_passed:  # Require at least 3 consecutive detections
                        change_percent_display = round(change_percent * 100, 2)
                        self.log(f"Major pixel change detected! Change: {change_percent_display}% (Confidence: {detection_intensity}/10)")
                        self.last_detection_time = current_time
                        
                        # Reset detection intensity after triggering
                        detection_intensity = 0
                        
                        # Update stats
                        self.stats["total_detections"] += 1
                        
                        # Calculate interval since last detection
                        if self.stats["last_detection_time"] > 0:
                            interval = current_time - self.stats["last_detection_time"]
                            # Update average detection interval using moving average
                            if self.stats["avg_detection_interval"] == 0:
                                self.stats["avg_detection_interval"] = interval
                            else:
                                self.stats["avg_detection_interval"] = (
                                    0.8 * self.stats["avg_detection_interval"] + 0.2 * interval
                                )
                        self.stats["last_detection_time"] = current_time
                        
                        # Emit the detection signal
                        self.detection_signal.emit()
                        
                        # Handle the detection with fishing sequence
                        self._handle_detection()
                else:
                    # Gradually decrease detection confidence
                    detection_intensity = max(detection_intensity - 0.5, 0)
                    
                # Store current frame as previous for next comparison if not using reference
                if self.reference_frame is None:
                    self.previous_frame = self.current_frame
                
                # Update performance metrics
                frame_counter += 1
                fps_counter += 1
                if time.time() - fps_timer >= 1.0:
                    fps = fps_counter
                    fps_counter = 0
                    fps_timer = time.time()
                    
                    # Update performance metrics
                    if hasattr(self, 'performance'):
                        self.performance["fps"] = fps
                        self.performance["processing_samples"] += 1
                        if self.performance["processing_samples"] > 100:
                            self.performance["processing_samples"] = 1
                
                # Sleep to control capture rate - use adaptive timing based on performance
                sleep_time = max(0.01, self.capture_interval)  # Minimum 10ms sleep
                time.sleep(sleep_time)
                
            except Exception as e:
                self.log(f"Error in detection loop: {e}")
                traceback.print_exc()
                time.sleep(0.1)  # Short delay on error
                # Reset detection intensity on errors
                detection_intensity = 0
        
        # Thread is exiting
        self.log("Detection thread exiting")
        self.running = False
        
    def _handle_detection(self):
        """Handle detection event with optimized sequence"""
        try:
            # STEP 1: Press fishing key to catch fish
            self.log("STEP 1: Catching fish...")
            success = False
            
            # Try up to 3 times to press fishing key
            for attempt in range(3):
                if self.focus_play_together_window():
                    self.log(f"Pressing {self.fishing_key.upper()} key to catch fish (attempt {attempt+1})")
                    if self.send_fishing_key():
                        success = True
                        break
                    time.sleep(0.2)
                else:
                    self.log(f"Failed to focus window, retrying ({attempt+1}/3)")
                    time.sleep(0.1)
            
            if not success:
                self.log("Failed to send fishing key after multiple attempts")
            
            # STEP 2: Wait for cooldown period
            cooldown = self.detection_cooldown
            self.log(f"STEP 2: Pausing for {cooldown:.1f} seconds...")
            
            # Update UI with countdown
            pause_start = time.time()
            pause_end = pause_start + cooldown
            
            while time.time() < pause_end and self.running and not self.thread_control.get("stop_requested", False):
                remaining = int(pause_end - time.time())
                if self.parent:
                    QTimer.singleShot(0, lambda r=remaining: self.parent.status_label.setText(f"Paused ({r}s)"))
                time.sleep(0.1)
            
            # STEP 3: Exit fishing menu with ESC key
            if self.running and not self.thread_control.get("stop_requested", False):
                self.log("STEP 3: Exiting fishing menu...")
                success = False
                
                # Try up to 3 times to press ESC key
                for attempt in range(3):
                    if self.focus_play_together_window():
                        self.log(f"Pressing ESC key (attempt {attempt+1})")
                        if self.send_esc_key():
                            success = True
                            break
                        time.sleep(0.2)
                    else:
                        self.log(f"Failed to focus window for ESC key, retrying ({attempt+1}/3)")
                        time.sleep(0.1)
                
                if not success:
                    self.log("Failed to send ESC key after multiple attempts")
            
            # STEP 4: Wait briefly for menu to close
            self.log("STEP 4: Waiting for menu to close...")
            menu_close_time = 2.0  # Wait 2 seconds for menu to close
            menu_close_end = time.time() + menu_close_time
            
            while time.time() < menu_close_end and self.running and not self.thread_control.get("stop_requested", False):
                time.sleep(0.1)
            
            # STEP 5: Cast fishing line again
            if self.running and not self.thread_control.get("stop_requested", False):
                self.log("STEP 5: Casting fishing line again...")
                success = False
                
                # Try up to 3 times to cast fishing line
                for attempt in range(3):
                    if self.focus_play_together_window():
                        self.log(f"Casting fishing line with {self.fishing_key.upper()} key (attempt {attempt+1})")
                        if self.send_fishing_key():
                            success = True
                            break
                        time.sleep(0.2)
                    else:
                        self.log(f"Failed to focus window for casting, retrying ({attempt+1}/3)")
                        time.sleep(0.1)
                
                if not success:
                    self.log("Failed to cast fishing line after multiple attempts")
                
                # Wait for screen to update after casting
                self.log("Waiting for screen to update after casting...")
                time.sleep(2)
                
                # Capture new reference frame
                self.log("Capturing new reference frame...")
                self.capture_reference()
                self.log("New reference frame captured after casting")
            
            # STEP 6: Resume monitoring
            if self.parent and self.running and not self.thread_control.get("stop_requested", False):
                self.log("STEP 6: Resuming monitoring...")
                QTimer.singleShot(0, lambda: self.parent.status_label.setText("Running - Monitoring for changes"))
            
            # STEP 7: Stabilization pause
            self.log("STEP 7: Short stabilization pause...")
            stabilize_time = min(1.5, self.detection_cooldown * 0.15)
            time.sleep(stabilize_time)
            
            self.log("Action sequence completed successfully")
            
        except Exception as e:
            self.log(f"Error during action sequence: {e}")
            traceback.print_exc()
            # Try to recover by updating status and capturing new reference
            if self.running and not self.thread_control.get("stop_requested", False):
                if self.parent:
                    QTimer.singleShot(0, lambda: self.parent.status_label.setText("Running - Monitoring after error"))
                # Try to capture new reference frame to recover
                try:
                    self.capture_reference()
                    self.log("Captured recovery reference frame")
                except:
                    pass
    
    def send_fishing_key(self):
        """Send the configured fishing key to the game window"""
        try:
            # Focus window for reliable key press detection
            if user32.GetForegroundWindow() != self.play_together_window:
                self.focus_play_together_window()
                time.sleep(0.05)  # Short delay
            
            # Method 1: Use keyboard library
            keyboard.press_and_release(self.fishing_key)
            time.sleep(0.05)
            
            # Method 2: Use direct virtual key code
            vk_code = ord(self.fishing_key.upper())
            win32api.keybd_event(vk_code, 0, 0, 0)  # key down
            time.sleep(0.05)
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)  # key up
            
            # Method 3: Send message to window
            win32gui.PostMessage(self.play_together_window, win32con.WM_KEYDOWN, vk_code, 0)
            time.sleep(0.05)
            win32gui.PostMessage(self.play_together_window, win32con.WM_KEYUP, vk_code, 0)
            
            self.log(f"Fishing key '{self.fishing_key}' sent via multiple methods")
            return True
        except Exception as e:
            self.log(f"Error sending fishing key: {e}")
            return False
            
    def send_esc_key(self):
        """Send ESC key to the game window"""
        try:
            # Focus window for reliable key press detection
            if user32.GetForegroundWindow() != self.play_together_window:
                self.focus_play_together_window()
                time.sleep(0.05)  # Short delay
            
            # Method 1: Use keyboard library
            keyboard.press_and_release('esc')
            time.sleep(0.05)
            
            # Method 2: Use virtual key code
            vk_code = 0x1B  # VK_ESCAPE
            win32api.keybd_event(vk_code, 0, 0, 0)  # key down
            time.sleep(0.05)
            win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)  # key up
            
            # Method 3: Send message to window
            win32gui.PostMessage(self.play_together_window, win32con.WM_KEYDOWN, vk_code, 0)
            time.sleep(0.05)
            win32gui.PostMessage(self.play_together_window, win32con.WM_KEYUP, vk_code, 0)
            
            self.log("ESC key sent via multiple methods")
            return True
        except Exception as e:
            self.log(f"Error sending ESC key: {e}")
            return False
    
    def focus_play_together_window(self):
        """Focus the Play Together window using multiple aggressive methods"""
        try:
            if not self.play_together_window:
                self.find_play_together_process()
                if not self.play_together_window:
                    self.log("Cannot focus window: Play Together window not found")
                    return False
                    
            # Check if window exists
            if not win32gui.IsWindow(self.play_together_window):
                self.log("Window no longer exists, trying to find it again")
                self.find_play_together_process()
                if not self.play_together_window:
                    return False
            
            # Method 1: Standard SetForegroundWindow
            current_hwnd = user32.GetForegroundWindow()
            if current_hwnd == self.play_together_window:
                return True  # Already in focus
                
            # Try standard approach first
            result = user32.SetForegroundWindow(self.play_together_window)
            
            # Method 2: Try AttachThreadInput approach
            if not result:
                foreground_thread = user32.GetWindowThreadProcessId(current_hwnd, None)
                target_thread = user32.GetWindowThreadProcessId(self.play_together_window, None)
                
                if foreground_thread != target_thread:
                    user32.AttachThreadInput(foreground_thread, target_thread, True)
                    result = user32.SetForegroundWindow(self.play_together_window)
                    user32.AttachThreadInput(foreground_thread, target_thread, False)
            
            # Method 3: Try BringWindowToTop and show window
            if not result:
                user32.ShowWindow(self.play_together_window, win32con.SW_RESTORE)
                user32.BringWindowToTop(self.play_together_window)
                user32.SetForegroundWindow(self.play_together_window)
            
            # Method 4: Use SetWindowPos with TOPMOST flag
            if not result:
                user32.SetWindowPos(
                    self.play_together_window,
                    HWND_TOPMOST,
                    0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
                )
                # Then set back to non-topmost to avoid staying always on top
                user32.SetWindowPos(
                    self.play_together_window,
                    win32con.HWND_NOTOPMOST,
                    0, 0, 0, 0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
                )
            
            # Final check if focus was achieved
            time.sleep(0.05)  # Short delay to let OS update window state
            focused_hwnd = user32.GetForegroundWindow()
            success = focused_hwnd == self.play_together_window
            
            if success:
                self.log("Successfully focused Play Together window")
            else:
                self.log(f"Warning: Failed to focus Play Together window (current focus: {focused_hwnd})")
                
            return success
            
        except Exception as e:
            self.log(f"Error focusing window: {e}")
            return False

# Main application class
class SimpleAutoFisherGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"AutoFisher Qt v{VERSION} - {VERSION_NAME}")
        self.setMinimumSize(700, 500)
        
        # Create message queue for logging
        self.log_queue = queue.Queue()
        
        # Create detector first so it's available for region selection
        self.detector = PixelChangeDetector(self)
        # Connect the detection signal to increment detection count
        self.detector.detection_signal.connect(self.increment_detection_count)
        
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
        
        # Configure logs update timer - add this to update logs every 100ms
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
        # Main central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout using splitter for adjustable sections
        main_layout = QVBoxLayout(central_widget)
        
        # Create splitter for top and bottom sections
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(self.main_splitter)
        
        # Top container
        top_container = QWidget()
        top_layout = QHBoxLayout(top_container)
        
        # Left panel for settings and controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(350)  # Limit width of left panel
        
        # Right panel for status and visualization
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Add panels to top container
        top_layout.addWidget(left_panel, 1)
        top_layout.addWidget(right_panel, 2)  # Give more space to right panel
        
        # Bottom container for logs
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        
        # Add containers to splitter
        self.main_splitter.addWidget(top_container)
        self.main_splitter.addWidget(bottom_container)
        self.main_splitter.setSizes([350, 150])  # Initial size distribution
        
        # Create settings group in left panel
        settings_group = QGroupBox("Settings")
        settings_layout = QGridLayout(settings_group)
        
        # Threshold
        settings_layout.addWidget(QLabel("Threshold:"), 0, 0)
        threshold_layout = QHBoxLayout()
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setMinimum(1)
        self.threshold_slider.setMaximum(50)
        self.threshold_slider.setValue(5)  # Default value of 0.05
        self.threshold_slider.valueChanged.connect(self.update_threshold_label)
        threshold_layout.addWidget(self.threshold_slider)
        
        self.threshold_label = QLabel("0.05")
        threshold_layout.addWidget(self.threshold_label)
        settings_layout.addLayout(threshold_layout, 0, 1)
        
        # Region Size
        settings_layout.addWidget(QLabel("Region Size:"), 1, 0)
        region_size_layout = QHBoxLayout()
        self.size_entry = QLineEdit("50")
        self.size_entry.setMaximumWidth(60)
        region_size_layout.addWidget(self.size_entry)
        region_size_layout.addWidget(QLabel("px"))
        region_size_layout.addStretch()
        settings_layout.addLayout(region_size_layout, 1, 1)
        
        # Cooldown
        settings_layout.addWidget(QLabel("Cooldown:"), 2, 0)
        cooldown_layout = QHBoxLayout()
        self.cooldown_entry = QLineEdit("5.0")
        self.cooldown_entry.setMaximumWidth(60)
        cooldown_layout.addWidget(self.cooldown_entry)
        cooldown_layout.addWidget(QLabel("sec"))
        cooldown_layout.addStretch()
        settings_layout.addLayout(cooldown_layout, 2, 1)
        
        # Fishing Key
        settings_layout.addWidget(QLabel("Fishing Key:"), 3, 0)
        fishing_key_layout = QHBoxLayout()
        self.fishing_key_entry = QLineEdit("f")
        self.fishing_key_entry.setMaximumWidth(40)
        fishing_key_layout.addWidget(self.fishing_key_entry)
        
        self.apply_button = QPushButton("Apply Settings")
        self.apply_button.clicked.connect(self.apply_settings)
        fishing_key_layout.addWidget(self.apply_button)
        settings_layout.addLayout(fishing_key_layout, 3, 1)
        
        # Advanced Options
        options_frame = QFrame()
        options_layout = QVBoxLayout(options_frame)
        options_layout.setContentsMargins(0, 10, 0, 0)
        
        # High Performance Mode
        self.high_performance_checkbox = QCheckBox("High Performance Mode (uses more CPU)")
        self.high_performance_checkbox.setChecked(self.detector.high_performance_mode)
        self.high_performance_checkbox.stateChanged.connect(self.update_high_performance)
        options_layout.addWidget(self.high_performance_checkbox)
        
        # Add description
        hp_desc = QLabel("Increases reliability using more system resources")
        hp_desc.setStyleSheet("color: gray; font-size: 10px;")
        options_layout.addWidget(hp_desc)
        
        # Respect Fullscreen Apps
        self.respect_fullscreen_checkbox = QCheckBox("Respect Fullscreen Apps (prevents interruptions)")
        self.respect_fullscreen_checkbox.setChecked(self.detector.respect_fullscreen)
        self.respect_fullscreen_checkbox.stateChanged.connect(self.update_respect_fullscreen)
        options_layout.addWidget(self.respect_fullscreen_checkbox)
        
        # Add description
        fs_desc = QLabel("Prevents interruption when other fullscreen applications are active")
        fs_desc.setStyleSheet("color: gray; font-size: 10px;")
        options_layout.addWidget(fs_desc)
        
        # Direct Control Mode
        self.direct_control_checkbox = QCheckBox("Direct Control Mode (recommended)")
        self.direct_control_checkbox.setChecked(self.detector.direct_control)
        self.direct_control_checkbox.stateChanged.connect(self.update_direct_control)
        options_layout.addWidget(self.direct_control_checkbox)
        
        # Add description
        dc_desc = QLabel("Uses direct input methods for maximum reliability")
        dc_desc.setStyleSheet("color: gray; font-size: 10px;")
        options_layout.addWidget(dc_desc)
        
        settings_layout.addWidget(options_frame, 4, 0, 1, 2)
        
        left_layout.addWidget(settings_group)
        
        # Control buttons
        control_group = QGroupBox("Control")
        control_layout = QGridLayout(control_group)
        
        # Region selection button
        self.region_button = QPushButton("Select Region")
        self.region_button.clicked.connect(self.select_region)
        control_layout.addWidget(self.region_button, 0, 0)
        
        # Start button
        self.start_button = QPushButton("Start")
        self.start_button.clicked.connect(self.start_detection)
        control_layout.addWidget(self.start_button, 1, 0)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_detection)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button, 0, 1)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.toggle_pause)
        self.pause_button.setEnabled(False)
        control_layout.addWidget(self.pause_button, 0, 2)
        
        # Second row of buttons
        self.ref_button = QPushButton("Capture Reference")
        self.ref_button.clicked.connect(self.capture_reference)
        control_layout.addWidget(self.ref_button, 1, 1, 1, 2)
        
        self.clear_logs_button = QPushButton("Clear Logs")
        self.clear_logs_button.clicked.connect(self.clear_logs)
        control_layout.addWidget(self.clear_logs_button, 1, 2, 1, 2)
        
        left_layout.addWidget(control_group)
        
        # Status and Statistics in left panel
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        
        self.status_label = QLabel("Ready - Select a region to begin")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        # Add a separator line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        status_layout.addWidget(separator)
        
        # Statistics grid
        stats_frame = QFrame()
        stats_layout = QGridLayout(stats_frame)
        stats_layout.setContentsMargins(0, 5, 0, 0)
        
        # Create statistics labels
        self.stats_labels = {}
        stats_items = [
            ("Detections", "total_detections"),
            ("Session Runtime", "session_runtime"),
            ("Detection Rate", "detections_per_hour"),
            ("Avg. Interval", "avg_interval"),
            ("Processing FPS", "processing_fps"),
            ("Threshold", "current_threshold"),
            ("Cooldown", "cooldown"),
            ("Key Mapping", "key_mapping")
        ]
        
        # Create grid of stats
        for i, (label, key) in enumerate(stats_items):
            row = i // 2
            col = i % 2
            
            # Label widget
            label_widget = QLabel(f"{label}:")
            stats_layout.addWidget(label_widget, row, col*2)
            
            # Value widget
            value_widget = QLabel("...")
            stats_layout.addWidget(value_widget, row, col*2+1)
            self.stats_labels[key] = value_widget
        
        status_layout.addWidget(stats_frame)
        left_layout.addWidget(status_group)
        
        # Region info display
        region_group = QGroupBox("Region Information")
        region_layout = QVBoxLayout(region_group)
        
        self.region_info_label = QLabel("No region selected")
        region_layout.addWidget(self.region_info_label)
        
        left_layout.addWidget(region_group)
        
        # Add spacer to left panel
        left_layout.addStretch()
        
        # Add visualization panel to right panel
        viz_group = QGroupBox("Monitoring")
        viz_layout = QVBoxLayout(viz_group)
        
        # Create a frame to contain the canvas with fixed aspect ratio
        viz_frame = QFrame()
        viz_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        viz_frame.setLineWidth(1)
        viz_frame.setStyleSheet("background-color: #232323; border: 1px solid #444;")
        
        # Use a layout that maintains the aspect ratio
        viz_frame_layout = QVBoxLayout(viz_frame)
        viz_frame_layout.setContentsMargins(4, 4, 4, 4)
        
        # Create matplotlib canvas for visualization with the correct aspect ratio (1.5:1)
        self.viz_canvas = MatplotlibCanvas(self, width=6, height=4, dpi=100, bg_color='#232323')
        
        # Add the canvas to the frame
        viz_frame_layout.addWidget(self.viz_canvas)
        
        # Add the frame to the main viz layout
        viz_layout.addWidget(viz_frame)
        
        # Add monitoring status indicators
        status_panel = QFrame()
        status_layout = QHBoxLayout(status_panel)
        status_layout.setContentsMargins(0, 4, 0, 0)
        
        # Add threshold indicator
        threshold_label = QLabel("Threshold:")
        threshold_label.setStyleSheet("color: #AAA; font-size: 9pt;")
        status_layout.addWidget(threshold_label)
        
        self.monitor_threshold = QLabel("0.05")
        self.monitor_threshold.setStyleSheet("color: #FF6961; font-weight: bold; font-size: 9pt;")
        status_layout.addWidget(self.monitor_threshold)
        
        status_layout.addStretch()
        
        # Add FPS indicator
        fps_label = QLabel("FPS:")
        fps_label.setStyleSheet("color: #AAA; font-size: 9pt;")
        status_layout.addWidget(fps_label)
        
        self.monitor_fps = QLabel("0")
        self.monitor_fps.setStyleSheet("color: #77DD77; font-weight: bold; font-size: 9pt;")
        status_layout.addWidget(self.monitor_fps)
        
        # Add the status panel to the viz layout
        viz_layout.addWidget(status_panel)
        
        right_layout.addWidget(viz_group)
        
        # Log console in bottom container
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        
        # Create log console with improved styling
        self.log_console = QTextEdit()
        self.log_console.setReadOnly(True)
        self.log_console.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #E0E0E0;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 10pt;
                border: 1px solid #333333;
                border-radius: 3px;
                padding: 5px;
            }
        """)
        log_layout.addWidget(self.log_console)
        
        # Add log control panel with clear button
        log_control_panel = QFrame()
        log_control_layout = QHBoxLayout(log_control_panel)
        log_control_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add spacer to push button to the right
        log_control_layout.addStretch()
        
        # Add clear button
        clear_log_button = QPushButton("Clear Logs")
        clear_log_button.setMaximumWidth(100)
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
                    
                # Apply style to make logs more readable
                self.log_console.setStyleSheet("""
                    QTextEdit {
                        background-color: #1E1E1E; 
                        color: #E0E0E0; 
                        font-family: Consolas, 'Courier New', monospace; 
                        font-size: 10pt;
                    }
                """)
                
                # Autoscroll only if we were already at the bottom
                if autoscroll:
                    self.log_console.verticalScrollBar().setValue(
                        self.log_console.verticalScrollBar().maximum()
                    )
        except Exception as e:
            # Emergency logging if the normal logging system fails
            print(f"Error updating logs: {e}")
            traceback.print_exc()
            
    def clear_logs(self):
        """Clear the log console"""
        self.log_console.clear()
        self.log("Logs cleared")
            
    def update_threshold_label(self, value):
        """Update threshold label"""
        threshold_value = value / 100.0
        self.threshold_label.setText(f"{threshold_value:.2f}")
        
    # Background mode removed
            
    def update_high_performance(self):
        """Update high performance mode setting"""
        self.detector.high_performance_mode = self.high_performance_checkbox.isChecked()
        if self.detector:
            self.detector.high_performance_mode = self.high_performance_checkbox.isChecked()
            mode = "enabled" if self.detector.high_performance_mode else "disabled"
            self.log(f"High performance mode {mode}")
            if self.detector.high_performance_mode:
                self.log("Warning: High performance mode may increase CPU usage")
                
    def update_respect_fullscreen(self):
        """Update respect fullscreen setting"""
        self.detector.respect_fullscreen = self.respect_fullscreen_checkbox.isChecked()
        if self.detector:
            self.detector.respect_fullscreen = self.respect_fullscreen_checkbox.isChecked()
            mode = "enabled" if self.detector.respect_fullscreen else "disabled"
            self.log(f"Fullscreen respect mode {mode}")
            if self.detector.respect_fullscreen:
                self.log("Fishing won't interrupt fullscreen applications")
            
    def update_direct_control(self):
        """Update direct control mode setting"""
        self.detector.direct_control = self.direct_control_checkbox.isChecked()
        if self.detector:
            self.detector.direct_control = self.direct_control_checkbox.isChecked()
            mode = "enabled" if self.detector.direct_control else "disabled"
            self.log(f"Direct control mode {mode}")
            if self.detector.direct_control:
                self.log("Warning: Direct control mode may reduce detection accuracy")
                
    def apply_settings(self):
        """Apply the settings to the detector"""
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
                old_threshold = self.detector.THRESHOLD if hasattr(self.detector, 'THRESHOLD') else 0
                old_cooldown = self.detector.detection_cooldown if hasattr(self.detector, 'detection_cooldown') else 0
                
                self.detector.THRESHOLD = threshold_value
                self.detector.detection_cooldown = cooldown_value
                self.detector.fishing_key = fishing_key
                self.detector.high_performance_mode = self.high_performance_checkbox.isChecked()
                self.detector.respect_fullscreen = self.respect_fullscreen_checkbox.isChecked()
                self.detector.direct_control = self.direct_control_checkbox.isChecked()
                
                high_perf_status = "enabled" if self.detector.high_performance_mode else "disabled"
                fullscreen_status = "enabled" if self.detector.respect_fullscreen else "disabled"
                direct_control_status = "enabled" if self.detector.direct_control else "disabled"
                
                self.log(f"Settings applied: threshold={threshold_value:.2f}, cooldown={cooldown_value}s, key={fishing_key}, high_perf={high_perf_status}, respect_fullscreen={fullscreen_status}, direct_control={direct_control_status}")
                
                # Log changes
                if old_threshold != threshold_value:
                    self.log(f"Threshold changed: {old_threshold:.2f} -> {threshold_value:.2f}")
                    
                if old_cooldown != cooldown_value:
                    self.log(f"Cooldown changed: {old_cooldown}s -> {cooldown_value}s")
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
        """
        Allow the user to select a region of the screen to monitor within the Play Together window
        """
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
            
        if not self.detector.find_play_together_process():
            self.log("Cannot start region selection: Play Together window not found")
            QMessageBox.warning(self, "Game Window Not Found", 
                                "Could not find the Play Together game window.\n"
                                "Please make sure the game is running before selecting a region.")
            return False
            
        # Get window position and size
        try:
            window_rect = win32gui.GetWindowRect(self.detector.play_together_window)
            win_left, win_top, win_right, win_bottom = window_rect
            win_width = win_right - win_left
            win_height = win_bottom - win_top
            
            # Get the client area (actual game content area)
            client_rect = win32gui.GetClientRect(self.detector.play_together_window)
            client_left, client_top, client_right, client_bottom = client_rect
            
            # Convert client coordinates to screen coordinates
            client_left, client_top = win32gui.ClientToScreen(self.detector.play_together_window, (client_left, client_top))
            client_right, client_bottom = win32gui.ClientToScreen(self.detector.play_together_window, (client_right, client_bottom))
            
            # Use client area dimensions for more accurate game content area
            game_width = client_right - client_left
            game_height = client_bottom - client_top
            
            self.log(f"Game window found: {win_width}x{win_height} at ({win_left},{win_top})")
            self.log(f"Game content area: {game_width}x{game_height} at ({client_left},{client_top})")
        except Exception as e:
            self.log(f"Error getting window dimensions: {e}")
            return
        
        # Calculate region dimensions based on 1.5:1 ratio
        width = int(size * 1.5)
        height = size
        
        # Temporarily minimize our own window
        self.hide()
        time.sleep(0.5)  # Give time for window to minimize
        
        # Create a transparent window for selection that matches the game window exactly
        selection_window = QWidget(None, Qt.WindowType.FramelessWindowHint | 
                                  Qt.WindowType.WindowStaysOnTopHint | 
                                  Qt.WindowType.Tool)
        selection_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        selection_window.setGeometry(client_left, client_top, game_width, game_height)
        
        # Create a custom widget for drawing
        class SelectionCanvas(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setMouseTracking(True)
                self.setGeometry(0, 0, game_width, game_height)
                self.current_x = game_width // 2
                self.current_y = game_height // 2
                self.box_width = width
                self.box_height = height
                self.client_left = client_left
                self.client_top = client_top
                self.preview_rect = None
                self.outline_rect = None
                self.grid_lines = []
                self.info_text = None
                
                # Colors for a clean, sleek interface
                self.colors = {
                    'bg_dark': QColor(0, 0, 0, 40),               # More transparent background
                    'accent': QColor(87, 207, 255, 220),           # Bright cyan blue
                    'highlight': QColor(255, 255, 255, 180),       # White with transparency
                    'text': QColor(255, 255, 255, 255),            # Pure white text
                    'text_shadow': QColor(0, 0, 0, 180),           # Text shadow
                    'grid': QColor(87, 207, 255, 80),              # Light grid lines
                    'target': QColor(255, 255, 100, 220),          # Yellow targeting color
                    'border': QColor(87, 207, 255, 180),           # Border blue
                    'header_bg': QColor(40, 40, 40, 200),          # Dark header background
                    'preview_border': QColor(255, 255, 255, 100)   # Preview area border
                }
                
                # Start a timer to track cursor position with higher frequency
                self.cursor_timer = QTimer(self)
                self.cursor_timer.setInterval(5)  # 5ms for smoother tracking
                self.cursor_timer.timeout.connect(self.track_cursor)
                self.cursor_timer.start()
                
                # For preview image
                self.preview_pixmap = None
                self.preview_timer = QTimer(self)
                self.preview_timer.setInterval(100)  # Update preview 10 times per second
                self.preview_timer.timeout.connect(self.update_preview)
                self.preview_timer.start()
                
                # For pulsing animation effect
                self.pulse_timer = QTimer(self)
                self.pulse_timer.setInterval(20)
                self.pulse_alpha = 0
                self.pulse_increasing = True
                self.pulse_timer.timeout.connect(self.update_pulse)
                self.pulse_timer.start()
                
            def update_pulse(self):
                """Create a pulsing animation effect"""
                if self.pulse_increasing:
                    self.pulse_alpha += 3
                    if self.pulse_alpha >= 100:
                        self.pulse_increasing = False
                else:
                    self.pulse_alpha -= 3
                    if self.pulse_alpha <= 20:
                        self.pulse_increasing = True
                self.update()
            
            def track_cursor(self):
                """Track the cursor position in global screen coordinates"""
                global_pos = QCursor.pos()
                
                # Check if cursor is within the game window bounds
                if (global_pos.x() >= self.client_left and 
                    global_pos.x() < self.client_left + game_width and
                    global_pos.y() >= self.client_top and 
                    global_pos.y() < self.client_top + game_height):
                    
                    # Convert global position to widget-local position
                    self.current_x = global_pos.x() - self.client_left
                    self.current_y = global_pos.y() - self.client_top
                
                # Always update to ensure the box follows cursor movement
                self.update()
            
            def update_preview(self):
                """Update the preview image of the current selection"""
                # Calculate box coordinates centered on cursor position
                left = self.current_x - self.box_width // 2
                top = self.current_y - self.box_height // 2
                right = left + self.box_width
                bottom = top + self.box_height
                
                # Ensure box stays within screen bounds
                if left < 0:
                    left = 0
                    right = self.box_width
                elif right > game_width:
                    right = game_width
                    left = right - self.box_width
                    
                if top < 0:
                    top = 0
                    bottom = self.box_height
                elif bottom > game_height:
                    bottom = game_height
                    top = bottom - self.box_height
                
                try:
                    # Calculate absolute screen coordinates for capture
                    abs_left = self.client_left + left
                    abs_top = self.client_top + top
                    abs_right = abs_left + (right - left)
                    abs_bottom = abs_top + (bottom - top)
                    
                    # Capture the current selection using QScreen
                    screen = QApplication.primaryScreen()
                    self.preview_pixmap = screen.grabWindow(
                        0,  # Capture entire screen
                        abs_left, abs_top,
                        abs_right - abs_left, abs_bottom - abs_top
                    )
                except Exception as e:
                    print(f"Error updating preview: {e}")
                
                self.update()  # Request a repaint
            
            def paintEvent(self, event):
                painter = QPainter(self)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                
                # Draw a very transparent background
                painter.fillRect(self.rect(), self.colors['bg_dark'])
                
                # Calculate box coordinates centered on cursor position
                left = self.current_x - self.box_width // 2
                top = self.current_y - self.box_height // 2
                right = left + self.box_width
                bottom = top + self.box_height
                
                # Ensure box stays within screen bounds
                if left < 0:
                    left = 0
                    right = self.box_width
                elif right > game_width:
                    right = game_width
                    left = right - self.box_width
                    
                if top < 0:
                    top = 0
                    bottom = self.box_height
                elif bottom > game_height:
                    bottom = game_height
                    top = bottom - self.box_height
                
                # Draw subtle guides (crosshair)
                painter.setPen(QPen(self.colors['grid'], 1, Qt.PenStyle.DashLine))
                painter.drawLine(self.current_x, 0, self.current_x, self.height())
                painter.drawLine(0, self.current_y, self.width(), self.current_y)
                
                # Draw selection box with glowing effect
                # Outer glow
                glow_size = 3
                for i in range(glow_size, 0, -1):
                    glow_color = QColor(self.colors['accent'])
                    glow_color.setAlpha(40 + (180//glow_size)*i)
                    painter.setPen(QPen(glow_color, i))
                    painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                    painter.drawRect(left-i, top-i, (right-left)+(i*2), (bottom-top)+(i*2))
                
                # Main border (crisp)
                painter.setPen(QPen(self.colors['accent'], 2, Qt.PenStyle.SolidLine))
                painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                painter.drawRect(left, top, right-left, bottom-top)
                
                # Very subtle fill
                fill_color = QColor(self.colors['accent'])
                fill_color.setAlpha(10 + self.pulse_alpha//4)
                painter.setBrush(QBrush(fill_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(left, top, right-left, bottom-top)
                
                # Add subtle grid lines
                cell_width = self.box_width // 3
                cell_height = self.box_height // 3
                
                grid_color = QColor(self.colors['grid'])
                grid_color.setAlpha(60)
                painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DotLine))
                
                # Vertical grid lines
                for i in range(1, 3):
                    painter.drawLine(left + i * cell_width, top, left + i * cell_width, bottom)
                    
                # Horizontal grid lines
                for i in range(1, 3):
                    painter.drawLine(left, top + i * cell_height, right, top + i * cell_height)
                
                # Create an elegant targeting element at center
                center_x = left + self.box_width // 2
                center_y = top + self.box_height // 2
                center_size = min(self.box_width, self.box_height) // 8
                
                # Pulsing target circle
                target_color = QColor(self.colors['target'])
                target_color.setAlpha(100 + self.pulse_alpha)
                
                # Outer targeting circle
                painter.setPen(QPen(target_color, 2))
                painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                painter.drawEllipse(center_x - center_size, center_y - center_size, 
                                   center_size*2, center_size*2)
                
                # Inner targeting circle
                painter.setPen(QPen(self.colors['target'], 1))
                painter.drawEllipse(center_x - center_size//2, center_y - center_size//2, 
                                   center_size, center_size)
                
                # Draw crosshair lines
                painter.setPen(QPen(target_color, 1, Qt.PenStyle.SolidLine))
                # Horizontal line
                painter.drawLine(int(center_x - center_size*1.5), int(center_y), 
                                int(center_x - center_size//2), int(center_y))
                painter.drawLine(int(center_x + center_size//2), int(center_y),
                                int(center_x + center_size*1.5), int(center_y))
                # Vertical line
                painter.drawLine(int(center_x), int(center_y - center_size*1.5),
                                int(center_x), int(center_y - center_size//2))
                painter.drawLine(int(center_x), int(center_y + center_size//2),
                                int(center_x), int(center_y + center_size*1.5))
                
                # Draw center dot
                painter.setBrush(QBrush(target_color))
                painter.drawEllipse(center_x-2, center_y-2, 4, 4)
                
                # Create modern header bar
                header_height = 36
                header_rect = QRect(0, 0, game_width, header_height)
                painter.fillRect(header_rect, self.colors['header_bg'])
                
                # Draw header text with shadow
                font = QFont("Segoe UI", 10)
                font.setBold(True)
                painter.setFont(font)
                
                header_text = "POSITION OVER FISHING BOBBER • CLICK TO SELECT • ESC TO CANCEL"
                
                # Draw text shadow
                painter.setPen(QPen(self.colors['text_shadow']))
                painter.drawText(QRect(1, 1, game_width, header_height), 
                                Qt.AlignmentFlag.AlignCenter, header_text)
                
                # Draw actual text
                painter.setPen(QPen(self.colors['highlight']))
                painter.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, header_text)
                
                # Add size info under header
                size_rect = QRect(0, header_height, game_width, 20)
                font.setPointSize(9)
                font.setBold(False)
                painter.setFont(font)
                
                detail_text = f"Selection size: {self.box_height}×{self.box_width} pixels • Center the target on the bobber"
                painter.drawText(size_rect, Qt.AlignmentFlag.AlignCenter, detail_text)
                
                # Draw elegant position indicator at bottom
                # Convert to absolute screen coordinates
                abs_left = self.client_left + left
                abs_top = self.client_top + top
                
                # Create bottom status bar with dark background
                status_height = 26
                status_rect = QRect(0, game_height - status_height, game_width, status_height)
                painter.fillRect(status_rect, self.colors['header_bg'])
                
                # Format position text
                coord_text = f"Position: ({abs_left},{abs_top}) • Size: {self.box_width}×{self.box_height}"
                
                # Draw text with shadow
                font.setBold(True)
                font.setPointSize(9)
                painter.setFont(font)
                painter.setPen(QPen(self.colors['text_shadow']))
                painter.drawText(QRect(1, game_height - status_height + 1, game_width, status_height), 
                                Qt.AlignmentFlag.AlignCenter, coord_text)
                
                painter.setPen(QPen(self.colors['text']))
                painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, coord_text)
                
                # Draw preview box with elegant styling
                if self.preview_pixmap:
                    preview_size = 160  # Preview size
                    preview_margin = 12
                    
                    # Create rounded preview container with QRectF instead of QRect
                    preview_rect = QRectF(
                        game_width - preview_size - preview_margin, 
                        header_height + 10, 
                        preview_size, 
                        preview_size * 0.75
                    )
                    
                    # Draw background with rounded corners
                    path = QPainterPath()
                    radius = 8
                    path.addRoundedRect(preview_rect, radius, radius)
                    painter.setPen(QPen(self.colors['preview_border'], 1))
                    painter.fillPath(path, self.colors['header_bg'])
                    painter.drawPath(path)
                    
                    # Draw preview title with accent color
                    label_rect = QRect(
                        game_width - preview_size - preview_margin,
                        header_height + 10,
                        preview_size,
                        24
                    )
                    
                    font.setPointSize(9)
                    painter.setFont(font)
                    painter.setPen(QPen(self.colors['accent']))
                    painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, "LIVE PREVIEW")
                    
                    # Calculate scaled preview image with proper margins
                    content_rect = QRectF(
                        preview_rect.left() + 8,
                        preview_rect.top() + 28,
                        preview_rect.width() - 16,
                        preview_rect.height() - 36
                    )
                    
                    scaled_pixmap = self.preview_pixmap.scaled(
                        int(content_rect.width()), 
                        int(content_rect.height()), 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    
                    # Center the preview image in the content area
                    x_offset = int((content_rect.width() - scaled_pixmap.width()) // 2)
                    
                    # Draw the preview image
                    painter.drawPixmap(
                        int(content_rect.left() + x_offset),
                        int(content_rect.top()),
                        scaled_pixmap
                    )
            
            def mousePressEvent(self, event):
                """Handle mouse click to finalize selection"""
                if event.button() == Qt.MouseButton.LeftButton:
                    # Stop all timers
                    self.cursor_timer.stop()
                    if hasattr(self, 'preview_timer') and self.preview_timer.isActive():
                        self.preview_timer.stop()
                    if hasattr(self, 'pulse_timer') and self.pulse_timer.isActive():
                        self.pulse_timer.stop()
                    
                    # Get final cursor position
                    # Calculate region coordinates centered on mouse position
                    left = self.current_x - self.box_width // 2
                    top = self.current_y - self.box_height // 2
                    right = left + self.box_width
                    bottom = top + self.box_height
                    
                    # Ensure region stays within screen bounds
                    if left < 0:
                        left = 0
                        right = self.box_width
                    elif right > game_width:
                        right = game_width
                        left = right - self.box_width
                        
                    if top < 0:
                        top = 0
                        bottom = self.box_height
                    elif bottom > game_height:
                        bottom = game_height
                        top = bottom - self.box_height
                    
                    # Convert to absolute screen coordinates
                    abs_left = self.client_left + left
                    abs_top = self.client_top + top
                    abs_right = abs_left + self.box_width
                    abs_bottom = abs_top + self.box_height
                    
                    # Close selection window and return the selected region
                    print(f"Selection completed at: {abs_left},{abs_top} to {abs_right},{abs_bottom}")
                    self.parent().selected_region = (abs_left, abs_top, abs_right, abs_bottom)
                    self.parent().selection_complete = True
                    self.parent().close()
            
            def keyPressEvent(self, event):
                """Handle key press to cancel selection"""
                if event.key() == Qt.Key.Key_Escape:
                    # Stop all timers
                    self.cursor_timer.stop()
                    if hasattr(self, 'preview_timer') and self.preview_timer.isActive():
                        self.preview_timer.stop()
                    if hasattr(self, 'pulse_timer') and self.pulse_timer.isActive():
                        self.pulse_timer.stop()
                        
                    # Cancel selection
                    self.parent().selected_region = None
                    self.parent().selection_complete = False
                    self.parent().close()
        
        # Set up selection window properties
        selection_window.selection_complete = False
        selection_window.selected_region = None
        
        # Create canvas and add to window
        canvas = SelectionCanvas(selection_window)
        
        # Set cursor to crosshair
        selection_window.setCursor(Qt.CursorShape.CrossCursor)
        canvas.setCursor(Qt.CursorShape.CrossCursor)
        
        # Show the selection window
        selection_window.show()
        selection_window.activateWindow()
        selection_window.raise_()
        
        # Force focus on the game window first
        force_focus_window(self.detector.play_together_window)
        time.sleep(0.1)
        
        # Now bring selection window to top
        selection_window.activateWindow()
        selection_window.raise_()
        
        # Initialize cursor position to center of window
        cursor = QCursor()
        center_x = client_left + (game_width // 2)
        center_y = client_top + (game_height // 2)
        cursor.setPos(center_x, center_y)
        
        # Set up a timer to check if selection is complete
        check_timer = QTimer(self)
        check_timer.setInterval(100)  # Check every 100ms
        
        def check_selection_status():
            if not selection_window.isVisible():
                check_timer.stop()
                
                # Show our window again
                self.show()
                self.activateWindow()
                
                if selection_window.selection_complete and selection_window.selected_region:
                    # Store the region in the detector
                    self.detector.region = selection_window.selected_region
                    left, top, right, bottom = self.detector.region
                    width = right - left
                    height = bottom - top
                    
                    self.log(f"Region selected: ({left},{top}) to ({right},{bottom}), size: {width}×{height}")
                    
                    # Update region info display
                    if hasattr(self, 'region_info_label'):
                        self.region_info_label.setText(f"Position: ({left},{top}) • Size: {width}×{height}")
                    
                    # Validate the region with a preview capture
                    if self.detector.validate_region():
                        # Also capture a reference frame right away
                        self.detector.capture_reference()
                        self.log("Reference frame captured for the selected region")
                        self.status_label.setText(f"Region selected: {width}×{height} at ({left},{top})")
                        self.start_button.setEnabled(True)
                    else:
                        self.log("Selected region is invalid")
                        self.status_label.setText("Invalid region selected")
                else:
                    self.log("Region selection canceled")
        
        # Connect timer and start it
        check_timer.timeout.connect(check_selection_status)
        check_timer.start()
        
        return True
    
    # except Exception as e:
    #     self.log(f"Error in region selection: {str(e)}")
    #     traceback.print_exc()
    #     self.show()  # Make sure our window is visible again
    #     return False
        
    def update_statistics(self):
        """Update statistics display"""
        if not self.detector:
            return
            
        # Calculate runtime
        runtime_secs = time.time() - self.start_time
        hours = int(runtime_secs // 3600)
        mins = int((runtime_secs % 3600) // 60)
        secs = int(runtime_secs % 60)
        runtime_str = f"{hours:02}:{mins:02}:{secs:02}"
        
        # Detection rate
        detections_per_hour = 0
        if runtime_secs > 0:
            detections_per_hour = (self.total_detections / runtime_secs) * 3600
            
        # Average interval
        avg_interval = "N/A"
        if hasattr(self.detector, 'stats') and "avg_detection_interval" in self.detector.stats:
            interval = self.detector.stats["avg_detection_interval"]
            if interval > 0:
                interval_mins = int(interval // 60)
                interval_secs = int(interval % 60)
                avg_interval = f"{interval_mins}m {interval_secs}s"
                
        # FPS
        fps = 0
        if hasattr(self.detector, 'performance') and "avg_processing_time" in self.detector.performance:
            fps = int(1.0 / max(0.01, self.detector.performance["avg_processing_time"]))
            
            # Update monitor FPS display
            if hasattr(self, 'monitor_fps'):
                self.monitor_fps.setText(f"{fps}")
            
        # Update stats labels
        stats_data = {
            "total_detections": str(self.total_detections),
            "session_runtime": runtime_str,
            "detections_per_hour": f"{detections_per_hour:.1f}/hr",
            "avg_interval": avg_interval,
            "processing_fps": f"{fps} FPS",
            "current_threshold": f"{self.detector.THRESHOLD:.3f}" if hasattr(self.detector, 'THRESHOLD') else "N/A",
            "cooldown": f"{self.detector.detection_cooldown:.1f}s" if hasattr(self.detector, 'detection_cooldown') else "N/A",
            "key_mapping": self.detector.fishing_key.upper() if hasattr(self.detector, 'fishing_key') else "N/A"
        }
        
        for key, label in self.stats_labels.items():
            if key in stats_data:
                label.setText(stats_data[key])
        
    def start_detection(self):
        """Start the detection process"""
        try:
            if self.detection_running:
                self.log("Detection is already running")
                return
                
            if not self.detector:
                self.detector = PixelChangeDetector(self.log_queue)
                self.detector.gui = self
                
            # Check if region is selected
            if not self.detector.region:
                self.log("You must select a region first")
                return
                
            # Update detector settings from UI
            self.apply_settings()
            
            # Reset statistics
            self.total_detections = 0
            self.start_time = time.time()
            
            # Initialize thread control
            self.detector.thread_control = {
                "running": True,
                "paused": False,
                "stop_requested": False
            }
            
            self.log(f"Starting detection with threshold: {self.detector.THRESHOLD:.2f}")
            
            # Start the detector
            self.detection_running = True
            self.detector.start_detection()
            
            # Start the visualization timer
            self.vis_timer.start()
            
            # Update UI
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            self.status_label.setText("Running - Monitoring for changes")
            self.status_label.setStyleSheet("font-weight: bold; color: #77DD77;")  # Green color
            
        except Exception as e:
            self.log(f"Error starting detection: {str(e)}")
            
    def stop_detection(self):
        """Stop the detection process"""
        if not self.detection_running:
            return
            
        # Signal thread to stop
        if hasattr(self.detector, 'thread_control'):
            self.detector.thread_control["stop_requested"] = True
            
        # Stop the detector
        if self.detector:
            self.detector.stop_detection()
            
        # Stop the visualization timer
        self.vis_timer.stop()
            
        self.detection_running = False
        self.log("Detection stopped")
        
        # Reset UI
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("Pause")
        self.status_label.setText("Stopped")
        self.status_label.setStyleSheet("font-weight: bold; color: #FF6961;")  # Red color
        
    def toggle_pause(self):
        """Pause or resume the detection process"""
        if not self.detection_running:
            return
            
        if self.detector.paused:
            # Resume detection
            self.detector.paused = False
            if hasattr(self.detector, 'thread_control'):
                self.detector.thread_control["paused"] = False
            self.pause_button.setText("Pause")
            self.status_label.setText("Running - Monitoring for changes")
            self.status_label.setStyleSheet("font-weight: bold; color: #77DD77;")  # Green color
            self.log("Detection resumed")
        else:
            # Pause detection
            self.detector.paused = True
            if hasattr(self.detector, 'thread_control'):
                self.detector.thread_control["paused"] = True
            self.pause_button.setText("Resume")
            self.status_label.setText("Paused")
            self.status_label.setStyleSheet("font-weight: bold; color: #FFB347;")  # Orange color
            self.log("Detection paused")
            
    def update_visualization(self):
        """Update the visualization with current frames"""
        if not self.detection_running or not self.detector:
            return
            
        try:
            # Update current frame
            if hasattr(self.detector, 'color_frame') and self.detector.color_frame is not None:
                self.viz_canvas.update_image(frame=self.detector.color_frame)
            elif hasattr(self.detector, 'current_frame') and self.detector.current_frame is not None:
                # Convert grayscale to RGB if needed
                if len(self.detector.current_frame.shape) < 3:
                    gray_display = cv2.cvtColor(self.detector.current_frame, cv2.COLOR_GRAY2RGB)
                    self.viz_canvas.update_image(frame=gray_display)
                else:
                    self.viz_canvas.update_image(frame=self.detector.current_frame)
            
            # Update difference frame
            if hasattr(self.detector, 'diff_frame') and self.detector.diff_frame is not None:
                self.viz_canvas.update_image(diff_frame=self.detector.diff_frame)
            
            # Update timeline
            if hasattr(self.detector, 'change_history'):
                self.viz_canvas.update_timeline(
                    history=self.detector.change_history,
                    threshold=self.detector.THRESHOLD if hasattr(self.detector, 'THRESHOLD') else 0.05
                )
                
            # Update status indicators
            if hasattr(self, 'monitor_threshold') and hasattr(self.detector, 'THRESHOLD'):
                self.monitor_threshold.setText(f"{self.detector.THRESHOLD:.3f}")
                
            if hasattr(self, 'monitor_fps') and hasattr(self.detector, 'performance'):
                fps = int(1.0 / max(0.01, self.detector.performance["avg_processing_time"]))
                self.monitor_fps.setText(f"{fps}")
                
        except Exception as e:
            self.log(f"Error updating visualization: {e}")
            
    def increment_detection_count(self):
        """Increment detection counter and update UI"""
        self.total_detections += 1
        
        # Update statistics display
        self.update_statistics()
        
        # Log the detection
        self.log(f"Detection #{self.total_detections} registered")

# Main function
def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show the main window
    main_window = SimpleAutoFisherGUI()
    main_window.show()
    
    # Get primary monitor dimensions to center the window
    screen = app.primaryScreen().geometry()
    screen_width, screen_height = screen.width(), screen.height()
    
    # Set window size based on monitor resolution
    window_width = min(int(screen_width * 0.5), 800)
    window_height = min(int(screen_height * 0.6), 600)
    
    # Center window on primary monitor
    center_x = int(screen_width/2 - window_width/2)
    center_y = int(screen_height/2 - window_height/2)
    
    main_window.resize(window_width, window_height)
    main_window.move(center_x, center_y)
    
    # Log monitor information
    with mss.mss() as sct:
        monitors = sct.monitors
        main_window.log(f"Detected {len(monitors)-1} physical monitors")
        main_window.log(f"Primary monitor: {screen_width}x{screen_height}")
    
    # Add welcome message
    main_window.log(f"AutoFisher Qt v{VERSION} - {VERSION_NAME} initialized")
    main_window.log("System ready - Please select a region to begin")
    main_window.log("To get started: (1) Select region size (2) Click select-region (3) Click start")
    main_window.log("Direct Control is enabled by default for maximum reliability")
    main_window.log("High Performance and Fullscreen Respect features enabled by default")
    
    # Start the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 