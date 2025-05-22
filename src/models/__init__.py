"""
Models package for pixel change detection
"""
import os

def get_detector_path():
    """Get the path to the detector module directory"""
    return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(filename):
    """Get the path to a resource file"""
    resource_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "resoure")
    return os.path.join(resource_dir, filename) 