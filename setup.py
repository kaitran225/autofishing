from setuptools import setup, find_packages

setup(
    name="autofishing",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "PyQt6",
        "numpy",
        "mss",
        "opencv-python",
        "matplotlib",
    ],
    entry_points={
        "console_scripts": [
            "autofishing=src.main:main",
        ],
    },
) 