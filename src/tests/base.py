"""Base class for functional tests."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum


class TestStatus(str, Enum):
    """Test execution status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """Result of a functional test."""
    name: str
    status: TestStatus
    duration_seconds: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class TestConfig:
    """Configuration for a functional test."""
    timeout_seconds: int = 300
    enabled: bool = True
    params: Dict[str, Any] = field(default_factory=dict)


class FunctionalTestBase(ABC):
    """Base class for functional hardware tests.

    Provides common functionality for:
    - Test lifecycle management
    - Metric collection
    - Result validation
    - Error handling
    """

    def __init__(self, config: Optional[TestConfig] = None):
        self.config = config or TestConfig()
        self._start_time: Optional[datetime] = None

    @property
    @abstractmethod
    def test_name(self) -> str:
        """Return the name of this test."""
        pass

    @abstractmethod
    def run(self) -> TestResult:
        """Execute the test.

        Returns:
            TestResult with status and metrics
        """
        pass

    def _start_timer(self) -> None:
        """Start test timer."""
        self._start_time = datetime.now()

    def _stop_timer(self) -> float:
        """Stop timer and return elapsed seconds."""
        if self._start_time is None:
            return 0.0
        elapsed = (datetime.now() - self._start_time).total_seconds()
        return elapsed

    def _create_result(
        self,
        status: TestStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, float]] = None
    ) -> TestResult:
        """Create a test result."""
        return TestResult(
            name=self.test_name,
            status=status,
            duration_seconds=self._stop_timer(),
            message=message,
            details=details or {},
            metrics=metrics or {}
        )

    def _validate_threshold(
        self,
        value: float,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ) -> tuple[bool, str]:
        """Validate a value against thresholds.

        Returns:
            (is_valid, message)
        """
        if min_value is not None and value < min_value:
            return False, f"Value {value} below minimum {min_value}"

        if max_value is not None and value > max_value:
            return False, f"Value {value} above maximum {max_value}"

        return True, ""
