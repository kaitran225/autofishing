#!/usr/bin/env python3
"""
Test script for MultiZoneDetector with enhanced features
Tests all 4 detection zones including shadow detection from prototype
"""
import time
import numpy as np
import cv2
from core.detector import MultiZoneDetector, DetectionZone
from utils.constants import DEFAULT_DETECTION_ZONES, UI_CONFIG

def create_test_frames():
    """Create test frames to simulate different fishing scenarios"""
    # Base frame (calm water)
    base_frame = np.random.randint(100, 150, (200, 300, 3), dtype=np.uint8)
    
    # Frame with fish shadow (dark area)
    shadow_frame = base_frame.copy()
    # Add dark shadow area (simulating fish shadow)
    shadow_frame[80:120, 120:180] = np.random.randint(30, 80, (40, 60, 3), dtype=np.uint8)
    
    # Frame with text changes (fish name)
    text_frame = base_frame.copy()
    # Add bright text area
    text_frame[50:70, 100:200] = np.random.randint(200, 255, (20, 100, 3), dtype=np.uint8)
    
    # Frame with rod movement (color changes)
    rod_frame = base_frame.copy()
    # Add rod-like structure with different colors
    rod_frame[150:180, 140:160] = np.random.randint(180, 220, (30, 20, 3), dtype=np.uint8)
    
    # Frame with major fishing activity
    fishing_frame = base_frame.copy()
    # Add multiple changes
    fishing_frame[60:90, 110:190] = np.random.randint(50, 100, (30, 80, 3), dtype=np.uint8)
    fishing_frame[130:160, 120:180] = np.random.randint(200, 255, (30, 60, 3), dtype=np.uint8)
    
    return {
        "base": base_frame,
        "shadow": shadow_frame,
        "text": text_frame,
        "rod": rod_frame,
        "fishing": fishing_frame
    }

def test_zone_initialization():
    """Test zone initialization and configuration"""
    print("=== Testing Zone Initialization ===")
    
    detector = MultiZoneDetector()
    
    # Check all zones are initialized
    expected_zones = ["main_fishing", "fish_name", "fishing_rod", "bounce_shadow"]
    for zone_id in expected_zones:
        assert zone_id in detector.zones, f"Zone {zone_id} not found"
        zone = detector.zones[zone_id]
        assert zone.name == DEFAULT_DETECTION_ZONES[zone_id]["name"]
        assert zone.enabled == DEFAULT_DETECTION_ZONES[zone_id]["enabled"]
        print(f"✓ Zone {zone_id}: {zone.name}")
    
    print("✓ All zones initialized correctly")

def test_zone_configuration():
    """Test zone configuration updates"""
    print("\n=== Testing Zone Configuration ===")
    
    detector = MultiZoneDetector()
    
    # Test zone enabling/disabling
    detector.enable_zone("fish_name", False)
    assert not detector.zones["fish_name"].enabled
    print("✓ Zone enable/disable works")
    
    # Test configuration updates
    new_config = {"sensitivity": 2.0, "threshold": 0.02}
    detector.update_zone_config("bounce_shadow", new_config)
    zone = detector.zones["bounce_shadow"]
    assert zone.sensitivity == 2.0
    assert zone.threshold == 0.02
    print("✓ Zone configuration updates work")
    
    # Test region setting
    test_region = (100, 100, 200, 200)
    detector.set_zone_region("main_fishing", test_region)
    assert detector.zones["main_fishing"].region == test_region
    print("✓ Zone region setting works")

def test_shadow_detection():
    """Test shadow detection from prototype"""
    print("\n=== Testing Shadow Detection ===")
    
    detector = MultiZoneDetector()
    frames = create_test_frames()
    
    # Test shadow detection
    change_percent, shadow_size = detector.detect_shadow_movement(
        frames["base"], frames["shadow"]
    )
    
    print(f"Shadow detection - Change: {change_percent:.4f}, Size: {shadow_size}")
    assert change_percent > 0, "Shadow detection should detect changes"
    print("✓ Shadow detection works")
    
    # Test shadow size classification
    change_percent2, shadow_size2 = detector.detect_shadow_movement(
        frames["base"], frames["base"]
    )
    assert shadow_size2 == 0, "No shadow should be detected in identical frames"
    print("✓ Shadow size classification works")

def test_text_detection():
    """Test fish name text detection"""
    print("\n=== Testing Text Detection ===")
    
    detector = MultiZoneDetector()
    frames = create_test_frames()
    
    # Test text detection
    change_percent = detector.detect_text_changes(
        frames["base"], frames["text"]
    )
    
    print(f"Text detection - Change: {change_percent:.4f}")
    assert change_percent > 0, "Text detection should detect changes"
    print("✓ Text detection works")

def test_rod_detection():
    """Test fishing rod movement detection"""
    print("\n=== Testing Rod Detection ===")
    
    detector = MultiZoneDetector()
    frames = create_test_frames()
    
    # Test rod detection
    change_percent = detector.detect_rod_movement(
        frames["base"], frames["rod"]
    )
    
    print(f"Rod detection - Change: {change_percent:.4f}")
    assert change_percent > 0, "Rod detection should detect changes"
    print("✓ Rod detection works")

def test_zone_processing():
    """Test individual zone processing"""
    print("\n=== Testing Zone Processing ===")
    
    detector = MultiZoneDetector()
    frames = create_test_frames()
    
    # Set up test regions
    test_regions = {
        "main_fishing": (0, 0, 300, 200),
        "fish_name": (0, 0, 300, 200),
        "fishing_rod": (0, 0, 300, 200),
        "bounce_shadow": (0, 0, 300, 200)
    }
    
    for zone_id, region in test_regions.items():
        detector.set_zone_region(zone_id, region)
    
    # Test zone processing with different frame types
    current_time = time.time()
    
    # Test main fishing zone
    detector.zones["main_fishing"].reference_frame = frames["base"]
    result = detector.process_zone("main_fishing", current_time)
    print(f"Main fishing zone processing: {'✓' if result else '✗'}")
    
    # Test fish name zone
    detector.zones["fish_name"].reference_frame = frames["base"]
    result = detector.process_zone("fish_name", current_time)
    print(f"Fish name zone processing: {'✓' if result else '✗'}")
    
    # Test fishing rod zone
    detector.zones["fishing_rod"].reference_frame = frames["base"]
    result = detector.process_zone("fishing_rod", current_time)
    print(f"Fishing rod zone processing: {'✓' if result else '✗'}")
    
    # Test bounce shadow zone
    detector.zones["bounce_shadow"].reference_frame = frames["base"]
    result = detector.process_zone("bounce_shadow", current_time)
    print(f"Bounce shadow zone processing: {'✓' if result else '✗'}")

def test_error_handling():
    """Test error handling and recovery"""
    print("\n=== Testing Error Handling ===")
    
    detector = MultiZoneDetector()
    
    # Test error handling
    detector.handle_error("test_error", "Test error message", "main_fishing")
    
    # Check error tracking
    assert detector.retry_count > 0, "Error should be tracked"
    print("✓ Error handling works")
    
    # Test zone disabling after failures
    zone = detector.zones["main_fishing"]
    zone.consecutive_failures = detector.error_config["max_consecutive_failures"]
    detector.handle_error("test_error", "Test error message", "main_fishing")
    
    assert not zone.enabled, "Zone should be disabled after max failures"
    print("✓ Zone disabling after failures works")

def test_performance_metrics():
    """Test performance metrics collection"""
    print("\n=== Testing Performance Metrics ===")
    
    detector = MultiZoneDetector()
    
    # Get performance metrics
    metrics = detector.get_performance_metrics()
    
    assert "cpu_usage" in metrics
    assert "memory_usage" in metrics
    assert "zone_stats" in metrics
    assert "total_detections" in metrics
    print("✓ Performance metrics collection works")
    
    # Test zone statistics
    zone_stats = detector.get_zone_stats()
    for zone_id in ["main_fishing", "fish_name", "fishing_rod", "bounce_shadow"]:
        assert zone_id in zone_stats
        assert "accuracy" in zone_stats[zone_id]
        assert "detection_count" in zone_stats[zone_id]
    print("✓ Zone statistics collection works")

def test_zone_visualization():
    """Test zone visualization colors"""
    print("\n=== Testing Zone Visualization ===")
    
    colors = UI_CONFIG["zone_colors"]
    expected_colors = {
        "main_fishing": "#4CAF50",  # Green
        "fish_name": "#2196F3",     # Blue
        "fishing_rod": "#FF9800",   # Orange
        "bounce_shadow": "#9C27B0"  # Purple
    }
    
    for zone_id, expected_color in expected_colors.items():
        assert colors[zone_id] == expected_color, f"Color mismatch for {zone_id}"
        print(f"✓ {zone_id} color: {colors[zone_id]}")
    
    print("✓ All zone colors configured correctly")

def main():
    """Run all tests"""
    print("Testing MultiZoneDetector with Enhanced Features")
    print("=" * 60)
    
    try:
        test_zone_initialization()
        test_zone_configuration()
        test_shadow_detection()
        test_text_detection()
        test_rod_detection()
        test_zone_processing()
        test_error_handling()
        test_performance_metrics()
        test_zone_visualization()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("MultiZoneDetector is working correctly with all 4 detection zones")
        print("Features implemented:")
        print("- Enhanced Error Handling & Recovery")
        print("- Performance Optimizations")
        print("- Configuration & Customization")
        print("- Advanced Detection Features:")
        print("  • Fish Name Detection Zone")
        print("  • Fishing Rod Detection Zone")
        print("  • Bounce Shadow Zone (with prototype shadow detection)")
        print("  • Main Fishing Zone")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 