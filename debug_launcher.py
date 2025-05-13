import os
import sys
import traceback
import datetime

# Setup error logging
error_log_path = os.path.expanduser("~/Desktop/autofishing_error.log")

def log_error(error_msg):
    """Log an error message to the desktop and console"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {error_msg}\n"
    
    print(full_msg)  # Print to console
    
    try:
        with open(error_log_path, "a") as f:
            f.write(full_msg)
    except:
        pass  # If we can't write to the log file, continue anyway

try:
    # Log startup
    log_error("Starting AutoFishing debug launcher...")
    
    # Log Python version and path
    log_error(f"Python version: {sys.version}")
    log_error(f"Python executable: {sys.executable}")
    log_error(f"Current directory: {os.getcwd()}")
    
    # Try importing key modules to see which one might be failing
    modules_to_check = [
        "PyQt6", "numpy", "cv2", "PIL", "matplotlib", "mss", 
        "time", "datetime", "threading", "queue", "subprocess"
    ]
    
    for module_name in modules_to_check:
        try:
            __import__(module_name)
            log_error(f"Successfully imported {module_name}")
        except ImportError as e:
            log_error(f"ERROR importing {module_name}: {str(e)}")
    
    # Now try to import and run the main application
    log_error("Attempting to import main application...")
    
    try:
        # Try to import and run the main application
        import mac_pixel_detector_simple
        log_error("Successfully imported main module. Starting application...")
        
        if hasattr(mac_pixel_detector_simple, 'main'):
            mac_pixel_detector_simple.main()
        else:
            log_error("ERROR: main() function not found in mac_pixel_detector_simple.py")
            
    except Exception as e:
        log_error(f"ERROR in main application: {str(e)}")
        log_error(traceback.format_exc())
        
except Exception as e:
    # Last resort error handling
    try:
        error_msg = f"CRITICAL ERROR: {str(e)}\n{traceback.format_exc()}"
        log_error(error_msg)
    except:
        pass  # If even our error logging fails
    
    # Create a simple file on desktop as a last resort
    try:
        with open(os.path.expanduser("~/Desktop/autofishing_crash.txt"), "w") as f:
            f.write(f"AutoFishing crashed: {str(e)}\n")
            f.write(traceback.format_exc())
    except:
        pass  # Nothing more we can do
        
    # Reraise to show the error to the user
    raise 