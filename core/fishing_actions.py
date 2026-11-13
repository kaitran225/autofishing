"""Shared catch → pause → ESC → recast sequence (prototype timing)."""
import time

from PyQt6.QtCore import QTimer


def run_fishing_sequence(detector) -> None:
    """Run bite handling on *detector* (GameCapture session)."""
    try:
        if detector.focus_play_together_window():
            detector.log(f"Pressing {detector.fishing_key.upper()} key to catch fish...")
            detector.send_fishing_key()
            time.sleep(0.2)
        else:
            detector.log("Failed to focus window, skipping key press")

        cooldown = detector.detection_cooldown
        detector.log(f"Pausing detection for {cooldown:.1f} seconds...")
        time.sleep(min(2.0, cooldown / 2))

        pause_end = time.time() + cooldown
        while (
            time.time() < pause_end
            and detector.is_running
            and not detector.thread_control.get("stop_requested", False)
        ):
            remaining = int(pause_end - time.time())
            gui = detector.gui
            if gui and hasattr(gui, "status_label") and gui.status_label:
                QTimer.singleShot(
                    0,
                    lambda r=remaining: gui.status_label.setText(f"Paused ({r}s)"),
                )
            time.sleep(0.1)

        if detector.is_running and not detector.thread_control.get("stop_requested", False):
            detector.log("Pressing ESC key to exit fishing menu...")
            if detector.focus_play_together_window():
                detector.send_esc_key()
            else:
                detector.log("Failed to focus window, skipping ESC key press")

        esc_end = time.time() + 2
        while (
            time.time() < esc_end
            and detector.is_running
            and not detector.thread_control.get("stop_requested", False)
        ):
            time.sleep(0.1)

        if detector.is_running and not detector.thread_control.get("stop_requested", False):
            detector.log(f"Pressing {detector.fishing_key.upper()} key to cast fishing line...")
            if detector.focus_play_together_window():
                detector.send_fishing_key()
                time.sleep(2)
            else:
                detector.log("Failed to focus window, skipping fishing cast")
            if hasattr(detector, "on_after_recast"):
                detector.on_after_recast()

        gui = detector.gui
        if gui and detector.is_running and not detector.thread_control.get("stop_requested", False):
            if hasattr(gui, "set_status_indicator"):
                QTimer.singleShot(0, lambda: gui.set_status_indicator("running"))

        time.sleep(min(2.0, detector.detection_cooldown * 0.2))
    except Exception as e:
        detector.log(f"Error handling detection: {e}")
        gui = detector.gui
        if gui and hasattr(gui, "set_status_indicator"):
            QTimer.singleShot(0, lambda: gui.set_status_indicator("running"))
