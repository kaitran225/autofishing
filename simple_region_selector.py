import tkinter as tk
from tkinter import ttk, simpledialog
import cv2
import numpy as np
import threading
import time
from PIL import Image, ImageTk
import mss
import mss.tools
import pygetwindow as gw
import psutil

class SimpleRegionSelector:
    def __init__(self, root):
        self.root = root
        self.root.title("Simple Region Selector")
        self.root.geometry("1000x600")
        self.root.minsize(800, 600)
        
        # Colors
        self.colors = {
            'bg_dark': '#121212',
            'text': '#FFFFFF',
            'accent': '#4CAF50',
            'highlight': '#2196F3',
            'warning': '#FF5722',
            'inactive': '#555555',
            'active': '#4CAF50'
        }
        
        # Initialize variables
        self.target_window = None
        self.selected_region = None  # Single region for all monitors
        self.is_monitoring = False
        self.monitor_thread = None
        self.sct = None  # Initialize this later in monitor_loop
        self.display_modes = ["Normal", "Grayscale", "Edge Detection", "Color Threshold"]
        
        # Configure the root window
        self.root.configure(bg=self.colors['bg_dark'])
        
        # Create main frame
        main_frame = tk.Frame(self.root, bg=self.colors['bg_dark'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create control frame (left side)
        control_frame = tk.Frame(main_frame, bg=self.colors['bg_dark'], width=300)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        control_frame.pack_propagate(False)
        
        # Create monitors frame (right side)
        monitors_frame = tk.Frame(main_frame, bg=self.colors['bg_dark'])
        monitors_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Create grid for monitors (2x2)
        self.monitor_frames = []
        self.canvases = []
        self.monitor_mode_labels = []
        
        # Create 4 monitor frames in a 2x2 grid
        for i in range(4):
            row = i // 2
            col = i % 2
            
            monitor_frame = tk.LabelFrame(
                monitors_frame,
                text=f"View {i+1}: {self.display_modes[i]}",
                bg=self.colors['bg_dark'],
                fg=self.colors['accent'],
                font=("Arial", 10, "bold")
            )
            monitor_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            # Canvas for displaying captured region
            canvas = tk.Canvas(
                monitor_frame,
                bg=self.colors['bg_dark'],
                highlightthickness=1,
                highlightbackground=self.colors['accent'],
                width=250,
                height=250
            )
            canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Mode label
            mode_label = tk.Label(
                monitor_frame,
                text=self.display_modes[i],
                bg=self.colors['bg_dark'],
                fg=self.colors['text'],
                font=("Arial", 9)
            )
            mode_label.pack(side=tk.BOTTOM, pady=(0, 5))
            
            # Store references
            self.monitor_frames.append(monitor_frame)
            self.canvases.append(canvas)
            self.monitor_mode_labels.append(mode_label)
        
        # Configure the grid to make cells expand evenly
        monitors_frame.grid_rowconfigure(0, weight=1)
        monitors_frame.grid_rowconfigure(1, weight=1)
        monitors_frame.grid_columnconfigure(0, weight=1)
        monitors_frame.grid_columnconfigure(1, weight=1)
        
        # Window selection section
        window_frame = tk.LabelFrame(
            control_frame,
            text="Window Selection",
            bg=self.colors['bg_dark'],
            fg=self.colors['accent'],
            font=("Arial", 12, "bold")
        )
        window_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Window list
        windows_label = tk.Label(
            window_frame,
            text="Select Target Window:",
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            font=("Arial", 10),
            anchor="w"
        )
        windows_label.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.window_listbox = tk.Listbox(
            window_frame,
            bg="#1E1E1E",
            fg=self.colors['text'],
            selectbackground=self.colors['highlight'],
            font=("Arial", 9),
            height=8
        )
        self.window_listbox.pack(fill=tk.X, padx=10, pady=5)
        self.window_listbox.bind("<<ListboxSelect>>", self.on_window_select)
        
        # Refresh window list button
        refresh_button = tk.Button(
            window_frame,
            text="Refresh Window List",
            command=self.refresh_window_list,
            bg="#333333",
            fg=self.colors['text'],
            activebackground=self.colors['accent'],
            activeforeground=self.colors['bg_dark'],
            font=("Arial", 9),
            relief=tk.FLAT,
            padx=10,
            pady=5
        )
        refresh_button.pack(padx=10, pady=10, fill=tk.X)
        
        # Region selection section
        region_frame = tk.LabelFrame(
            control_frame,
            text="Region Selection",
            bg=self.colors['bg_dark'],
            fg=self.colors['accent'],
            font=("Arial", 12, "bold")
        )
        region_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Region size
        size_frame = tk.Frame(region_frame, bg=self.colors['bg_dark'])
        size_frame.pack(fill=tk.X, padx=10, pady=10)
        
        size_label = tk.Label(
            size_frame,
            text="Region Size:",
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            font=("Arial", 10),
            width=10,
            anchor="w"
        )
        size_label.pack(side=tk.LEFT, padx=(0, 5))
        
        self.size_var = tk.StringVar(value="100")
        size_entry = tk.Entry(
            size_frame,
            textvariable=self.size_var,
            bg="#1E1E1E",
            fg=self.colors['text'],
            insertbackground=self.colors['text'],
            width=5,
            font=("Arial", 10)
        )
        size_entry.pack(side=tk.LEFT)
        
        px_label = tk.Label(
            size_frame,
            text="px",
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            font=("Arial", 10)
        )
        px_label.pack(side=tk.LEFT, padx=5)
        
        # Select region button
        select_button = tk.Button(
            region_frame,
            text="Select Region",
            command=self.select_region,
            bg=self.colors['accent'],
            fg=self.colors['bg_dark'],
            activebackground=self.colors['highlight'],
            activeforeground=self.colors['bg_dark'],
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            padx=10,
            pady=8
        )
        select_button.pack(padx=10, pady=10, fill=tk.X)
        
        # Window info
        self.window_info = tk.Label(
            region_frame,
            text="No window selected",
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            font=("Arial", 9),
            anchor="w",
            justify=tk.LEFT,
            wraplength=220
        )
        self.window_info.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Status label
        self.status_label = tk.Label(
            control_frame,
            text="Ready to select window",
            bg=self.colors['bg_dark'],
            fg=self.colors['text'],
            font=("Arial", 10)
        )
        self.status_label.pack(pady=(10, 5), fill=tk.X)
        
        # Start/Stop monitoring
        self.monitor_button = tk.Button(
            control_frame,
            text="Start Monitoring",
            command=self.toggle_monitoring,
            bg="#333333",
            fg=self.colors['text'],
            activebackground=self.colors['accent'],
            activeforeground=self.colors['bg_dark'],
            font=("Arial", 10, "bold"),
            relief=tk.FLAT,
            padx=10,
            pady=8,
            state=tk.DISABLED
        )
        self.monitor_button.pack(pady=5, fill=tk.X)
        
        # Initialize
        self.refresh_window_list()
        
        # Get monitor info
        with mss.mss() as sct:
            self.monitors = sct.monitors
            print(f"Detected {len(self.monitors)} monitors:")
            for i, m in enumerate(self.monitors):
                print(f"  Monitor {i}: {m['width']}x{m['height']} at ({m['left']},{m['top']})")

    def refresh_window_list(self):
        """Refresh the list of available windows"""
        self.window_listbox.delete(0, tk.END)
        self.windows = []
        
        # Get all windows
        all_windows = gw.getAllWindows()
        
        for window in all_windows:
            # Filter out small or system windows
            if (window.width > 100 and window.height > 100 and 
                window.title and window.title != ""):
                self.window_listbox.insert(tk.END, window.title)
                self.windows.append(window)
        
        self.status_label.config(text="Select a window from the list")
    
    def on_window_select(self, event):
        """Handle window selection from the listbox"""
        if not self.window_listbox.curselection():
            return
        
        index = self.window_listbox.curselection()[0]
        self.target_window = self.windows[index]
        
        # Update window info
        info_text = (
            f"Title: {self.target_window.title}\n"
            f"Size: {self.target_window.width}×{self.target_window.height}\n"
            f"Position: ({self.target_window.left}, {self.target_window.top})"
        )
        self.window_info.config(text=info_text)
        self.status_label.config(text=f"Selected: {self.target_window.title}")

    def select_region(self):
        """Select a region of the target window"""
        if not self.target_window:
            self.status_label.config(text="Error: No window selected")
            return
        
        # Ensure window is still valid
        try:
            title = self.target_window.title
            if not self.target_window.isActive:
                self.target_window.activate()
                time.sleep(0.2)  # Give time to activate
        except Exception as e:
            self.status_label.config(text=f"Error: Window not available")
            return
        
        try:
            # Get region size
            try:
                size = int(self.size_var.get())
                if size < 10:
                    self.status_label.config(text="Error: Size must be at least 10px")
                    return
            except ValueError:
                self.status_label.config(text="Error: Invalid size value")
                return
            
            # Temporarily minimize our window
            self.root.iconify()
            time.sleep(0.3)
            
            # Get window position and size
            win_left = self.target_window.left
            win_top = self.target_window.top
            win_width = self.target_window.width
            win_height = self.target_window.height
            
            # Create selection overlay
            overlay = tk.Toplevel(self.root)
            overlay.attributes('-alpha', 0.3)
            overlay.attributes('-topmost', True)
            overlay.overrideredirect(True)
            overlay.geometry(f"{win_width}x{win_height}+{win_left}+{win_top}")
            
            # Create canvas for drawing
            canvas = tk.Canvas(overlay, bg="black", highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)
            
            # Variables for selection
            region_rect = None
            preview_cross = None
            preview_info = None
            
            def on_mouse_move(event):
                nonlocal region_rect, preview_cross, preview_info
                
                # Calculate region coordinates
                left = max(0, min(event.x - size//2, win_width - size))
                top = max(0, min(event.y - size//2, win_height - size))
                right = left + size
                bottom = top + size
                
                # Clear previous drawings
                if region_rect:
                    canvas.delete(region_rect)
                if preview_cross:
                    canvas.delete(preview_cross[0])
                    canvas.delete(preview_cross[1])
                if preview_info:
                    canvas.delete(preview_info)
                
                # Draw selection rectangle
                region_rect = canvas.create_rectangle(
                    left, top, right, bottom,
                    outline="#00FF00",
                    width=2
                )
                
                # Draw crosshair
                h_line = canvas.create_line(
                    0, event.y, win_width, event.y,
                    fill="#00FFFF", dash=(4, 4)
                )
                v_line = canvas.create_line(
                    event.x, 0, event.x, win_height,
                    fill="#00FFFF", dash=(4, 4)
                )
                preview_cross = (h_line, v_line)
                
                # Show coordinates
                preview_info = canvas.create_text(
                    win_width//2, win_height - 30,
                    text=f"Position: ({win_left + left}, {win_top + top}) • Size: {size}×{size}",
                    fill="white",
                    font=("Arial", 10)
                )
            
            def on_mouse_click(event):
                # Calculate region coordinates (absolute screen coordinates)
                left = max(0, min(event.x - size//2, win_width - size))
                top = max(0, min(event.y - size//2, win_height - size))
                
                # Convert to absolute screen coordinates
                screen_left = win_left + left
                screen_top = win_top + top
                
                # Store the selected region
                self.selected_region = {
                    'left': screen_left,
                    'top': screen_top, 
                    'width': size,
                    'height': size
                }
                
                # Close overlay
                overlay.destroy()
                self.root.deiconify()
                
                # Update status
                self.status_label.config(
                    text=f"Region selected: {size}×{size} at ({screen_left}, {screen_top})"
                )
                
                # Enable monitoring button
                self.monitor_button.config(state=tk.NORMAL)
                
                # Take a preview screenshot
                self.take_preview_screenshot()
            
            # Bind events
            canvas.bind("<Motion>", on_mouse_move)
            canvas.bind("<Button-1>", on_mouse_click)
            
            # Add instruction text
            canvas.create_text(
                win_width//2, 30,
                text="Click to select region • ESC to cancel",
                fill="white",
                font=("Arial", 12, "bold")
            )
            
            # Handle escape key
            def on_escape(event):
                overlay.destroy()
                self.root.deiconify()
            
            overlay.bind("<Escape>", on_escape)
            
        except Exception as e:
            print(f"Error in region selection: {str(e)}")
            self.status_label.config(text=f"Error: {str(e)}")
            self.root.deiconify()
    
    def take_preview_screenshot(self):
        """Take a preview screenshot of the selected region"""
        if not self.selected_region:
            return
            
        try:
            with mss.mss() as sct:
                # Capture the region
                screenshot = sct.grab(self.selected_region)
                
                # Display in all 4 views with different processing
                self.process_and_display_image(Image.frombytes("RGB", screenshot.size, screenshot.rgb))
                
        except Exception as e:
            print(f"Error taking preview screenshot: {str(e)}")
            self.status_label.config(text=f"Error: {str(e)}")
    
    def toggle_monitoring(self):
        """Start or stop monitoring the selected region"""
        if self.is_monitoring:
            # Stop monitoring
            self.is_monitoring = False
            self.monitor_button.config(text="Start Monitoring")
            self.status_label.config(text="Monitoring stopped")
        else:
            # Start monitoring
            if not self.selected_region:
                self.status_label.config(text="Error: No region selected")
                return
                
            self.is_monitoring = True
            self.monitor_button.config(text="Stop Monitoring")
            self.status_label.config(text="Monitoring active...")
            
            # Start monitor thread
            if not self.monitor_thread or not self.monitor_thread.is_alive():
                self.monitor_thread = threading.Thread(target=self.monitor_loop)
                self.monitor_thread.daemon = True
                self.monitor_thread.start()
    
    def monitor_loop(self):
        """Monitor loop to capture and display the selected region"""
        # Create a new mss instance inside this thread
        with mss.mss() as sct:
            frame_count = 0
            start_time = time.time()
            fps_update_interval = 1.0  # Update FPS every second
            
            while self.is_monitoring:
                try:
                    if not self.selected_region:
                        time.sleep(0.1)
                        continue
                    
                    # Capture the region
                    screenshot = sct.grab(self.selected_region)
                    
                    # Convert to PIL Image
                    img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
                    
                    # Calculate FPS
                    frame_count += 1
                    elapsed_time = time.time() - start_time
                    if elapsed_time >= fps_update_interval:
                        fps = frame_count / elapsed_time
                        frame_count = 0
                        start_time = time.time()
                        
                        # Update status with FPS info
                        region = self.selected_region
                        
                        # Use the main thread to update UI
                        self.root.after(0, lambda f=fps, r=region: self.status_label.config(
                            text=f"LIVE: {r['width']}×{r['height']} • {f:.1f} FPS"
                        ))
                    
                    # Use the main thread to update UI with processed images
                    self.root.after(0, lambda img=img: self.process_and_display_image(img))
                    
                except Exception as e:
                    print(f"Error in monitor loop: {str(e)}")
                    if self.is_monitoring:  # Only update if still monitoring
                        self.root.after(0, lambda e=e: self.status_label.config(text=f"Error: {str(e)}"))
                    time.sleep(0.5)  # Slow down on errors
                    continue
                
                # Try to maintain a steady frame rate
                try:
                    # Check system load for adaptive frame rate
                    system_load = psutil.cpu_percent(interval=None)
                    if system_load > 80:
                        time.sleep(0.05)  # 20 FPS for high load
                    elif system_load > 50:
                        time.sleep(0.033)  # 30 FPS for medium load
                    else:
                        time.sleep(0.016)  # 60 FPS for low load
                except:
                    time.sleep(0.033)  # Default 30 FPS
    
    def process_and_display_image(self, img):
        """Process captured image in different ways and display in all 4 monitors"""
        try:
            # Store original image
            images = [img]
            
            # Mode 1: Grayscale
            gray_img = img.convert('L')
            gray_img = Image.merge('RGB', (gray_img, gray_img, gray_img))  # Convert back to RGB
            images.append(gray_img)
            
            # Mode 2: Edge detection (using OpenCV)
            cv_img = np.array(img)
            # Convert RGB to BGR for OpenCV
            cv_img = cv_img[:, :, ::-1].copy()
            # Convert to grayscale
            gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            # Apply Canny edge detection
            edges = cv2.Canny(gray, 100, 200)
            # Convert back to RGB
            edges_rgb = cv2.cvtColor(edges, cv2.COLOR_GRAY2RGB)
            edge_img = Image.fromarray(edges_rgb)
            images.append(edge_img)
            
            # Mode 3: Color threshold
            cv_img_hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
            # Green range in HSV
            lower_green = np.array([40, 40, 40])
            upper_green = np.array([80, 255, 255])
            # Create a mask of green areas
            mask = cv2.inRange(cv_img_hsv, lower_green, upper_green)
            # Apply the mask to the original image
            result = cv2.bitwise_and(cv_img, cv_img, mask=mask)
            thresh_img = Image.fromarray(result[:, :, ::-1])  # Convert BGR back to RGB
            images.append(thresh_img)
            
            # Display images in each canvas
            for i, processed_img in enumerate(images):
                # Scale image to fit canvas (max 250x250)
                canvas_width = 250
                canvas_height = 250
                
                # Calculate scaling factor
                width, height = processed_img.size
                scale = min(canvas_width / width, canvas_height / height)
                
                # Apply scaling
                new_width = int(width * scale)
                new_height = int(height * scale)
                
                # Resize the image
                resized_img = processed_img.resize((new_width, new_height), Image.LANCZOS)
                
                # Convert to PhotoImage
                photo = ImageTk.PhotoImage(resized_img)
                
                # Store reference to avoid garbage collection
                setattr(self, f"_current_photo_{i}", photo)
                
                # Clear canvas and display image
                self.canvases[i].delete("all")
                
                # Center the image in the canvas
                x_offset = (canvas_width - new_width) // 2
                y_offset = (canvas_height - new_height) // 2
                
                self.canvases[i].create_image(x_offset, y_offset, anchor=tk.NW, image=photo)
                self.canvases[i].image = photo  # Keep a reference
                
        except Exception as e:
            print(f"Error processing image: {e}")
            import traceback
            traceback.print_exc()

def main():
    root = tk.Tk()
    app = SimpleRegionSelector(root)
    
    # Set window position to center of screen
    window_width = 1000
    window_height = 600
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    center_x = int(screen_width/2 - window_width/2)
    center_y = int(screen_height/2 - window_height/2)
    root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
    
    root.mainloop()

if __name__ == "__main__":
    main() 