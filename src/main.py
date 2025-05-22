#!/usr/bin/env python3
import sys
from PyQt6.QtWidgets import QApplication
from src.ui.main_window import PixelChangeApp

def main():
    """Main entry point for the application"""
    app = QApplication(sys.argv)
    window = PixelChangeApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 