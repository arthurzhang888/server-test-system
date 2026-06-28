"""Adapters for external system integration."""

from src.adapters.base import BaseAdapter
from src.adapters.ems_dummy import DummyEMSAdapter
from src.adapters.ems_adapter import (
    EMSAdapter,
    HTTPBasedEMSAdapter,
    WebhookEMSAdapter,
    EMSAdapterFactory,
    EMSConfig,
    EMSAuthType
)

__all__ = [
    "BaseAdapter",
    "DummyEMSAdapter",
    "EMSAdapter",
    "HTTPBasedEMSAdapter",
    "WebhookEMSAdapter",
    "EMSAdapterFactory",
    "EMSConfig",
    "EMSAuthType"
]
