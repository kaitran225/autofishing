# Build Instructions for AutoFishing

This document explains how to recreate the build, dist, and release folders that are excluded from Git tracking.

## Prerequisites

1. Make sure you have Python installed (preferably Python 3.9+)
2. Set up a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate     # On Windows
   ```
3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Building the Application

### Standard Debug Build

To build the debug version of the application:

```bash
pyinstaller autofishing_debug.spec
```

This will create:
- `build/AutoFishingDebug/` - intermediary build files
- `dist/AutoFishingDebug.app/` - the macOS application bundle (debug version)

### Production Build

To build the release version of the application:

```bash
pyinstaller autofishing.spec
```

This will create:
- `build/AutoFishing/` - intermediary build files
- `dist/AutoFishing.app/` - the macOS application bundle (release version)

### Test Permissions Build

To build the test permissions application:

```bash
pyinstaller test_permissions.spec
```

This will create:
- `build/test_permissions/` - intermediary build files
- `dist/test_permissions.app/` - the test permissions application bundle

## Creating Release Packages

To create a ZIP package for distribution:

```bash
mkdir -p release
cd dist
zip -r ../release/AutoFishing-macOS.zip AutoFishing.app/
cd ..
```

This will create:
- `release/AutoFishing-macOS.zip` - release package ready for distribution

## Directory Structure

After building, your directory structure should look like:

```
autofishing/
├── .venv/
├── build/
│   ├── AutoFishing/
│   ├── AutoFishingDebug/
│   └── test_permissions/
├── dist/
│   ├── AutoFishing.app/
│   ├── AutoFishingDebug.app/
│   └── test_permissions.app/
├── release/
│   └── AutoFishing-macOS.zip
└── ... (other source files)
```

## Tips for macOS Builds

- Make sure your macOS permissions are properly set up for screen recording
- Test the application with `debug_launcher.py` first to ensure all components work
- Check for any error logs on desktop if the application quits unexpectedly 