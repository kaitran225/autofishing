# Autofishing Pixel Detector

This directory contains the modular implementation of the autofishing pixel detection application.

## Directory Structure

```
src/
├── __init__.py                # Package initialization
├── main.py                    # Application entry point
├── models/                    # Core business logic
│   ├── __init__.py            # Package initialization
│   └── detector.py            # Pixel change detection implementation
├── ui/                        # User interface components
│   ├── __init__.py            # Package initialization
│   ├── main_window.py         # Main application window
│   └── components/            # Reusable UI components
│       ├── __init__.py        # Package initialization
│       ├── monitoring_display.py  # Live monitoring display
│       ├── region_selection.py    # Region selection overlay
│       └── timeline_plot.py       # Activity timeline visualization
└── utils/                     # Utilities and helpers
    └── __init__.py            # Package initialization
```

## Running the Application

From the root directory, run:

```bash
python -m src.main
```

## Components

### Models
- `detector.py` - Core implementation of pixel change detection with optimized algorithms

### UI Components
- `main_window.py` - Main application window with settings, controls, and visualization
- `monitoring_display.py` - Real-time display of the monitored region
- `region_selection.py` - Interactive overlay for selecting screen regions
- `timeline_plot.py` - Visualization of activity history and thresholds

## Design Patterns

The application follows these object-oriented design patterns:
- **Observer Pattern**: Components observe the detector via signals/slots
- **Model-View-Controller (MVC)**: Separates data (models) from presentation (views) and control logic
- **Strategy Pattern**: Pluggable detection strategies and visualization approaches 