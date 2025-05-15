#!/bin/bash
# AutoFisher launching script for Unix-based systems

# Change to the project directory (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$PROJECT_DIR" || {
    echo "Error: Could not change to project directory at $PROJECT_DIR"
    exit 1
}

# Check if running in a virtual environment, if not, try to activate it
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d ".venv" ]; then
        echo "Activating virtual environment..."
        if [ -f ".venv/bin/activate" ]; then
            # shellcheck disable=SC1091
            source .venv/bin/activate
        else
            echo "Warning: Virtual environment found but activate script not found."
        fi
    fi
fi

# Run the main python file
echo "Starting AutoFisher..."
python autofishing.py

# Exit with the same code as the Python script
exit $? 