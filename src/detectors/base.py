from abc import ABC, abstractmethod
from enum import Enum


class DetectorMode(str, Enum):
    """Mode for hardware detection - mock for testing, real for production."""
    MOCK = "mock"
    REAL = "real"


class BaseDetector(ABC):
    """Abstract base class for all hardware detectors.

    Supports both mock (simulated) and real hardware detection modes.
    The mode is controlled via configuration and allows testing without
    actual hardware present.
    """

    def __init__(self, mode: DetectorMode = DetectorMode.REAL):
        self.mode = mode

    @abstractmethod
    def detect_real(self) -> dict:
        """Perform actual hardware detection.

        This method should contain the real hardware detection logic
        using system calls, libraries, or hardware interfaces.

        Returns:
            Dictionary containing detected hardware information.
        """
        pass

    @abstractmethod
    def detect_mock(self) -> dict:
        """Return simulated hardware data.

        This method returns realistic mock data for testing purposes
        when actual hardware is not available.

        Returns:
            Dictionary containing simulated hardware information.
        """
        pass

    def detect(self) -> dict:
        """Unified detection entry point.

        Routes to either detect_real() or detect_mock() based on mode.

        Returns:
            Dictionary containing hardware information (real or mock).
        """
        if self.mode == DetectorMode.MOCK:
            return self.detect_mock()
        return self.detect_real()

    @property
    def name(self) -> str:
        """Return detector name (class name without 'Detector' suffix)."""
        class_name = self.__class__.__name__
        return class_name.replace("Detector", "").lower()
