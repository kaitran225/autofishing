import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw

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

# Save the image as an icon file
img.save('app_icon.png')
img.save('app_icon.icns', format='ICNS')

print("Icon created successfully!") 