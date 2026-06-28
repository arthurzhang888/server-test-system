from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from datetime import datetime
import time
import threading


class MetricStatus(str, Enum):
    """Status of a metric reading."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class ThresholdConfig:
    """Configuration for metric thresholds.

    Attributes:
        min_value: Minimum acceptable value (None = no lower bound)
        max_value: Maximum acceptable value (None = no upper bound)
        warning_pct: Percentage of range to trigger warning (default 80%)
        critical_pct: Percentage of range to trigger critical (default 95%)
    """
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    warning_pct: float = 0.8
    critical_pct: float = 0.95

    def check_value(self, value: float) -> MetricStatus:
        """Check if value is within thresholds."""
        if self.min_value is not None and value < self.min_value:
            return MetricStatus.CRITICAL
        if self.max_value is not None and value > self.max_value:
            return MetricStatus.CRITICAL

        # Calculate percentage of range
        if self.min_value is not None and self.max_value is not None:
            range_size = self.max_value - self.min_value
            if range_size > 0:
                pct = (value - self.min_value) / range_size
                if pct >= self.critical_pct:
                    return MetricStatus.CRITICAL
                if pct >= self.warning_pct:
                    return MetricStatus.WARNING

        return MetricStatus.NORMAL


@dataclass
class MetricResult:
    """Result of a single metric reading."""
    name: str
    value: float
    unit: str
    status: MetricStatus
    timestamp: datetime = field(default_factory=datetime.now)
    message: str = ""


@dataclass
class StressTestResult:
    """Complete result of a stress test."""
    test_name: str
    duration_seconds: float
    status: str  # passed, failed, error
    metrics: List[MetricResult] = field(default_factory=list)
    samples: List[Dict[str, Any]] = field(default_factory=list)
    error_message: str = ""

    @property
    def has_violations(self) -> bool:
        """Check if any metric exceeded thresholds."""
        return any(
            m.status == MetricStatus.CRITICAL for m in self.metrics
        )


class StressTestBase(ABC):
    """Base class for stress tests.

    Supports:
    - Configurable duration and intensity
    - Metric thresholds with min/max bounds
    - Periodic sampling during test
    - Real-time progress callbacks
    """

    def __init__(
        self,
        duration_seconds: int = 300,
        sample_interval_seconds: int = 5,
        thresholds: Optional[Dict[str, ThresholdConfig]] = None
    ):
        self.duration_seconds = duration_seconds
        self.sample_interval_seconds = sample_interval_seconds
        self.thresholds = thresholds or {}
        self._stop_event = threading.Event()
        self._progress_callback: Optional[Callable[[float, Dict[str, Any]], None]] = None

    @property
    @abstractmethod
    def test_name(self) -> str:
        """Return the name of this stress test."""
        pass

    @abstractmethod
    def start_stress(self) -> bool:
        """Start the stress workload.

        Returns:
            True if stress started successfully, False otherwise.
        """
        pass

    @abstractmethod
    def stop_stress(self) -> None:
        """Stop the stress workload."""
        pass

    @abstractmethod
    def collect_metrics(self) -> Dict[str, float]:
        """Collect current metrics during stress test.

        Returns:
            Dictionary of metric name -> value.
        """
        pass

    def set_progress_callback(self, callback: Callable[[float, Dict[str, Any]], None]) -> None:
        """Set callback for progress updates.

        Args:
            callback: Function receiving (percentage_complete, current_metrics)
        """
        self._progress_callback = callback

    def run(self) -> StressTestResult:
        """Run the complete stress test.

        Returns:
            StressTestResult with all metrics and status.
        """
        start_time = time.time()
        samples = []
        self._stop_event.clear()

        # Start stress workload
        if not self.start_stress():
            return StressTestResult(
                test_name=self.test_name,
                duration_seconds=0,
                status="error",
                error_message="Failed to start stress workload"
            )

        try:
            # Collect samples during stress
            elapsed = 0
            while elapsed < self.duration_seconds and not self._stop_event.is_set():
                time.sleep(self.sample_interval_seconds)
                elapsed = time.time() - start_time

                metrics = self.collect_metrics()
                sample = {
                    "timestamp": datetime.now().isoformat(),
                    "elapsed_seconds": elapsed,
                    "metrics": metrics
                }
                samples.append(sample)

                # Report progress
                if self._progress_callback:
                    pct = min(100.0, (elapsed / self.duration_seconds) * 100)
                    self._progress_callback(pct, metrics)

        finally:
            self.stop_stress()

        # Analyze results
        actual_duration = time.time() - start_time
        metric_results = self._analyze_samples(samples)

        # Determine status
        status = "passed"
        if any(m.status == MetricStatus.CRITICAL for m in metric_results):
            status = "failed"

        return StressTestResult(
            test_name=self.test_name,
            duration_seconds=actual_duration,
            status=status,
            metrics=metric_results,
            samples=samples
        )

    def stop(self) -> None:
        """Signal the stress test to stop early."""
        self._stop_event.set()

    def _analyze_samples(self, samples: List[Dict[str, Any]]) -> List[MetricResult]:
        """Analyze collected samples against thresholds."""
        results = []

        if not samples:
            return results

        # Calculate statistics for each metric
        metric_names = set()
        for sample in samples:
            metric_names.update(sample["metrics"].keys())

        for metric_name in metric_names:
            values = [
                s["metrics"][metric_name]
                for s in samples
                if metric_name in s["metrics"]
            ]

            if not values:
                continue

            avg_value = sum(values) / len(values)
            max_value = max(values)

            # Check against thresholds
            threshold = self.thresholds.get(metric_name)
            if threshold:
                status = threshold.check_value(max_value)
                unit = self._get_metric_unit(metric_name)

                message = ""
                if status == MetricStatus.CRITICAL:
                    message = f"Exceeded threshold: {max_value:.2f}"
                elif status == MetricStatus.WARNING:
                    message = f"Near threshold: {max_value:.2f}"

                results.append(MetricResult(
                    name=metric_name,
                    value=max_value,
                    unit=unit,
                    status=status,
                    message=message
                ))
            else:
                # No threshold configured, just record the value
                results.append(MetricResult(
                    name=metric_name,
                    value=max_value,
                    unit=self._get_metric_unit(metric_name),
                    status=MetricStatus.NORMAL
                ))

        return results

    def _get_metric_unit(self, metric_name: str) -> str:
        """Get unit for a metric (can be overridden)."""
        unit_map = {
            "temperature": "°C",
            "temp": "°C",
            "power": "W",
            "watts": "W",
            "utilization": "%",
            "usage": "%",
            "memory": "MB",
            "bandwidth": "MB/s",
            "iops": "IOPS",
            "latency": "ms",
        }

        for key, unit in unit_map.items():
            if key in metric_name.lower():
                return unit

        return ""
