# 测试引擎实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现测试引擎（EventSystem + DetectorScheduler + TestEngine），支持检测器调度、并行执行、进度通知

**Architecture:** 事件驱动架构，调度器支持顺序/并行/分组策略，引擎统一 orchestration

**Tech Stack:** Python 3.9+, threading, concurrent.futures, dataclasses

---

## 文件结构总览

| 文件路径 | 职责 |
|----------|------|
| `src/core/events.py` | 事件系统（发布/订阅） |
| `src/core/scheduler.py` | 检测器调度器 |
| `src/core/engine.py` | 测试引擎主控 |
| `tests/test_core/test_events.py` | 事件系统测试 |
| `tests/test_core/test_scheduler.py` | 调度器测试 |
| `tests/test_core/test_engine.py` | 测试引擎测试 |

---

## Task 1: 事件系统

**Files:**
- Create: `src/core/events.py`
- Create: `tests/test_core/test_events.py`
- Modify: `src/core/__init__.py`

- [ ] **Step 1: 编写事件系统测试**

Create `tests/test_core/test_events.py`:
```python
import pytest
from datetime import datetime
from src.core.events import EventSystem, EventType, Event


class TestEventSystem:
    def test_subscribe_and_publish(self):
        events = EventSystem()
        received = []

        def handler(event):
            received.append(event)

        events.subscribe(EventType.TEST_STARTED, handler)
        events.publish(Event(EventType.TEST_STARTED, datetime.now(), "test", {}))

        assert len(received) == 1
        assert received[0].type == EventType.TEST_STARTED

    def test_multiple_handlers(self):
        events = EventSystem()
        count = [0]

        def handler1(event):
            count[0] += 1

        def handler2(event):
            count[0] += 1

        events.subscribe(EventType.TEST_STARTED, handler1)
        events.subscribe(EventType.TEST_STARTED, handler2)
        events.publish(Event(EventType.TEST_STARTED, datetime.now(), "test", {}))

        assert count[0] == 2

    def test_unsubscribe(self):
        events = EventSystem()
        received = []

        def handler(event):
            received.append(event)

        events.subscribe(EventType.TEST_STARTED, handler)
        events.unsubscribe(EventType.TEST_STARTED, handler)
        events.publish(Event(EventType.TEST_STARTED, datetime.now(), "test", {}))

        assert len(received) == 0

    def test_different_event_types(self):
        events = EventSystem()
        started = []
        completed = []

        events.subscribe(EventType.TEST_STARTED, lambda e: started.append(e))
        events.subscribe(EventType.TEST_COMPLETED, lambda e: completed.append(e))

        events.publish(Event(EventType.TEST_STARTED, datetime.now(), "test", {}))

        assert len(started) == 1
        assert len(completed) == 0

    def test_event_data(self):
        events = EventSystem()
        received_data = {}

        def handler(event):
            received_data.update(event.data)

        events.subscribe(EventType.PROGRESS_UPDATE, handler)
        events.publish(Event(
            EventType.PROGRESS_UPDATE,
            datetime.now(),
            "engine",
            {"percentage": 50.0, "completed": 10}
        ))

        assert received_data["percentage"] == 50.0
        assert received_data["completed"] == 10

    def test_clear_handlers(self):
        events = EventSystem()
        received = []

        events.subscribe(EventType.TEST_STARTED, lambda e: received.append(e))
        events.clear_handlers()
        events.publish(Event(EventType.TEST_STARTED, datetime.now(), "test", {}))

        assert len(received) == 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_core/test_events.py -v
```

Expected: ImportError - EventSystem not found

- [ ] **Step 3: 实现事件系统**

Create `src/core/events.py`:
```python
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Any, Callable
from datetime import datetime


class EventType(str, Enum):
    """Types of events that can be published."""
    TEST_STARTED = "test_started"
    TEST_COMPLETED = "test_completed"
    TEST_FAILED = "test_failed"
    PROGRESS_UPDATE = "progress_update"
    DETECTOR_STARTED = "detector_started"
    DETECTOR_COMPLETED = "detector_completed"
    DETECTOR_FAILED = "detector_failed"
    ALL_TESTS_COMPLETED = "all_tests_completed"


@dataclass
class Event:
    """An event in the system."""
    type: EventType
    timestamp: datetime
    source: str
    data: Dict[str, Any]


class EventSystem:
    """Pub-sub event system for test progress notifications."""

    def __init__(self):
        self._handlers: Dict[EventType, List[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Subscribe to events of a specific type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Unsubscribe from events."""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] if h != handler
            ]

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception:
                # Handler errors should not affect other handlers
                pass

    def clear_handlers(self) -> None:
        """Clear all event handlers."""
        self._handlers.clear()
```

- [ ] **Step 4: 更新核心模块导出**

Update `src/core/__init__.py`:
```python
from .state import TestStatus, TestResult, TestReport
from .events import EventSystem, EventType, Event

__all__ = [
    "TestStatus",
    "TestResult",
    "TestReport",
    "EventSystem",
    "EventType",
    "Event"
]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_core/test_events.py -v
```

Expected: 6 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/core/events.py tests/test_core/test_events.py src/core/__init__.py
git commit -m "feat(core): add EventSystem for progress notifications

- Pub-sub event system with subscribe/unsubscribe/publish
- Event types: TEST_STARTED, TEST_COMPLETED, PROGRESS_UPDATE, etc.
- Event dataclass with timestamp, source, and data
- Error isolation between handlers

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 2: 检测器调度器

**Files:**
- Create: `src/core/scheduler.py`
- Create: `tests/test_core/test_scheduler.py`
- Modify: `src/core/__init__.py`

- [ ] **Step 1: 编写调度器测试**

Create `tests/test_core/test_scheduler.py`:
```python
import pytest
from dataclasses import dataclass, field
from typing import Dict, Any

from src.core.scheduler import DetectorScheduler, SchedulerConfig
from src.core.events import EventSystem, EventType
from src.detectors.base import BaseDetector, DetectorMode


@dataclass
class MockDetector(BaseDetector):
    """Mock detector for testing."""
    name: str
    should_fail: bool = False
    delay_ms: int = 0

    def detect_real(self) -> Dict[str, Any]:
        import time
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000)
        if self.should_fail:
            raise RuntimeError(f"{self.name} failed")
        return {"name": self.name, "mode": "real"}

    def detect_mock(self) -> Dict[str, Any]:
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
        # Parallel execution should be faster than sequential
        assert duration < 0.1  # Less than 100ms for parallel

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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_core/test_scheduler.py -v
```

Expected: ImportError - DetectorScheduler not found

- [ ] **Step 3: 实现调度器**

Create `src/core/scheduler.py`:
```python
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
    strategy: str = "parallel"  # sequential, parallel, grouped
    max_workers: int = 4
    timeout_per_detector: int = 30  # seconds
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
        """Execute detectors in groups (not implemented yet)."""
        # For now, fall back to parallel
        return self.schedule_parallel(detectors)

    def _execute_detector(self, detector: BaseDetector) -> TestResult:
        """Execute a single detector with error handling."""
        detector_name = detector.name

        # Publish started event
        self.events.publish(Event(
            type=EventType.DETECTOR_STARTED,
            timestamp=datetime.now(),
            source=detector_name,
            data={"mode": detector.mode.value}
        ))

        start_time = time.time()

        try:
            # Execute detection
            data = detector.detect()
            duration_ms = int((time.time() - start_time) * 1000)

            result = TestResult(
                name=detector_name,
                status=TestStatus.PASSED,
                duration_ms=duration_ms,
                details=data
            )

            # Publish completed event
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

            # Publish failed event
            self.events.publish(Event(
                type=EventType.DETECTOR_FAILED,
                timestamp=datetime.now(),
                source=detector_name,
                data={"error": str(e)}
            ))

            return result
```

- [ ] **Step 4: 更新核心模块导出**

Update `src/core/__init__.py`:
```python
from .state import TestStatus, TestResult, TestReport
from .events import EventSystem, EventType, Event
from .scheduler import DetectorScheduler, SchedulerConfig

__all__ = [
    "TestStatus",
    "TestResult",
    "TestReport",
    "EventSystem",
    "EventType",
    "Event",
    "DetectorScheduler",
    "SchedulerConfig"
]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_core/test_scheduler.py -v
```

Expected: 10 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/core/scheduler.py tests/test_core/test_scheduler.py src/core/__init__.py
git commit -m "feat(core): add DetectorScheduler for detector execution

- Support sequential and parallel execution strategies
- Configurable max workers and timeout
- Continue on error option
- Event publishing for detector lifecycle
- ThreadPoolExecutor for parallel execution

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 3: 测试引擎

**Files:**
- Create: `src/core/engine.py`
- Create: `tests/test_core/test_engine.py`
- Modify: `src/core/__init__.py`

- [ ] **Step 1: 编写测试引擎测试**

Create `tests/test_core/test_engine.py`:
```python
import pytest
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any

from src.core.engine import TestEngine, EngineConfig
from src.core.state import TestStatus
from src.core.events import EventType
from src.detectors.base import DetectorMode


class TestEngineConfig:
    def test_default_config(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic"
        )
        assert config.server_sn == "SN123"
        assert config.detector_mode == DetectorMode.MOCK


class TestTestEngineBasic:
    def test_engine_creation(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic"
        )
        engine = TestEngine(config)
        assert engine.config == config

    def test_register_default_detectors(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic"
        )
        engine = TestEngine(config)
        engine.register_default_detectors()
        assert len(engine.detectors) > 0

    def test_run_mock_mode(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic",
            detector_mode=DetectorMode.MOCK
        )
        engine = TestEngine(config)
        engine.register_default_detectors()

        # Limit to first 3 detectors for faster test
        engine.detectors = engine.detectors[:3]

        report = engine.run()

        assert report.server_sn == "SN123"
        assert len(report.results) == 3
        assert all(r.status == TestStatus.PASSED for r in report.results)

    def test_progress_events(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic",
            detector_mode=DetectorMode.MOCK
        )
        engine = TestEngine(config)
        engine.register_default_detectors()
        engine.detectors = engine.detectors[:2]

        progress_events = []
        engine.on_progress(lambda e: progress_events.append(e))

        engine.run()

        assert len(progress_events) > 0

    def test_report_summary(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic",
            detector_mode=DetectorMode.MOCK
        )
        engine = TestEngine(config)
        engine.register_default_detectors()
        engine.detectors = engine.detectors[:3]

        report = engine.run()

        assert report.summary["total"] == 3
        assert report.summary["passed"] == 3
        assert report.overall_status == TestStatus.PASSED

    def test_run_specific_detector(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic",
            detector_mode=DetectorMode.MOCK
        )
        engine = TestEngine(config)
        engine.register_default_detectors()

        result = engine.run_detector("cpu")

        assert result.name == "cpu"
        assert result.status == TestStatus.PASSED
        assert "model" in result.details
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_core/test_engine.py -v
```

Expected: ImportError - TestEngine not found

- [ ] **Step 3: 实现测试引擎**

Create `src/core/engine.py`:
```python
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
        # Set detector mode from engine config
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
        # Create report
        report = TestReport(
            server_sn=self.config.server_sn,
            server_model=self.config.server_model,
            server_type=self.config.server_type,
            start_time=datetime.now()
        )

        # Publish test started event
        self.events.publish(Event(
            type=EventType.TEST_STARTED,
            timestamp=datetime.now(),
            source="TestEngine",
            data={
                "detector_count": len(self.detectors),
                "mode": self.config.detector_mode.value
            }
        ))

        # Track progress
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

        # Run detectors
        results = self.scheduler.schedule(self.detectors)
        report.results = results
        report.end_time = datetime.now()

        # Publish completion event
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

        # Save reports
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

        # Save JSON report
        if "json" in self.config.output_formats:
            from src.reporters.json_reporter import JSONReporter
            reporter = JSONReporter()
            reporter.save(report, output_path / "test_report.json")
```

- [ ] **Step 4: 更新核心模块导出**

Update `src/core/__init__.py`:
```python
from .state import TestStatus, TestResult, TestReport
from .events import EventSystem, EventType, Event
from .scheduler import DetectorScheduler, SchedulerConfig
from .engine import TestEngine, EngineConfig

__all__ = [
    "TestStatus",
    "TestResult",
    "TestReport",
    "EventSystem",
    "EventType",
    "Event",
    "DetectorScheduler",
    "SchedulerConfig",
    "TestEngine",
    "EngineConfig"
]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_core/test_engine.py -v
```

Expected: 6 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/core/engine.py tests/test_core/test_engine.py src/core/__init__.py
git commit -m "feat(core): add TestEngine for orchestrating detector execution

- TestEngine orchestrates all 20 detectors
- Register default detectors or specific detectors
- Progress events with percentage updates
- Run all or single detector
- Automatic report generation and saving

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 4: CLI 集成

**Files:**
- Modify: `src/cli/app.py`

- [ ] **Step 1: 更新 CLI 使用测试引擎**

Update `src/cli/app.py` run command:
```python
@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to config file')
@click.option('--output', '-o', type=click.Path(), default='./reports', help='Output directory')
@click.option('--mock', is_flag=True, help='Use mock mode for testing')
@click.option('--parallel/--sequential', default=True, help='Execution mode')
@click.option('--workers', '-w', type=int, default=4, help='Number of parallel workers')
def run(config, output, mock, parallel, workers):
    """Run hardware detection tests."""
    from src.core.engine import TestEngine, EngineConfig
    from src.core.scheduler import SchedulerConfig
    from src.detectors.base import DetectorMode
    from src.core.events import EventType

    click.echo("Starting Server Test System...")

    # Configure engine
    detector_mode = DetectorMode.MOCK if mock else DetectorMode.REAL
    strategy = "parallel" if parallel else "sequential"

    engine_config = EngineConfig(
        server_sn="UNKNOWN",  # Could detect from BIOS
        server_model="Unknown Model",
        server_type="generic",
        detector_mode=detector_mode,
        scheduler_config=SchedulerConfig(
            strategy=strategy,
            max_workers=workers
        ),
        output_dir=output
    )

    engine = TestEngine(engine_config)

    # Register progress callback
    engine.on_progress(lambda e: click.echo(
        f"Progress: {e.data['completed']}/{e.data['total']} "
        f"({e.data['percentage']:.1f}%) - {e.data['current_detector']}"
    ))

    # Register and run detectors
    engine.register_default_detectors()

    click.echo(f"Running {len(engine.detectors)} detectors in {strategy} mode...")

    report = engine.run()

    # Print summary
    click.echo("\n" + "=" * 50)
    click.echo("Test Summary")
    click.echo("=" * 50)
    click.echo(f"Total: {report.summary['total']}")
    click.echo(f"Passed: {report.summary['passed']}")
    click.echo(f"Failed: {report.summary['failed']}")
    click.echo(f"Errors: {report.summary['errors']}")
    click.echo(f"Duration: {report.duration_seconds:.2f}s")
    click.echo(f"Overall: {report.overall_status.value}")
    click.echo("=" * 50)
    click.echo(f"\nReport saved to: {output}/test_report.json")
```

- [ ] **Step 2: 运行测试**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m src.main run --mock --sequential
```

Expected: Shows progress and summary

- [ ] **Step 3: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/cli/app.py
git commit -m "feat(cli): integrate TestEngine with CLI

- Use TestEngine for detector execution
- Add --parallel/--sequential options
- Add --workers option for parallel execution
- Show progress during execution
- Display test summary

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## 验收检查清单

| 验收项 | 验证命令 | 预期结果 |
|--------|----------|----------|
| 事件系统测试 | `pytest tests/test_core/test_events.py -v` | 6 tests PASS |
| 调度器测试 | `pytest tests/test_core/test_scheduler.py -v` | 10 tests PASS |
| 测试引擎测试 | `pytest tests/test_core/test_engine.py -v` | 6 tests PASS |
| 完整测试套件 | `pytest` | 222+ tests PASS |
| CLI mock 模式 | `python -m src.main run --mock` | 成功执行 |
| CLI 并行模式 | `python -m src.main run --mock --parallel -w 8` | 成功执行 |

---

*计划完成，准备执行*
