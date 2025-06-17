"""
Region selection overlay for screen capture
"""
import time
import cv2
import numpy as np
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect, QPoint, QRectF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPixmap, QImage, QCursor, QPainterPath

class RegionSelectionOverlay(QWidget):
    """Overlay widget for selecting a region of the screen"""
    
    region_selected = pyqtSignal(tuple)  # Signal emitted when region is selected
    selection_canceled = pyqtSignal()    # Signal emitted when selection is canceled
    
    def __init__(self, window_geometry, parent=None):
        super().__init__(parent)
        # Store the target window geometry
        self.target_window_geometry = window_geometry
        
        # Set overlay to be frameless and always on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        
        # Allow the widget to capture mouse events outside its area
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Initialize selection state
        self.selecting = False
        self.selection_start = QPoint(0, 0)
        self.selection_end = QPoint(0, 0)
        self.current_cursor_pos = QPoint(0, 0)
        
        # For preview
        self.preview_image = QImage()
        self.preview_rect = QRectF(0, 0, 200, 150)  # Default size
        self.preview_padding = 10  # Padding around the preview
        
        # Setup cursor tracking
        self.setMouseTracking(True)
        
        # Animation variables
        self.pulse_opacity = 0.5
        self.pulse_increasing = True
        
        # Setup animation timer
        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(50)  # 20 FPS for animation
        self.pulse_timer.timeout.connect(self.update_pulse)
        
        # Screen tracking timer
        self.cursor_timer = QTimer(self)
        self.cursor_timer.setInterval(30)  # 33 FPS for cursor tracking
        self.cursor_timer.timeout.connect(self.track_cursor)
        
        # Preview timer
        self.preview_timer = QTimer(self)
        self.preview_timer.setInterval(100)  # 10 FPS for preview
        self.preview_timer.timeout.connect(self.update_preview)
        
    def showEvent(self, event):
        """When widget is shown, start animation timers"""
        super().showEvent(event)
        self.pulse_timer.start()
        self.cursor_timer.start()
        self.preview_timer.start()
        
    def check_position(self):
        """Check that the overlay is properly positioned over the target window"""
        # If we have a target window geometry, ensure overlay covers it
        if self.target_window_geometry and all(self.target_window_geometry):
            left, top, width, height = self.target_window_geometry
            self.setGeometry(left, top, width, height)
        else:
            # Otherwise, cover the entire screen
            desktop = self.screen().virtualGeometry()
            self.setGeometry(desktop)
        
    def update_preview(self):
        """Update the preview image based on current selection"""
        if not self.selecting:
            return
            
        # If we have a valid selection rectangle
        if self.selection_start != self.selection_end:
            try:
                # Calculate selection rect
                x1 = min(self.selection_start.x(), self.selection_end.x())
                y1 = min(self.selection_start.y(), self.selection_end.y())
                x2 = max(self.selection_start.x(), self.selection_end.x()) 
                y2 = max(self.selection_start.y(), self.selection_end.y())
                
                width = x2 - x1
                height = y2 - y1
                
                if width > 10 and height > 10:
                    # Capture screen region
                    import mss
                    with mss.mss() as sct:
                        # Convert region format for mss
                        region = {
                            "left": x1,
                            "top": y1,
                            "width": width,
                            "height": height
                        }
                        
                        # Capture and convert to QImage
                        screenshot = np.array(sct.grab(region))
                        h, w = screenshot.shape[:2]
                        
                        # Convert to RGB format for Qt
                        rgb_image = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2RGB)
                        
                        # Create QImage from numpy array
                        self.preview_image = QImage(
                            rgb_image.data,
                            w, h,
                            rgb_image.strides[0],
                            QImage.Format.Format_RGB888
                        )
            except Exception as e:
                print(f"Error updating preview: {e}")
                
    def update_current_box(self):
        """Update the current selection box based on cursor position"""
        if self.selecting:
            self.selection_end = self.mapFromGlobal(QCursor.pos())
        else:
            self.current_cursor_pos = self.mapFromGlobal(QCursor.pos())
            # Create a small box around cursor for highlighting
            self.selection_start = QPoint(
                self.current_cursor_pos.x() - 25,
                self.current_cursor_pos.y() - 25
            )
            self.selection_end = QPoint(
                self.current_cursor_pos.x() + 25,
                self.current_cursor_pos.y() + 25
            )
            
        # Request redraw
        self.update()
        
    def update_pulse(self):
        """Update the pulse effect for animations"""
        step = 0.05
        if self.pulse_increasing:
            self.pulse_opacity += step
            if self.pulse_opacity >= 0.8:
                self.pulse_opacity = 0.8
                self.pulse_increasing = False
        else:
            self.pulse_opacity -= step
            if self.pulse_opacity <= 0.3:
                self.pulse_opacity = 0.3
                self.pulse_increasing = True
                
        # Redraw
        self.update()
        
    def track_cursor(self):
        """Track cursor position and update highlighting"""
        if not self.selecting:
            self.update_current_box()
            
    def mouseMoveEvent(self, event):
        """Handle mouse movement during selection"""
        if self.selecting:
            self.selection_end = event.pos()
            self.update()
        
    def mousePressEvent(self, event):
        """Handle mouse press to begin selection"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.selecting = True
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            # Cancel selection
            self.selection_canceled.emit()
            self.close()
            
    def keyPressEvent(self, event):
        """Handle key presses for ESC to cancel"""
        if event.key() == Qt.Key.Key_Escape:
            self.selection_canceled.emit()
            self.close()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.finalize_selection()
            
    def mouseReleaseEvent(self, event):
        """Handle mouse release to complete selection"""
        if event.button() == Qt.MouseButton.LeftButton and self.selecting:
            self.finalize_selection()
            
    def finalize_selection(self):
        """Complete the selection and emit coordinates"""
        if self.selecting:
            # Get normalized selection coordinates
            x1 = min(self.selection_start.x(), self.selection_end.x())
            y1 = min(self.selection_start.y(), self.selection_end.y())
            x2 = max(self.selection_start.x(), self.selection_end.x()) 
            y2 = max(self.selection_start.y(), self.selection_end.y())
            
            # Check if selection is valid (minimum size)
            if x2 - x1 > 10 and y2 - y1 > 10:
                # Emit the selected region coordinates
                self.region_selected.emit((x1, y1, x2, y2))
                self.close()
                
    def paintEvent(self, event):
        """Draw the overlay with selection rectangle"""
        painter = QPainter(self)
        
        # Create semi-transparent dark overlay for the entire area
        overlay_color = QColor(0, 0, 0, 150)
        painter.fillRect(self.rect(), overlay_color)
        
        # Draw selection rectangle or cursor highlight
        if self.selecting:
            # Get normalized selection coordinates
            x1 = min(self.selection_start.x(), self.selection_end.x())
            y1 = min(self.selection_start.y(), self.selection_end.y())
            x2 = max(self.selection_start.x(), self.selection_end.x()) 
            y2 = max(self.selection_start.y(), self.selection_end.y())
            
            selection_width = x2 - x1
            selection_height = y2 - y1
            
            # Draw the selection area (clear)
            selection_rect = QRect(x1, y1, selection_width, selection_height)
            painter.fillRect(selection_rect, QBrush(Qt.GlobalColor.transparent))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(selection_rect, QBrush(Qt.GlobalColor.white))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            
            # Draw the selection rectangle border
            border_pen = QPen(QColor("#77DDFF"))
            border_pen.setWidth(2)
            border_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(border_pen)
            painter.drawRect(selection_rect)
            
            # Calculate the preview dimensions - use a larger portion of the screen
            preview_size = min(self.width(), self.height()) // 2  # Use up to half of the smaller dimension
            
            # Calculate the preview container with padding
            preview_container_width = preview_size
            preview_container_height = preview_size
            
            # Position in top-right corner with padding
            preview_container_x = self.width() - preview_container_width - self.preview_padding
            preview_container_y = self.preview_padding
            
            # Draw preview container background and border
            preview_container = QRect(
                preview_container_x,
                preview_container_y,
                preview_container_width,
                preview_container_height
            )
            
            # Draw a semi-transparent background for the preview
            bg_color = QColor(0, 0, 0, 180)
            painter.fillRect(preview_container, bg_color)
            
            # Draw preview border
            painter.setPen(QPen(QColor("#77DDFF"), 2))
            painter.drawRect(preview_container)
            
            # Draw preview title
            title_rect = QRect(
                preview_container_x,
                preview_container_y - 25,  # Position above the preview
                preview_container_width,
                20
            )
            
            # Draw title background
            title_bg = QColor(0, 0, 0, 180)
            painter.fillRect(title_rect, title_bg)
            
            # Draw title text
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "PREVIEW")
            
            # If we have a valid preview image, draw it
            if not self.preview_image.isNull():
                # Calculate inner content area for the preview (accounting for borders)
                inner_padding = 10
                content_rect = QRect(
                    preview_container_x + inner_padding,
                    preview_container_y + inner_padding,
                    preview_container_width - (inner_padding * 2),
                    preview_container_height - (inner_padding * 2)
                )
                
                # Scale the image to fit the content rect while maintaining aspect ratio
                pixmap = QPixmap.fromImage(self.preview_image)
                scaled_pixmap = pixmap.scaled(
                    content_rect.width(),
                    content_rect.height(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Center the preview in the content area
                x_offset = (content_rect.width() - scaled_pixmap.width()) // 2
                y_offset = (content_rect.height() - scaled_pixmap.height()) // 2
                
                # Draw the preview image
                painter.drawPixmap(
                    content_rect.left() + x_offset,
                    content_rect.top() + y_offset,
                    scaled_pixmap
                )
        else:
            # Draw cursor highlight with pulse effect
            cursor_pos = self.current_cursor_pos
            highlight_size = 50
            
            # Yellow targeting circle
            pulse_color = QColor("#FFCC00")
            pulse_color.setAlphaF(self.pulse_opacity)
            
            # Outer circle with pulse effect
            outer_pen = QPen(pulse_color, 2, Qt.PenStyle.DashLine)
            painter.setPen(outer_pen)
            outer_rect = QRect(
                cursor_pos.x() - highlight_size//2,
                cursor_pos.y() - highlight_size//2,
                highlight_size,
                highlight_size
            )
            painter.drawEllipse(outer_rect)
            
            # Inner circle (solid)
            inner_pen = QPen(QColor("#FFCC00"), 1, Qt.PenStyle.SolidLine)
            painter.setPen(inner_pen)
            inner_rect = QRect(
                cursor_pos.x() - 12,
                cursor_pos.y() - 12,
                24,
                24
            )
            painter.drawEllipse(inner_rect)
            
            # Crosshair lines
            crosshair_pen = QPen(QColor("#FFFFFF"), 1, Qt.PenStyle.DotLine)
            painter.setPen(crosshair_pen)
            
            # Horizontal line
            painter.drawLine(
                cursor_pos.x() - highlight_size,
                cursor_pos.y(),
                cursor_pos.x() + highlight_size,
                cursor_pos.y()
            )
            
            # Vertical line
            painter.drawLine(
                cursor_pos.x(),
                cursor_pos.y() - highlight_size,
                cursor_pos.x(),
                cursor_pos.y() + highlight_size
            )
            
            # Instructions text
            instructions_bg = QColor("#333333")
            instructions_bg.setAlpha(200)
            instructions_text = QColor("#FFFFFF")
            
            instructions = "Click and drag to select region  •  Press ESC to cancel"
            instructions_width = painter.fontMetrics().horizontalAdvance(instructions) + 20
            instructions_height = 30
            
            instructions_x = (self.width() - instructions_width) // 2
            instructions_y = self.height() - instructions_height - 20
            
            # Draw rounded background for instructions
            instructions_rect = QRectF(instructions_x, instructions_y, 
                                     instructions_width, instructions_height)
            instructions_path = QPainterPath()
            instructions_path.addRoundedRect(instructions_rect, 15, 15)
            painter.fillPath(instructions_path, instructions_bg)
            
            # Draw instructions text
            painter.setPen(QPen(instructions_text))
            painter.drawText(instructions_rect, Qt.AlignmentFlag.AlignCenter, instructions)
            
            # Draw title header
            header_bg = QColor("#333333")
            header_bg.setAlpha(220)
            header_text = QColor("#77DDFF")
            
            header = "Select Fishing Bobber Region"
            header_width = self.width()
            header_height = 40
            
            header_x = 0
            header_y = 0
            
            # Draw header background
            header_rect = QRect(header_x, header_y, header_width, header_height)
            painter.fillRect(header_rect, header_bg)
            
            # Draw header text
            font = painter.font()
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QPen(header_text))
            painter.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, header)
            
            # Reset font
            font.setPointSize(9)
            font.setBold(False)
            painter.setFont(font) 