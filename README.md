# AutoFisher

An automated fishing tool for PlayTogether game with cross-platform support for Windows and macOS.

> [!NOTE]
> This repository has been cleaned up and reorganized to follow modern Python package structure.
> For details, see the [Cleanup Summary](docs/CLEANUP_SUMMARY.md).

## Features

- **Cross-platform support**: Works on both Windows and macOS
- **Modern PyQt5 user interface**: Clean, responsive design
- **Real-time detection**: Detects fishing exclamation marks and fish shadows
- **Customizable detection regions**: Interactive region selection
- **Adjustable parameters**: Fine-tune detection thresholds
- **Automatic fishing sequence**: Configurable fishing action sequence

## Screenshots

![AutoFisher UI](screenshots/autofisher_ui.png)

## Requirements

- Python 3.6 or higher
- Required Python packages (automatically installed with setup.py):
  - numpy
  - opencv-python
  - mss
  - keyboard
  - PyQt5
  - Pillow
- For Windows: pywin32 (for key sending and window focus)
- For macOS: AppleScript support (built-in)

## Installation

### From source

```bash
# Clone the repository
git clone https://github.com/username/autofisher.git
cd autofisher

# Install the package and dependencies
pip install -e .

# For Windows, install additional dependencies
pip install pywin32
```

## Usage

### Starting the application

```bash
# Run directly with Python
python -m autofisher

# Or if installed as a package
autofisher
```

### Basic workflow

1. Launch AutoFisher
2. Click "Setup Detection Regions" to select screen areas
3. Position the exclamation region where '!' marks appear
4. Position the shadow region where fish shadows are visible
5. Click "Capture Reference Frames" when no fish or markers are visible
6. Click "Start Fishing" to begin auto-fishing
7. Use "Pause" button to temporarily stop the fishing process

### Tips

- Position the game window before setting up regions
- Make sure the exclamation region covers where the '!' mark appears
- The shadow region should be positioned to detect fish shadows in the water
- Adjust thresholds if detection is too sensitive or not sensitive enough
- If detection is unreliable, try recapturing reference frames

## Project Structure

```
autofisher/
├── core/             # Core fishing logic and detection algorithms
├── os_adapters/      # OS-specific adapters for different platforms
├── ui/               # User interface components
├── utils/            # Utility modules
└── __main__.py       # Entry point for the application
```

## Documentation

For more detailed documentation, check out the [docs directory](docs/).

- [Project Structure](docs/PROJECT_STRUCTURE.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [PlayTogether Fishing Guide](docs/PLAYTOGETHER_FISHING_GUIDE.md)

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Development

See `DEVELOPMENT.md` for the roadmap and development guidelines.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- Thanks to the game development community
- Contributors and testers who helped improve the tool 