import time
import keyboard
import subprocess

class KeySenderMac:
    def __init__(self):
        try:
            # Test if we can execute AppleScript
            self._test_applescript()
            self.applescript_available = True
            print("macOS key sender module initialized with AppleScript support")
        except Exception as e:
            self.applescript_available = False
            print(f"Error initializing macOS AppleScript: {e}")
            print("Falling back to keyboard module")
    
    def _test_applescript(self):
        """Test if we can run AppleScript"""
        script = 'osascript -e "return \"AppleScript available\""'
        result = subprocess.run(script, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception("AppleScript not available")
    
    def _send_applescript_key(self, key):
        """Send a key press using AppleScript"""
        try:
            # Map common keys to their AppleScript key codes
            key_mapping = {
                'f': 'f',
                'esc': 'escape',
                'enter': 'return',
                'return': 'return',
                'space': 'space'
            }
            
            # Use mapped key or the key itself
            applescript_key = key_mapping.get(key.lower(), key.lower())
            
            # Create AppleScript to send key
            script = f"""
            osascript -e '
            tell application "System Events"
                keystroke "{applescript_key}"
            end tell
            '
            """
            
            result = subprocess.run(script, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True
            else:
                print(f"AppleScript key send error: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error sending AppleScript key: {e}")
            return False
    
    def _send_applescript_keycode(self, keycode):
        """Send a key by keycode using AppleScript"""
        try:
            # Create AppleScript to send key code
            script = f"""
            osascript -e '
            tell application "System Events"
                key code {keycode}
            end tell
            '
            """
            
            result = subprocess.run(script, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True
            else:
                print(f"AppleScript keycode send error: {result.stderr}")
                return False
        except Exception as e:
            print(f"Error sending AppleScript keycode: {e}")
            return False
    
    def send_key(self, key):
        """Send a key press to the application"""
        print(f"Sending key: {key}")
        
        # Special key codes for macOS
        key_codes = {
            'esc': 53,
            'f': 3,  # f key
        }
        
        success = False
        
        # Try to use AppleScript first for more reliable input
        if self.applescript_available:
            if key.lower() in key_codes:
                success = self._send_applescript_keycode(key_codes[key.lower()])
            else:
                success = self._send_applescript_key(key)
        
        # Fall back to the keyboard module if AppleScript failed or not available
        if not success:
            try:
                keyboard.press_and_release(key)
                success = True
            except Exception as e:
                print(f"Error sending key with keyboard module: {e}")
                success = False
        
        return success
    
    def send_key_combination(self, keys):
        """Send a combination of keys, e.g. ['command', 'c']"""
        if not isinstance(keys, list):
            return self.send_key(keys)
        
        # AppleScript key mapping
        modifier_mapping = {
            'ctrl': 'control',
            'control': 'control',
            'cmd': 'command',
            'command': 'command',
            'alt': 'option',
            'option': 'option',
            'shift': 'shift'
        }
        
        # Try to use AppleScript for key combinations
        if self.applescript_available:
            try:
                # Split modifiers and key
                modifiers = [k for k in keys if k.lower() in modifier_mapping]
                key = next((k for k in keys if k.lower() not in modifier_mapping), None)
                
                if modifiers and key:
                    # Build AppleScript modifiers string
                    modifier_str = ' '.join([f"using {modifier_mapping[m.lower()]} down" for m in modifiers])
                    
                    # Create AppleScript
                    script = f"""
                    osascript -e '
                    tell application "System Events"
                        keystroke "{key}" {modifier_str}
                    end tell
                    '
                    """
                    
                    result = subprocess.run(script, shell=True, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        return True
            except Exception as e:
                print(f"Error sending AppleScript key combination: {e}")
        
        # Fall back to keyboard module
        try:
            # Press all keys in sequence
            for key in keys:
                keyboard.press(key)
            
            # Release all keys in reverse order
            for key in reversed(keys):
                keyboard.release(key)
                
            return True
        except Exception as e:
            print(f"Error sending key combination: {e}")
            return False

if __name__ == "__main__":
    # Test the key sender
    sender = KeySenderMac()
    
    print("Testing key sender...")
    print("Sending 'F' key in 3 seconds...")
    time.sleep(3)
    sender.send_key('f')
    
    print("Sending 'ESC' key in 3 seconds...")
    time.sleep(3)
    sender.send_key('esc')
    
    print("Sending Command+C combination in 3 seconds...")
    time.sleep(3)
    sender.send_key_combination(['command', 'c']) 