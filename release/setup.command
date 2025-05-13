#!/bin/bash

# Get directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

clear
echo "==============================================="
echo "       AutoFishing Setup Assistant"
echo "==============================================="
echo ""
echo "This script will help you set up the AutoFishing app properly."
echo ""
echo "Steps to follow:"
echo ""
echo "1. IMPORTANT: You must grant permissions for this app to work"
echo "   • Screen Recording (to detect pixel changes)"
echo "   • Accessibility (to send keyboard commands)"
echo ""
echo "2. When first launching the app:"
echo "   • Right-click on AutoFishing.app and select 'Open'"
echo "   • Click 'Open' on the security warning"
echo ""
echo "3. If you see a permissions request popup, click 'OK'"
echo "   and follow the instructions to enable permissions"
echo ""
echo "4. If no popup appears, manually enable permissions in:"
echo "   System Preferences → Security & Privacy → Privacy → Screen Recording"
echo "   System Preferences → Security & Privacy → Privacy → Accessibility"
echo ""
echo "Do you want to launch AutoFishing.app now? (y/n)"
read -p "> " choice

if [[ $choice == "y" || $choice == "Y" ]]; then
    echo ""
    echo "Launching AutoFishing.app..."
    echo "Be sure to grant permissions when prompted!"
    echo ""
    open "$DIR/AutoFishing.app"
else
    echo ""
    echo "OK, you can manually launch AutoFishing.app when ready."
    echo "Remember to right-click and select 'Open' the first time."
fi

echo ""
echo "To see debugging information if the app crashes,"
echo "run this command in Terminal:"
echo "open -a $DIR/AutoFishing.app"
echo ""
echo "Press any key to exit..."
read -n 1 -s
exit 0 