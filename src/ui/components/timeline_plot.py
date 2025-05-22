import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

class TimelinePlot(FigureCanvas):
    """Timeline plot for visualizing change history"""
    def __init__(self, parent=None, width=6, height=1, dpi=100):
        # Define matcha wood theme colors for plot
        self.colors = {
            'bg_dark': '#2C3639',      # Deep charcoal background
            'bg_wood': '#3F4E4F',      # Wood tone
            'grid': '#555555',         # Grid color
            'matcha': '#A0C49D',       # Medium matcha
            'matcha_light': '#DAE5D0', # Light matcha
            'alert': '#F87474',        # Soft red
            'text': '#FFFFFF',         # White text
            'text_dim': '#DCD7C9',     # Dim text
        }
        
        # Create figure and axes with matcha wood theme
        self.fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        self.fig.set_facecolor(self.colors['bg_wood'])
        self.ax.set_facecolor(self.colors['bg_wood'])
        
        # Initialize with empty data
        self.x_data = np.arange(100)
        self.y_data = np.zeros(100)
        
        # Create the plot with matcha colors
        self.activity_line, = self.ax.plot(self.x_data, self.y_data, color=self.colors['matcha'], linewidth=1.5)
        self.threshold_line = self.ax.axhline(y=0.05, color=self.colors['alert'], linestyle='--', alpha=0.7, linewidth=1)
        
        # Configure appearance for matcha wood theme
        self.ax.set_xlim(0, 99)
        self.ax.set_ylim(0, 1)
        self.ax.set_xticks([])
        
        # Add subtle grid lines
        self.ax.grid(True, alpha=0.15, color=self.colors['grid'])
        
        # Set text styling - using standard fonts that matplotlib supports
        self.ax.set_title("Activity Timeline", color=self.colors['matcha_light'], fontsize=11, 
                         fontweight='medium')
        
        # Set text color for axis labels and ticks
        self.ax.tick_params(axis='y', colors=self.colors['text_dim'], labelsize=9)
        self.ax.yaxis.label.set_color(self.colors['text'])
        
        # Remove spines
        for spine in self.ax.spines.values():
            spine.set_color(self.colors['grid'])
            spine.set_linewidth(0.5)
        
        # Initialize the canvas
        super().__init__(self.fig)
        self.setParent(parent)
        
        # Set up a tight layout
        self.fig.tight_layout(pad=1.2)
        
    def update_plot(self, history, threshold):
        """Update the plot with new data"""
        if not history:
            return
            
        # Create data array, padded with zeros if necessary
        data = history[-100:].copy()
        if len(data) < 100:
            data = [0] * (100 - len(data)) + data
            
        # Update the plot
        self.activity_line.set_ydata(data)
        self.threshold_line.set_ydata([threshold, threshold])
        
        # Update title with threshold value in minimal format - using standard fonts
        self.ax.set_title(f"Activity Timeline [threshold: {threshold:.2f}]", 
                        color=self.colors['matcha_light'], fontsize=11, 
                        fontweight='medium')
        
        # Redraw the canvas
        self.draw() 