# AutoFishing

A macOS application for automatically detecting pixel changes on screen and triggering keyboard actions. Perfect for automating fishing in games.

## Features

- Advanced pixel change detection with special handling for bright backgrounds
- Customizable detection threshold
- Real-time visualization of changes
- Automatic keyboard actions when change is detected
- Modern macOS UI design with Matcha Wood theme

## Installation

1. Download the `AutoFishing.app` file
2. Move it to your Applications folder
3. When first running the app, you may need to right-click and select "Open" to bypass Gatekeeper

## Usage

1. Launch the application
2. Click "Select Region" to select the area of the screen to monitor (fishing float/bobber)
3. Adjust the threshold as needed (lower values = more sensitive)
4. Enable "Enhanced Bright Detection" for bright backgrounds
5. Click "Start" to begin monitoring
6. The app will automatically press the F key when a change is detected

## Permissions

This app requires screen recording permissions to function. When prompted, please grant these permissions in System Preferences > Security & Privacy > Privacy > Screen Recording.

## Troubleshooting

- If the app doesn't respond to pixel changes, try adjusting the threshold
- For bright backgrounds, make sure "Enhanced Bright Detection" is enabled
- If keys aren't being sent to the game, ensure the game window name contains "PLAY TOGETHER" or modify the code for your game

## Building from Source

If you want to build the application from source:

```bash
# Install dependencies
pip install pyinstaller numpy pyautogui mss opencv-python pillow matplotlib PyQt6

# Build the application
pyinstaller autofishing.spec
```

The compiled app will be in the `dist` folder.

## License

This project is provided as-is for educational purposes. 