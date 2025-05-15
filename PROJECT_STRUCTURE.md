# AutoFishing Project Structure

## Directory Structure

```
autofishing/
├── autofishing.py           # Main entry point
├── requirements.txt         # Project dependencies
├── README.md                # Project documentation
├── DEVELOPMENT.md           # Development roadmap
├── LICENSE                  # Project license
├── setup.py                 # Package setup script
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── test_detection.py    # Detection tests
│   ├── test_ui.py           # UI tests
│   └── test_integration.py  # Integration tests
├── autofisher/              # Main package
│   ├── __init__.py
│   ├── ui/                  # Cross-platform UI
│   │   ├── __init__.py
│   │   ├── app.py           # Main application window
│   │   ├── config_panel.py  # Configuration panel
│   │   ├── detection_view.py# Detection visualization
│   │   └── styles.py        # UI styling
│   ├── core/                # Core functionality
│   │   ├── __init__.py
│   │   ├── detector.py      # Common detection interface
│   │   ├── input.py         # Input simulation
│   │   └── config.py        # Configuration management
│   └── platforms/           # Platform-specific code
│       ├── __init__.py
│       ├── common.py        # Common platform functions
│       ├── windows/         # Windows implementation
│       │   ├── __init__.py
│       │   └── pixel_change_trigger.py
│       └── mac/             # macOS implementation
│           ├── __init__.py
│           └── mac_pixel_detector.py
├── scripts/                 # Utility scripts
│   ├── build.py             # Build script
│   └── install.py           # Installation helper
└── docs/                    # Documentation
    ├── index.md             # Documentation home
    ├── usage.md             # Usage guide
    ├── development.md       # Developer documentation
    └── api/                 # API documentation
        ├── ui.md
        ├── core.md
        └── platforms.md
```

## Module Responsibilities

### autofishing.py
Main entry point that detects the platform and launches the appropriate version.

### autofisher.ui
Cross-platform UI implementation using PyQt5.

### autofisher.core
Core functionality that is shared across platforms:
- Detection algorithms
- Input simulation
- Configuration management

### autofisher.platforms
Platform-specific implementations:
- Windows: Uses pixel_change_trigger for detection
- macOS: Uses mac_pixel_detector for detection

## Implementation Strategy

1. **Core Engine**: Implement platform-agnostic detection algorithms
2. **Platform Adapters**: Create platform-specific implementations
3. **UI Layer**: Build a unified UI that works across platforms
4. **Configuration**: Implement a flexible configuration system
5. **Tests**: Create comprehensive tests for all components 