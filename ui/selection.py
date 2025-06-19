"""
Region selection functionality for the autofisher application
"""
import time
import cv2
import numpy as np
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRect, QPoint, QRectF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPixmap, QImage, QCursor, QPainterPath, QFont

# Import tkinter for the legacy selector (matches reference implementation)
import tkinter as tk
import win32gui
import mss
import mss.tools

class TkRegionSelector:
    """
    Region selector that uses tkinter, following the reference implementation
    """
    def __init__(self, parent, size=50):
        """
        Initialize a region selector using tkinter
        
        Args:
            parent: The parent window/object that will receive callbacks
            size: The height of the region (width will be size * 1.5)
        """
        self.parent = parent
        self.height = size
        self.width = int(size * 1.5)
        self.region = None  # Selected region (x1, y1, x2, y2)
        self._configure_colors()
        
    def _configure_colors(self):
        """Configure the colors for the selection UI"""
        # These colors match the matcha theme
        self.colors = {
            'bg_dark': '#181914',         # Oak wood dark
            'accent': '#A3D977',          # Matcha green
            'green': '#A3D977',           # Matcha green
            'text_bright': '#FFFFFF',     # White text
            'text': '#F8F5E3',            # Warm off-white
            'border': '#6B6E58',          # Border color
        }
        
    def select_region(self, window_hwnd=None):
        """
        Start the region selection process
        
        Args:
            window_hwnd: Window handle for the game window
            
        Returns:
            tuple: (x1, y1, x2, y2) coordinates of selected region, or None if cancelled
        """
        print("Starting region selection using tkinter...")
        
        # If no window handle provided, find the Play Together window
        if window_hwnd is None:
            # Import here to avoid circular imports
            from utils.win32_utils import find_window_by_pattern
            from utils.constants import GAME_WINDOW_NAMES
            window_hwnd = find_window_by_pattern(GAME_WINDOW_NAMES)
            if not window_hwnd:
                print("Cannot select region: No target window found")
                return None
        
        # Get window position and size
        try:
            window_rect = win32gui.GetWindowRect(window_hwnd)
            win_left, win_top, win_right, win_bottom = window_rect
            win_width = win_right - win_left
            win_height = win_bottom - win_top
            
            # Get the client area (actual game content area)
            client_rect = win32gui.GetClientRect(window_hwnd)
            client_left, client_top, client_right, client_bottom = client_rect
            
            # Convert client coordinates to screen coordinates
            client_left, client_top = win32gui.ClientToScreen(window_hwnd, (client_left, client_top))
            client_right, client_bottom = win32gui.ClientToScreen(window_hwnd, (client_right, client_bottom))
            
            # Use client area dimensions for more accurate game content area
            game_width = client_right - client_left
            game_height = client_bottom - client_top
            
            print(f"Game window found: {win_width}x{win_height} at ({win_left},{win_top})")
            print(f"Game content area: {game_width}x{game_height} at ({client_left},{client_top})")
        except Exception as e:
            print(f"Error getting window dimensions: {e}")
            return None
            
        # Check if window is valid size
        if game_width < 50 or game_height < 50:
            print(f"Game window too small: {game_width}x{game_height}")
            return None
            
        # Minimize any Qt parent window if we have one
        if hasattr(self.parent, 'showMinimized'):
            self.parent.showMinimized()
            time.sleep(0.2)  # Give time for window to minimize
            
        # Create a transparent tkinter window for selection
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        selection_window = tk.Toplevel(root)
        selection_window.geometry(f"{game_width}x{game_height}+{client_left}+{client_top}")
        selection_window.attributes('-alpha', 0.2)
        selection_window.attributes('-topmost', True)
        selection_window.overrideredirect(True)  # Remove window decorations
        selection_window.configure(bg=self.colors['bg_dark'])
        
        # Create canvas for drawing
        canvas = tk.Canvas(selection_window, cursor="cross", bg=self.colors['bg_dark'], 
                          highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)
        
        # Variables to track selection
        preview_rect = None
        outline_rect = None
        grid_lines = []
        info_text = None
        result = [None]  # Use list to store result from callbacks
        
        def update_preview(event):
            nonlocal preview_rect, outline_rect, grid_lines, info_text
            
            # Calculate region coordinates centered on mouse position
            left = event.x - self.width // 2
            top = event.y - self.height // 2
            right = left + self.width
            bottom = top + self.height
            
            # Ensure region stays within game window bounds
            if left < 0:
                left = 0
                right = self.width
            elif right > game_width:
                right = game_width
                left = right - self.width
                
            if top < 0:
                top = 0
                bottom = self.height
            elif bottom > game_height:
                bottom = game_height
                top = bottom - self.height
            
            # Clear previous shapes
            if preview_rect:
                canvas.delete(preview_rect)
            if outline_rect:
                canvas.delete(outline_rect)
            for line in grid_lines:
                canvas.delete(line)
            grid_lines = []
            if info_text:
                canvas.delete(info_text)
            
            # Draw a clean, minimal border (slightly larger for visibility)
            outline_rect = canvas.create_rectangle(
                left-2, top-2, right+2, bottom+2,
                outline=self.colors['accent'], width=2
            )
            
            # Draw the inner rectangle with minimal styling
            preview_rect = canvas.create_rectangle(
                left, top, right, bottom,
                outline=self.colors['green'], width=1,
                fill=self.colors['accent'], stipple="gray12"  # Sparse fill
            )
            
            # Add grid lines (3x3 grid)
            cell_width = self.width // 3
            cell_height = self.height // 3
            
            # Vertical grid lines
            for i in range(1, 3):
                line = canvas.create_line(
                    left + i * cell_width, top,
                    left + i * cell_width, bottom,
                    fill=self.colors['green'], width=1, dash=(2, 2)
                )
                grid_lines.append(line)
                
            # Horizontal grid lines
            for i in range(1, 3):
                line = canvas.create_line(
                    left, top + i * cell_height,
                    right, top + i * cell_height,
                    fill=self.colors['green'], width=1, dash=(2, 2)
                )
                grid_lines.append(line)
            
            # Create coordinate display with more information
            # Convert to absolute screen coordinates
            abs_left = client_left + left
            abs_top = client_top + top
            coord_text = f"position: ({abs_left},{abs_top}) • size: {self.width}×{self.height}"
            
            # Display information at the bottom center
            info_text = canvas.create_text(
                game_width // 2, game_height - 30,
                text=coord_text,
                fill=self.colors['text_bright'],
                font=("Segoe UI", 10)
            )
            
        def on_mouse_click(event):
            nonlocal preview_rect, outline_rect, grid_lines, result
            
            # Calculate region coordinates centered on mouse position
            left = event.x - self.width // 2
            top = event.y - self.height // 2
            right = left + self.width
            bottom = top + self.height
            
            # Ensure region stays within game window bounds
            if left < 0:
                left = 0
                right = self.width
            elif right > game_width:
                right = game_width
                left = right - self.width
                
            if top < 0:
                top = 0
                bottom = self.height
            elif bottom > game_height:
                bottom = game_height
                top = bottom - self.height
            
            # Convert to absolute screen coordinates
            abs_left = client_left + left
            abs_top = client_top + top
            abs_right = client_left + right
            abs_bottom = client_top + bottom
            
            # Store result as absolute screen coordinates
            result[0] = (abs_left, abs_top, abs_right, abs_bottom)
            
            # Close selection window
            selection_window.destroy()
            
        def on_escape(event):
            """Handle ESC key to cancel selection"""
            selection_window.destroy()
        
        # Bind events
        canvas.bind("<Motion>", update_preview)  # Update preview on mouse move
        canvas.bind("<ButtonPress-1>", on_mouse_click)
        selection_window.bind("<Escape>", on_escape)
        
        # Add instructions header
        instructions_frame = tk.Frame(
            canvas,
            bg=self.colors['bg_dark'],
            highlightbackground=self.colors['accent'],
            highlightthickness=1,
            padx=15,
            pady=10
        )
        
        instruction_label = tk.Label(
            instructions_frame,
            text="SELECT REGION • CLICK TO PLACE • ESC TO CANCEL",
            font=("Segoe UI", 11, "bold"),
            fg=self.colors['green'],
            bg=self.colors['bg_dark']
        )
        instruction_label.pack()
        
        # Add second line of instructions
        detail_label = tk.Label(
            instructions_frame,
            text=f"Region size: {self.width}×{self.height} pixels • Move mouse to position",
            font=("Segoe UI", 10),
            fg=self.colors['text'],
            bg=self.colors['bg_dark']
        )
        detail_label.pack()
        
        # Place instruction frame at top center
        canvas.create_window(game_width // 2, 50, window=instructions_frame)
        
        # Add crosshair guides for center positioning
        canvas.create_line(
            0, game_height // 2,
            game_width, game_height // 2,
            fill=self.colors['accent'], width=1, dash=(8, 8)
        )
        
        canvas.create_line(
            game_width // 2, 0,
            game_width // 2, game_height,
            fill=self.colors['accent'], width=1, dash=(8, 8)
        )
        
        # Wait for selection (this is a blocking operation)
        root.wait_window(selection_window)
        
        # Destroy the root window when done
        root.destroy()
        
        # Restore parent window if it's Qt
        if hasattr(self.parent, 'showNormal'):
            self.parent.showNormal()
            
        return result[0]
        
    def capture_preview(self, region):
        """
        Capture a preview of the selected region
        
        Args:
            region: (x1, y1, x2, y2) coordinates
            
        Returns:
            numpy.ndarray: The captured image
        """
        if not region:
            return None
            
        x1, y1, x2, y2 = region
        width = x2 - x1
        height = y2 - y1
        
        try:
            # Use mss for fast screen capture
            with mss.mss() as sct:
                # Convert region format to mss format (left, top, width, height)
                mss_region = {
                    "left": x1,
                    "top": y1,
                    "width": width,
                    "height": height
                }
                
                # Capture the region
                screenshot = sct.grab(mss_region)
                
                # Convert to numpy array
                frame = np.array(screenshot)
                
                # Convert to RGB (from BGRA)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                
                return rgb_frame
        except Exception as e:
            print(f"Error capturing preview: {e}")
            return None
            
    def capture_preview_and_select(self):
        """
        Start the selection process and capture a preview if successful
        
        Returns:
            tuple: (x1, y1, x2, y2) coordinates of selected region, or None if cancelled
        """
        # Select the region
        region = self.select_region()
        
        # If region was selected successfully, store it
        if region:
            self.region = region
            # Try to capture a preview
            preview = self.capture_preview(region)
            if preview is not None:
                print(f"Preview captured: {preview.shape}")
        
        return region

# Keep the original RegionSelectionOverlay for compatibility
class RegionSelectionOverlay(QWidget):
    """Overlay widget for selecting a region of the screen"""
    
    region_selected = pyqtSignal(tuple)  # Signal emitted when region is selected
    selection_canceled = pyqtSignal()    # Signal emitted when selection is canceled
    selection_finished = pyqtSignal()    # Signal emitted when selection is finished (either selected or canceled)
    
    def __init__(self, window_geometry, parent=None):
        super().__init__(parent)
        print(f"RegionSelectionOverlay init with geometry: {window_geometry}")
        
        # Store the target window geometry
        self.target_window_geometry = window_geometry
        
        # Set overlay to be frameless and always on top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # Add Tool flag to avoid taskbar button
        )
        
        # Allow the widget to capture mouse events outside its area
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)  # Ensure it activates
        
        # Initialize selection state
        self.selecting = False
        self.selection_start = QPoint(0, 0)
        self.selection_end = QPoint(0, 0)
        self.current_cursor_pos = QPoint(0, 0)
        
        # Region size for the fixed size selection (will be set by caller)
        self.region_size = (75, 50)  # Default width, height
        
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
        
        print("RegionSelectionOverlay initialization complete")
        
    def showEvent(self, event):
        """When widget is shown, start animation timers"""
        print("RegionSelectionOverlay showEvent")
        super().showEvent(event)
        self.pulse_timer.start()
        self.cursor_timer.start()
        self.preview_timer.start()
        self.check_position()
        print(f"Current geometry: {self.geometry()}")
        print(f"Is visible: {self.isVisible()}")
        
    def closeEvent(self, event):
        """When widget is closed, emit the selection_finished signal"""
        print("RegionSelectionOverlay closeEvent")
        self.selection_finished.emit()
        super().closeEvent(event)
        
    def check_position(self):
        """Check that the overlay is properly positioned over the target window"""
        print("Checking overlay position")
        # If we have a target window geometry, ensure overlay covers it
        if self.target_window_geometry and all(self.target_window_geometry):
            left, top, width, height = self.target_window_geometry
            print(f"Setting geometry to match target: {left}, {top}, {width}, {height}")
            self.setGeometry(left, top, width, height)
        else:
            # Otherwise, cover the entire screen
            desktop = self.screen().virtualGeometry()
            print(f"Setting geometry to cover screen: {desktop}")
            self.setGeometry(desktop)
        print(f"Final geometry: {self.geometry()}")
        
    def update_preview(self):
        """Update the preview image based on current selection"""
        # Don't print anything here as it runs frequently
        if not self.selecting:
            return
            
        # Calculate selection rect based on cursor position and fixed region size
        width, height = self.region_size
        x = self.current_cursor_pos.x() - width // 2
        y = self.current_cursor_pos.y() - height // 2
            
        # If we have a valid selection rectangle
        if width > 0 and height > 0:
            try:
                # Ensure coordinates are within window bounds
                x1 = max(0, x)
                y1 = max(0, y)
                x2 = min(self.width(), x1 + width)
                y2 = min(self.height(), y1 + height)
                
                if x2 - x1 > 10 and y2 - y1 > 10:  # Minimum size check
                    # Convert to screen coordinates
                    if self.target_window_geometry:
                        win_left, win_top, _, _ = self.target_window_geometry
                        screen_x1 = win_left + x1
                        screen_y1 = win_top + y1
                        screen_x2 = win_left + x2
                        screen_y2 = win_top + y2
                    else:
                        screen_x1, screen_y1 = x1, y1
                        screen_x2, screen_y2 = x2, y2
                        
                    # Capture screen region
                    import mss
                    with mss.mss() as sct:
                        # Convert region format for mss
                        region = {
                            "left": screen_x1,
                            "top": screen_y1,
                            "width": screen_x2 - screen_x1,
                            "height": screen_y2 - screen_y1
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
        width, height = self.region_size
        self.current_cursor_pos = self.mapFromGlobal(QCursor.pos())
        
        # Calculate box coordinates centered on cursor
        x = self.current_cursor_pos.x() - width // 2
        y = self.current_cursor_pos.y() - height // 2
        
        # Ensure coordinates are within window bounds
        x = max(0, min(self.width() - width, x))
        y = max(0, min(self.height() - height, y))
        
        self.selection_start = QPoint(x, y)
        self.selection_end = QPoint(x + width, y + height)
            
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
        self.update_current_box()
            
    def mouseMoveEvent(self, event):
        """Handle mouse movement to update selection position"""
        print(f"Mouse move at {event.pos()}")
        self.current_cursor_pos = event.pos()
        self.update_current_box()
        
    def mousePressEvent(self, event):
        """Handle mouse press to confirm selection or cancel"""
        print(f"Mouse press at {event.pos()}, button: {event.button()}")
        if event.button() == Qt.MouseButton.LeftButton:
            self.finalize_selection()
        elif event.button() == Qt.MouseButton.RightButton:
            # Cancel selection
            print("Selection canceled by right-click")
            self.selection_canceled.emit()
            self.selection_finished.emit()
            self.close()
            
    def keyPressEvent(self, event):
        """Handle key presses for ESC to cancel"""
        print(f"Key press: {event.key()}")
        if event.key() == Qt.Key.Key_Escape:
            print("Selection canceled by ESC key")
            self.selection_canceled.emit()
            self.selection_finished.emit()
            self.close()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.finalize_selection()
            
    def mouseReleaseEvent(self, event):
        """Handle mouse release events (not used in fixed size mode)"""
        print(f"Mouse release at {event.pos()}")
        pass
            
    def finalize_selection(self):
        """Complete the selection and emit coordinates"""
        # Get final selection coordinates
        x1 = self.selection_start.x()
        y1 = self.selection_start.y()
        x2 = self.selection_end.x() 
        y2 = self.selection_end.y()
        
        print(f"Finalizing selection: ({x1}, {y1}) to ({x2}, {y2})")
        
        # Check if selection is valid (minimum size)
        if x2 - x1 > 10 and y2 - y1 > 10:
            # Convert to absolute screen coordinates if we have target window info
            if self.target_window_geometry:
                win_left, win_top, _, _ = self.target_window_geometry
                x1 += win_left
                y1 += win_top
                x2 += win_left
                y2 += win_top
                
            print(f"Emitting final selection: ({x1}, {y1}) to ({x2}, {y2})")
            # Emit the selected region coordinates
            self.region_selected.emit((x1, y1, x2, y2))
            self.selection_finished.emit()
            self.close()
        else:
            print("Selection too small, ignoring")
                
    def paintEvent(self, event):
        """Draw the overlay with selection rectangle"""
        # Don't print here as it runs frequently
        painter = QPainter(self)
        
        # Create semi-transparent dark overlay for the entire area
        overlay_color = QColor(0, 0, 0, 150)
        painter.fillRect(self.rect(), overlay_color)
        
        # Draw fixed size selection rectangle
        # Get selection coordinates
        x1 = self.selection_start.x()
        y1 = self.selection_start.y()
        x2 = self.selection_end.x() 
        y2 = self.selection_end.y()
        
        selection_width = x2 - x1
        selection_height = y2 - y1
        
        # Calculate coordinates for screen conversion display
        screen_x1, screen_y1 = x1, y1
        if self.target_window_geometry:
            win_left, win_top, _, _ = self.target_window_geometry
            screen_x1 += win_left
            screen_y1 += win_top
        
        # Draw the selection area (clear)
        selection_rect = QRect(x1, y1, selection_width, selection_height)
        painter.fillRect(selection_rect, QBrush(Qt.GlobalColor.transparent))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(selection_rect, QBrush(Qt.GlobalColor.white))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        
        # Draw the selection rectangle borders (outer border plus inner grid)
        # Outer border with animation effect
        border_pen = QPen(QColor(119, 221, 255, int(255 * self.pulse_opacity)))
        border_pen.setWidth(2)
        painter.setPen(border_pen)
        painter.drawRect(selection_rect)
        
        # Draw inner grid (3x3)
        grid_pen = QPen(QColor(163, 217, 119, 180))  # Matcha green
        grid_pen.setWidth(1)
        grid_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(grid_pen)
        
        # Vertical grid lines
        cell_width = selection_width // 3
        for i in range(1, 3):
            painter.drawLine(
                x1 + i * cell_width, y1,
                x1 + i * cell_width, y2
            )
            
        # Horizontal grid lines
        cell_height = selection_height // 3
        for i in range(1, 3):
            painter.drawLine(
                x1, y1 + i * cell_height,
                x2, y1 + i * cell_height
            )
        
        # Draw instructions at the top of the screen
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        text_rect = QRect(0, 20, self.width(), 30)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "SELECT REGION • CLICK TO PLACE • ESC TO CANCEL")
        
        # Draw size information
        painter.setFont(QFont("Segoe UI", 9))
        size_text = f"Region size: {selection_width}×{selection_height} pixels"
        size_rect = QRect(0, 50, self.width(), 20)
        painter.drawText(size_rect, Qt.AlignmentFlag.AlignCenter, size_text)
        
        # Draw coordinates at the bottom of the screen
        coord_text = f"Position: ({screen_x1}, {screen_y1}) • Size: {selection_width}×{selection_height}"
        coord_rect = QRect(0, self.height() - 30, self.width(), 20)
        painter.drawText(coord_rect, Qt.AlignmentFlag.AlignCenter, coord_text) 