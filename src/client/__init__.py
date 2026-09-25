"""Sakai API client package."""

try:
    from src.client.sakai_client import SakaiClient

    __all__ = ["SakaiClient"]
except ImportError:
    __all__ = []
