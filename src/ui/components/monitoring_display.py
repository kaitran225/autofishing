import time
import numpy as np
import cv2
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QImage, QColor

class MonitoringDisplay(QWidget):
    """Widget for displaying the captured region and difference visualization"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 220)
        
        # Define colors - use the modern clean theme
        self.colors = {
            'bg_dark': '#1E1E2E',      # Deep blue-gray background
            'bg_panel': '#2A2A3C',     # Slightly lighter panel bg
            'bg_card': '#313244',      # Card backgrounds
            'primary': '#89B4FA',      # Light blue primary 
            'primary_light': '#B4BEFE', # Light blue highlight
            'secondary': '#CBA6F7',    # Purple secondary
            'alert': '#F38BA8',        # Soft red for alerts
            'warning': '#FAB387',      # Soft orange warning
            'success': '#A6E3A1',      # Soft green success
            'text': '#CDD6F4',         # Main text
            'text_dim': '#A6ADC8',     # Secondary text
        }
        
        # Initialize bright mode tracking
        self.bright_mode_enabled = True
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # Image display label with rounded corners and subtle border
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(f"""
            background-color: {self.colors['bg_card']}; 
            border: 1px solid {self.colors['bg_panel']}; 
            border-radius: 8px;
            padding: 4px;
        """)
        layout.addWidget(self.image_label)
        
        # Status indicators in a slim frame
        status_frame = QFrame()
        status_frame.setMaximumHeight(30)
        status_frame.setStyleSheet(f"""
            background-color: {self.colors['bg_card']};
            border-radius: 6px;
            padding: 0px;
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(10, 3, 10, 3)
        status_layout.setSpacing(6)
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.status_label)
        
        self.change_label = QLabel("Change: 0.00%")
        self.change_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-weight: 500; font-size: 12px;")
        status_layout.addWidget(self.change_label, alignment=Qt.AlignmentFlag.AlignRight)
        
        layout.addWidget(status_frame)
        
        # Pre-allocate reusable image buffers for performance
        self._last_pixmap = None
        self._last_display_time = 0
        self._display_throttle_ms = 16.67  # ~60fps
        
    def update_display(self, current_frame, diff_frame, change_percent):
        """Update the display with current frame, difference visualization, and change percentage"""
        try:
            # Check if we have valid frames
            if current_frame is None:
                return
                
            # Convert the current frame to a QImage for display
            height, width = current_frame.shape[:2]
            
            # Create a composite view: current frame on the left, diff on the right (if available)
            if diff_frame is not None:
                # Resize diff frame to match current frame height if needed
                if diff_frame.shape[0] != height:
                    scale_factor = height / diff_frame.shape[0]
                    new_width = int(diff_frame.shape[1] * scale_factor)
                    diff_frame = cv2.resize(diff_frame, (new_width, height))
                
                # Create a colorized version of diff frame (convert grayscale to color heatmap)
                if len(diff_frame.shape) == 2:  # Grayscale
                    # Use a more modern colormap - PLASMA instead of JET
                    diff_color = cv2.applyColorMap(diff_frame, cv2.COLORMAP_PLASMA)
                else:
                    diff_color = diff_frame
                    
                # Handle input frame with proper channel checking
                if len(current_frame.shape) == 3:
                    if current_frame.shape[2] == 4:  # BGRA format (4 channels)
                        current_rgb = cv2.cvtColor(current_frame, cv2.COLOR_BGRA2RGB)
                    elif current_frame.shape[2] == 3:  # BGR format (3 channels)
                        current_rgb = cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB)
                    else:
                        # Unknown format, just use as is
                        current_rgb = current_frame
                else:
                    # Convert grayscale to RGB
                    current_rgb = cv2.cvtColor(current_frame, cv2.COLOR_GRAY2RGB)
                
                # Create a side-by-side composite view
                # Add a subtle separator line between the frames
                composite_width = width + diff_color.shape[1]
                composite = np.zeros((height, composite_width, 3), dtype=np.uint8)
                
                # Add the frames to the composite
                composite[:, :width, :] = current_rgb
                
                # Draw a vertical separator line
                separator_color = (80, 80, 120)  # Dark lavender separator
                composite[:, width:width+1, :] = separator_color
                
                # Add diff frame with offset of 1 pixel for the separator
                # Check if the source and target dimensions match
                target_width = min(diff_color.shape[1], composite_width - width - 1)
                composite[:, width+1:width+1+target_width, :] = diff_color[:, :target_width, :]
                
                # Create QImage from the composite
                bytes_per_line = 3 * composite_width
                q_img = QImage(composite.data, composite_width, height, bytes_per_line, QImage.Format.Format_RGB888)
            else:
                # Just display the current frame with proper format handling
                if len(current_frame.shape) == 3:
                    if current_frame.shape[2] == 4:  # BGRA format
                        current_rgb = cv2.cvtColor(current_frame, cv2.COLOR_BGRA2RGB)
                        bytes_per_line = 3 * width
                        q_img = QImage(current_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
                    elif current_frame.shape[2] == 3:  # BGR format
                        current_rgb = cv2.cvtColor(current_frame, cv2.COLOR_BGR2RGB)
                        bytes_per_line = 3 * width
                        q_img = QImage(current_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
                    else:
                        # Unknown format, create a blank image as fallback
                        q_img = QImage(width, height, QImage.Format.Format_RGB888)
                        q_img.fill(QColor(0, 0, 0))
                elif len(current_frame.shape) == 2:  # Grayscale
                    bytes_per_line = width
                    q_img = QImage(current_frame.data, width, height, bytes_per_line, QImage.Format.Format_Grayscale8)
                else:
                    # Invalid format, create a blank image
                    q_img = QImage(width, height, QImage.Format.Format_RGB888)
                    q_img.fill(QColor(0, 0, 0))
            
            # Convert QImage to QPixmap for display
            pixmap = QPixmap.fromImage(q_img)
            
            # Scale pixmap to fit the label while maintaining aspect ratio
            self.image_label.setPixmap(pixmap.scaled(
                self.image_label.width(), 
                self.image_label.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
            
            # Update change percentage display
            if change_percent is not None:
                self.change_label.setText(f"Change: {change_percent:.2%}")
                
                # Adjust color based on threshold
                if change_percent > 0.2:
                    self.change_label.setStyleSheet(f"color: {self.colors['alert']}; font-weight: 600; font-size: 12px;")
                elif change_percent > 0.1:
                    self.change_label.setStyleSheet(f"color: {self.colors['warning']}; font-weight: 600; font-size: 12px;")
                else:
                    self.change_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-weight: 500; font-size: 12px;")
                    
        except Exception as e:
            print(f"Error updating display: {e}")
            import traceback
            traceback.print_exc()
        
    def set_status(self, status):
        """Update the status display with modern clean theme colors"""
        if status == "running":
            self.status_label.setText("Status: Running")
            self.status_label.setStyleSheet(f"color: {self.colors['success']}; font-weight: 600; font-size: 12px;")
        elif status == "stopped":
            self.status_label.setText("Status: Stopped")
            self.status_label.setStyleSheet(f"color: {self.colors['alert']}; font-weight: 600; font-size: 12px;")
        elif status == "paused":
            self.status_label.setText("Status: Paused")
            self.status_label.setStyleSheet(f"color: {self.colors['warning']}; font-weight: 600; font-size: 12px;")
        elif status == "action_sequence":
            self.status_label.setText("Status: Action Sequence")
            self.status_label.setStyleSheet(f"color: {self.colors['primary']}; font-weight: 600; font-size: 12px;")
        else:
            self.status_label.setText(f"Status: {status}")
            self.status_label.setStyleSheet(f"color: {self.colors['text']}; font-weight: 500; font-size: 12px;")
            
    def set_bright_mode(self, enabled):
        """Set whether bright detection mode is enabled"""
        self.bright_mode_enabled = enabled 