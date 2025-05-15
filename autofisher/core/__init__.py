"""
Core functionality for the AutoFisher tool.
Contains detection algorithms and fishing logic.
"""

from autofisher.core.detector import PixelChangeDetector
from autofisher.core.fisher import Fisher
from autofisher.core.fishing_sequence import FishingSequenceManager

__all__ = ['PixelChangeDetector', 'Fisher', 'FishingSequenceManager'] 