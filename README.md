# AutoFisher

A cross-platform automated fishing bot for games. Detects pixel changes on screen and automatically responds with keypresses to catch fish.

## Features

- **Cross-Platform Support**: Works on both Windows and macOS
- **Modern UI**: Clean, dark-themed PyQt6 interface
- **Visual Monitoring**: Real-time display of screen capture and pixel changes
- **Customizable Detection**: Adjust sensitivity and enhancement settings
- **Timeline Visualization**: Track detection events over time
- **Robust Detection**: Enhanced detection algorithms for varying lighting conditions

## Installation

### Prerequisites

- Python 3.7+
- PIP package manager

### Setup

1. Clone the repository:
```
git clone https://github.com/yourusername/autofisher.git
cd autofisher
```

2. Create a virtual environment (recommended):
```
python -m venv .venv
```

3. Activate the virtual environment:
   - Windows: `.venv\Scripts\activate`
   - macOS/Linux: `source .venv/bin/activate`

4. Install dependencies:
```
pip install -r requirements.txt
```

## Usage

1. Run the application:
```
python autofishing.py
```

2. Select a screen region to monitor (where fishing activity occurs)
3. Adjust detection sensitivity if needed
4. Click "Start Detection" to begin automated fishing
5. Use "Pause Detection" to temporarily pause or "Stop Detection" to end

## Configuration

- **Sensitivity**: Adjust the threshold slider to control detection sensitivity
- **Noise Reduction**: Enable/disable to filter out minor pixel variations
- **Enhanced Bright Detection**: Improves detection in bright or high-contrast areas
- **Reference Frame**: Capture a new reference frame when lighting conditions change

## Building Standalone Application

To build a standalone executable:

```
python build.py
```

This will create a platform-specific executable in the `dist` directory.

### Manual Build Process

If you prefer to build manually using PyInstaller:

1. Ensure you have PyInstaller installed:
   ```
   pip install pyinstaller
   ```

2. For Windows:
   ```
   pyinstaller build/autofishing_windows.spec
   ```
   
3. For macOS:
   ```
   pyinstaller build/autofishing_mac.spec
   ```

### Creating Release Packages

To create a ZIP package for distribution:

```
mkdir -p release
cd dist
# For macOS
zip -r ../release/AutoFisher-macOS.zip AutoFisher.app/
# For Windows
zip -r ../release/AutoFisher-Windows.zip AutoFisher_Windows.exe
cd ..
```

### Platform-Specific Considerations

#### macOS
- The application requires Screen Recording permission
- You may need to right-click and select "Open" the first time you run it
- If the app quits unexpectedly, check Console.app for crash logs

#### Windows
- The application requires permission to send keyboard input
- The app will focus the game window automatically when using keyboard commands

## Development

The project has been restructured for better organization:

- `autofisher/` - Main package
  - `core/` - Core detection functionality
  - `ui/` - PyQt6 user interface
  - `backends/` - Platform-specific implementations
  - `utils/` - Utility functions

## Troubleshooting

- **No Detection**: Try adjusting the sensitivity or capturing a new reference frame
- **Game Window Not Found**: Make sure the game window is visible and not minimized
- **Keypresses Not Working**: Ensure the application has permission to send key events

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- PyQt6 for the cross-platform UI framework
- OpenCV for image processing capabilities 