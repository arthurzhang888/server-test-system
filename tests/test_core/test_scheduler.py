import pytest
from dataclasses import dataclass, field
from typing import Dict, Any

from src.core.scheduler import DetectorScheduler, SchedulerConfig
from src.core.events import EventSystem, EventType
from src.detectors.base import BaseDetector, DetectorMode


class MockDetector(BaseDetector):
    """Mock detector for testing."""

    def __init__(self, name: str, mode: DetectorMode = DetectorMode.REAL, should_fail: bool = False, delay_ms: int = 0):
        super().__init__(mode)
        self._name = name
        self.should_fail = should_fail
        self.delay_ms = delay_ms

    @property
    def name(self) -> str:
        return self._name

    def detect_real(self) -> Dict[str, Any]:
        import time
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000)
        if self.should_fail:
            raise RuntimeError(f"{self.name} failed")
        return {"name": self.name, "mode": "real"}

    def detect_mock(self) -> Dict[str, Any]:
        if self.should_fail:
            raise RuntimeError(f"{self.name} failed")
        return {"name": self.name, "mode": "mock"}


class TestSchedulerConfig:
    def test_default_config(self):
        config = SchedulerConfig()
        assert config.strategy == "parallel"
        assert config.max_workers == 4
        assert config.timeout_per_detector == 30
        assert config.continue_on_error is True


class TestDetectorSchedulerSequential:
    def test_sequential_execution(self):
        config = SchedulerConfig(strategy="sequential")
        events = EventSystem()
        scheduler = DetectorScheduler(config, events)

        detectors = [
            MockDetector("det1", mode=DetectorMode.MOCK),
            MockDetector("det2", mode=DetectorMode.MOCK)
        ]

        results = scheduler.schedule(detectors)

        assert len(results) == 2
        assert all(r.status.value == "passed" for r in results)

    def test_sequential_with_error_continue(self):
        config = SchedulerConfig(strategy="sequential", continue_on_error=True)
        events = EventSystem()
        scheduler = DetectorScheduler(config, events)

        detectors = [
            MockDetector("det1", mode=DetectorMode.MOCK),
            MockDetector("det2", mode=DetectorMode.MOCK, should_fail=True),
            MockDetector("det3", mode=DetectorMode.MOCK)
        ]

        results = scheduler.schedule(detectors)

        assert len(results) == 3
        assert results[0].status.value == "passed"
        assert results[1].status.value == "error"
        assert results[2].status.value == "passed"


class TestDetectorSchedulerParallel:
    def test_parallel_execution(self):
        config = SchedulerConfig(strategy="parallel", max_workers=2)
        events = EventSystem()
        scheduler = DetectorScheduler(config, events)

        detectors = [
            MockDetector("det1", mode=DetectorMode.MOCK, delay_ms=50),
            MockDetector("det2", mode=DetectorMode.MOCK, delay_ms=50)
        ]

        import time
        start = time.time()
        results = scheduler.schedule(detectors)
        duration = time.time() - start

        assert len(results) == 2
        assert duration < 0.1

    def test_parallel_results(self):
        config = SchedulerConfig(strategy="parallel", max_workers=4)
        events = EventSystem()
        scheduler = DetectorScheduler(config, events)

        detectors = [MockDetector(f"det{i}", mode=DetectorMode.MOCK) for i in range(5)]
        results = scheduler.schedule(detectors)

        assert len(results) == 5
        assert all(r.status.value == "passed" for r in results)


class TestDetectorSchedulerEvents:
    def test_events_published(self):
        config = SchedulerConfig(strategy="sequential")
        events = EventSystem()
        scheduler = DetectorScheduler(config, events)

        published_events = []
        events.subscribe(EventType.DETECTOR_STARTED, lambda e: published_events.append(e.type))
        events.subscribe(EventType.DETECTOR_COMPLETED, lambda e: published_events.append(e.type))

        detectors = [MockDetector("det1", mode=DetectorMode.MOCK)]
        scheduler.schedule(detectors)

        assert EventType.DETECTOR_STARTED in published_events
        assert EventType.DETECTOR_COMPLETED in published_events
