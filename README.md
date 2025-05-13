# AutoFishing

A cross-platform application for automatically detecting pixel changes on screen and triggering keyboard actions. Perfect for automating fishing in games.

## Features

- Advanced pixel change detection with special handling for bright backgrounds
- Customizable detection threshold
- Real-time visualization of changes
- Automatic keyboard actions when change is detected
- Support for both Windows and macOS

## Platform Support

- **Windows**: Full support with a terminal-inspired modern UI
- **macOS**: Full support with a modern macOS UI design

## Installation

### Pre-built Binaries
1. Download the latest release for your operating system
2. For macOS: Move `AutoFishing.app` to your Applications folder
3. For Windows: Extract the zip file and run the executable

### Running from Source
1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run `python autofishing.py` (automatically selects correct version for your OS)

## Required Permissions

### macOS
This app requires the following macOS permissions to function properly:

1. **Screen Recording Permission**: To detect pixel changes on screen
2. **Accessibility Permission**: To send keyboard commands

### Windows
This app requires:

1. **Administrator privileges**: May be required for some keyboard actions
2. **No special firewall permissions**: The app does not connect to the internet

## Usage

1. Launch the application
2. Click "Select Region" to select the area of the screen to monitor (fishing float/bobber)
3. Adjust the threshold as needed (lower values = more sensitive)
4. Click "Start" to begin monitoring
5. The app will automatically press F when a change is detected, wait for a bite, press ESC if no bite, then cast again

## Project Structure

- `autofishing.py` - Main entry point that detects OS and launches appropriate version
- `src/windows` - Windows-specific implementation
- `src/mac` - macOS-specific implementation

## Troubleshooting

If the application quits unexpectedly:

1. Make sure you've granted all required permissions
2. Try running from the command line to see error messages

## Support

For questions or assistance, please create an issue in the project repository.

## License

MIT License

## Building from Source

If you want to build the application from source:

### macOS
```bash
# Install dependencies
pip install -r requirements.txt

# Build the application
pyinstaller autofishing_mac.spec
```

### Windows
```bash
# Install dependencies
pip install -r requirements.txt

# Build the application
pyinstaller autofishing_windows.spec
```

The compiled app will be in the `dist` folder. 