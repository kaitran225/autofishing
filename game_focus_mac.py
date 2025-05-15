import time
import subprocess
import os

class GameFocusMac:
    def __init__(self):
        self.game_window_title = "PLAY TOGETHER"
        try:
            # We'll test if we can execute AppleScript
            self._test_applescript()
            self.applescript_available = True
            print("macOS game focus module initialized")
        except Exception as e:
            self.applescript_available = False
            print(f"Error initializing macOS game focus module: {e}")
            print("AppleScript may not be available")
    
    def _test_applescript(self):
        """Test if we can run AppleScript"""
        script = 'osascript -e "return \"AppleScript available\""'
        result = subprocess.run(script, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception("AppleScript not available")
    
    def find_game_window(self):
        """Find the game window using AppleScript"""
        if not self.applescript_available:
            print("AppleScript not available")
            return False
        
        try:
            # AppleScript to list all window names
            script = """
            osascript -e '
            tell application "System Events"
                set windowNames to {}
                set allProcesses to processes
                repeat with proc in allProcesses
                    set procName to name of proc
                    set windowList to windows of proc
                    repeat with win in windowList
                        try
                            set winName to name of win
                            if winName contains "PLAY TOGETHER" then
                                set end of windowNames to {procName, winName}
                            end if
                        end try
                    end repeat
                end repeat
                return windowNames
            end tell
            '
            """
            
            result = subprocess.run(script, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and "PLAY TOGETHER" in result.stdout:
                print("Game window found")
                return True
            else:
                print("Game window not found")
                return False
        except Exception as e:
            print(f"Error finding game window: {e}")
            return False
    
    def focus_game_window(self):
        """Focus the game window using AppleScript"""
        if not self.applescript_available:
            print("AppleScript not available")
            return False
        
        try:
            # First try to find the process name from window title
            process_script = """
            osascript -e '
            tell application "System Events"
                set targetProc to ""
                set allProcesses to processes
                repeat with proc in allProcesses
                    try
                        set windowList to windows of proc
                        repeat with win in windowList
                            if name of win contains "PLAY TOGETHER" then
                                set targetProc to name of proc
                                exit repeat
                            end if
                        end repeat
                        if targetProc is not "" then
                            exit repeat
                        end if
                    end try
                end repeat
                return targetProc
            end tell
            '
            """
            
            proc_result = subprocess.run(process_script, shell=True, capture_output=True, text=True)
            
            if proc_result.returncode == 0 and proc_result.stdout.strip():
                process_name = proc_result.stdout.strip()
                
                # Now activate the application by process name
                activate_script = f"""
                osascript -e '
                tell application "System Events"
                    set frontmost of process "{process_name}" to true
                end tell
                '
                """
                
                activate_result = subprocess.run(activate_script, shell=True, capture_output=True, text=True)
                
                if activate_result.returncode == 0:
                    print(f"Successfully focused game window (process: {process_name})")
                    return True
                else:
                    print(f"Failed to activate process: {process_name}")
                    return False
            else:
                print("Could not find game process")
                return False
        except Exception as e:
            print(f"Error focusing game window: {e}")
            return False
    
    def set_game_window_title(self, title):
        """Set the game window title to search for"""
        self.game_window_title = title
        print(f"Game window title set to: {title}")
    
    def get_game_window_rect(self):
        """Get the game window rectangle (x, y, width, height) using AppleScript"""
        if not self.applescript_available:
            return None
        
        try:
            # AppleScript to get window position and size
            script = """
            osascript -e '
            tell application "System Events"
                set windowInfo to {}
                set allProcesses to processes
                repeat with proc in allProcesses
                    try
                        set windowList to windows of proc
                        repeat with win in windowList
                            if name of win contains "PLAY TOGETHER" then
                                set winBounds to position of win & size of win
                                set windowInfo to winBounds
                                exit repeat
                            end if
                        end repeat
                        if windowInfo is not {} then
                            exit repeat
                        end if
                    end try
                end repeat
                return windowInfo
            end tell
            '
            """
            
            result = subprocess.run(script, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                # Parse the output (format is: {x, y, width, height})
                coords = result.stdout.strip().replace("{", "").replace("}", "").split(", ")
                if len(coords) == 4:
                    try:
                        x, y, width, height = map(int, coords)
                        return (x, y, width, height)
                    except ValueError:
                        print("Could not parse window coordinates")
                        return None
            
            print("Could not get window rectangle")
            return None
        except Exception as e:
            print(f"Error getting window rectangle: {e}")
            return None

if __name__ == "__main__":
    # Test the game window focus
    focus = GameFocusMac()
    
    # Find the game window
    print("Searching for game window...")
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