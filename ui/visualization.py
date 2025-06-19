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
    """Timeline canvas for displaying real-time activity graph"""
    
    def __init__(self, parent=None, width=5, height=1, dpi=100, bg_color='#333333'):
        # Create figure for the timeline with proper sizing
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor=bg_color)
        self.fig.subplots_adjust(left=0.02, right=0.98, top=0.85, bottom=0.15)  # Maximize plot area
        
        # Create a single subplot for the timeline
        self.timeline_ax = self.fig.add_subplot(111)
        self.timeline_ax.set_facecolor(bg_color)
        
        # Clean up axis ticks - only show y-axis on left with minimal ticks
        self.timeline_ax.set_xticks([])
        self.timeline_ax.set_yticks([0, 0.5, 1.0])
        self.timeline_ax.set_yticklabels(['0', '', '1'], fontsize=8, color='#aaaaaa')
        self.timeline_ax.tick_params(axis='y', colors='#999999', labelsize=7, length=2, pad=1)
        
        # Add subtle grid with low opacity
        self.timeline_ax.grid(True, linestyle=':', alpha=0.2, color='#999999')
        
        # Clean up spines (borders)
        for spine in ['top', 'right', 'bottom', 'left']:
            self.timeline_ax.spines[spine].set_visible(False)
        
        # Initialize timeline data
        x_data = np.arange(100)
        y_data = np.zeros(100)  # Start with zeros
        
        # Add a subtle background area fill
        self.timeline_ax.fill_between(x_data, 0, 0, color='#77DD77', alpha=0.05)
        
        # Add the main activity line with a slight gradient effect
        self.activity_line, = self.timeline_ax.plot(x_data, y_data, color='#77DD77', 
                                                   linewidth=1.5, alpha=0.9)
        
        # Add threshold line with better visibility
        self.threshold_line = self.timeline_ax.axhline(y=0.05, color='#FF6961', 
                                                      linestyle='--', alpha=0.7, linewidth=1)
        
        # Add annotations for clarity
        self.threshold_annotation = self.timeline_ax.annotate(
            'threshold', xy=(99, 0.05), xytext=(92, 0.1),
            textcoords='data', color='#FF6961', fontsize=7, alpha=0.8,
            bbox=dict(boxstyle='round,pad=0.1', fc=bg_color, alpha=0.7, ec='none')
        )
        self.threshold_annotation.set_visible(False)  # Start hidden
        
        # Set axis limits
        self.timeline_ax.set_ylim(0, 1.05)  # Slight padding at top
        self.timeline_ax.set_xlim(0, 99)
        
        # Add title to timeline with threshold value - more compact
        self.timeline_ax.set_title("ACTIVITY", color='#77DD77', 
                                  fontsize=9, fontweight='bold', pad=2)
        
        # Initialize the figure canvas
        super(ActivityGraphCanvas, self).__init__(self.fig)
        self.setParent(parent)
        
        # Set minimum height
        self.setMinimumHeight(60)
        
    def update(self, history=None, threshold=0.05):
        """Update the activity graph with new data"""
        try:
            if not history:
                # If no data, just clear the graph and return
                self.activity_line.set_ydata([0] * 100)
                # Clear all collections
                for collection in self.timeline_ax.collections:
                    collection.remove()
                self.threshold_line.set_ydata([threshold, threshold])
                self.canvas.draw_idle()
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
                collection.remove()

            # Add new fill
            fill_data = data.copy()
            for i in range(len(fill_data)):
                if fill_data[i] > threshold:
                    # Do nothing - keep the value above threshold
                    pass
                else:
                    fill_data[i] = 0  # Set below-threshold values to 0
            
            # Create the fill between activity line and zero baseline
            x_data = range(len(fill_data))
            self.timeline_ax.fill_between(
                x_data, fill_data, 0, 
                where=(fill_data > threshold),
                interpolate=True, 
                color=self.theme_colors.get('accent', '#77DD77'), 
                alpha=0.3
            )

            # Redraw the canvas
            self.canvas.draw_idle()
        except Exception as e:
            print(f"Error updating activity graph: {e}")
            import traceback
            traceback.print_exc()

class MatplotlibCanvas(FigureCanvas):
    """Matplotlib canvas for displaying real-time monitoring data"""
    
    def __init__(self, parent=None, width=5, height=3.33, dpi=100, bg_color='#333333'):
        # Create figure with correct aspect ratio (1.5:1 width to height)
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor=bg_color)
        
        # Maximize the plot area by removing margins
        self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=0, hspace=0)
        
        # Main image display
        self.current_ax = self.fig.add_subplot(111)
        self.current_ax.set_facecolor(bg_color)
        self.current_ax.axis('off')
        
        # Initialize empty image with correct aspect ratio (1.5:1)
        empty_img = np.zeros((100, 150, 3), dtype=np.uint8)  # 150x100 = 1.5:1 ratio
        self.current_image = self.current_ax.imshow(empty_img, aspect='auto', interpolation='none')
        self.diff_overlay = self.current_ax.imshow(np.zeros((100, 150, 4), dtype=np.uint8), 
                                                  alpha=0.5, interpolation='none')
        
        # Add rectangle border around image - for the full frame
        rect = plt.Rectangle((0, 0), 1, 1, fill=False, ec='#666', linewidth=1.5, 
                            transform=self.current_ax.transAxes, clip_on=False)
        self.current_ax.add_patch(rect)
        
        # Initialize the figure canvas
        super(MatplotlibCanvas, self).__init__(self.fig)
        self.setParent(parent)
        
        # Add placeholder text
        self.placeholder_text = self.fig.text(0.5, 0.45, "Awaiting data...", color='#999', 
                                             ha='center', va='center', fontsize=10)
        
        # Set min/fixed size to maintain aspect ratio
        self.setMinimumSize(300, 200)
        
    def resizeEvent(self, event):
        """Handle resize events to maintain proper aspect ratio"""
        super().resizeEvent(event)
        # Don't constrain to equal aspect ratio to allow filling available space
        self.current_ax.figure.canvas.draw_idle()

    def update_image(self, frame=None, diff_frame=None):
        """Update the displayed image maintaining aspect ratio"""
        if self.placeholder_text:
            self.placeholder_text.remove()
            self.placeholder_text = None
            
        if frame is not None:
            # Keep the original frame dimensions to fill the space
            self.current_image.set_data(frame)
            
        if diff_frame is not None:
            # Create a colored diff frame with alpha channel
            diff_display = cv2.convertScaleAbs(diff_frame, alpha=3)
            diff_colored = cv2.applyColorMap(diff_display, cv2.COLORMAP_INFERNO)
            colored_diff = cv2.cvtColor(diff_colored, cv2.COLOR_BGR2RGB)
            
            colored_diff_alpha = np.zeros((colored_diff.shape[0], colored_diff.shape[1], 4), dtype=np.uint8)
            colored_diff_alpha[..., :3] = colored_diff
            
            # Set alpha based on difference intensity
            alpha_threshold = 30
            for i in range(diff_display.shape[0]):
                for j in range(diff_display.shape[1]):
                    if diff_display[i, j] > alpha_threshold:
                        # Scale alpha with intensity
                        safe_value = min(127, diff_display[i, j])
                        colored_diff_alpha[i, j, 3] = min(255, int(safe_value * 2))
                    else:
                        colored_diff_alpha[i, j, 3] = 0
            
            self.diff_overlay.set_data(colored_diff_alpha)
        
        # Use 'auto' aspect ratio to fill the available space
        self.current_ax.set_aspect('auto')
        self.current_ax.figure.canvas.draw_idle() 