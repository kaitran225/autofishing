#!/usr/bin/env python3
"""
Simple launcher script for the autofishing application.
This script adds the project root to Python path so modules can be imported correctly.
"""
import os
import sys

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import and run the main function
from src.main import main

if __name__ == "__main__":
    main() 