"""
Play Together window find + client-area screen capture.

Detection / bite logic removed — preview and session controls only.
"""
from __future__ import annotations

import datetime
import threading
import time
from typing import Optional, Tuple

import mss
import numpy as np
from PyQt6.QtCore import QObject

from utils.constants import (
    DEFAULT_DETECTION_COOLDOWN,
    DEFAULT_EXCLAMATION_MATCH,
    DEFAULT_FISHING_KEY,
)
from utils.coords import get_client_area_screen_rect
from utils.input import send_esc, send_key_press
from utils.win32_utils import find_play_together_window, force_focus_window, user32

ClientRect = Tuple[int, int, int, int]


class GameCapture(QObject):
    """Game window + MSS capture for the overlay UI."""

    def __init__(self, log_queue=None, parent=None):
        super().__init__(parent)
        self.log_queue = log_queue
        self.gui = None

        self.match_threshold = DEFAULT_EXCLAMATION_MATCH
        self.detection_cooldown = DEFAULT_DETECTION_COOLDOWN
        self.fishing_key = DEFAULT_FISHING_KEY
        self.geometry_min = 0.42

        self.is_running = False
        self.region: Optional[ClientRect] = None
        self.respect_fullscreen = True
        self.current_frame: Optional[np.ndarray] = None

        self.play_together_window: Optional[int] = None
        self.play_together_pid: Optional[int] = None
        self.client_rect: Optional[ClientRect] = None

        self.stats = {
            "total_detections": 0,
            "session_start_time": time.time(),
            "last_detection_time": 0,
            "avg_detection_interval": 0,
        }

        self.thread_control = {
            "running": False,
            "paused": False,
            "stop_requested": False,
        }

        self._capture_lock = threading.Lock()
        self._mss = mss.mss()
        self._capture_count = 0
        self._last_window_scan = 0.0
        self._window_scan_interval = 2.5

        self.find_play_together_process()

    def log(self, message: str) -> None:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted = f"[{timestamp}] {message}"
        if self.log_queue:
            self.log_queue.put(formatted)
        else:
            print(formatted)

    def find_play_together_process(self, *, force: bool = False) -> bool:
        now = time.time()
        if (
            not force
            and self.play_together_window
            and (now - self._last_window_scan) < self._window_scan_interval
        ):
            return True

        self._last_window_scan = now
        prev = self.play_together_window
        self.play_together_window, self.play_together_pid = find_play_together_window()
        if self.play_together_window:
            self._update_client_rect()
            if force or self.play_together_window != prev:
                self.log(f"Found Play Together window (HWND: {self.play_together_window})")
        elif force or prev:
            self.log("No Play Together window found. Please make sure the game is running.")
        return self.play_together_window is not None

    def _update_client_rect(self) -> None:
        self.client_rect = get_client_area_screen_rect(self.play_together_window)
        if self.client_rect:
            l, t, r, b = self.client_rect
            self.region = (l, t, r, b)

    def _exclude_hwnds(self) -> list:
        hwnds = []
        if self.gui and hasattr(self.gui, "winId"):
            try:
                hwnds.append(int(self.gui.winId()))
            except Exception:
                pass
        return hwnds

    def focus_play_together_window(self) -> bool:
        if not self.play_together_window and not self.find_play_together_process():
            return False
        try:
            import win32gui

            if not win32gui.IsWindow(self.play_together_window):
                if not self.find_play_together_process():
                    return False
            user32.SetForegroundWindow(self.play_together_window)
            time.sleep(0.05)
            if user32.GetForegroundWindow() == self.play_together_window:
                return True
            return force_focus_window(self.play_together_window)
        except Exception as e:
            self.log(f"Error focusing window: {e}")
            return False

    def send_fishing_key(self) -> bool:
        return send_key_press(
            self.fishing_key,
            self.play_together_window,
            respect_fullscreen=self.respect_fullscreen,
            exclude_hwnds=self._exclude_hwnds(),
        )

    def send_esc_key(self) -> bool:
        return send_esc(
            self.play_together_window,
            respect_fullscreen=self.respect_fullscreen,
            exclude_hwnds=self._exclude_hwnds(),
        )

    def capture_client_frame(self) -> Optional[np.ndarray]:
        with self._capture_lock:
            if not self.play_together_window:
                self.find_play_together_process()
            if self._capture_count % 45 == 0:
                self._update_client_rect()
            self._capture_count += 1
            if not self.client_rect:
                return None
            try:
                l, t, r, b = self.client_rect
                w, h = r - l, b - t
                if w < 10 or h < 10:
                    return None
                frame = np.array(
                    self._mss.grab({"left": l, "top": t, "width": w, "height": h})
                )
                if frame.size == 0:
                    return None
                self.current_frame = frame
                return frame
            except Exception as e:
                self.log(f"Error capturing client: {e}")
                return None

    def capture_screen(self) -> Optional[np.ndarray]:
        return self.capture_client_frame()

    def start_session(self, thread_control=None) -> bool:
        if not self.find_play_together_process():
            self.log("Cannot start: Play Together window not found")
            return False
        if not self.client_rect:
            self.log("Cannot start: game client area not available")
            return False

        self.is_running = True
        self.stats["session_start_time"] = time.time()
        self.thread_control = thread_control or {
            "running": True,
            "paused": False,
            "stop_requested": False,
        }
        self.log("Session started — live preview only (no bite detection yet)")
        return True

    def stop_session(self) -> None:
        self.is_running = False
        if self.thread_control:
            self.thread_control["stop_requested"] = True
        self.log("Session stopped")

    # Aliases used by overlay / fishing_actions from the old detector API
    def start_detection(self, thread_control=None) -> bool:
        return self.start_session(thread_control)

    def stop_detection(self) -> None:
        self.stop_session()

    def on_after_recast(self) -> None:
        self.log("Ready for next cast")
