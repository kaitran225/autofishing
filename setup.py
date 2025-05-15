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
    name="autofisher",
    version="1.0.0",
    description="Automated fishing tool for PlayTogether game",
    author="AutoFisher Team",
    author_email="autofisher@example.com",
    packages=find_packages(),
    install_requires=install_requires,
    extras_require={
        "windows": ["pywin32"],
    },
    entry_points={
        "console_scripts": [
            "autofisher=autofisher.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Games/Entertainment",
    ],
    python_requires=">=3.6",
) 