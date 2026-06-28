from dataclasses import dataclass, field
from typing import List, Callable, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from src.detectors.base import BaseDetector, DetectorMode
from src.detectors import (
    CPUDetector, MemoryDetector, StorageDetector, NetworkDetector,
    GPUDetector, BMCDetector, PCIeDetector, RAIDDetector, PSUDetector,
    SensorDetector, TPMDetector, BIOSDetector, USBDetector,
    IBDetector, FPGADetector, SecurityDetector, ChassisDetector,
    DIMMDetector, NVMeHealthDetector, SerialDetector
)
from src.core.state import TestResult, TestReport, TestStatus
from src.core.events import EventSystem, EventType, Event
from src.core.scheduler import DetectorScheduler, SchedulerConfig


@dataclass
class EngineConfig:
    """Configuration for test engine."""
    server_sn: str
    server_model: str
    server_type: str
    detector_mode: DetectorMode = DetectorMode.MOCK
    scheduler_config: SchedulerConfig = field(default_factory=SchedulerConfig)
    output_formats: List[str] = field(default_factory=lambda: ["json"])
    output_dir: str = "./reports"


class TestEngine:
    """Main test orchestration engine."""

    def __init__(self, config: EngineConfig):
        self.config = config
        self.events = EventSystem()
        self.scheduler = DetectorScheduler(config.scheduler_config, self.events)
        self.detectors: List[BaseDetector] = []

    def register_detector(self, detector: BaseDetector) -> None:
        """Register a detector for execution."""
        detector.mode = self.config.detector_mode
        self.detectors.append(detector)

    def register_default_detectors(self) -> None:
        """Register all default detectors."""
        detector_classes = [
            CPUDetector, MemoryDetector, StorageDetector, NetworkDetector,
            GPUDetector, BMCDetector, PCIeDetector, RAIDDetector, PSUDetector,
            SensorDetector, TPMDetector, BIOSDetector, USBDetector,
            IBDetector, FPGADetector, SecurityDetector, ChassisDetector,
            DIMMDetector, NVMeHealthDetector, SerialDetector
        ]

        for detector_class in detector_classes:
            self.register_detector(detector_class())

    def run(self) -> TestReport:
        """Run all registered detectors and generate report."""
        report = TestReport(
            server_sn=self.config.server_sn,
            server_model=self.config.server_model,
            server_type=self.config.server_type,
            start_time=datetime.now()
        )

        self.events.publish(Event(
            type=EventType.TEST_STARTED,
            timestamp=datetime.now(),
            source="TestEngine",
            data={
                "detector_count": len(self.detectors),
                "mode": self.config.detector_mode.value
            }
        ))

        completed = 0
        total = len(self.detectors)

        def on_detector_completed(event: Event):
            nonlocal completed
            completed += 1
            self.events.publish(Event(
                type=EventType.PROGRESS_UPDATE,
                timestamp=datetime.now(),
                source="TestEngine",
                data={
                    "completed": completed,
                    "total": total,
                    "percentage": (completed / total * 100) if total > 0 else 0,
                    "current_detector": event.source
                }
            ))

        self.events.subscribe(EventType.DETECTOR_COMPLETED, on_detector_completed)
        self.events.subscribe(EventType.DETECTOR_FAILED, on_detector_completed)

        results = self.scheduler.schedule(self.detectors)
        report.results = results
        report.end_time = datetime.now()

        self.events.publish(Event(
            type=EventType.ALL_TESTS_COMPLETED,
            timestamp=datetime.now(),
            source="TestEngine",
            data={
                "total": len(results),
                "passed": report.summary["passed"],
                "failed": report.summary["failed"],
                "errors": report.summary["errors"],
                "duration_seconds": report.duration_seconds
            }
        ))

        self._save_reports(report)

        return report

    def run_detector(self, detector_name: str) -> TestResult:
        """Run a specific detector by name."""
        for detector in self.detectors:
            if detector.name == detector_name:
                return self.scheduler._execute_detector(detector)

        raise ValueError(f"Detector not found: {detector_name}")

    def on_progress(self, handler: Callable[[Event], None]) -> None:
        """Register progress event handler."""
        self.events.subscribe(EventType.PROGRESS_UPDATE, handler)

    def _save_reports(self, report: TestReport) -> None:
        """Save test reports to files."""
        output_path = Path(self.config.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        if "json" in self.config.output_formats:
            from src.reporters.json_reporter import JSONReporter
            reporter = JSONReporter()
            reporter.save(report, output_path / "test_report.json")
