#!/usr/bin/env python3
"""
Generate the app icon for AutoFisher
"""
import os
import sys
from PIL import Image, ImageDraw

def generate_app_icon(output_path):
    """
    Generate a basic app icon for AutoFisher
    
    Args:
        output_path (str): Path to save the generated icon
    """
    try:
        # Create a 512x512 image with an RGBA color space
        icon_size = 512
        img = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw a rounded rectangle for the background
        rect_padding = 30
        rect_size = icon_size - 2*rect_padding
        draw.rounded_rectangle(
            [(rect_padding, rect_padding), (rect_padding + rect_size, rect_padding + rect_size)], 
            radius=60, 
            fill=(63, 78, 79, 255)  # Dark wood background color
        )
            
        # Draw a fishing bob icon
        center_x = icon_size // 2
        center_y = icon_size // 2
        
        # Draw the fishing line
        line_color = (255, 255, 255, 220)
        line_width = 6
        draw.line([(center_x, rect_padding + 50), (center_x, center_y + 40)], fill=line_color, width=line_width)
        
        # Draw the bob (float)
        bob_radius = 40
        bob_outer_color = (248, 116, 116, 255)  # Red alert color
        bob_inner_color = (255, 255, 255, 255)  # White
        
        draw.ellipse(
            [(center_x - bob_radius, center_y + 40 - bob_radius), 
             (center_x + bob_radius, center_y + 40 + bob_radius)], 
            fill=bob_outer_color
        )
        
        # Inner white circle
        inner_radius = bob_radius // 2
        draw.ellipse(
            [(center_x - inner_radius, center_y + 40 - inner_radius), 
             (center_x + inner_radius, center_y + 40 + inner_radius)], 
            fill=bob_inner_color
        )
        
        # Draw a pixel detection grid in the background
        grid_size = 6
        cell_size = rect_size // grid_size
        grid_start_x = rect_padding + rect_size // 8
        grid_start_y = rect_padding + rect_size // 3
        
        for i in range(grid_size):
            for j in range(grid_size):
                if (i + j) % 2 == 0:  # Alternate cells for a checkerboard pattern
                    # Fill some cells with matcha green
                    cell_color = (160, 196, 157, 100)  # Matcha color with transparency
                    draw.rectangle(
                        [(grid_start_x + i * cell_size, grid_start_y + j * cell_size), 
                         (grid_start_x + (i+1) * cell_size, grid_start_y + (j+1) * cell_size)],
                        fill=cell_color
                    )
        
        # Save the image
        img.save(output_path)
        print(f"Icon created successfully at {output_path}")
        return True
    except Exception as e:
        print(f"Error generating icon: {e}")
        return False

def main():
    """Main function"""
    # Define paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    resources_dir = os.path.join(os.path.dirname(script_dir), "resources")
    
    # Ensure resources directory exists
    if not os.path.exists(resources_dir):
        os.makedirs(resources_dir)
        
    output_path = os.path.join(resources_dir, 'app_icon.png')
    
    success = generate_app_icon(output_path)
    
    if success:
        # Try to generate platform-specific icons if needed
        if sys.platform == 'darwin':
            from autofisher.utils.create_icon import create_icns
            icns_path = os.path.join(resources_dir, 'app_icon.icns')
            create_icns(output_path, icns_path)
        elif sys.platform == 'win32':
            from autofisher.utils.convert_icon import convert_png_to_ico
            ico_path = os.path.join(resources_dir, 'app_icon.ico')
            convert_png_to_ico(output_path, ico_path)
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 