#!/usr/bin/env python3
"""
AutoFisher — bite detection via the in-game exclamation mark.
Watches the full Play Together client area (no region selection).

Run:
  python main.py
  python program_alert.py
"""
import sys

if sys.platform == "win32":
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.overlay_window import OverlayAutoFisher
from utils.constants import ALERT_VERSION, ALERT_VERSION_NAME


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    window = OverlayAutoFisher()
    window.show()
    window.add_log(f"AutoFisher Alert v{ALERT_VERSION} — {ALERT_VERSION_NAME}")
    window.add_log("Open Play Together, cast your line, then press Start")
    window.add_log("Live preview: game view + raw zone + zone zoom")
    window.add_log("Detection zone: 80% size, centered")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
