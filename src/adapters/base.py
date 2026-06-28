"""Base adapter class for external system integration."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseAdapter(ABC):
    """Abstract base class for all adapters.

    Adapters are used to integrate with external systems such as
    Enterprise Management Systems (EMS), monitoring systems, or
    other data sinks/sources.
    """

    def __init__(self, name: str):
        """Initialize adapter.

        Args:
            name: Unique identifier for this adapter instance.
        """
        self.name = name
        self._is_running = False

    @abstractmethod
    def start(self) -> None:
        """Start the adapter.

        This method should initialize any connections,
        start servers, or prepare resources.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the adapter.

        This method should gracefully shutdown any
        connections or servers.
        """
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Check if adapter is currently running.

        Returns:
            True if adapter is active, False otherwise.
        """
        pass

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on adapter.

        Returns:
            Dictionary containing health status information.
        """
        return {
            "name": self.name,
            "running": self.is_running(),
            "healthy": self.is_running()
        }
