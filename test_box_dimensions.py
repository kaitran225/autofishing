import sys
from PyQt6.QtWidgets import QApplication, QDialog, QLabel
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

class TestOverlay(QDialog):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        
        # Set fixed box dimensions to 50x75 (height x width)
        self.box_height = 50
        self.box_width = 75
        
        # Get screen dimensions
        screen = QApplication.primaryScreen()
        geometry = screen.availableGeometry()
        self.screen_width = geometry.width()
        self.screen_height = geometry.height()
        
        # Set window size
        self.setGeometry(0, 0, self.screen_width, self.screen_height)
        
        # Create info label
        self.info_label = QLabel(f"Box dimensions: {self.box_width}×{self.box_height}", self)
        self.info_label.setStyleSheet("background-color: rgba(0, 0, 0, 180); color: white; padding: 5px;")
        self.info_label.adjustSize()
        self.info_label.move((self.screen_width - self.info_label.width()) // 2, self.screen_height - 50)
        
        self.current_x = self.screen_width // 2
        self.current_y = self.screen_height // 2
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw semi-transparent background
        painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, 0, self.width(), self.height())
        
        # Draw selection box
        left = int(self.current_x - self.box_width / 2)
        top = int(self.current_y - self.box_height / 2)
        
        # Draw box
        painter.setPen(QPen(QColor(0, 255, 0), 2))
        painter.setBrush(QBrush(QColor(0, 255, 0, 50)))
        painter.drawRect(left, top, self.box_width, self.box_height)
        
        # Draw dimensions text
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(left + 5, top + 20, f"{self.box_width}×{self.box_height}")
        
        painter.end()
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    overlay = TestOverlay()
    overlay.show()
    sys.exit(app.exec())
