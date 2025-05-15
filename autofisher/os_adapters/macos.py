"""
macOS-specific implementations for screen capture, key sending, and window focus.
"""
import time
import mss
import numpy as np
import cv2
import keyboard
import subprocess


class MacOSScreenCapturer:
    """macOS implementation of screen capture functionality."""
    
    def __init__(self):
        """Initialize the screen capturer with mss."""
        self.sct = mss.mss()
    
    def capture_region(self, region):
        """Capture a specific region of the screen.
        
        Args:
            region: Dictionary with left, top, width, height
            
        Returns:
            Numpy array with captured image data
        """
        try:
            # Convert region to mss format
            monitor = {
                "left": region["left"],
                "top": region["top"],
                "width": region["width"],
                "height": region["height"]
            }
            
            # Capture the screen region
            sct_img = self.sct.grab(monitor)
            
            # Convert to numpy array in BGR format (for OpenCV)
            img = np.array(sct_img)
            return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            print(f"Error capturing screen: {e}")
            return None
    
    def get_screen_size(self):
        """Get the screen size.
        
        Returns:
            Tuple of (width, height)
        """
        monitor = self.sct.monitors[0]  # Primary monitor
        return monitor["width"], monitor["height"]
    
    def close(self):
        """Clean up resources."""
        self.sct.close()


class MacOSKeySender:
    """macOS implementation of key sending functionality."""
    
    def __init__(self):
        """Initialize the key sender."""
        self.use_applescript = False
        
        # Test if we can use AppleScript
        try:
            self._test_applescript()
            self.use_applescript = True
            print("macOS AppleScript key sender initialized")
        except Exception as e:
            print(f"AppleScript not available, falling back to keyboard module: {e}")
            self.use_applescript = False
    
    def _test_applescript(self):
        """Test if AppleScript is available.
        
        Raises:
            Exception: If AppleScript is not available
        """
        script = 'osascript -e "return \\\"AppleScript available\\\""'
        result = subprocess.run(script, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception("AppleScript not available")
    
    def send_key(self, key):
        """Send a key press to the active window.
        
        Args:
            key: The key to send (e.g., 'f', 'esc')
        """
        # Try AppleScript first for better game compatibility
        if self.use_applescript:
            try:
                self._send_key_applescript(key)
                return
            except Exception as e:
                print(f"AppleScript key send failed: {e}")
                # Fall back to keyboard module
        
        # Use the keyboard module (more compatible but less reliable for games)
        keyboard.press_and_release(key)
    
    def _send_key_applescript(self, key):
        """Send a key using AppleScript for better game compatibility.
        
        Args:
            key: The key to send (e.g., 'f', 'esc')
        """
        if not self.use_applescript:
            return
        
        # Format the key for AppleScript
        if key.lower() == 'esc':
            key_name = 'escape'
        else:
            key_name = key.lower()
        
        # Create AppleScript command
        script = f'''
        osascript -e 'tell application "System Events"
            key down "{key_name}"
            delay 0.05
            key up "{key_name}"
        end tell'
        '''
        
        # Execute the AppleScript
        result = subprocess.run(script, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"AppleScript execution failed: {result.stderr}")


class MacOSWindowFocus:
    """macOS implementation of window focus functionality."""
    
    def __init__(self):
        """Initialize the window focus handler."""
        self.game_window_title = "PLAY TOGETHER"
        self.use_applescript = False
        
        # Test if we can use AppleScript
        try:
            self._test_applescript()
            self.use_applescript = True
            print("macOS AppleScript window focus initialized")
        except Exception as e:
            print(f"AppleScript not available, window focus features disabled: {e}")
            self.use_applescript = False
    
    def _test_applescript(self):
        """Test if AppleScript is available.
        
        Raises:
            Exception: If AppleScript is not available
        """
        script = 'osascript -e "return \\\"AppleScript available\\\""'
        result = subprocess.run(script, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception("AppleScript not available")
    
    def find_game_window(self):
        """Find the game window.
        
        Returns:
            Boolean indicating success or failure
        """
        if not self.use_applescript:
            return False
        
        try:
            # This AppleScript lists all windows and checks if our game is running
            script = f'''
            osascript -e '
            tell application "System Events"
                set allProcesses to processes whose name contains "{self.game_window_title}"
                if (count of allProcesses) > 0 then
                    return true
                else
                    return false
                end if
            end tell'
            '''
            
            result = subprocess.run(script, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and "true" in result.stdout.strip().lower():
                print(f"Found game window: {self.game_window_title}")
                return True
            else:
                print("Game window not found.")
                return False
        except Exception as e:
            print(f"Error finding game window: {e}")
            return False
    
    def focus_game_window(self):
        """Focus the game window.
        
        Returns:
            Boolean indicating success or failure
        """
        if not self.use_applescript:
            return False
        
        try:
            # This AppleScript activates the game window
            script = f'''
            osascript -e '
            tell application "System Events"
                set allProcesses to processes whose name contains "{self.game_window_title}"
                if (count of allProcesses) > 0 then
                    set frontmost of first item of allProcesses to true
                    return true
                else
                    return false
                end if
            end tell'
            '''
            
            result = subprocess.run(script, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and "true" in result.stdout.strip().lower():
                # Give some time for window to gain focus
                time.sleep(0.1)
                return True
            else:
                return False
        except Exception as e:
            print(f"Error focusing game window: {e}")
            return False
    
    def is_game_window_focused(self):
        """Check if the game window is currently focused.
        
        Returns:
            Boolean indicating if game window is focused
        """
        if not self.use_applescript:
            return False
        
        try:
            # This AppleScript checks if our game is the frontmost application
            script = f'''
            osascript -e '
            tell application "System Events"
                set frontApp to first application process whose frontmost is true
                if name of frontApp contains "{self.game_window_title}" then
                    return true
                else
                    return false
                end if
            end tell'
            '''
            
            result = subprocess.run(script, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and "true" in result.stdout.strip().lower():
                return True
            else:
                return False
        except Exception as e:
            print(f"Error checking window focus: {e}")
            return False 