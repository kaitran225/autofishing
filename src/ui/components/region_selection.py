import os
import time
import subprocess
import numpy as np
import mss
import cv2
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QImage, QFont, QPainterPath
from PyQt6.QtCore import QRectF

class RegionSelectionOverlay(QDialog):
    """Overlay for selecting a screen region"""
    region_selected = pyqtSignal(tuple)
    
    def __init__(self, parent=None, default_size=100):
        super().__init__(parent, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowState(Qt.WindowState.WindowFullScreen)
        
        # Force this window to be on top of all others
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        
        # Get screen information - full desktop size
        self.get_full_screen_dimensions()
        
        # Capture the current screen before showing the selection overlay
        self.background_pixmap = self.capture_screen_background()
        
        # Box dimensions (1.5:1 ratio)
        self.box_height = default_size
        self.box_width = int(default_size * 1.5)
        
        # For tracking mouse position
        self.mouse_pos = QPoint(self.screen_width // 2, self.screen_height // 2)
        
        # For drag and drop functionality
        self.is_dragging = False
        self.box_rect = QRect(
            self.mouse_pos.x() - self.box_width // 2,
            self.mouse_pos.y() - self.box_height // 2,
            self.box_width,
            self.box_height
        )
        
        # Modern macOS theme colors
        self.colors = {
            'bg_overlay': QColor(25, 25, 25, 150),     # Dark background with transparency
            'bg_medium': QColor(53, 54, 57, 220),      # Medium background with transparency
            'accent_blue': QColor(10, 132, 255, 255),  # macOS blue accent
            'accent_blue_light': QColor(50, 172, 255, 200), # Lighter blue
            'accent_green': QColor(48, 209, 88, 255),  # macOS green
            'text': QColor(255, 255, 255, 255),        # White text
            'border': QColor(90, 90, 95, 180)          # Border color with transparency
        }
        
        # For finding "PLAY TOGETHER" window
        self.play_together_rect = None
        self.find_play_together_window()
        
        # Initialize UI
        self._init_ui()
        
        # Ensure window is activated properly
        self.activateWindow()
        self.raise_()
        
    def get_full_screen_dimensions(self):
        """Get the full screen dimensions of the entire desktop"""
        # Get primary screen geometry
        primary_screen = QApplication.primaryScreen()
        self.screen_geometry = primary_screen.geometry()
        self.screen_width = self.screen_geometry.width()
        self.screen_height = self.screen_geometry.height()
        
        # Handle high DPI screens
        self.device_pixel_ratio = primary_screen.devicePixelRatio()
        
        # For macOS, try to get the full desktop size using mss directly
        try:
            with mss.mss() as sct:
                # Get monitor information for the primary display
                monitor_info = sct.monitors[1]  # 0 is all monitors combined, 1 is the primary
                
                # Store the native screen resolution
                self.full_width = monitor_info["width"]
                self.full_height = monitor_info["height"]
                
                # Debug output
                print(f"Qt Screen geometry: {self.screen_width}x{self.screen_height}")
                print(f"MSS Monitor size: {self.full_width}x{self.full_height}")
                print(f"Device pixel ratio: {self.device_pixel_ratio}")
                
                # Update screen size based on what we found
                if self.full_width > self.screen_width or self.full_height > self.screen_height:
                    # Use the larger dimensions for fullscreen capture
                    self.screen_width = self.full_width
                    self.screen_height = self.full_height
                    print(f"Using full screen size: {self.screen_width}x{self.screen_height}")
        except Exception as e:
            print(f"Error getting full screen dimensions: {e}")
            # Fallback to Qt screen geometry if mss fails
            self.full_width = self.screen_width
            self.full_height = self.screen_height
        
        # Set the window size to match the full screen
        self.setGeometry(0, 0, self.screen_width, self.screen_height)
        
    def capture_screen_background(self):
        """Capture the entire screen to use as background"""
        try:
            # Give a small delay to ensure any other windows are properly hidden
            time.sleep(0.3)
            
            # Capture the entire screen using MSS
            with mss.mss() as sct:
                # Capture the primary monitor at full resolution
                monitor_idx = 1  # Primary monitor
                monitor = sct.monitors[monitor_idx]
                
                # Ensure we get the full monitor, not just the application window
                screenshot = sct.grab(monitor)
                
                # Convert to numpy array
                img_array = np.array(screenshot)
                
                # Convert from BGRA to RGB for proper display
                if img_array.shape[2] == 4:  # If it has an alpha channel
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_BGRA2RGB)
                else:
                    img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
                
                # Get the dimensions of the captured image
                height, width, channels = img_array.shape
                print(f"Captured image dimensions: {width}x{height}")
                
                # Scale if the captured size doesn't match our window size
                if width != self.screen_width or height != self.screen_height:
                    img_array = cv2.resize(img_array, (self.screen_width, self.screen_height))
                    print(f"Resized image to: {self.screen_width}x{self.screen_height}")
                
                # Convert to QImage
                height, width, channels = img_array.shape
                bytes_per_line = channels * width
                
                q_img = QImage(img_array.data, width, height, 
                               bytes_per_line, QImage.Format.Format_RGB888)
                
                # Convert to QPixmap for drawing
                pixmap = QPixmap.fromImage(q_img)
                
                # Debug
                print(f"Final pixmap dimensions: {pixmap.width()}x{pixmap.height()}")
                
                return pixmap
        except Exception as e:
            print(f"Error capturing screen background: {e}")
            return None
    
    def _init_ui(self):
        """Initialize the UI components with modern macOS theme"""
        # Add label with instructions
        self.instructions = QLabel("Click and drag to move selection box. Release to place. (ESC to cancel)", self)
        self.instructions.setStyleSheet("""
            color: white; 
            background-color: rgba(53, 54, 57, 220); 
            padding: 12px;
            border-radius: 10px;
            font-family: Helvetica, Arial, sans-serif;
            font-weight: 500;
            font-size: 13px;
        """)
        self.instructions.setGeometry(
            (self.screen_width - 500) // 2,  # Center horizontally
            30,  # Position from top
            500,  # Width
            40   # Height
        )
        self.instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Add "Position on PLAY TOGETHER" button
        self.play_together_button = QPushButton("Position on PLAY TOGETHER", self)
        self.play_together_button.setStyleSheet("""
            background-color: rgba(10, 132, 255, 220); 
            color: white; 
            border: none; 
            padding: 10px 16px;
            border-radius: 10px;
            font-family: Helvetica, Arial, sans-serif;
            font-weight: 500;
            font-size: 13px;
        """)
        self.play_together_button.setGeometry(self.screen_width - 250, 70, 220, 40)
        self.play_together_button.clicked.connect(self.position_on_play_together)
        
        # Show button only if PLAY TOGETHER window was found
        self.play_together_button.setVisible(self.play_together_rect is not None)
        
    def find_play_together_window(self):
        """Try to find the PLAY TOGETHER game window using AppleScript"""
        try:
            # AppleScript to find windows with PLAY TOGETHER in the title and get more details
            script = '''
            tell application "System Events"
                set windowInfo to {}
                repeat with proc in application processes
                    set procName to name of proc
                    repeat with w in windows of proc
                        if name of w contains "PLAY TOGETHER" or name of w contains "Play Together" or name of w contains "play together" then
                            set winPos to position of w
                            set winSize to size of w
                            set winName to name of w
                            return {item 1 of winPos, item 2 of winPos, item 1 of winSize, item 2 of winSize, procName, winName}
                        end if
                    end repeat
                end repeat
                return ""
            end tell
            '''
            
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=False)
            if result.stdout.strip():
                try:
                    # Parse the result: left, top, width, height, process name, window name
                    values = result.stdout.strip().split(", ")
                    if len(values) >= 4:
                        left = int(values[0])
                        top = int(values[1])
                        width = int(values[2])
                        height = int(values[3])
                        
                        # Store process name and window name if available
                        self.play_together_proc = values[4] if len(values) > 4 else ""
                        self.play_together_name = values[5] if len(values) > 5 else "PLAY TOGETHER"
                        
                        self.play_together_rect = QRect(left, top, width, height)
                        print(f"Found game window: {self.play_together_name} ({self.play_together_proc}) at {left},{top} size {width}x{height}")
                        return True
                except Exception as e:
                    print(f"Error parsing window dimensions: {e}")
                    
            # Alternative approach - try to list all windows for debugging
            script2 = '''
            tell application "System Events"
                set allWindows to {}
                repeat with proc in application processes
                    set procName to name of proc
                    repeat with w in windows of proc
                        set winName to name of w
                        set entry to procName & ": " & winName
                        set allWindows to allWindows & entry & return
                    end repeat
                end repeat
                return allWindows
            end tell
            '''
            
            result2 = subprocess.run(['osascript', '-e', script2], capture_output=True, text=True, check=False)
            print(f"Available windows: {result2.stdout}")
            
            return False
        except Exception as e:
            print(f"Error finding PLAY TOGETHER window: {e}")
            return False
    
    def position_on_play_together(self):
        """Position the selection box centered on the PLAY TOGETHER window"""
        if self.play_together_rect is not None:
            # Center the box on the game window
            center_x = self.play_together_rect.left() + self.play_together_rect.width() // 2
            center_y = self.play_together_rect.top() + self.play_together_rect.height() // 2
            
            # Position the box
            self.box_rect.moveCenter(QPoint(center_x, center_y))
            
            # Ensure box stays within screen bounds
            self.constrain_box_to_screen()
            
            # Update the display
            self.update()
            
    def showEvent(self, event):
        """Ensure window is on top when shown"""
        super().showEvent(event)
        self.activateWindow()
        self.raise_()
        
        # Use Apple Script to ensure window focus (for macOS)
        try:
            script = '''
            tell application "System Events" 
                set frontmost of every process whose unix id is %d to true
            end tell
            ''' % os.getpid()
            subprocess.run(['osascript', '-e', script], check=True)
        except Exception as e:
            print(f"Error focusing window: {e}")
        
    def paintEvent(self, event):
        """Draw the selection overlay with modern macOS theme"""
        painter = QPainter(self)
        
        # Set up rendering hints for better quality
        painter.setRenderHints(QPainter.RenderHint.SmoothPixmapTransform | 
                             QPainter.RenderHint.Antialiasing)
        
        # Draw the captured screen background
        if hasattr(self, 'background_pixmap') and self.background_pixmap is not None:
            target_rect = self.rect()
            painter.drawPixmap(target_rect, self.background_pixmap, 
                             QRect(0, 0, self.background_pixmap.width(), self.background_pixmap.height()))
            
            # Apply a slight darkening overlay
            painter.fillRect(target_rect, QColor(25, 25, 25, 100))  # Dark overlay
        else:
            # Fallback to a semi-transparent background if no screenshot
            painter.fillRect(self.rect(), self.colors['bg_overlay'])
        
        # Highlight PLAY TOGETHER window if found
        if self.play_together_rect is not None:
            play_together_highlight = QRect(
                self.play_together_rect.left(),
                self.play_together_rect.top(),
                self.play_together_rect.width(),
                self.play_together_rect.height()
            )
            painter.fillRect(play_together_highlight, QColor(10, 132, 255, 30))  # Blue highlight
            painter.setPen(QPen(self.colors['accent_blue'], 2, Qt.PenStyle.DashLine))
            painter.drawRect(play_together_highlight)
            
            # Display a label identifying the window
            game_label_rect = QRect(
                self.play_together_rect.left(), 
                self.play_together_rect.top() - 30,
                self.play_together_rect.width(), 
                30
            )
            painter.fillRect(game_label_rect, QColor(53, 54, 57, 220))  # Dark background
            painter.setPen(self.colors['accent_blue'])
            painter.setFont(QFont("Helvetica", 10, QFont.Weight.Medium))
            painter.drawText(game_label_rect, Qt.AlignmentFlag.AlignCenter, "PLAY TOGETHER WINDOW")
        
        # Draw dimmed rectangle around the selection area to highlight it
        # Create four rectangles to cover all areas except the selection
        # Top area
        painter.fillRect(
            QRect(0, 0, self.screen_width, self.box_rect.top()),
            QColor(25, 25, 25, 150)  # Dark with transparency
        )
        # Bottom area
        painter.fillRect(
            QRect(0, self.box_rect.bottom() + 1, self.screen_width, self.screen_height - self.box_rect.bottom() - 1),
            QColor(25, 25, 25, 150)
        )
        # Left area
        painter.fillRect(
            QRect(0, self.box_rect.top(), self.box_rect.left(), self.box_rect.height()),
            QColor(25, 25, 25, 150)
        )
        # Right area
        painter.fillRect(
            QRect(self.box_rect.right() + 1, self.box_rect.top(), 
                  self.screen_width - self.box_rect.right() - 1, self.box_rect.height()),
            QColor(25, 25, 25, 150)
        )
        
        # Draw crosshairs - blue accent
        painter.setPen(QPen(self.colors['accent_blue'], 1, Qt.PenStyle.DashLine))
        painter.drawLine(0, self.mouse_pos.y(), self.screen_width, self.mouse_pos.y())
        painter.drawLine(self.mouse_pos.x(), 0, self.mouse_pos.x(), self.screen_height)
        
        # Ensure box stays within screen bounds
        self.constrain_box_to_screen()
        
        # Draw selection box border - blue accent
        outer_pen = QPen(self.colors['accent_blue'], 2)
        painter.setPen(outer_pen)
        painter.drawRoundedRect(self.box_rect, 10, 10)  # Rounded corners
        
        # Add a second, inner border for better visibility
        inner_rect = QRect(
            self.box_rect.left() + 3, 
            self.box_rect.top() + 3, 
            self.box_rect.width() - 6, 
            self.box_rect.height() - 6
        )
        painter.setPen(QPen(self.colors['accent_blue_light'], 1))
        painter.drawRoundedRect(inner_rect, 8, 8)  # Rounded corners
        
        # Draw semi-transparent fill
        painter.fillRect(self.box_rect, QColor(10, 132, 255, 15))  # Very light blue
        
        # Draw grid lines
        painter.setPen(QPen(self.colors['accent_blue_light'], 1, Qt.PenStyle.DashLine))
        # Vertical grid lines
        cell_width = self.box_width // 3
        for i in range(1, 3):
            painter.drawLine(
                self.box_rect.left() + i * cell_width, self.box_rect.top(),
                self.box_rect.left() + i * cell_width, self.box_rect.bottom()
            )
        # Horizontal grid lines
        cell_height = self.box_height // 3
        for i in range(1, 3):
            painter.drawLine(
                self.box_rect.left(), self.box_rect.top() + i * cell_height,
                self.box_rect.right(), self.box_rect.top() + i * cell_height
            )
        
        # Draw coordinates with macOS-style pill background
        coord_text = f"Position: ({self.box_rect.left()},{self.box_rect.top()}) • Size: {self.box_width}×{self.box_height}"
        text_width = 400
        text_height = 30
        
        # Create pill background
        coord_rect = QRect(
            (self.screen_width - text_width) // 2,
            self.screen_height - 50, 
            text_width, 
            text_height
        )
        
        # Draw background pill
        path = QPainterPath()
        path.addRoundedRect(QRectF(coord_rect), 15, 15)
        painter.fillPath(path, QColor(53, 54, 57, 220))  # Dark background
        
        # Draw text
        painter.setPen(self.colors['text'])
        painter.setFont(QFont("Helvetica", 11, QFont.Weight.Medium))
        painter.drawText(
            coord_rect, 
            Qt.AlignmentFlag.AlignCenter, 
            coord_text
        )
        
    def mouseMoveEvent(self, event):
        """Track mouse movement for dragging or positioning the box"""
        self.mouse_pos = event.pos()
        
        if self.is_dragging:
            # Move the box with the mouse
            dx = event.pos().x() - self.drag_start_pos.x()
            dy = event.pos().y() - self.drag_start_pos.y()
            
            self.box_rect.moveTopLeft(self.box_start_pos + QPoint(dx, dy))
        else:
            # Center box on cursor when not dragging
            self.box_rect = QRect(
                self.mouse_pos.x() - self.box_width // 2,
                self.mouse_pos.y() - self.box_height // 2,
                self.box_width,
                self.box_height
            )
            
        self.update()  # Redraw
        
    def mousePressEvent(self, event):
        """Start dragging when mouse pressed"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Check if click is inside box
            if self.box_rect.contains(event.pos()):
                self.is_dragging = True
                self.drag_start_pos = event.pos()
                self.box_start_pos = self.box_rect.topLeft()
            else:
                # Center box on click position
                self.box_rect = QRect(
                    event.pos().x() - self.box_width // 2,
                    event.pos().y() - self.box_height // 2,
                    self.box_width,
                    self.box_height
                )
                self.is_dragging = True
                self.drag_start_pos = event.pos()
                self.box_start_pos = self.box_rect.topLeft()
                
            self.update()  # Redraw
            
    def mouseReleaseEvent(self, event):
        """Finalize selection on mouse release"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            
            # Constrain box to screen before finalizing
            self.constrain_box_to_screen()
            
            # Get the exact coordinates from the box
            left = self.box_rect.left()
            top = self.box_rect.top()
            right = self.box_rect.right() + 1  # +1 because right/bottom are inclusive
            bottom = self.box_rect.bottom() + 1
            
            # Ensure coordinates are within screen bounds and have correct dimensions
            if left < 0: left = 0
            if top < 0: top = 0
            if right > self.screen_width: right = self.screen_width
            if bottom > self.screen_height: bottom = self.screen_height
            
            # Debug output
            print(f"Selected region: ({left}, {top}, {right}, {bottom})")
            print(f"Dimensions: {right-left}x{bottom-top}")
            
            # Emit signal with selected region
            region = (left, top, right, bottom)
            self.region_selected.emit(region)
            self.accept()
    
    def constrain_box_to_screen(self):
        """Ensure the box stays within screen bounds"""
        # Get current position
        left = self.box_rect.left()
        top = self.box_rect.top()
        
        # Adjust for screen boundaries
        if left < 0:
            left = 0
        elif left + self.box_width > self.screen_width:
            left = self.screen_width - self.box_width
            
        if top < 0:
            top = 0
        elif top + self.box_height > self.screen_height:
            top = self.screen_height - self.box_height
            
        # Update rectangle position
        self.box_rect = QRect(left, top, self.box_width, self.box_height)
            
    def keyPressEvent(self, event):
        """Handle key presses"""
        if event.key() == Qt.Key.Key_Escape:
            self.reject() 