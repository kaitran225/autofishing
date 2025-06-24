# AutoFisher: Comprehensive Improvement Guide

This document combines analysis and recommendations for improving the AutoFisher Qt project by learning from the strengths of the prototype implementation.

## Table of Contents
1. [Critical Improvements](#critical-improvements)
2. [Feature Enhancements](#feature-enhancements)
3. [Prototype-Inspired Implementation](#prototype-inspired-implementation)
4. [Implementation Plan](#implementation-plan)
5. [Completed Improvements](#completed-improvements)

---

<a id="critical-improvements"></a>
# 1. Critical Improvements

Based on the comprehensive analysis comparing the AutoFisher Qt project with the prototype, these are specific improvements that can be made to the Qt version by learning from the prototype's strengths.

## 1.1. Window Management Improvements

- [ ] **Implement Tiered Window Focus Strategy**  
  *Priority: High*  
  Adopt the prototype's layered approach to window focusing: try quick, lightweight methods first (direct SetForegroundWindow) before resorting to more heavyweight approaches.
  ```python
  # Example implementation
  def focus_play_together_window(self):
      # Quick attempt first
      if self.play_together_window:
          try:
              user32.SetForegroundWindow(self.play_together_window)
              time.sleep(0.05)
              # Verify focus success
              if user32.GetForegroundWindow() == self.play_together_window:
                  return True
          except Exception:
              pass  # Fall through to more intensive method
          
      # Only use heavyweight method if quick method failed    
      return force_focus_window(self.play_together_window)
  ```

- [ ] **Enhanced Window Detection**  
  *Priority: Medium*  
  Add more flexible window name matching similar to the prototype for better game window detection.
  
- [ ] **Add Specific Fullscreen App Detection**  
  *Priority: Medium*  
  Implement the prototype's fullscreen detection and handling to better respect other applications.

## 1.2. Input Simulation Enhancements

- [ ] **Multi-Method Input Redundancy**  
  *Priority: High*  
  Implement the prototype's cascading approach to key input:
  ```python
  def send_key_press(key, window_handle):
      # Method 1: Direct Windows API
      try:
          # SendInput implementation
          success = send_input_method(key)
          if success:
              return True
      except Exception:
          pass
          
      # Method 2: PostMessage approach
      try:
          win32gui.PostMessage(window_handle, win32con.WM_CHAR, ord(key.lower()), 0)
          return True
      except Exception:
          pass
          
      # Method 3: Fallback to keyboard library
      try:
          keyboard.press_and_release(key)
          return True
      except Exception:
          return False
  ```

- [ ] **Special Case Input Handling**  
  *Priority: Medium*  
  Add specific handling for different input scenarios (e.g., minimized window, fullscreen, etc.)

## 1.3. Detection Algorithm Optimizations

- [ ] **Fast-Path Detection Option**  
  *Priority: High*  
  Add an option to use the prototype's simpler, more responsive detection algorithm for scenarios requiring immediate response:
  ```python
  def calculate_frame_difference(self, frame1, frame2, fast_mode=False):
      # Fast path for immediate response (like prototype)
      if fast_mode:
          # Simple HSV difference calculation without morphological operations
          return self._calculate_simple_difference(frame1, frame2)
      
      # Normal path with full processing
      return self._calculate_enhanced_difference(frame1, frame2)
  ```

- [ ] **Hybrid Confidence System**  
  *Priority: Medium*  
  Combine immediate threshold detection with confidence building:
  - Trigger on major changes immediately (prototype style)
  - Use confidence building for subtle changes (Qt style)

## 1.4. Resource Management

- [ ] **Optimize Screen Capture**  
  *Priority: High*  
  Adopt the prototype's approach of creating/destroying MSS instances for each capture to prevent resource leaks, especially for long-running sessions:
  ```python
  def capture_screen(self):
      # Create fresh MSS instance each time (like prototype)
      with mss.mss() as sct:
          # Perform capture
          screenshot = sct.grab(self.mss_region)
          # Process immediately
          frame = np.array(screenshot)
          return frame
      # MSS instance automatically cleaned up
  ```

- [ ] **Simplified Thread Management**  
  *Priority: Medium*  
  Reduce complexity in thread control and management by adopting the prototype's simpler approach.

## 1.5. Error Recovery & Resilience

- [ ] **Integrate Fallback Mechanisms**  
  *Priority: High*  
  Add fallback approaches for critical operations similar to the prototype.

- [ ] **Fast Restart Capability**  
  *Priority: Medium*  
  Implement the prototype's ability to quickly restart detection without full reinitialization.

- [ ] **Simplified State Management**  
  *Priority: Medium*  
  Reduce state complexity by consolidating thread control flags and detection state.

## 1.6. Architecture Improvements

- [ ] **Reduce Abstraction Layers**  
  *Priority: Medium*  
  Flatten some of the class hierarchy to reduce indirection for critical paths.

- [ ] **Direct Mode Option**  
  *Priority: High*  
  Add a "direct mode" configuration option that bypasses most of the abstraction layers for critical operations:
  ```python
  def send_fishing_key(self):
      if self.config.direct_mode:
          # Direct implementation similar to prototype
          # Bypass utility functions and abstractions
          return self._send_key_direct()
      else:
          # Normal implementation with abstraction layers
          return send_key_press(self.fishing_key, self.play_together_window)
  ```

## 1.7. User Interface Enhancements

- [ ] **Prototype Compatibility Mode**  
  *Priority: Medium*  
  Add a UI toggle for "Prototype Compatibility Mode" that enables direct implementations.

- [ ] **Performance Mode Toggle**  
  *Priority: Medium*  
  Add option to disable advanced features for better performance on low-end systems.

---

<a id="feature-enhancements"></a>
# 2. Feature Enhancements

Based on analysis of the prototype implementation, this section outlines specific feature enhancements that could be integrated into the Qt version to improve functionality and user experience.

## 2.1. Detection System Enhancements

### Multi-Zone Detection Capability
The prototype uses a flexible detection region system that could be enhanced further:

- [ ] **Implement multiple detection zones with different sensitivities**
  ```python
  class MultiZoneDetector:
      def __init__(self):
          self.primary_zone = {"region": (100, 100, 200, 200), "sensitivity": 0.8}
          self.secondary_zones = [
              {"region": (300, 100, 400, 200), "sensitivity": 0.5},
              {"region": (500, 100, 600, 200), "sensitivity": 0.3}
          ]
  ```

- [ ] **Zone-specific algorithms**  
  Allow different detection algorithms for different screen regions (e.g., simple pixel change for bobber, HSV for splash)

### Visual Pattern Recognition

- [ ] **Add template matching functionality**
  ```python
  def detect_template(self, frame, template, threshold=0.8):
      """Detect a specific visual pattern in the frame"""
      result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
      locations = np.where(result >= threshold)
      return list(zip(*locations[::-1])) if len(locations[0]) > 0 else []
  ```

- [ ] **Fish type identification**  
  Build a database of splash patterns to identify different fish types

## 2.2. Automation Improvements

### Adaptive Timing System

- [ ] **Dynamic timing adjustment**  
  Analyze game response patterns to dynamically adjust timings:
  ```python
  def adaptive_wait(self, action_type):
      """Wait appropriate time based on historical timing data"""
      if action_type not in self.timing_history:
          return self.default_timings[action_type]
      
      # Use rolling average with outlier rejection
      recent_timings = self.timing_history[action_type][-10:]
      if len(recent_timings) >= 3:
          # Remove outliers (values more than 2 std devs from mean)
          mean = statistics.mean(recent_timings)
          stdev = statistics.stdev(recent_timings) if len(recent_timings) > 1 else 0
          filtered = [t for t in recent_timings if abs(t - mean) <= 2 * stdev]
          return statistics.mean(filtered) if filtered else mean
      return statistics.mean(recent_timings)
  ```

- [ ] **Session-specific timing profiles**  
  Save and load timing profiles for specific games or network conditions

### Advanced Automation Sequences

- [ ] **Custom action sequence recording**
  ```python
  def record_custom_sequence(self):
      """Record user actions to create custom automation sequence"""
      print("Recording sequence - press ESC to stop")
      sequence = []
      start_time  = time.time()
      last_action_time = start_time
      
      # Simplified keyboard hook example
      while True:
          if keyboard.is_pressed('esc'):
              break
          
          for key in "wasdrf":  # Common fishing keys
              if keyboard.is_pressed(key):
                  current_time = time.time()
                  delay = current_time - last_action_time
                  sequence.append({"key": key, "delay": delay})
                  last_action_time = current_time
                  time.sleep(0.1)  # Debounce
      
      return sequence
  ```

- [ ] **Sequence optimization**  
  Analyze and optimize recorded sequences for maximum efficiency

## 2.3. User Interface Features

### Enhanced Visual Feedback

- [ ] **Live detection visualization**
  ```python
  def update_visualization_frame(self, frame, regions, confidence):
      """Update UI with detection visualization"""
      # Draw detection regions
      for region in regions:
          x, y, w, h = region
          cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
      
      # Add confidence meter
      bar_width = 100
      bar_height = 20
      fill_width = int(bar_width * confidence)
      cv2.rectangle(frame, (10, 10), (10+bar_width, 10+bar_height), (0, 0, 0), -1)
      cv2.rectangle(frame, (10, 10), (10+fill_width, 10+bar_height), (0, 255, 0), -1)
      
      return frame
  ```

- [ ] **Fish activity graph**  
  Show graph of detection activity over time to help tune sensitivity

### Configuration GUI Improvements

- [ ] **Visual region selector**
  ```python
  class RegionSelectorUI:
      """Visual interface for selecting screen regions"""
      def __init__(self, parent):
          self.parent = parent
          self.start_pos = None
          self.current_pos = None
          self.regions = []
          
      def mouse_callback(self, event, x, y, flags, param):
          if event == cv2.EVENT_LBUTTONDOWN:
              self.start_pos = (x, y)
          elif event == cv2.EVENT_MOUSEMOVE and self.start_pos:
              self.current_pos = (x, y)
          elif event == cv2.EVENT_LBUTTONUP:
              self.regions.append((
                  min(self.start_pos[0], x),
                  min(self.start_pos[1], y),
                  abs(self.start_pos[0] - x),
                  abs(self.start_pos[1] - y)
              ))
              self.start_pos = None
  ```

- [ ] **Real-time parameter tuning**  
  Add sliders for real-time adjustment of detection parameters

## 2.4. Performance Optimization

### Efficient Resource Management

- [ ] **Smart capture rate adjustment**
  ```python
  def adjust_capture_rate(self, cpu_usage, current_fps):
      """Dynamically adjust capture rate based on system load"""
      target_fps = 30  # Default target
      
      if cpu_usage > 80:
          # Reduce by 25% if CPU is high
          target_fps = max(10, current_fps * 0.75)
      elif cpu_usage < 40 and current_fps < 30:
          # Increase if CPU has headroom
          target_fps = min(30, current_fps * 1.25)
          
      return target_fps
  ```

- [ ] **Resolution scaling**  
  Dynamically scale capture resolution based on CPU/GPU usage

### Multi-threading Improvements

- [ ] **Worker pool system**
  ```python
  class WorkerPool:
      """Pool of workers for parallel processing"""
      def __init__(self, max_workers=4):
          self.max_workers = max_workers
          self.tasks = queue.Queue()
          self.results = queue.Queue()
          self.workers = []
          
          for _ in range(max_workers):
              worker = threading.Thread(target=self._worker_loop)
              worker.daemon = True
              worker.start()
              self.workers.append(worker)
      
      def _worker_loop(self):
          """Process tasks from the queue"""
          while True:
              func, args, kwargs = self.tasks.get()
              try:
                  result = func(*args, **kwargs)
                  self.results.put((result, None))
              except Exception as e:
                  self.results.put((None, e))
              self.tasks.task_done()
      
      def submit(self, func, *args, **kwargs):
          """Submit task to worker pool"""
          self.tasks.put((func, args, kwargs))
  ```

- [ ] **Priority-based processing**  
  Implement task prioritization for critical vs. non-critical operations

## 2.5. Game Integration Features

### Game State Detection

- [ ] **Inventory monitoring**
  ```python
  def detect_inventory_state(self, frame):
      """Detect if inventory is open and how many items of each type"""
      inventory_roi = frame[self.inventory_region[1]:self.inventory_region[3], 
                           self.inventory_region[0]:self.inventory_region[2]]
      
      # Use template matching to detect item slots
      item_count = {}
      for item_name, template in self.item_templates.items():
          matches = self.detect_template(inventory_roi, template)
          item_count[item_name] = len(matches)
      
      return item_count
  ```

- [ ] **Game menu detection**  
  Recognize different game menus and adapt behavior accordingly

### Advanced Game Interaction

- [ ] **Auto-inventory management**
  ```python
  def manage_inventory(self):
      """Manage inventory when it gets full"""
      # Check if inventory is near full
      if self.is_inventory_nearly_full():
          # Open inventory
          self.press_key('i')
          time.sleep(1.0)
          
          # Get current screen
          frame = self.capture_screen()
          
          # Find and sell low-value items
          for item in self.detect_low_value_items(frame):
              self.click_at_position(item["position"])
              time.sleep(0.2)
              self.press_key('s')  # Sell key
              time.sleep(0.2)
          
          # Close inventory
          self.press_key('i')
  ```

- [ ] **Multi-game support**  
  Create profiles for different fishing games with game-specific behaviors

## 2.6. Analytics & Reporting

### Statistics System

- [ ] **Comprehensive fishing statistics**
  ```python
  class FishingStats:
      """Track and analyze fishing statistics"""
      def __init__(self):
          self.session_start = time.time()
          self.fish_caught = 0
          self.bites_missed = 0
          self.cast_count = 0
          self.fish_types = {}
          self.hourly_rates = []
          
      def log_catch(self, fish_type="unknown"):
          """Log a successful catch"""
          self.fish_caught += 1
          self.fish_types[fish_type] = self.fish_types.get(fish_type, 0) + 1
          
      def calculate_efficiency(self):
          """Calculate fishing efficiency"""
          if self.cast_count == 0:
              return 0
          return self.fish_caught / self.cast_count
          
      def update_hourly_rate(self):
          """Update hourly catch rate"""
          session_hours = (time.time() - self.session_start) / 3600
          if session_hours > 0:
              hourly = self.fish_caught / session_hours
              self.hourly_rates.append((time.time(), hourly))
  ```

- [ ] **Export options**  
  Add CSV/JSON export for detailed analysis in external tools

### Performance Analysis

- [ ] **Detection reliability metrics**
  ```python
  def analyze_detection_performance(self, session_data):
      """Analyze detection performance from session data"""
      total_detections = len(session_data["detections"])
      false_positives = sum(1 for d in session_data["detections"] if d["confirmed"] == False)
      missed_detections = session_data["missed_count"]
      
      precision = (total_detections - false_positives) / total_detections if total_detections > 0 else 0
      recall = (total_detections - false_positives) / (total_detections - false_positives + missed_detections) if (total_detections - false_positives + missed_detections) > 0 else 0
      
      return {
          "precision": precision,
          "recall": recall,
          "f1_score": 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
      }
  ```

- [ ] **Auto-optimization recommendations**  
  Analyze session data to suggest optimal settings

---

<a id="prototype-inspired-implementation"></a>
# 3. Prototype-Inspired Implementation

This section details a concrete implementation example that leverages the strengths of the prototype's direct approach while maintaining the modularity of the Qt version.

## 3.1. Hybrid Detection System

The following implementation combines the prototype's simple, efficient detection algorithm with the Qt version's more advanced features:

```python
import time
import numpy as np
import cv2
from mss import mss
import win32gui
import win32con
import win32api
import ctypes
import keyboard
from PyQt6.QtCore import QThread

class HybridDetector(QThread):
    """
    Hybrid fishing detector that combines the prototype's direct approach
    with the Qt version's structured design
    """
    
    def __init__(self, config=None):
        super().__init__()
        self.running = False
        self.paused = False
        self.config = config or self._default_config()
        
        # Window handling
        self.game_window_handle = None
        self.last_focus_attempt = 0
        self.focus_retry_interval = 1.0  # seconds
        
        # Detection state
        self.previous_frame = None
        self.detection_threshold = 0.05
        self.confidence = 0
        self.low_diff_streak = 0
        self.high_diff_streak = 0
        
        # Statistics
        self.frames_processed = 0
        self.detection_count = 0
        self.false_positives = 0
        self.session_start = time.time()

    def _default_config(self):
        """Default configuration values"""
        return {
            'detection_region': None,  # Will be set during setup
            'threshold': 0.05,
            'direct_mode': True,  # Use prototype-style direct implementation
            'confidence_required': 3,  # How many consecutive frames to confirm detection
            'fishing_key': 'f',
            'catch_key': 'f',
            'window_name': 'Play Together',
        }
    
    # Additional methods and implementation would go here
    # (Focus management, screen capture, detection algorithms, etc.)
```

## 3.2. Key Features of this Implementation

1. **Tiered Window Focus Strategy**: Uses the prototype's layered approach to first attempt a quick window focus, then fall back to more intensive methods only when needed.

2. **Multi-Method Input Mechanism**: Implements three redundant methods for key input (SendInput, PostMessage, keyboard library) with fallback capabilities.

3. **Fresh Screen Capture**: Creates a new MSS instance for each capture to prevent resource leaks in long sessions.

4. **Hybrid Detection Algorithm**: 
   - Combines prototype's immediate large-change detection for high responsiveness
   - Uses Qt version's confidence building for subtle changes to reduce false positives

5. **Direct Windows API Access**: Uses the prototype's direct API calls when appropriate while maintaining class structure.

6. **Simplified State Management**: Reduces state complexity with clear, direct flags.

7. **Self-Contained Implementation**: Maintains all critical functionality in one class while still fitting into Qt's QThread model.

## 3.3. Integration with Qt Application

This hybrid detector can be integrated into the existing Qt structure:

```python
# In main_window.py
from PyQt6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget
from PyQt6.QtCore import pyqtSlot

from hybrid_detector import HybridDetector

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AutoFisher - Hybrid Edition")
        
        # Create detector
        self.detector = HybridDetector()
        
        # Create UI
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        layout = QVBoxLayout(self.central_widget)
        
        self.start_button = QPushButton("Start Fishing")
        self.start_button.clicked.connect(self.toggle_fishing)
        layout.addWidget(self.start_button)
        
        # Additional UI elements would go here
        
        self.fishing_active = False
    
    @pyqtSlot()
    def toggle_fishing(self):
        if not self.fishing_active:
            self.start_button.setText("Stop Fishing")
            self.detector.start()
            self.fishing_active = True
        else:
            self.start_button.setText("Start Fishing")
            self.detector.stop()
            self.fishing_active = False
    
    def closeEvent(self, event):
        """Handle window close"""
        if self.fishing_active:
            self.detector.stop()
        event.accept()
```

## 3.4. Benefits of this Hybrid Approach

1. **Reliability**: Adopts the prototype's proven reliable approaches for critical operations
2. **Responsiveness**: Uses direct implementation for core functionality
3. **Maintainability**: Retains class structure and Qt integration
4. **Flexibility**: Allows both simple and advanced detection strategies
5. **Resource Efficiency**: Prevents resource leaks with proper cleanup

---

<a id="implementation-plan"></a>
# 4. Implementation Plan

## 4.1. Phased Roll-out

### Phase 1: Critical Reliability Improvements
1. Implement tiered window focus strategy
2. Add multi-method input redundancy
3. Optimize screen capture
4. Implement fast-path detection option

### Phase 2: Architecture Enhancements
1. Add direct mode option
2. Reduce abstraction layers
3. Simplify thread management

### Phase 3: User Experience Updates
1. Add prototype compatibility mode UI
2. Implement performance mode toggle
3. Add enhanced window detection

## 4.2. Feature Priority

1. **High Impact / Low Effort:**
   - Adaptive timing system
   - Live detection visualization
   - Smart capture rate adjustment

2. **Strategic Improvements:**
   - Multi-zone detection
   - Visual region selector
   - Comprehensive fishing statistics

3. **Advanced Features:**
   - Game state detection
   - Auto-inventory management
   - Custom action sequence recording

## 4.3. Testing Strategy

For each improvement, compare reliability metrics between:
1. Original Qt implementation
2. Prototype implementation
3. Improved Qt implementation

Focus testing on problematic scenarios identified during comparison:
- Unusual window management
- Games with subtle visual cues
- Lower-end systems
- Long-running sessions

---

<a id="completed-improvements"></a>
# 5. Completed Improvements

This section tracks improvements that have been successfully implemented in the AutoFisher Qt application.

## 5.1. User Interface Improvements

- [x] **Full Overlay Interface**  
  *Completed: Yes*  
  Implemented a full-featured overlay interface that stays on top of the game window, providing all functionality without needing to switch back to the main application.

- [x] **Overlay-Only Mode**  
  *Completed: Yes*  
  Created a streamlined version that launches directly into overlay mode without showing the main window, providing a more seamless experience.

- [x] **Advanced Visualization**  
  *Completed: Yes*  
  Added real-time visualization of detection activity in the overlay interface.

## 5.2. Detection System Enhancements

- [x] **Multi-Zone Detection**  
  *Completed: Yes*  
  Implemented support for multiple detection zones with individual configuration options.
  
- [x] **Zone-specific Sensitivities**  
  *Completed: Yes*  
  Added per-zone sensitivity controls with real-time adjustment capability.

## 5.3. Usability Improvements

- [x] **Draggable Interface**  
  *Completed: Yes*  
  Created a fully draggable overlay that can be positioned anywhere on screen.
  
- [x] **Collapsible Panels**  
  *Completed: Yes*  
  Added ability to collapse the overlay to minimize screen space usage when not actively configuring.

- [x] **Direct Exit Button**  
  *Completed: Yes*  
  Added safe application exit button to the overlay with confirmation dialog.
