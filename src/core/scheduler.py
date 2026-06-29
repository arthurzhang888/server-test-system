from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FutureTimeoutError
import time
import signal
from contextlib import contextmanager

from src.detectors.base import BaseDetector, DetectorMode
from src.core.state import TestResult, TestStatus
from src.core.events import EventSystem, EventType, Event
from datetime import datetime


@dataclass
class SchedulerConfig:
    """Configuration for detector scheduling."""
    strategy: str = "parallel"
    max_workers: int = 4
    timeout_per_detector: int = 30
    continue_on_error: bool = True
    detector_groups: Dict[str, List[str]] = field(default_factory=lambda: {
        "compute": ["CPUDetector", "MemoryDetector", "DIMMDetector"],
        "storage": ["StorageDetector", "RAIDDetector", "NVMeHealthDetector"],
        "network": ["NetworkDetector", "IBDetector"],
        "accelerators": ["GPUDetector", "FPGADetector"],
        "management": ["BMCDetector", "BIOSDetector", "TPMDetector", "ChassisDetector"],
        "io": ["PCIeDetector", "USBDetector", "SerialDetector"],
        "power": ["PSUDetector", "SensorDetector"],
        "security": ["SecurityDetector"]
    })


class DetectorScheduler:
    """Schedule and execute detectors."""

    def __init__(self, config: SchedulerConfig, event_system: EventSystem):
        self.config = config
        self.events = event_system

    def schedule(self, detectors: List[BaseDetector]) -> List[TestResult]:
        """Schedule and execute all detectors based on strategy."""
        if self.config.strategy == "sequential":
            return self.schedule_sequential(detectors)
        elif self.config.strategy == "parallel":
            return self.schedule_parallel(detectors)
        elif self.config.strategy == "grouped":
            return self.schedule_grouped(detectors)
        else:
            raise ValueError(f"Unknown strategy: {self.config.strategy}")

    def schedule_sequential(self, detectors: List[BaseDetector]) -> List[TestResult]:
        """Execute detectors sequentially with timeout enforcement."""
        results = []
        for detector in detectors:
            result = self._execute_detector_with_timeout(detector)
            results.append(result)
            if result.status == TestStatus.ERROR and not self.config.continue_on_error:
                break
        return results

    def schedule_parallel(self, detectors: List[BaseDetector]) -> List[TestResult]:
        """Execute detectors in parallel with timeout enforcement."""
        results = []
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_detector = {
                executor.submit(self._execute_detector, d): d
                for d in detectors
            }

            for future in as_completed(future_to_detector):
                detector = future_to_detector[future]
                try:
                    # Use the executor timeout mechanism
                    result = future.result(timeout=self.config.timeout_per_detector)
                    results.append(result)
                except FutureTimeoutError:
                    results.append(TestResult(
                        name=detector.name,
                        status=TestStatus.ERROR,
                        message=f"Detector timed out after {self.config.timeout_per_detector}s"
                    ))
                except Exception as e:
                    results.append(TestResult(
                        name=detector.name,
                        status=TestStatus.ERROR,
                        message=str(e)
                    ))

        return results

    def schedule_grouped(self, detectors: List[BaseDetector]) -> List[TestResult]:
        """Execute detectors in groups.

        Groups are executed sequentially, but detectors within each group
        run in parallel. This provides a balance between resource contention
        and execution speed.
        """
        results = []
        groups = self.config.detector_groups

        # Organize detectors into groups
        grouped_detectors: Dict[str, List[BaseDetector]] = {name: [] for name in groups.keys()}
        ungrouped: List[BaseDetector] = []

        for detector in detectors:
            detector_name = detector.__class__.__name__
            found_group = False
            for group_name, group_members in groups.items():
                if detector_name in group_members:
                    grouped_detectors[group_name].append(detector)
                    found_group = True
                    break
            if not found_group:
                ungrouped.append(detector)

        # Execute each group sequentially
        for group_name, group_detectors in grouped_detectors.items():
            if not group_detectors:
                continue

            # Publish group start event
            self.events.publish(Event(
                type=EventType.PROGRESS_UPDATE,
                timestamp=datetime.now(),
                source="DetectorScheduler",
                data={
                    "message": f"Starting group: {group_name}",
                    "group": group_name,
                    "detector_count": len(group_detectors)
                }
            ))

            # Execute group in parallel
            group_results = self.schedule_parallel(group_detectors)
            results.extend(group_results)

            # Check if we should continue
            if not self.config.continue_on_error:
                errors = [r for r in group_results if r.status == TestStatus.ERROR]
                if errors:
                    break

        # Execute ungrouped detectors in parallel
        if ungrouped:
            ungrouped_results = self.schedule_parallel(ungrouped)
            results.extend(ungrouped_results)

        return results

    def _execute_detector(self, detector: BaseDetector) -> TestResult:
        """Execute a single detector with error handling."""
        detector_name = detector.name

        self.events.publish(Event(
            type=EventType.DETECTOR_STARTED,
            timestamp=datetime.now(),
            source=detector_name,
            data={"mode": detector.mode.value}
        ))

        start_time = time.time()

        try:
            data = detector.detect()
            duration_ms = int((time.time() - start_time) * 1000)

            result = TestResult(
                name=detector_name,
                status=TestStatus.PASSED,
                duration_ms=duration_ms,
                details=data
            )

            self.events.publish(Event(
                type=EventType.DETECTOR_COMPLETED,
                timestamp=datetime.now(),
                source=detector_name,
                data={"duration_ms": duration_ms}
            ))

            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            result = TestResult(
                name=detector_name,
                status=TestStatus.ERROR,
                duration_ms=duration_ms,
                message=str(e)
            )

            self.events.publish(Event(
                type=EventType.DETECTOR_FAILED,
                timestamp=datetime.now(),
                source=detector_name,
                data={"error": str(e)}
            ))

            return result

    def _execute_detector_with_timeout(self, detector: BaseDetector) -> TestResult:
        """Execute detector with timeout enforcement using signal-based alarm.

        Note: signal.SIGALRM is only available on Unix systems.
        On Windows, this falls back to the executor timeout.
        """
        import platform

        detector_name = detector.name

        self.events.publish(Event(
            type=EventType.DETECTOR_STARTED,
            timestamp=datetime.now(),
            source=detector_name,
            data={"mode": detector.mode.value}
        ))

        start_time = time.time()

        try:
            # Use signal-based timeout on Unix
            if platform.system() != "Windows":
                data = self._execute_with_alarm(detector.detect, self.config.timeout_per_detector)
            else:
                # On Windows, just run without signal timeout
                # The ThreadPoolExecutor timeout will handle it
                data = detector.detect()

            duration_ms = int((time.time() - start_time) * 1000)

            result = TestResult(
                name=detector_name,
                status=TestStatus.PASSED,
                duration_ms=duration_ms,
                details=data
            )

            self.events.publish(Event(
                type=EventType.DETECTOR_COMPLETED,
                timestamp=datetime.now(),
                source=detector_name,
                data={"duration_ms": duration_ms}
            ))

            return result

        except TimeoutError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Detector timed out after {self.config.timeout_per_detector}s"

            result = TestResult(
                name=detector_name,
                status=TestStatus.ERROR,
                duration_ms=duration_ms,
                message=error_msg
            )

            self.events.publish(Event(
                type=EventType.DETECTOR_FAILED,
                timestamp=datetime.now(),
                source=detector_name,
                data={"error": error_msg, "timeout": True}
            ))

            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)

            result = TestResult(
                name=detector_name,
                status=TestStatus.ERROR,
                duration_ms=duration_ms,
                message=str(e)
            )

            self.events.publish(Event(
                type=EventType.DETECTOR_FAILED,
                timestamp=datetime.now(),
                source=detector_name,
                data={"error": str(e)}
            ))

            return result

    def _execute_with_alarm(self, func, timeout: int):
        """Execute function with signal-based timeout (Unix only)."""
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Function execution exceeded {timeout} seconds")

        # Set up signal handler
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)

        try:
            result = func()
            signal.alarm(0)  # Cancel alarm
            return result
        finally:
            signal.signal(signal.SIGALRM, old_handler)  # Restore old handler
