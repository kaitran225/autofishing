import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

class TimelinePlot(FigureCanvas):
    """Timeline plot for visualizing change history"""
    def __init__(self, parent=None, width=6, height=1, dpi=100):
        # Define modern clean theme colors for plot
        self.colors = {
            'bg_dark': '#1E1E2E',      # Deep blue-gray background
            'bg_panel': '#2A2A3C',     # Slightly lighter panel bg
            'grid': '#45475A',         # Grid lines
            'primary': '#89B4FA',      # Light blue accent
            'primary_light': '#B4BEFE', # Light blue highlight
            'alert': '#F38BA8',        # Soft red for alerts
            'text': '#CDD6F4',         # Main text color
            'text_dim': '#A6ADC8',     # Secondary text
        }
        
        # Create figure and axes with modern clean theme
        self.fig, self.ax = plt.subplots(figsize=(width, height), dpi=dpi)
        self.fig.set_facecolor(self.colors['bg_dark'])
        self.ax.set_facecolor(self.colors['bg_dark'])
        
        # Initialize with empty data
        self.x_data = np.arange(100)
        self.y_data = np.zeros(100)
        
        # Create the plot with primary accent colors
        self.activity_line, = self.ax.plot(self.x_data, self.y_data, 
                                          color=self.colors['primary'], 
                                          linewidth=1.5,
                                          alpha=0.9)
        
        self.threshold_line = self.ax.axhline(y=0.05, 
                                             color=self.colors['alert'], 
                                             linestyle='--', 
                                             alpha=0.8, 
                                             linewidth=1.5)
        
        # Configure appearance for modern clean theme
        self.ax.set_xlim(0, 99)
        self.ax.set_ylim(0, 1)
        self.ax.set_xticks([])
        
        # Add subtle grid lines
        self.ax.grid(True, alpha=0.2, color=self.colors['grid'])
        
        # Set text styling with smaller font - using standard fonts that matplotlib supports
        self.ax.set_title("Activity Timeline", 
                         color=self.colors['primary_light'], 
                         fontsize=10, 
                         fontweight='medium',
                         fontfamily='sans-serif')
        
        # Set text color for axis labels and ticks
        self.ax.tick_params(axis='y', colors=self.colors['text_dim'], labelsize=8)
        self.ax.yaxis.label.set_color(self.colors['text'])
        
        # Remove spines or make them subtle
        for spine in self.ax.spines.values():
            spine.set_color(self.colors['grid'])
            spine.set_linewidth(0.5)
        
        # Initialize the canvas
        super().__init__(self.fig)
        self.setParent(parent)
        
        # Set up a tight layout with smaller padding
        self.fig.tight_layout(pad=0.8)
        
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
        
        # Update title with threshold value
        self.ax.set_title(f"Activity Timeline [threshold: {threshold:.2f}]", 
                        color=self.colors['primary_light'], 
                        fontsize=9, 
                        fontweight='medium',
                        fontfamily='sans-serif')
        
        # Redraw the canvas
        self.draw() 