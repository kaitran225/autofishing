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

class MatplotlibCanvas(FigureCanvas):
    """Matplotlib canvas for displaying real-time monitoring data"""
    
    def __init__(self, parent=None, width=5, height=3.33, dpi=100, bg_color='#333333'):
        # Create figure with correct aspect ratio (1.5:1 width to height)
        # Add extra height for the timeline
        adjusted_height = height * 1.15  # Add 15% height for timeline
        self.fig = Figure(figsize=(width, adjusted_height), dpi=dpi, facecolor=bg_color)
        
        # Create properly spaced subplots - one for image, one for timeline
        gs = self.fig.add_gridspec(2, 1, height_ratios=[9, 1], hspace=0.15)
        
        # Main image display - top subplot
        self.current_ax = self.fig.add_subplot(gs[0, 0])
        self.current_ax.set_facecolor(bg_color)
        self.current_ax.axis('off')
        
        # Initialize empty image with correct aspect ratio (1.5:1)
        empty_img = np.zeros((100, 150, 3), dtype=np.uint8)  # 150x100 = 1.5:1 ratio
        self.current_image = self.current_ax.imshow(empty_img, aspect='equal', interpolation='none')
        self.diff_overlay = self.current_ax.imshow(np.zeros((100, 150, 4), dtype=np.uint8), 
                                                  alpha=0.5, interpolation='none')
        
        # Add rectangle border around image
        rect = plt.Rectangle((0, 0), 1, 1, fill=False, ec='#666', linewidth=1.5, 
                            transform=self.current_ax.transAxes, clip_on=False)
        self.current_ax.add_patch(rect)
        
        # Add timeline for activity monitoring in separate subplot
        self.timeline_ax = self.fig.add_subplot(gs[1, 0])
        self.timeline_ax.set_facecolor(bg_color)
        self.timeline_ax.set_xticks([])
        self.timeline_ax.set_yticks([])
        
        # Add border for timeline
        self.timeline_ax.spines['top'].set_visible(False)
        self.timeline_ax.spines['right'].set_visible(False)
        self.timeline_ax.spines['bottom'].set_visible(False)
        self.timeline_ax.spines['left'].set_visible(False)
        
        # Initialize timeline data
        x_data = np.arange(100)
        y_data = np.ones(100) * 0.5
        self.activity_line, = self.timeline_ax.plot(x_data, y_data, color='#77DD77', linewidth=1.5)
        self.threshold_line = self.timeline_ax.axhline(y=0.05, color='#FF6961', 
                                                      linestyle='--', alpha=0.7, linewidth=1)
        self.timeline_ax.set_ylim(0, 1)
        
        # Add title to timeline with threshold value
        self.timeline_ax.set_title("ACTIVITY", color='#77DD77', fontsize=8, fontweight='normal', pad=2)
        
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
        # Update aspect ratio by adjusting the axes
        self.current_ax.set_aspect('equal')
        self.current_ax.figure.canvas.draw_idle()

    def update_image(self, frame=None, diff_frame=None):
        """Update the displayed image maintaining aspect ratio"""
        if self.placeholder_text:
            self.placeholder_text.remove()
            self.placeholder_text = None
            
        if frame is not None:
            # If frame doesn't have the correct aspect ratio, resize it
            h, w = frame.shape[:2]
            target_ratio = 1.5
            actual_ratio = w / h
            
            if abs(actual_ratio - target_ratio) > 0.01:  # If ratio is off by more than 1%
                # Resize the image to match the target ratio
                new_w = w
                new_h = int(w / target_ratio)
                if new_h > h:
                    new_h = h
                    new_w = int(h * target_ratio)
                
                # Center crop to the new size
                y_start = (h - new_h) // 2
                x_start = (w - new_w) // 2
                frame = frame[y_start:y_start+new_h, x_start:x_start+new_w]
                
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
        
        # Ensure display maintains correct aspect ratio
        self.current_ax.set_aspect('equal')
        self.current_ax.figure.canvas.draw_idle()
    
    def update_timeline(self, history=None, threshold=0.05):
        """Update the activity timeline"""
        if history and len(history) > 0:
            # Normalize values to 0-1 range for clean display
            max_val = max(history) if max(history) > 0 else 1
            normalized_history = [min(h / max_val, 1.0) for h in history]
            
            # Pad with zeros if needed
            if len(normalized_history) < 100:
                normalized_history = [0] * (100 - len(normalized_history)) + normalized_history
            elif len(normalized_history) > 100:
                normalized_history = normalized_history[-100:]
                
            # Update the line data
            self.activity_line.set_ydata(normalized_history)
            
            # Update threshold line position (normalized)
            threshold_value = min(threshold / max_val, 1.0)
            self.threshold_line.set_ydata([threshold_value, threshold_value])
        
        self.fig.canvas.draw_idle() 