import subprocess
import platform
import os
import sys
import mss
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt

def request_screen_recording_permission():
    """Explicitly request screen recording permission on macOS"""
    if platform.system() != "Darwin":  # Only needed for macOS
        return
        
    try:
        # Use AppleScript to trigger a permissions dialog
        script = '''
        tell application "System Events"
            # This will force the system to check if the app has screen recording permission
            set processInfo to get process "Finder"
            # No actual screenshot is taken here, just triggering the check
        end tell
        '''
        subprocess.run(['osascript', '-e', script], check=False, capture_output=True)
        
        # Also try TCC reset in case app is stuck in a denied state
        # This is a more aggressive approach that should only be used if other methods fail
        app_identifier = f"com.{os.path.basename(sys.argv[0])}"
        subprocess.run(['tccutil', 'reset', 'ScreenCapture', app_identifier], 
                      check=False, capture_output=True)
                      
    except Exception as e:
        print(f"Error requesting permission: {e}")


def check_screen_recording_permission():
    """Check if screen recording permission is granted and attempt to guide the user if not"""
    if platform.system() != "Darwin":  # Only needed for macOS
        return True
        
    try:
        # Try to take a small screenshot as a test
        with mss.mss() as sct:
            test_monitor = {"top": 0, "left": 0, "width": 100, "height": 100}
            test_screenshot = sct.grab(test_monitor)
            # If we got here without exception, we have permission
            return True
    except Exception as e:
        error_str = str(e).lower()
        # Check for specific permission-related errors
        if "permission" in error_str or "not allowed" in error_str or "denied" in error_str:
            return False
        else:
            # This might be some other error
            print(f"Screenshot test error: {e}")
            return False


def show_permissions_help(parent=None):
    """Show a comprehensive help dialog for fixing permissions issues"""
    help_text = """
<h3>Screen Recording Permission Troubleshooting</h3>

<p><b>Common Issue:</b> On macOS, screen recording permissions are granted to specific application bundles rather than to executables or scripts.</p>

<h4>If you're running from a packaged app (.app):</h4>
<ol>
    <li>Open <b>System Settings</b> → <b>Privacy & Security</b> → <b>Screen Recording</b></li>
    <li>Ensure the application bundle is in the list and allowed</li>
    <li>If it's not in the list:
        <ul>
            <li>Run the app once (it will fail but should appear in the list)</li>
            <li>Then enable it in the permissions list</li>
            <li>Restart the application</li>
        </ul>
    </li>
</ol>

<h4>If you're running from an IDE but packaged the app:</h4>
<p>The permission might be granted to the IDE's Python interpreter, but not to the packaged app. These are considered different applications by macOS.</p>

<h4>Advanced Troubleshooting:</h4>
<ol>
    <li>Open Terminal</li>
    <li>Reset TCC database permission for Screen Recording:
        <pre>tccutil reset ScreenCapture</pre>
    </li>
    <li>Restart your computer</li>
    <li>Run the application again, and you should get a fresh permission dialog</li>
</ol>

<h4>For Developers Packaging the App:</h4>
<p>If you're using PyInstaller or similar tools, ensure:</p>
<ul>
    <li>The app is code-signed with a valid certificate</li>
    <li>The app has the proper entitlements for screen recording</li>
    <li>The Info.plist includes usage description for screen recording:<br>
    <pre>NSScreenCaptureUsageDescription</pre></li>
</ul>
"""

    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle("Screen Recording Permission Help")
    msg_box.setText(help_text)
    msg_box.setTextFormat(Qt.TextFormat.RichText)
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.setMinimumWidth(600)
    msg_box.setMinimumHeight(400)
    
    # Apply themed styling
    msg_box.setStyleSheet("""
        QMessageBox {
            background-color: #2C2417;
            color: #F8F4E3;
        }
        QLabel {
            color: #F8F4E3;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        }
        QPushButton {
            background-color: #8DC370;
            color: #2C2417;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #A7CF90;
        }
    """)
    
    msg_box.exec() 