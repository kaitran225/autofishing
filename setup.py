import subprocess
import sys
import pkg_resources

def check_python_version():
    """Check if Python version is compatible"""
    required_version = (3, 7)
    current_version = sys.version_info[:2]
    
    if current_version < required_version:
        print(f"Error: Python {required_version[0]}.{required_version[1]} or higher is required")
        print(f"Current version: {current_version[0]}.{current_version[1]}")
        return False
    return True

def install_requirements():
    """Install required packages"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error installing requirements: {e}")
        return False

def verify_imports():
    """Verify that all required packages can be imported"""
    required_packages = {
        'pyautogui': 'pyautogui',
        'cv2': 'opencv-python',
        'numpy': 'numpy',
        'PIL': 'Pillow',
        'tkinter': 'tk'
    }
    
    missing_packages = []
    
    for module, package in required_packages.items():
        try:
            __import__(module)
            print(f"✓ {package} is installed")
        except ImportError:
            missing_packages.append(package)
            print(f"✗ {package} is missing")
    
    return len(missing_packages) == 0

def main():
    print("Checking Python version...")
    if not check_python_version():
        return
    
    print("\nInstalling requirements...")
    if not install_requirements():
        return
    
    print("\nVerifying imports...")
    if not verify_imports():
        print("\nSome packages are missing. Please try running:")
        print("pip install -r requirements.txt")
        return
    
    print("\nAll dependencies are installed and verified!")
    print("You can now run the application with:")
    print("python game_automation.py")

if __name__ == "__main__":
    main() 