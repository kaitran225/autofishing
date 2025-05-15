#!/usr/bin/env python3
"""
Create ICNS icon file for macOS application
Requires command-line tool iconutil (built-in on macOS)
"""
import os
import sys
import subprocess
import shutil
from PIL import Image

def create_icns(input_path, output_path, iconset_dir=None):
    """
    Create an ICNS file from a PNG image
    
    Args:
        input_path (str): Path to the input PNG file
        output_path (str): Path to the output ICNS file
        iconset_dir (str): Path to the temporary iconset directory (will be created if None)
    """
    try:
        if sys.platform != 'darwin':
            print("This script requires macOS to generate .icns files")
            print("For Windows, use convert_icon.py instead")
            return False
            
        # If no iconset_dir provided, create a temporary one
        if not iconset_dir:
            iconset_dir = output_path.replace('.icns', '.iconset')
            if os.path.exists(iconset_dir):
                shutil.rmtree(iconset_dir)
            os.makedirs(iconset_dir)
            
        # Open the source image
        image = Image.open(input_path)
        
        # Define the sizes needed for the iconset
        # Format: (size, scale, output_name)
        icon_sizes = [
            (16, 1, '16x16.png'),
            (16, 2, '16x16@2x.png'),
            (32, 1, '32x32.png'),
            (32, 2, '32x32@2x.png'),
            (64, 1, '64x64.png'),  # added for good measure
            (128, 1, '128x128.png'),
            (128, 2, '128x128@2x.png'),
            (256, 1, '256x256.png'),
            (256, 2, '256x256@2x.png'),
            (512, 1, '512x512.png'),
            (512, 2, '512x512@2x.png'),
            (1024, 1, '1024x1024.png')
        ]
        
        # Generate each size and save to the iconset directory
        for size, scale, output_name in icon_sizes:
            output_size = size * scale
            resized = image.resize((output_size, output_size), Image.Resampling.LANCZOS)
            output_file = os.path.join(iconset_dir, output_name)
            resized.save(output_file)
            print(f"Created {output_file}")
            
        # Convert the iconset to icns using iconutil
        # This works only on macOS
        iconutil_cmd = ['iconutil', '-c', 'icns', iconset_dir, '-o', output_path]
        subprocess.run(iconutil_cmd, check=True)
        
        # Clean up the temporary iconset directory
        shutil.rmtree(iconset_dir)
        
        print(f"Successfully created {output_path}")
        return True
    except Exception as e:
        print(f"Error creating .icns file: {e}")
        # Clean up the temporary directory if it exists
        if iconset_dir and os.path.exists(iconset_dir):
            shutil.rmtree(iconset_dir)
        return False

def main():
    """Main function"""
    # Define paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(script_dir))  # Navigate to project root
    resources_dir = os.path.join(os.path.dirname(script_dir), "resources")  # Navigate to resources directory
    
    # Ensure resources directory exists
    if not os.path.exists(resources_dir):
        os.makedirs(resources_dir)
        
    input_path = os.path.join(resources_dir, 'app_icon.png')
    output_path = os.path.join(resources_dir, 'app_icon.icns')
    
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at {input_path}")
        return False
    
    return create_icns(input_path, output_path)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 