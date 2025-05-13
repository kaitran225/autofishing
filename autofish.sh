#!/bin/bash

# Pixel Change Detector Launcher Script

# Go to the directory containing the script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if we're in a virtual environment
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Run the application
echo "Starting Pixel Change Detector..."
python mac_pixel_detector_simple.py

# Exit with the same code as the Python script
exit $? 