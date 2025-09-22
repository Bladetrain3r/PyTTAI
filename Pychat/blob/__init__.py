# lmchat/__init__.py
"""Pyttai - AI Shell Client"""
__version__ = "0.1.0"
__author__ = "Zerofuchs Software"
__license__ = "MIT"

# Import key classes for convenience
from .core import ChatController, ProviderManager
from .core.providers import LMStudioProvider, ClaudeProvider

__all__ = [
    "core",
    "features",
    "main",
    "ChatController",
    "ProviderManager",
    "LMStudioProvider",
    "ClaudeProvider"
]
