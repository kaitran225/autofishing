import time
import numpy as np
import cv2
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImage

class MonitoringDisplay(QWidget):
    """Widget for displaying the captured region and difference visualization"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 250)
        
        # Define colors
        self.colors = {
            'bg_dark': '#2C3639',      # Deep charcoal background
            'bg_wood': '#3F4E4F',      # Wood tone
            'matcha': '#A0C49D',       # Medium matcha
            'matcha_light': '#DAE5D0', # Light matcha
            'matcha_dark': '#7D8F69',  # Dark matcha
            'alert': '#F87474',        # Soft red
            'warning': '#F9B572',      # Soft orange
            'text': '#FFFFFF',         # White text
        }
        
        # Initialize bright mode tracking
        self.bright_mode_enabled = True
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)  # Reduced spacing for slimmer appearance
        
        # Image display label with rounded corners
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(f"""
            background-color: {self.colors['bg_wood']}; 
            border: none; 
            border-radius: 10px;
            padding: 4px;
        """)
        layout.addWidget(self.image_label)
        
        # Status indicators in a ultra-slim frame
        status_frame = QFrame()
        status_frame.setMaximumHeight(28)  # Make it slimmer
        status_frame.setStyleSheet(f"""
            background-color: {self.colors['bg_wood']};
            border-radius: 6px;
            padding: 0px;
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 2, 8, 2)  # Very slim padding
        status_layout.setSpacing(6)
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.status_label)
        
        self.change_label = QLabel("Change: 0.00%")
        self.change_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.change_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addWidget(status_frame)
        
        # Pre-allocate reusable image buffers for performance
        self._last_pixmap = None
        self._last_display_time = 0
        self._display_throttle_ms = 16.67  # ~60fps
        
    def update_display(self, color_frame, diff_frame, change_percent):
        """Update the display with improved rendering to reduce noise - optimized for performance"""
        if color_frame is None:
            return
            
        # Throttle updates for better performance, but with higher frame rate
        current_time = time.time() * 1000  # Convert to ms
        if current_time - self._last_display_time < self._display_throttle_ms:
            return
            
        self._last_display_time = current_time
            
        try:
            # Create a clean copy for display - optimize by avoiding unnecessary copies
            display_frame = color_frame

            if diff_frame is not None:
                # Apply a more selective highlighting approach
                # Convert diff_frame to 3 channel if it's grayscale
                if len(diff_frame.shape) == 2:
                    # Create a colored mask for changes - using blue for visibility (macOS style)
                    # Optimized version with fewer operations
                    change_indices = diff_frame > 0
                    if np.any(change_indices):
                        # Only modify pixels that actually changed - create a copy only when needed
                        if id(display_frame) == id(color_frame):
                            display_frame = color_frame.copy()
                        # Use matcha green for highlights
                        display_frame[change_indices, 0] = 157   # B value (in BGR)
                        display_frame[change_indices, 1] = 196   # G value
                        display_frame[change_indices, 2] = 160   # R value
            
            # Convert BGR to RGB for proper display
            display_frame_rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            
            # Add a small indicator for bright detection mode if enabled
            if hasattr(self, 'bright_mode_enabled') and self.bright_mode_enabled:
                # Add a small "B" indicator in the bottom right corner
                height, width = display_frame_rgb.shape[:2]
                cv2.putText(display_frame_rgb, "BRIGHT", (width-70, height-10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 200, 255), 1, cv2.LINE_AA)
            
            # Convert to QImage for display - avoid memory copies when possible
            height, width, channels = display_frame_rgb.shape
            bytes_per_line = channels * width
            
            q_img = QImage(display_frame_rgb.data, width, height, 
                          bytes_per_line, QImage.Format.Format_RGB888)
            
            # Scale image to fit label while maintaining aspect ratio
            pixmap = QPixmap.fromImage(q_img)
            
            # Only rescale if the size changed
            if (self._last_pixmap is None or 
                self.image_label.width() != self._last_pixmap.width() or 
                self.image_label.height() != self._last_pixmap.height()):
                
                scaled_pixmap = pixmap.scaled(
                    self.image_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation  # Use smooth transformation for better quality
                )
                self._last_pixmap = scaled_pixmap
            else:
                # Use cached pixmap size
                scaled_pixmap = pixmap.scaled(
                    self._last_pixmap.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self._last_pixmap = scaled_pixmap
                
            self.image_label.setPixmap(self._last_pixmap)
            
            # Update change percentage display
            self.change_label.setText(f"Change: {change_percent:.2%}")
            
        except Exception as e:
            print(f"Error updating display: {e}")
    
    def set_status(self, status):
        """Update the status display with Matcha Wood theme colors"""
        if status == "running":
            self.status_label.setText("Status: Running")
            self.status_label.setStyleSheet(f"color: {self.colors['matcha']}; font-weight: 500; font-size: 12px;")
        elif status == "stopped":
            self.status_label.setText("Status: Stopped")
            self.status_label.setStyleSheet(f"color: {self.colors['alert']}; font-weight: 500; font-size: 12px;")
        elif status == "paused":
            self.status_label.setText("Status: Paused")
            self.status_label.setStyleSheet(f"color: {self.colors['warning']}; font-weight: 500; font-size: 12px;")
        elif status == "action_sequence":
            self.status_label.setText("Status: Action Sequence")
            self.status_label.setStyleSheet(f"color: {self.colors['matcha_light']}; font-weight: 500; font-size: 12px;")
        else:
            self.status_label.setText(f"Status: {status}")
            self.status_label.setStyleSheet(f"color: {self.colors['text']}; font-weight: 500; font-size: 12px;")
            
    def set_bright_mode(self, enabled):
        """Set whether bright detection mode is enabled"""
        self.bright_mode_enabled = enabled 