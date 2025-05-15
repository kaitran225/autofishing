#!/usr/bin/env python3

from setuptools import setup, find_packages
import platform

# Platform-specific dependencies
platform_specific = {
    'darwin': [
        'pyobjc>=7.0',
    ],
    'win32': [
        'pywin32>=300',
    ]
}

# Get the current platform
current_platform = platform.system().lower()
if current_platform == 'windows':
    current_platform = 'win32'

# Core dependencies
install_requires = [
    'numpy>=1.20.0',
    'opencv-python>=4.5.0',
    'Pillow>=8.0.0',
    'pynput>=1.7.0',
    'pyautogui>=0.9.50',
    'mss>=6.1.0',
    'PyQt5>=5.15.0',
]

# Add platform-specific dependencies
if current_platform in platform_specific:
    install_requires.extend(platform_specific[current_platform])

setup(
    name="autofishing",
    version="0.1.0",
    packages=find_packages(),
    
    # Dependencies
    install_requires=install_requires,
    python_requires='>=3.8',
    
    # Metadata
    author="Your Name",
    author_email="your.email@example.com",
    description="A cross-platform automation tool for fishing in games",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    keywords="gaming, automation, fishing, pixel-detection",
    url="https://github.com/yourusername/autofishing",
    
    # Classifiers
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Gamers",
        "Topic :: Gaming :: Automation",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    
    # Entry points
    entry_points={
        'console_scripts': [
            'autofishing=autofishing:main',
        ],
    },
    
    # Include data files
    package_data={
        'autofisher': ['ui/resources/*'],
    },
) 