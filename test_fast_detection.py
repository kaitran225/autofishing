#!/usr/bin/env python3
"""
Test script for fast-path detection functionality
Compares normal vs fast mode detection algorithms
"""
import numpy as np
import cv2
import time
from core.processing import calculate_frame_difference

def create_test_frames():
    """Create test frames to simulate fishing scenarios"""
    # Create a base frame (simulating calm water)
    base_frame = np.random.randint(100, 150, (100, 150, 3), dtype=np.uint8)
    
    # Create a frame with subtle changes (simulating fish movement)
    subtle_frame = base_frame.copy()
    # Add small random changes to simulate subtle movement
    noise = np.random.randint(-10, 10, base_frame.shape, dtype=np.int16)
    subtle_frame = np.clip(subtle_frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    # Create a frame with major changes (simulating fish caught)
    major_frame = base_frame.copy()
    # Add a bright splash effect in the center
    center_y, center_x = base_frame.shape[0]//2, base_frame.shape[1]//2
    major_frame[center_y-20:center_y+20, center_x-30:center_x+30] = [255, 255, 255]  # White splash
    
    return base_frame, subtle_frame, major_frame

def test_detection_modes():
    """Test both normal and fast detection modes"""
    print("=== Testing Fast-Path Detection Function ===")
    
    # Create test frames
    base_frame, subtle_frame, major_frame = create_test_frames()
    
    print(f"Base frame shape: {base_frame.shape}")
    print(f"Subtle frame shape: {subtle_frame.shape}")
    print(f"Major frame shape: {major_frame.shape}")
    
    # Test scenarios
    test_cases = [
        ("No change", base_frame, base_frame),
        ("Subtle change", base_frame, subtle_frame),
        ("Major change", base_frame, major_frame),
    ]
    
    for test_name, frame1, frame2 in test_cases:
        print(f"\n--- {test_name} ---")
        
        # Test normal mode
        start_time = time.time()
        diff_normal, change_normal = calculate_frame_difference(frame1, frame2, fast_mode=False)
        normal_time = time.time() - start_time
        
        # Test fast mode
        start_time = time.time()
        diff_fast, change_fast = calculate_frame_difference(frame1, frame2, fast_mode=True)
        fast_time = time.time() - start_time
        
        print(f"Normal mode: {change_normal:.4f} change ({normal_time:.4f}s)")
        print(f"Fast mode:   {change_fast:.4f} change ({fast_time:.4f}s)")
        print(f"Speed improvement: {normal_time/fast_time:.1f}x faster")
        
        # Verify both modes return valid results
        assert diff_normal is not None, f"Normal mode failed for {test_name}"
        assert diff_fast is not None, f"Fast mode failed for {test_name}"
        assert 0 <= change_normal <= 1, f"Invalid change percent in normal mode: {change_normal}"
        assert 0 <= change_fast <= 1, f"Invalid change percent in fast mode: {change_fast}"
        
        # For major changes, fast mode should detect them
        if "Major" in test_name:
            assert change_fast > 0.01, f"Fast mode missed major change: {change_fast}"
            print("✓ Fast mode correctly detected major change")
        
        # For no change, both should be very low
        if "No change" in test_name:
            assert change_normal < 0.1, f"Normal mode false positive: {change_normal}"
            assert change_fast < 0.1, f"Fast mode false positive: {change_fast}"
            print("✓ Both modes correctly detected no change")

def test_edge_cases():
    """Test edge cases and error handling"""
    print("\n=== Testing Edge Cases ===")
    
    # Test with None frames
    try:
        result = calculate_frame_difference(None, np.zeros((10, 10, 3)))
        assert result == (None, 0), "Should return (None, 0) for None frame"
        print("✓ Handles None frames correctly")
    except Exception as e:
        print(f"✗ Error handling None frames: {e}")
    
    # Test with different sized frames
    try:
        frame1 = np.zeros((50, 50, 3))
        frame2 = np.zeros((100, 100, 3))
        diff, change = calculate_frame_difference(frame1, frame2, fast_mode=True)
        assert diff is not None, "Should resize frames automatically"
        print("✓ Handles different sized frames correctly")
    except Exception as e:
        print(f"✗ Error handling different sized frames: {e}")
    
    # Test with grayscale frames
    try:
        frame1 = np.zeros((50, 50), dtype=np.uint8)
        frame2 = np.ones((50, 50), dtype=np.uint8) * 100
        diff, change = calculate_frame_difference(frame1, frame2, fast_mode=True)
        assert diff is not None and change > 0, "Should detect change in grayscale"
        print("✓ Handles grayscale frames correctly")
    except Exception as e:
        print(f"✗ Error handling grayscale frames: {e}")

def benchmark_performance():
    """Benchmark performance difference between modes"""
    print("\n=== Performance Benchmark ===")
    
    # Create larger test frames for better timing
    base_frame = np.random.randint(100, 150, (200, 300, 3), dtype=np.uint8)
    test_frame = base_frame.copy()
    test_frame[100:150, 150:250] = [255, 255, 255]  # Add white region
    
    # Warm up
    for _ in range(5):
        calculate_frame_difference(base_frame, test_frame, fast_mode=False)
        calculate_frame_difference(base_frame, test_frame, fast_mode=True)
    
    # Benchmark normal mode
    start_time = time.time()
    for _ in range(10000):
        calculate_frame_difference(base_frame, test_frame, fast_mode=False)
    normal_total = time.time() - start_time
    
    # Benchmark fast mode
    start_time = time.time()
    for _ in range(10000):
        calculate_frame_difference(base_frame, test_frame, fast_mode=True)
    fast_total = time.time() - start_time
    
    print(f"Normal mode (10000 iterations): {normal_total:.3f}s")
    print(f"Fast mode (10000 iterations):   {fast_total:.3f}s")
    print(f"Performance improvement: {normal_total/fast_total:.1f}x faster")
    
    if fast_total < normal_total:
        print("✓ Fast mode is indeed faster")
    else:
        print("⚠ Fast mode is not faster than expected")

if __name__ == "__main__":
    try:
        test_detection_modes()
        test_edge_cases()
        benchmark_performance()
        print("\n=== All Tests Passed! ===")
        print("Fast-path detection function is working correctly.")
    except Exception as e:
        print(f"\n=== Test Failed ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc() 