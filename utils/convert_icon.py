#!/usr/bin/env python3
"""
Convert PNG icon to ICO format for Windows
"""
import os
import sys
from PIL import Image

def convert_png_to_ico(input_path, output_path, sizes=(16, 24, 32, 48, 64, 128, 256)):
    """
    Convert a PNG image to ICO format with multiple sizes
    
    Args:
        input_path (str): Path to the input PNG file
        output_path (str): Path to the output ICO file
        sizes (tuple): Tuple of sizes to include in the ICO file
    """
    try:
        # Open the PNG image
        img = Image.open(input_path)
        
        # Create a list to store the resized images
        icon_sizes = []
        
        # Resize the image to all required sizes
        for size in sizes:
            resized_img = img.resize((size, size), Image.Resampling.LANCZOS)
            icon_sizes.append(resized_img)
        
        # Save as ICO
        icon_sizes[0].save(
            output_path,
            format='ICO',
            sizes=[(size, size) for size in sizes],
            append_images=icon_sizes[1:]
        )
        
        print(f"Successfully converted {input_path} to {output_path}")
        return True
    except Exception as e:
        print(f"Error converting icon: {e}")
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
    output_path = os.path.join(resources_dir, 'app_icon.ico')
    
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at {input_path}")
        return False
    
    return convert_png_to_ico(input_path, output_path)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 