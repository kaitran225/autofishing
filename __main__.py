"""
Main entry point for the AutoFisher application.
"""
import sys
from autofisher.ui import AutoFisherApp
from PyQt5.QtWidgets import QApplication


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Apply stylesheet for a modern look
    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #f0f0f0;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #cccccc;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px;
        }
        QPushButton {
            background-color: #2a82da;
            color: white;
            border: none;
            border-radius: 3px;
            padding: 6px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #3a92ea;
        }
        QPushButton:pressed {
            background-color: #1a72ca;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            color: #888888;
        }
        QSlider::groove:horizontal {
            border: 1px solid #bbb;
            background: white;
            height: 10px;
            border-radius: 4px;
        }
        QSlider::handle:horizontal {
            background: #2a82da;
            border: 1px solid #5c5c5c;
            width: 18px;
            margin: -2px 0;
            border-radius: 3px;
        }
    """)
    
    window = AutoFisherApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main() 