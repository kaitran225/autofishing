# Project Reorganization

This document describes how the AutoFishing project has been reorganized into a cross-platform application with separate implementations for macOS and Windows.

## Directory Structure

The project has been reorganized into the following structure:

```
autofishing/
│
├── src/
│   ├── mac/
│   │   └── mac_pixel_detector.py  (macOS implementation)
│   │
│   ├── windows/
│   │   └── pixel_change_trigger.py  (Windows implementation)
│   │
│   └── README.md  (Explains the src directory structure)
│
├── autofishing.py  (Main entry point that detects OS and launches appropriate version)
├── autofishing_mac.spec  (PyInstaller spec file for macOS builds)
├── autofishing_windows.spec  (PyInstaller spec file for Windows builds)
├── build.py  (Build script for both platforms)
├── convert_icon.py  (Utility to convert PNG icon to ICO for Windows)
├── file_version_info.txt  (Windows version metadata)
├── requirements.txt  (Updated with platform-specific dependencies)
└── README.md  (Updated for cross-platform support)
```

## Changes Made

1. **Created Platform-Specific Directories**:
   - `src/mac/` for macOS implementation
   - `src/windows/` for Windows implementation

2. **Moved Existing Code**:
   - `pixel_change_trigger.py` → `src/windows/pixel_change_trigger.py`
   - `mac_pixel_detector_simple.py` → `src/mac/mac_pixel_detector.py`

3. **Created Main Entry Point**:
   - Added `autofishing.py` that detects the OS and launches the appropriate version

4. **Updated Build Configuration**:
   - Created separate PyInstaller spec files for each platform
   - Added `build.py` script to handle building for the current platform
   - Created `convert_icon.py` utility to generate Windows icon

5. **Updated Documentation**:
   - Updated main README.md with cross-platform information
   - Added platform-specific README in the src directory
   - Created this REORGANIZATION.md document

## Next Steps

1. **Install Dependencies**:
   ```
   pip install -r requirements.txt
   ```

2. **Testing**:
   - Test the application on both Windows and macOS
   - Verify the auto-detection in `autofishing.py` works correctly

3. **Building**:
   - On Windows: `python build.py` (creates Windows executable)
   - On macOS: `python build.py` (creates macOS application)

4. **Distribution**:
   - Create separate release packages for Windows and macOS
   - Add installation instructions for each platform

## Notes

- The Windows implementation relies on Win32 APIs for screen capture and input simulation
- The macOS implementation uses macOS-specific APIs through PyObjC and PyQt6
- Both implementations share the same core functionality but use platform-specific methods for:
  - Screen capture
  - Window management
  - Keyboard simulation
  - UI rendering 