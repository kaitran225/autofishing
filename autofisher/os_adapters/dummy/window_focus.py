"""
Dummy window focus implementation for unsupported platforms.
"""

class DummyWindowFocus:
    def __init__(self):
        self.game_window_title = "PLAY TOGETHER"
        print("WARNING: Using dummy window focus implementation")
        print("This platform is not supported for window focusing")
        print("Autofisher only fully supports Windows and macOS")
    
    def find_game_window(self):
        """Dummy implementation of find_game_window"""
        print(f"Dummy: Would find game window '{self.game_window_title}' if platform was supported")
        return False
    
    def focus_game_window(self):
        """Dummy implementation of focus_game_window"""
        print(f"Dummy: Would focus game window '{self.game_window_title}' if platform was supported")
        return False
    
    def set_game_window_title(self, title):
        """Dummy implementation of set_game_window_title"""
        self.game_window_title = title
        print(f"Dummy: Game window title set to '{title}'")
    
    def get_game_window_rect(self):
        """Dummy implementation of get_game_window_rect"""
        print("Dummy: Would get game window rectangle if platform was supported")
        return None 