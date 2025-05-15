import time
import keyboard

class KeySenderWin:
    def __init__(self):
        try:
            # Import Windows-specific modules
            import ctypes
            self.ctypes = ctypes
            
            # Initialize user32 DLL for low-level keyboard input
            self.user32 = ctypes.WinDLL('user32', use_last_error=True)
            
            # Key constants
            self.VK_F = 0x46  # Virtual key code for 'F'
            self.VK_ESC = 0x1B  # Virtual key code for 'ESC'
            self.KEYEVENTF_KEYUP = 0x0002
            self.INPUT_KEYBOARD = 1
            
            # Input type for SendInput
            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", ctypes.c_ushort),
                    ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
                ]
            self.KEYBDINPUT = KEYBDINPUT
            
            class INPUT_UNION(ctypes.Union):
                _fields_ = [
                    ("ki", KEYBDINPUT),
                    # Other input types omitted for brevity
                ]
            self.INPUT_UNION = INPUT_UNION
            
            class INPUT(ctypes.Structure):
                _fields_ = [
                    ("type", ctypes.c_ulong),
                    ("ii", INPUT_UNION)
                ]
            self.INPUT = INPUT
            
            self.win_input_available = True
            print("Windows key sender module initialized")
        except Exception as e:
            self.win_input_available = False
            print(f"Error initializing Windows key sender module: {e}")
            print("Falling back to keyboard module")
    
    def _send_win_input(self, vk_code):
        """Send a key press using Windows SendInput API"""
        try:
            # Create input structure
            kb_input = self.INPUT()
            kb_input.type = self.INPUT_KEYBOARD
            kb_input.ii.ki.wVk = vk_code
            kb_input.ii.ki.wScan = 0
            kb_input.ii.ki.dwFlags = 0
            kb_input.ii.ki.time = 0
            kb_input.ii.ki.dwExtraInfo = self.ctypes.pointer(self.ctypes.c_ulong(0))
            
            # Press key
            self.user32.SendInput(1, self.ctypes.byref(kb_input), self.ctypes.sizeof(self.INPUT))
            time.sleep(0.05)
            
            # Release key
            kb_input.ii.ki.dwFlags = self.KEYEVENTF_KEYUP
            self.user32.SendInput(1, self.ctypes.byref(kb_input), self.ctypes.sizeof(self.INPUT))
            
            return True
        except Exception as e:
            print(f"Error sending Windows input: {e}")
            return False
    
    def send_key(self, key):
        """Send a key press to the application"""
        print(f"Sending key: {key}")
        
        success = False
        
        # Try to use Windows SendInput first for more reliable input
        if self.win_input_available:
            if key.lower() == 'f':
                success = self._send_win_input(self.VK_F)
            elif key.lower() == 'esc':
                success = self._send_win_input(self.VK_ESC)
            else:
                success = self._send_win_input(ord(key.upper()))
        
        # Fall back to the keyboard module if Windows SendInput failed or is not available
        if not success:
            try:
                keyboard.press_and_release(key)
                success = True
            except Exception as e:
                print(f"Error sending key with keyboard module: {e}")
                success = False
        
        return success
    
    def send_key_combination(self, keys):
        """Send a combination of keys, e.g. ['ctrl', 'c']"""
        if not isinstance(keys, list):
            return self.send_key(keys)
            
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
    sender = KeySenderWin()
    
    print("Testing key sender...")
    print("Sending 'F' key in 3 seconds...")
    time.sleep(3)
    sender.send_key('f')
    
    print("Sending 'ESC' key in 3 seconds...")
    time.sleep(3)
    sender.send_key('esc')
    
    print("Sending Ctrl+C combination in 3 seconds...")
    time.sleep(3)
    sender.send_key_combination(['ctrl', 'c']) 