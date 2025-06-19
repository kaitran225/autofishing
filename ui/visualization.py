"""
Visualization components for real-time monitoring
"""
import numpy as np
import cv2
import matplotlib
matplotlib.use('qt5agg')  # Must set backend before imports
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class ActivityGraphCanvas(FigureCanvas):
    """Canvas for displaying activity timeline"""
    
    def __init__(self, parent=None, width=5, height=1.5, dpi=100):
        # Create figure with specified dimensions
        self.fig = plt.Figure(figsize=(width, height), dpi=dpi)
        
        # Define theme colors
        self.theme_colors = {
            'bg_dark': '#181914',         # Oak wood dark
            'accent': '#A3D977',          # Matcha green
            'green': '#A3D977',           # Matcha green
            'text_bright': '#FFFFFF',     # White text
            'text': '#F8F5E3',            # Warm off-white
            'border': '#6B6E58',          # Border color
        }
        
        # Set up the figure
        self.fig.patch.set_facecolor(self.theme_colors['bg_dark'])
        gs = plt.GridSpec(1, 1, figure=self.fig)
        self.timeline_ax = self.fig.add_subplot(gs[0])
        self.timeline_ax.set_facecolor(self.theme_colors['bg_dark'])
        
        # Set up the timeline
        self.timeline_ax.set_xlim(0, 99)
        self.timeline_ax.set_ylim(0, 1)
        self.timeline_ax.set_xticks([])
        self.timeline_ax.set_yticks([])
        
        # Remove spines
        for spine in self.timeline_ax.spines.values():
            spine.set_visible(False)
            
        # Create baseline
        self.timeline_ax.axhline(y=0.5, color=self.theme_colors['border'], linestyle='-', alpha=0.3, linewidth=0.5)
        
        # Create activity line
        x_data = np.arange(100)
        y_data = np.ones(100) * 0.5
        self.activity_line, = self.timeline_ax.plot(x_data, y_data, color=self.theme_colors['accent'], linewidth=1)
        
        # Create threshold line
        self.threshold_line = self.timeline_ax.axhline(y=0.05, color='#FF6B6B', linestyle='--', alpha=0.5, linewidth=0.5)
        
        # Create threshold annotation
        self.threshold_annotation = self.timeline_ax.annotate(
            "threshold", xy=(99, 0.05), xytext=(5, 0), textcoords="offset points",
            ha="right", va="center", fontsize=7, color='#FF6B6B', alpha=0.7,
            bbox=dict(boxstyle="round,pad=0.1", fc=self.theme_colors['bg_dark'], ec="none", alpha=0.7)
        )
        self.threshold_annotation.set_visible(False)
        
        # Initialize the canvas
        super().__init__(self.fig)
        
    def update(self, history=None, threshold=0.05):
        """Update the activity graph with new data"""
        try:
            if not history:
                # If no data, just clear the graph and return
                self.activity_line.set_ydata([0] * 100)
                # Clear all collections
                for collection in self.timeline_ax.collections:
                    try:
                        collection.remove()
                    except Exception as e:
                        pass  # Silently ignore removal errors
                self.threshold_line.set_ydata([threshold, threshold])
                self.draw_idle()  # Use self directly as we are a FigureCanvas
                return

            # Process data for display
            data = history[-100:] if len(history) > 100 else history
            if len(data) < 100:
                # Pad with zeros
                data = [0] * (100 - len(data)) + data

            # Update the line data
            self.activity_line.set_ydata(data)

            # Update threshold line
            self.threshold_line.set_ydata([threshold, threshold])

            # Clear previous fills
            # Clear all collections (fills) by removing them safely
            for collection in list(self.timeline_ax.collections):
                try:
                    collection.remove()
                except Exception as e:
                    pass  # Silently ignore removal errors

            # Add new fill
            fill_data = data.copy()
            
            # Create mask for values above threshold
            x_data = range(len(fill_data))
            mask = []
            for val in fill_data:
                mask.append(val > threshold)
                
            # Create the fill between activity line and zero baseline
            try:
                self.timeline_ax.fill_between(
                    x_data, fill_data, 0, 
                    where=mask,  # Use the pre-computed mask instead
                    interpolate=True, 
                    color=self.theme_colors.get('accent', '#77DD77'), 
                    alpha=0.3
                )
            except Exception as e:
                print(f"Error creating fill: {e}")

            # Redraw the canvas
            self.draw_idle()  # Use self directly as we are a FigureCanvas
        except Exception as e:
            print(f"Error updating activity graph: {e}")
            import traceback
            traceback.print_exc()

class MatplotlibCanvas(FigureCanvas):
    """Matplotlib canvas for visualizing frames"""
    
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        """Initialize the canvas with figure and axes"""
        self.fig = plt.Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        
        # Set background color to match the application theme
        self.fig.patch.set_facecolor('#181914')  # Dark background
        self.axes.set_facecolor('#181914')
        
        # Remove axis ticks and labels
        self.axes.set_xticks([])
        self.axes.set_yticks([])
        
        # Create placeholders for images
        self.main_image = None
        self.diff_overlay = None
        
        # Store the last frame for refreshing
        self.last_frame = None
        self.last_diff = None
        
        # Set up the figure layout
        self.fig.tight_layout(pad=0)
        
    def update_image(self, frame, diff_frame=None):
        """Update the image display with a new frame"""
        try:
            # Store the frame for refreshing
            self.last_frame = frame
            
            # Clear previous images
            self.axes.clear()
            self.axes.set_xticks([])
            self.axes.set_yticks([])
            
            # Display the raw image without filtering
            # Make sure we're showing RGB data (convert if needed)
            if len(frame.shape) == 3 and frame.shape[2] == 4:  # RGBA
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2RGB)
                self.main_image = self.axes.imshow(rgb_frame, interpolation='none')
            elif len(frame.shape) == 2:  # Grayscale
                self.main_image = self.axes.imshow(frame, interpolation='none', cmap='gray')
            else:  # Already RGB
                self.main_image = self.axes.imshow(frame, interpolation='none')
            
            # If we have a difference frame, overlay it
            if diff_frame is not None:
                self.update_diff(diff_frame)
            
            # Redraw the canvas
            self.draw_idle()
        except Exception as e:
            print(f"Error updating image: {e}")
            import traceback
            traceback.print_exc()
            
    def update_diff(self, diff_frame):
        """Update the difference overlay"""
        if diff_frame is None:
            return
            
        try:
            # Store the diff frame
            self.last_diff = diff_frame
            
            # If we're starting with just a diff frame, create a black background
            if self.main_image is None and self.last_frame is not None:
                self.update_image(self.last_frame)
                
            # For raw visualization, just show the difference directly with minimal processing
            # No need to remove previous overlay since we cleared the axes in update_image
            
            # Create a simple overlay that shows raw differences
            # Normalize the difference values for visibility
            if len(diff_frame.shape) == 2:  # Grayscale diff
                # Create a colored version for better visibility
                colored_diff = cv2.applyColorMap(diff_frame, cv2.COLORMAP_JET)
                colored_diff = cv2.cvtColor(colored_diff, cv2.COLOR_BGR2RGB)
                
                # Create the new overlay with partial transparency
                self.diff_overlay = self.axes.imshow(
                    colored_diff, 
                    interpolation='none',
                    alpha=0.3,  # Lower alpha for less filtering effect
                )
            else:
                # Already colored diff
                self.diff_overlay = self.axes.imshow(
                    diff_frame,
                    interpolation='none',
                    alpha=0.3,  # Lower alpha for less filtering effect
                )
            
            # Redraw the canvas
            self.draw_idle()
        except Exception as e:
            print(f"Error updating diff overlay: {e}")
            import traceback
            traceback.print_exc()
            
    def refresh(self):
        """Refresh the display with the last frame"""
        if self.last_frame is not None:
            self.update_image(self.last_frame, self.last_diff)