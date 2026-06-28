"""Stress test engine for running hardware stress tests with threshold monitoring."""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime

from src.stress_tests.base import StressTestBase, StressTestResult
from src.stress_tests.cpu_stress import CPUStressTest, CPUThresholds
from src.stress_tests.gpu_stress import GPUStressTest, GPUThresholds
from src.stress_tests.nvme_stress import NVMeStressTest, NVMeThresholds
from src.core.state import TestResult, TestStatus
from src.core.events import EventSystem, EventType, Event


@dataclass
class StressEngineConfig:
    """Configuration for stress test engine."""
    # Which stress tests to run
    run_cpu_stress: bool = True
    run_gpu_stress: bool = True
    run_nvme_stress: bool = True

    # Test durations
    cpu_duration_seconds: int = 300
    gpu_duration_seconds: int = 300
    nvme_duration_seconds: int = 300

    # Sample intervals
    sample_interval_seconds: int = 5

    # Thresholds (None = use defaults)
    cpu_thresholds: Optional[CPUThresholds] = None
    gpu_thresholds: Optional[GPUThresholds] = None
    nvme_thresholds: Optional[NVMeThresholds] = None

    # Device selection (None = auto-detect)
    gpu_indices: Optional[List[int]] = None
    nvme_devices: Optional[List[str]] = None


class StressTestEngine:
    """Engine for running hardware stress tests.

    Integrates with TestEngine to provide stress testing capabilities
    with configurable thresholds and real-time monitoring.
    """

    def __init__(
        self,
        config: StressEngineConfig,
        event_system: Optional[EventSystem] = None
    ):
        self.config = config
        self.events = event_system or EventSystem()
        self._progress_callbacks: List[Callable[[str, float, Dict[str, Any]], None]] = []

    def add_progress_callback(
        self,
        callback: Callable[[str, float, Dict[str, Any]], None]
    ) -> None:
        """Add callback for progress updates.

        Args:
            callback: Function receiving (test_name, percentage, metrics)
        """
        self._progress_callbacks.append(callback)

    def run_all_stress_tests(self) -> List[StressTestResult]:
        """Run all configured stress tests.

        Returns:
            List of StressTestResult for each test.
        """
        results = []

        if self.config.run_cpu_stress:
            result = self.run_cpu_stress()
            results.append(result)

        if self.config.run_gpu_stress:
            result = self.run_gpu_stress()
            results.append(result)

        if self.config.run_nvme_stress:
            result = self.run_nvme_stress()
            results.append(result)

        return results

    def run_cpu_stress(self) -> StressTestResult:
        """Run CPU stress test."""
        self.events.publish(Event(
            type=EventType.TEST_STARTED,
            timestamp=datetime.now(),
            source="StressTestEngine",
            data={"test_name": "cpu_stress"}
        ))

        test = CPUStressTest(
            duration_seconds=self.config.cpu_duration_seconds,
            sample_interval_seconds=self.config.sample_interval_seconds,
            thresholds=self.config.cpu_thresholds
        )

        # Set up progress reporting
        test.set_progress_callback(
            lambda pct, metrics: self._report_progress("cpu_stress", pct, metrics)
        )

        result = test.run()

        self.events.publish(Event(
            type=EventType.TEST_COMPLETED,
            timestamp=datetime.now(),
            source="StressTestEngine",
            data={
                "test_name": "cpu_stress",
                "status": result.status,
                "duration": result.duration_seconds
            }
        ))

        return result

    def run_gpu_stress(self) -> StressTestResult:
        """Run GPU stress test."""
        self.events.publish(Event(
            type=EventType.TEST_STARTED,
            timestamp=datetime.now(),
            source="StressTestEngine",
            data={"test_name": "gpu_stress"}
        ))

        test = GPUStressTest(
            duration_seconds=self.config.gpu_duration_seconds,
            sample_interval_seconds=self.config.sample_interval_seconds,
            gpu_indices=self.config.gpu_indices,
            thresholds=self.config.gpu_thresholds
        )

        test.set_progress_callback(
            lambda pct, metrics: self._report_progress("gpu_stress", pct, metrics)
        )

        result = test.run()

        self.events.publish(Event(
            type=EventType.TEST_COMPLETED,
            timestamp=datetime.now(),
            source="StressTestEngine",
            data={
                "test_name": "gpu_stress",
                "status": result.status,
                "duration": result.duration_seconds
            }
        ))

        return result

    def run_nvme_stress(self) -> StressTestResult:
        """Run NVMe stress test."""
        self.events.publish(Event(
            type=EventType.TEST_STARTED,
            timestamp=datetime.now(),
            source="StressTestEngine",
            data={"test_name": "nvme_stress"}
        ))

        test = NVMeStressTest(
            duration_seconds=self.config.nvme_duration_seconds,
            sample_interval_seconds=self.config.sample_interval_seconds,
            devices=self.config.nvme_devices,
            thresholds=self.config.nvme_thresholds
        )

        test.set_progress_callback(
            lambda pct, metrics: self._report_progress("nvme_stress", pct, metrics)
        )

        result = test.run()

        self.events.publish(Event(
            type=EventType.TEST_COMPLETED,
            timestamp=datetime.now(),
            source="StressTestEngine",
            data={
                "test_name": "nvme_stress",
                "status": result.status,
                "duration": result.duration_seconds
            }
        ))

        return result

    def _report_progress(
        self,
        test_name: str,
        percentage: float,
        metrics: Dict[str, Any]
    ) -> None:
        """Report progress to all callbacks."""
        for callback in self._progress_callbacks:
            try:
                callback(test_name, percentage, metrics)
            except Exception:
                pass  # Don't let callbacks break the test

    def convert_to_test_results(
        self,
        stress_results: List[StressTestResult]
    ) -> List[TestResult]:
        """Convert stress test results to TestResult format."""
        results = []

        for sr in stress_results:
            # Determine status
            if sr.status == "passed":
                status = TestStatus.PASSED
            elif sr.status == "failed":
                status = TestStatus.FAILED
            else:
                status = TestStatus.ERROR

            # Build message from violations
            messages = []
            for metric in sr.metrics:
                if metric.status.value == "critical":
                    messages.append(
                        f"{metric.name}: {metric.value}{metric.unit} - {metric.message}"
                    )

            message = "; ".join(messages) if messages else "All metrics within thresholds"

            # Build details
            details = {
                "duration_seconds": sr.duration_seconds,
                "metrics": [
                    {
                        "name": m.name,
                        "value": m.value,
                        "unit": m.unit,
                        "status": m.status.value
                    }
                    for m in sr.metrics
                ],
                "sample_count": len(sr.samples)
            }

            results.append(TestResult(
                name=sr.test_name,
                status=status,
                duration_ms=int(sr.duration_seconds * 1000),
                message=message,
                details=details
            ))

        return results
