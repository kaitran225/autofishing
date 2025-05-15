import time

class GameFocusWin:
    def __init__(self):
        try:
            # Import Windows-specific modules
            import win32gui
            import win32con
            import win32process
            import win32api
            import ctypes
            
            self.win32gui = win32gui
            self.win32con = win32con
            self.win32process = win32process
            self.win32api = win32api
            self.ctypes = ctypes
            self.user32 = ctypes.WinDLL('user32', use_last_error=True)
            self.kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            
            self.modules_loaded = True
            print("Windows game focus module initialized")
        except ImportError as e:
            self.modules_loaded = False
            print(f"Error initializing Windows game focus module: {e}")
            print("Make sure pywin32 is installed: pip install pywin32")
        
        self.game_window = None
        self.game_window_title = "PLAY TOGETHER"
    
    def find_game_window(self):
        """Find the game window handle"""
        if not self.modules_loaded:
            print("Windows modules not loaded")
            return False
            
        try:
            # Search for window by title
            self.game_window = self.win32gui.FindWindow(None, self.game_window_title)
            if not self.game_window:
                # Try fuzzy match with partial title
                def enum_windows_callback(hwnd, result):
                    if self.win32gui.IsWindowVisible(hwnd):
                        title = self.win32gui.GetWindowText(hwnd)
                        if "PLAY TOGETHER" in title.upper():
                            result.append(hwnd)
                            return False
                    return True
                
                result = []
                self.win32gui.EnumWindows(enum_windows_callback, result)
                if result:
                    self.game_window = result[0]
            
            if self.game_window:
                print(f"Found game window: {self.win32gui.GetWindowText(self.game_window)}")
                return True
            else:
                print("Game window not found")
                return False
        except Exception as e:
            print(f"Error finding game window: {e}")
            return False
    
    def focus_game_window(self):
        """Focus the game window before sending keys"""
        if not self.modules_loaded:
            print("Windows modules not loaded")
            return False
            
        try:
            if not self.game_window and not self.find_game_window():
                return False
            
            # Check if window exists
            if not self.win32gui.IsWindow(self.game_window):
                if not self.find_game_window():
                    return False
            
            # Try to focus window with multiple methods
            if self.win32gui.IsIconic(self.game_window):  # If minimized
                self.win32gui.ShowWindow(self.game_window, self.win32con.SW_RESTORE)
                time.sleep(0.1)
            
            # Set the window position to top-most temporarily
            self.win32gui.SetWindowPos(
                self.game_window, 
                self.win32con.HWND_TOPMOST, 
                0, 0, 0, 0, 
                self.win32con.SWP_NOMOVE | self.win32con.SWP_NOSIZE | self.win32con.SWP_SHOWWINDOW
            )
            time.sleep(0.05)
            self.win32gui.SetWindowPos(
                self.game_window, 
                self.win32con.HWND_NOTOPMOST, 
                0, 0, 0, 0,
                self.win32con.SWP_NOMOVE | self.win32con.SWP_NOSIZE | self.win32con.SWP_SHOWWINDOW
            )
            
            # Multiple focus attempts
            self.user32.SetForegroundWindow(self.game_window)
            self.user32.SetFocus(self.game_window)
            self.user32.BringWindowToTop(self.game_window)
            
            # Force active window
            self.user32.SwitchToThisWindow(self.game_window, True)
            
            # Verify focus
            active_window = self.user32.GetForegroundWindow()
            result = (active_window == self.game_window)
            print(f"Focus result: {result}")
            return result
        except Exception as e:
            print(f"Error focusing window: {e}")
            return False
    
    def set_game_window_title(self, title):
        """Set the game window title to search for"""
        self.game_window_title = title
        # Reset window handle since we're changing the target
        self.game_window = None
        print(f"Game window title set to: {title}")
    
    def get_game_window_rect(self):
        """Get the game window rectangle (x, y, width, height)"""
        if not self.modules_loaded:
            return None
            
        if not self.game_window and not self.find_game_window():
            return None
            
        try:
            left, top, right, bottom = self.win32gui.GetWindowRect(self.game_window)
            width = right - left
            height = bottom - top
            return (left, top, width, height)
        except Exception as e:
            print(f"Error getting window rect: {e}")
            return None
    
if __name__ == "__main__":
    # Test the game window focus
    focus = GameFocusWin()
    
    # Find the game window
    if focus.find_game_window():
        print("Game window found!")
        
        # Get window rectangle
        rect = focus.get_game_window_rect()
        if rect:
            print(f"Window rect: {rect}")
        
        # Focus the window
        print("Attempting to focus window...")
        if focus.focus_game_window():
            print("Successfully focused game window")
        else:
            print("Failed to focus game window")
    else:
        print("Game window not found. Make sure the game is running.") 