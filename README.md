# AutoFisher Qt

An automatic fishing bot for the "Play Together" game, built with Python and PyQt6.

## Features

- Modern Qt-based user interface with customizable settings
- Real-time visualization of pixel changes and activity
- Advanced detection algorithm with hysteresis for reliable detection
- Multiple input simulation methods for increased reliability
- Automatic sequence handling for fishing (catch, exit menu, recast)
- Region selection with visual preview
- Session statistics tracking
- **New: Full overlay mode for seamless integration with the game**
- **New: Overlay-only mode that runs without a main window**

## Installation

### Requirements

- Python 3.8 or higher
- PyQt6
- OpenCV (cv2)
- NumPy
- Matplotlib
- Keyboard
- MSS (screen capture)
- PyWin32 (for Windows specific functions)

### Setup

1. Clone this repository:
```bash
git clone https://github.com/your-username/autofisher-qt.git
cd autofisher-qt
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:
```bash
python main.py
```

2. The application now starts directly in overlay-only mode
3. Click on the region selection button to choose the area where the fishing bobber appears
4. Adjust settings as needed using the settings panel:
   - Threshold: How sensitive the detection should be (lower = more sensitive)
   - Cooldown: Time between actions
   - Fishing Key: The key your game uses for fishing actions (usually 'f')
   
5. Click the Start button to begin automated fishing

### Overlay Interface

The new overlay interface provides all functionality directly on top of your game:

- **Draggable Header**: Move the overlay anywhere on your screen
- **Toggle Panels**: Show/hide settings, zones, and visualization panels
- **Start/Stop Controls**: Begin or end the fishing process with a single click
- **Real-time Statistics**: View detection count and runtime
- **Collapsible Design**: Minimize the overlay when not needed
- **Zone Configuration**: Set up multiple detection zones with sensitivity controls
- **Exit Button**: Safely close the application when finished

### Command Line Options

The application now starts in overlay-only mode by default. No command line options are needed.

### Advanced Settings

- **High Performance Mode**: Uses more CPU but increases reliability
- **Respect Fullscreen Apps**: Pauses actions when another full-screen app is active
- **Direct Control Mode**: Uses multiple methods to send key presses to the game
- **Multi-Zone Detection**: Configure separate detection zones for different game elements

## Project Structure

- `core/`: Core functionality (detection, processing, action sequences)
- `ui/`: User interface components
- `utils/`: Utility functions and constants
- `main.py`: Application entry point

## Troubleshooting

### Common Issues

- **Game Not Found**: Make sure Play Together is running and visible
- **No Detection**: Try adjusting the threshold to a lower value
- **False Positives**: Set the threshold higher
- **Missed Fish**: Make sure the selected region properly captures the bobber movement

## License

This project is for educational purposes only. Use at your own risk.

## Contributors

- Your Name - Initial work 