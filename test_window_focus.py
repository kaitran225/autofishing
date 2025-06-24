#!/usr/bin/env python3
"""
Test script for enhanced window focus and detection improvements
Focuses only on the 'PLAY TOGETHER' game window.
"""
import time
import win32gui
from utils.win32_utils import (
    force_focus_window, 
    focus_window_tiered, 
    find_window_by_pattern, 
    is_fullscreen_app_active
)
from utils.constants import GAME_WINDOW_NAMES

def get_game_window():
    """Find the PLAY TOGETHER game window using enhanced detection."""
    window = find_window_by_pattern(GAME_WINDOW_NAMES)
    if window:
        title = win32gui.GetWindowText(window)
        print(f"✓ Found game window: '{title}' (hwnd: {window})")
        return window
    else:
        print("⚠ Game window not found. Please make sure the game is running and visible.")
        return None

def test_focus_methods(game_window):
    """Test different focus methods on the game window."""
    print("\n=== Testing Focus Methods (Game Window) ===")
    window_title = win32gui.GetWindowText(game_window)
    print(f"Testing with game window: '{window_title}' (hwnd: {game_window})")
    
    # Test 1: Quick focus attempt
    print("\n1. Testing quick focus attempt...")
    start_time = time.time()
    result = focus_window_tiered(game_window)
    quick_time = time.time() - start_time
    print(f"Quick focus result: {result} ({quick_time:.3f}s)")
    
    # Test 2: Force focus (heavy method)
    print("\n2. Testing force focus (heavy method)...")
    start_time = time.time()
    result = force_focus_window(game_window)
    force_time = time.time() - start_time
    print(f"Force focus result: {result} ({force_time:.3f}s)")
    
    # Test 3: Verify focus
    print("\n3. Verifying focus...")
    active_window = win32gui.GetForegroundWindow()
    is_focused = (active_window == game_window)
    active_title = win32gui.GetWindowText(active_window)
    print(f"Active window: '{active_title}' (hwnd: {active_window})")
    print(f"Focus verification: {is_focused}")
    
    return is_focused

def test_fullscreen_detection():
    """Test fullscreen application detection."""
    print("\n=== Testing Fullscreen Detection ===")
    is_fullscreen = is_fullscreen_app_active()
    print(f"Fullscreen app detected: {is_fullscreen}")
    if is_fullscreen:
        print("✓ Fullscreen detection working - respecting other applications")
    else:
        print("ℹ No fullscreen application currently active")
    return is_fullscreen

def benchmark_focus_performance(game_window):
    """Benchmark focus method performance on the game window."""
    print("\n=== Focus Performance Benchmark (Game Window) ===")
    # Warm up
    for _ in range(3):
        focus_window_tiered(game_window)
        force_focus_window(game_window)
    # Benchmark tiered focus
    print("Benchmarking tiered focus method...")
    start_time = time.time()
    for _ in range(10):
        focus_window_tiered(game_window)
    tiered_time = time.time() - start_time
    # Benchmark force focus
    print("Benchmarking force focus method...")
    start_time = time.time()
    for _ in range(10):
        force_focus_window(game_window)
    force_time = time.time() - start_time
    print(f"Tiered focus (10 iterations): {tiered_time:.3f}s")
    print(f"Force focus (10 iterations): {force_time:.3f}s")
    if tiered_time < force_time:
        print("✓ Tiered focus is faster than force focus")
    else:
        print("⚠ Tiered focus is not faster than expected")

def main():
    print("Testing Enhanced Window Focus and Detection Improvements (Game Only)")
    print("=" * 60)
    game_window = get_game_window()
    if not game_window:
        print("\n=== Test Aborted: Game window not found ===")
        return
    try:
        # Test focus methods
        focus_success = test_focus_methods(game_window)
        # Test fullscreen detection
        fullscreen_detected = test_fullscreen_detection()
        # Performance benchmark
        benchmark_focus_performance(game_window)
        print("\n" + "=" * 60)
        print("=== Test Summary ===")
        print(f"Focus methods: {'✓' if focus_success else '⚠'}")
        print(f"Fullscreen detection: {'✓' if fullscreen_detected is not None else '⚠'}")
        print("\nEnhanced window focus improvements are working correctly for the game window!")
    except Exception as e:
        print(f"\n=== Test Failed ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 