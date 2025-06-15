# AutoFishing Project Report

## Project Overview

The AutoFishing project is a collection of automation tools designed primarily for fishing in games. The project contains several prototype implementations that use different approaches including pixel detection, image recognition, and UI-based interaction to automate repetitive fishing tasks in various games.

## Repository Structure

The project is organized into several prototype implementations:

```
.prototype/
├── UI.py                     # PyQt6-based comprehensive implementation
├── fish_shadow_detection.py  # Specialized fish detection for LDPlayer
├── feature_suggestions.md    # Future enhancement ideas
├── prototype.py              # Basic tkinter implementation
└── pixel_change_trigger.py   # Advanced pixel change detection system
```

## Technical Implementations

### 1. prototype.py (2686 lines)

A simple GUI-based region selector built with tkinter that monitors screen regions for changes.

#### Key Features:
- **Window Selection**: Target specific applications for monitoring
- **Region Selection**: Define specific screen areas to watch
- **Multiple Display Modes**: 
  - Normal view
  - Grayscale 
  - Edge Detection
  - Color Threshold
- **Simple Monitoring System**: Detect pixel changes in the selected region
- **Visual Feedback**: Display captured regions with different processing modes

#### Technical Approach:
- Uses tkinter for the UI
- Captures screen regions with mss
- Processes images with OpenCV
- Implements threading for non-blocking UI

### 2. fish_shadow_detection.py (291 lines)

A specialized tool designed specifically for detecting fish shadows in a game running in LDPlayer (Android emulator).

#### Key Features:
- **Window Capture**: Specifically targets LDPlayer window
- **Fish Shadow Detection**: Uses contour analysis to identify fish shadows
- **Size Classification**: Categorizes fish into different sizes (1-4)
- **Automated Actions**: Presses keys based on detection results
- **Game State Detection**: Identifies states like broken rods/ropes
- **Repair Functionality**: Automates the repair process for broken equipment

#### Technical Approach:
- Uses win32gui for window capture
- Implements OpenCV for image processing and contour detection
- Utilizes win32api for key simulation
- Uses thresholding techniques adapted to different lighting conditions

### 3. pixel_change_trigger.py (1813 lines)

A more advanced pixel change detection system with a terminal-inspired UI.

#### Key Features:
- **Sophisticated UI**: Clean, minimalist terminal-inspired theme
- **Visualization**: Real-time display of pixel changes
- **Direct Key Simulation**: Multiple methods for reliable key presses
- **Window Focus Management**: Ensures target window receives inputs
- **Logging System**: Comprehensive logging of events and actions
- **Threshold Adjustment**: Fine-tune detection sensitivity
- **Health Checks**: Monitors system state and recovers from errors

#### Technical Approach:
- Uses tkinter with custom styling
- Implements matplotlib for data visualization
- Uses ctypes for low-level window and input management
- Employs queue-based logging system
- Implements multiple fallback methods for window focus and key simulation

### 4. UI.py (2686 lines)

The most comprehensive implementation using PyQt6 with advanced features and a modern UI.

#### Key Features:
- **Modern UI**: Clean, responsive interface with multiple views
- **Region Selection**: Visual selection of monitoring regions
- **Window Targeting**: Comprehensive window selection and focus
- **Key Capture**: Records and simulates keyboard inputs
- **Action Sequencing**: Creates complex sequences of automated actions
- **Multiple Monitoring Modes**: Different visualization options
- **Health Checks**: Robust error detection and recovery
- **Preview Mode**: Live preview of selected regions
- **Customizable Actions**: Configure complex action chains

#### Technical Approach:
- Built with PyQt6 for a modern, responsive UI
- Uses QThread for background processing
- Implements OpenCV for image processing
- Uses direct Win32 API calls for window management
- Comprehensive keyboard and mouse input simulation
- Object-oriented design with worker classes

## Common Functionality Across Implementations

All prototypes share these core capabilities:

1. **Window Selection**: Targeting specific applications
2. **Region Definition**: Selecting screen areas to monitor
3. **Change Detection**: Analyzing pixels for meaningful changes
4. **Action Triggering**: Executing keyboard/mouse actions in response
5. **Visualization**: Displaying monitored regions and detection results

## Future Enhancements (from feature_suggestions.md)

The project includes a comprehensive list of potential enhancements:

### High Priority Features:
1. **Profile Management**: Save and load settings profiles for different games
2. **Randomization Options**: Add controlled randomness to actions for more natural behavior
3. **Global Hotkeys**: Configure keyboard shortcuts that work when the app isn't focused
4. **Visual History**: Capture and display thumbnails of recent detections
5. **Multiple Region Monitoring**: Monitor several screen regions simultaneously

### Medium Priority Features:
6. **Anti-AFK Options**: Prevent being kicked for inactivity
7. **Scheduled Operation**: Set up automated schedules for starting/stopping
8. **Action Testing Visualizer**: Visual feedback during action sequence testing
9. **Pattern Recognition**: Advanced image recognition beyond pixel changes
10. **Advanced Action Conditions**: Complex triggering conditions

### Additional Proposed Features:
11. **Statistics Dashboard**: Track and display session statistics
12. **Audio Detection**: React to game audio cues
13. **Overlay Mode**: Show critical information on top of the game
14. **Macro Recording**: Record complex action sequences by demonstration
15. **Community Integration**: Share and discover automation profiles

## Technical Challenges and Solutions

### Challenge: Window Focus Management
**Solution**: Multiple layered approaches to ensure window focus:
- Thread attachment between application and target window
- Temporary topmost window setting
- Multiple focus attempts with verification
- Alt key simulation to help with focus

### Challenge: Reliable Input Simulation
**Solution**: Redundant input methods:
- Direct keyboard hook via keyboard library
- Virtual key code simulation via win32api
- Message posting to window via PostMessage
- SendInput API for lower-level input simulation

### Challenge: False Positive Detections
**Solution**: Multiple processing techniques:
- Threshold adjustment for sensitivity control
- Different image processing modes (grayscale, edge detection)
- Contour analysis for specific shapes
- Area-based filtering of detected objects

### Challenge: Game State Detection
**Solution**: Reference pixel value comparison:
- Storing known pixel values for specific game states
- Checking multiple regions to confirm state changes
- Color analysis for specific game elements

## Conclusion

The AutoFishing project demonstrates a progression of increasingly sophisticated approaches to game automation, from simple pixel monitoring to complex action sequencing with robust error handling. The PyQt6 implementation (UI.py) represents the most advanced version with the richest feature set, while the specialized implementations like fish_shadow_detection.py show how the approach can be tailored to specific games.

The feature suggestions document indicates a clear roadmap for future development, focusing on usability enhancements, detection reliability, and more sophisticated automation capabilities. 