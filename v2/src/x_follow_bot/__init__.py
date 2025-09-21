"""
X Follow Bot v2.0

A modern Python bot for X (Twitter) automation with API v2 support.
"""

__version__ = "2.0.0"
__author__ = "Kyros"
__email__ = "kyros@example.com"

from .core.client import XClient
from .core.auth import XAuth
from .models.user import User
from .models.tweet import Tweet

__all__ = [
    "XClient",
    "XAuth", 
    "User",
    "Tweet",
]