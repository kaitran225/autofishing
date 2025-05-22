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
        
        # Define colors - use the macOS style theme
        self.colors = {
            'bg_dark': '#FFFFFF',        # Background (light mode)
            'bg_panel': '#F5F5F7',       # Panel background
            'bg_card': '#F0F0F2',        # Card background
            'primary': '#0A84FF',        # macOS blue
            'primary_light': '#40A8FF',  # Light blue
            'secondary': '#5E5CE6',      # Purple
            'alert': '#FF453A',          # macOS red
            'warning': '#FF9F0A',        # macOS orange
            'success': '#30D158',        # macOS green
            'text': '#1D1D1F',           # Primary text
            'text_dim': '#484848',       # Secondary text
        }
        
        # Initialize bright mode tracking
        self.bright_mode_enabled = True
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Image display label with rounded corners and subtle border
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(f"""
            background-color: {self.colors['bg_card']}; 
            border: 1px solid {self.colors['bg_panel']}; 
            border-radius: 6px;
            padding: 8px;
        """)
        layout.addWidget(self.image_label)
        
        # Status indicators in a slim frame
        status_frame = QFrame()
        status_frame.setMaximumHeight(28)
        status_frame.setStyleSheet(f"""
            background-color: {self.colors['bg_panel']};
            border-radius: 6px;
            padding: 0px;
        """)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(12, 0, 12, 0)
        status_layout.setSpacing(8)
        
        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-weight: 500; font-size: 13px;")
        status_layout.addWidget(self.status_label)
        
        self.change_label = QLabel("Change: 0.00%")
        self.change_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-weight: 500; font-size: 13px;")
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
                    # Use a more macOS-friendly colormap - INFERNO instead of PLASMA
                    diff_color = cv2.applyColorMap(diff_frame, cv2.COLORMAP_INFERNO)
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
                
                # Create a side-by-side composite view with a clean separator
                composite_width = width + diff_color.shape[1] + 1  # +1 for separator
                composite = np.zeros((height, composite_width, 3), dtype=np.uint8)
                
                # Set background color for better visual appearance - light gray for light mode
                bg_color = (240, 240, 242)  # RGB light gray
                composite.fill(bg_color[0])  # Fill with bg color
                
                # Add the frames to the composite
                composite[:, :width, :] = current_rgb
                
                # Draw a vertical separator line (subtle gray)
                separator_color = (200, 200, 200)  # Light gray separator
                composite[:, width:width+1, :] = separator_color
                
                # Add diff frame with offset of 1 pixel for the separator
                # Check if the source and target dimensions match
                target_width = min(diff_color.shape[1], composite_width - width - 1)
                target_area = composite[:, width+1:width+1+target_width, :]
                source_area = diff_color[:, :target_width, :]
                
                # Only copy if dimensions match
                if target_area.shape == source_area.shape:
                    target_area[:] = source_area
                
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
                        q_img.fill(QColor(240, 240, 242))  # Light gray
                elif len(current_frame.shape) == 2:  # Grayscale
                    bytes_per_line = width
                    q_img = QImage(current_frame.data, width, height, bytes_per_line, QImage.Format.Format_Grayscale8)
                else:
                    # Invalid format, create a blank image
                    q_img = QImage(width, height, QImage.Format.Format_RGB888)
                    q_img.fill(QColor(240, 240, 242))  # Light gray
            
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
                    self.change_label.setStyleSheet(f"color: {self.colors['alert']}; font-weight: 600; font-size: 13px;")
                elif change_percent > 0.1:
                    self.change_label.setStyleSheet(f"color: {self.colors['warning']}; font-weight: 600; font-size: 13px;")
                else:
                    self.change_label.setStyleSheet(f"color: {self.colors['text_dim']}; font-weight: 500; font-size: 13px;")
                    
        except Exception as e:
            print(f"Error updating display: {e}")
            import traceback
            traceback.print_exc()
        
    def set_status(self, status):
        """Update the status display with macOS style colors"""
        if status == "running":
            self.status_label.setText("Status: Running")
            self.status_label.setStyleSheet(f"color: {self.colors['success']}; font-weight: 600; font-size: 13px;")
        elif status == "stopped":
            self.status_label.setText("Status: Stopped")
            self.status_label.setStyleSheet(f"color: {self.colors['alert']}; font-weight: 600; font-size: 13px;")
        elif status == "paused":
            self.status_label.setText("Status: Paused")
            self.status_label.setStyleSheet(f"color: {self.colors['warning']}; font-weight: 600; font-size: 13px;")
        elif status == "action_sequence":
            self.status_label.setText("Status: Action Sequence")
            self.status_label.setStyleSheet(f"color: {self.colors['primary']}; font-weight: 600; font-size: 13px;")
        else:
            self.status_label.setText(f"Status: {status}")
            self.status_label.setStyleSheet(f"color: {self.colors['text']}; font-weight: 500; font-size: 13px;")
            
    def set_bright_mode(self, enabled):
        """Set whether bright detection mode is enabled"""
        self.bright_mode_enabled = enabled 