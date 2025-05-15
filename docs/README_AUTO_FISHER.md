# Auto-Fisher for PlayTogether

This is a Python-based tool that automatically detects and responds to fishing events in PlayTogether by monitoring both exclamation marks and fish shadows/bouncy bait.

## Features

- Cross-platform support (Windows and macOS)
- Interactive region setup
- Automatic calibration
- Dual detection system:
  - Exclamation mark detection for fishing rod reeling
  - Fish shadow and bouncy bait detection for optimal positioning
- Raw image capture for debugging
- Visual feedback with live monitoring

## Installation

1. Install Python 3.8+ if not already installed
2. Install required dependencies:
   ```
   pip install numpy opencv-python pillow pyautogui mss pynput
   ```
   
3. For Windows users, also install:
   ```
   pip install pywin32
   ```
   
4. For macOS users, also install:
   ```
   pip install pyobjc
   ```

## Usage

1. Run the script:
   ```
   python auto_fisher.py
   ```

2. Follow the interactive setup process:
   - A window will show your screen (scaled down)
   - Click to position the first region where exclamation marks appear
   - Click to position the second region where fish shadows and bouncy bait appear

3. During calibration:
   - Try to have both an exclamation mark and fish shadow visible
   - The tool will capture several frames to optimize detection parameters

4. Auto-fishing:
   - The program will display both detection regions in real-time
   - When a fish shadow is detected, it will position near it
   - When an exclamation mark is detected, it will automatically reel in
   - Press 'q' to quit at any time

## How It Works

1. **Exclamation Mark Detection**:
   - Uses frame differencing to detect sudden changes
   - Filters based on brightness and size
   - Automatically clicks when detected

2. **Fish Shadow/Bait Detection**:
   - Detects darker regions in water that match fish shadow characteristics
   - Identifies bouncy bait based on motion and shape
   - Helps position for optimal fishing

## Troubleshooting

- **No exclamation detection**: Try decreasing the exclamation threshold
- **False positives**: Increase thresholds for the problematic detection type
- **Missing fish shadows**: Adjust the shadow area size ranges in the code

## File Structure

- `auto_fisher.py`: Main script
- `captured_regions/`: Contains saved images for debugging
  - `raw_exclamation`: Regular exclamation region captures
  - `raw_shadow`: Regular shadow region captures
  - `exclamation_region`: Detected exclamation marks
  - `shadow_region`: Detected fish shadows
  - `bait_region`: Detected bouncy bait
  - `detection_frame_*`: Frames with detections highlighted
  - `calibration_*`: Calibration images
  - `