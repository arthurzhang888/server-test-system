"""Adapters for external system integration."""

from src.adapters.base import BaseAdapter
from src.adapters.ems_dummy import DummyEMSAdapter

__all__ = ["BaseAdapter", "DummyEMSAdapter"]
