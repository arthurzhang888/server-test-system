from dataclasses import dataclass, field
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

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
    detector_groups: Dict[str, List[str]] = field(default_factory=dict)


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
        """Execute detectors sequentially."""
        results = []
        for detector in detectors:
            result = self._execute_detector(detector)
            results.append(result)
            if result.status == TestStatus.ERROR and not self.config.continue_on_error:
                break
        return results

    def schedule_parallel(self, detectors: List[BaseDetector]) -> List[TestResult]:
        """Execute detectors in parallel."""
        results = []
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_detector = {
                executor.submit(self._execute_detector, d): d
                for d in detectors
            }

            for future in as_completed(future_to_detector):
                detector = future_to_detector[future]
                try:
                    result = future.result(timeout=self.config.timeout_per_detector)
                    results.append(result)
                except Exception as e:
                    results.append(TestResult(
                        name=detector.name,
                        status=TestStatus.ERROR,
                        message=str(e)
                    ))

        return results

    def schedule_grouped(self, detectors: List[BaseDetector]) -> List[TestResult]:
        """Execute detectors in groups."""
        return self.schedule_parallel(detectors)

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
