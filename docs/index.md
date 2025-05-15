# AutoFisher Documentation

Welcome to the AutoFisher documentation. AutoFisher is a cross-platform tool for automating fishing in the PlayTogether game.

## Contents

- [Project Structure](PROJECT_STRUCTURE.md): Details about the code organization and architecture
- [Development Guide](DEVELOPMENT.md): Information for developers who want to contribute
- [PlayTogether Fishing Guide](PLAYTOGETHER_FISHING_GUIDE.md): Guide for the fishing mechanics in PlayTogether
- [Original README](README_AUTO_FISHER.md): Original documentation from the project
- [Cleanup Summary](CLEANUP_SUMMARY.md): Summary of the repository organization changes

## Getting Started

To get started with AutoFisher, refer to the main [README.md](../README.md) file in the root directory.

## Requirements

- Python 3.6 or higher
- Required packages are listed in `requirements.txt`
- Platform-specific dependencies:
  - Windows: pywin32
  - macOS: AppleScript support (built-in)

## Installation

```bash
# Clone the repository
git clone https://github.com/username/autofisher.git
cd autofisher

# Install the package and dependencies
pip install -e .
```

## Usage

```bash
# Run directly with Python
python -m autofisher

# Or if installed as a package
autofisher
```

## Repository Organization

The repository has been organized to follow modern Python package structure:

```
autofishing/
├── autofisher/          # Main package
│   ├── core/            # Core fishing logic and detection algorithms
│   ├── os_adapters/     # OS-specific adapters for different platforms
│   │   ├── windows/     # Windows-specific implementations
│   │   ├── macos/       # macOS-specific implementations
│   │   └── dummy/       # Fallback implementations for unsupported platforms
│   ├── ui/              # User interface components
│   ├── utils/           # Utility modules
│   └── __main__.py      # Entry point for the application
├── docs/                # Documentation
├── scripts/             # Utility scripts
├── requirements.txt     # Project dependencies
├── setup.py             # Package setup script
└── README.md            # Project overview
```

For a detailed explanation of the repository organization and cleanup process, see the [Cleanup Summary](CLEANUP_SUMMARY.md). 