#!/usr/bin/env python3
"""
Convert app_icon.png to app_icon.ico for Windows
"""
import os
import sys
from PIL import Image

def png_to_ico(png_file, ico_file):
    """Convert a PNG file to an ICO file with multiple sizes"""
    try:
        # Check if PIL/Pillow is installed
        if not hasattr(Image, 'open'):
            print("Error: Pillow library is required")
            print("Install with: pip install Pillow")
            return False
            
        img = Image.open(png_file)
        
        # Create different sizes for the ico file
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        images = []
        
        for size in sizes:
            resized_img = img.resize(size, Image.Resampling.LANCZOS)
            images.append(resized_img)
            
        # Save as .ico
        images[0].save(
            ico_file,
            format='ICO',
            sizes=[(img.width, img.height) for img in images],
            append_images=images[1:]
        )
        
        print(f"Successfully converted {png_file} to {ico_file}")
        print(f"Icon sizes included: {', '.join([f'{size[0]}x{size[1]}' for size in sizes])}")
        
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    png_file = "app_icon.png"
    ico_file = "app_icon.ico"
    
    if not os.path.exists(png_file):
        print(f"Error: {png_file} not found")
        sys.exit(1)
        
    if png_to_ico(png_file, ico_file):
        print("Conversion completed successfully")
    else:
        print("Conversion failed")
        sys.exit(1) 