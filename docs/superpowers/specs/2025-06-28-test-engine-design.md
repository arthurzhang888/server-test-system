# 测试引擎设计文档

## 文档信息
- **日期**: 2025-06-28
- **版本**: v1.0
- **状态**: 已批准
- **目标**: 实现测试引擎，支持检测器调度、并行执行、进度通知

---

## 1. 概述

### 1.1 背景
服务器测试系统已有 20 个硬件检测器，但缺乏统一的执行引擎。需要实现一个测试引擎来调度检测器执行、支持并行检测、提供进度通知。

### 1.2 核心组件

| 组件 | 职责 | 文件 |
|------|------|------|
| EventSystem | 事件发布/订阅，进度通知 | `core/events.py` |
| DetectorScheduler | 检测器调度，并行执行控制 | `core/scheduler.py` |
| TestEngine | 测试流程 orchestration | `core/engine.py` |

---

## 2. 事件系统设计

### 2.1 事件类型

```python
class EventType(str, Enum):
    TEST_STARTED = "test_started"
    TEST_COMPLETED = "test_completed"
    TEST_FAILED = "test_failed"
    PROGRESS_UPDATE = "progress_update"
    DETECTOR_STARTED = "detector_started"
    DETECTOR_COMPLETED = "detector_completed"
    ALL_TESTS_COMPLETED = "all_tests_completed"
```

### 2.2 事件数据结构

```python
@dataclass
class Event:
    type: EventType
    timestamp: datetime
    source: str  # detector name or engine
    data: Dict[str, Any]

# Example events:
Event(
    type=EventType.DETECTOR_STARTED,
    timestamp=datetime.now(),
    source="CPUDetector",
    data={"mode": "mock"}
)

Event(
    type=EventType.PROGRESS_UPDATE,
    timestamp=datetime.now(),
    source="TestEngine",
    data={
        "completed": 5,
        "total": 20,
        "percentage": 25.0,
        "current_detector": "MemoryDetector"
    }
)
```

### 2.3 事件系统接口

```python
class EventSystem:
    """Pub-sub event system for test progress notifications."""

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Subscribe to events of a specific type."""

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Unsubscribe from events."""

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""

    def clear_handlers(self) -> None:
        """Clear all event handlers."""
```

---

## 3. 调度器设计

### 3.1 调度策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| SEQUENTIAL | 顺序执行 | 资源受限，避免冲突 |
| PARALLEL | 并行执行 | 默认策略，最大化性能 |
| GROUPED | 分组并行 | 按类别分组执行 |

### 3.2 调度器配置

```python
@dataclass
class SchedulerConfig:
    strategy: str = "parallel"  # sequential, parallel, grouped
    max_workers: int = 4
    timeout_per_detector: int = 30  # seconds
    continue_on_error: bool = True
    detector_groups: Dict[str, List[str]] = field(default_factory=dict)
```

### 3.3 调度器接口

```python
class DetectorScheduler:
    """Schedule and execute detectors."""

    def __init__(self, config: SchedulerConfig, event_system: EventSystem):
        self.config = config
        self.events = event_system

    def schedule(self, detectors: List[BaseDetector]) -> List[TestResult]:
        """Schedule and execute all detectors."""

    def schedule_sequential(self, detectors: List[BaseDetector]) -> List[TestResult]:
        """Execute detectors sequentially."""

    def schedule_parallel(self, detectors: List[BaseDetector]) -> List[TestResult]:
        """Execute detectors in parallel."""

    def schedule_grouped(self, detectors: List[BaseDetector]) -> List[TestResult]:
        """Execute detectors in groups."""

    def _execute_detector(self, detector: BaseDetector) -> TestResult:
        """Execute a single detector with error handling."""
```

---

## 4. 测试引擎设计

### 4.1 引擎配置

```python
@dataclass
class EngineConfig:
    server_sn: str
    server_model: str
    server_type: str
    detector_mode: DetectorMode = DetectorMode.MOCK
    scheduler_config: SchedulerConfig = field(default_factory=SchedulerConfig)
    output_formats: List[str] = field(default_factory=lambda: ["json"])
    output_dir: str = "./reports"
```

### 4.2 引擎接口

```python
class TestEngine:
    """Main test orchestration engine."""

    def __init__(self, config: EngineConfig):
        self.config = config
        self.events = EventSystem()
        self.scheduler = DetectorScheduler(config.scheduler_config, self.events)
        self.detectors: List[BaseDetector] = []

    def register_detector(self, detector: BaseDetector) -> None:
        """Register a detector for execution."""

    def register_default_detectors(self) -> None:
        """Register all default detectors."""

    def run(self) -> TestReport:
        """Run all registered detectors and generate report."""

    def run_detector(self, detector_name: str) -> TestResult:
        """Run a specific detector by name."""

    def on_progress(self, handler: Callable[[Event], None]) -> None:
        """Register progress event handler."""

    def _generate_report(self, results: List[TestResult]) -> TestReport:
        """Generate test report from results."""
```

### 4.3 执行流程

```
┌─────────────────────────────────────────┐
│           TestEngine.run()              │
├─────────────────────────────────────────┤
│  1. Initialize TestReport               │
│  2. Publish TEST_STARTED event          │
├─────────────────────────────────────────┤
│  3. For each detector:                  │
│     a. Publish DETECTOR_STARTED         │
│     b. Execute detector                 │
│     c. Create TestResult                │
│     d. Publish DETECTOR_COMPLETED       │
│     e. Publish PROGRESS_UPDATE          │
├─────────────────────────────────────────┤
│  4. Finalize TestReport                 │
│  5. Publish ALL_TESTS_COMPLETED         │
│  6. Save reports                        │
└─────────────────────────────────────────┘
```

---

## 5. 使用示例

### 5.1 基本使用

```python
# Configure engine
config = EngineConfig(
    server_sn="SN123456",
    server_model="Dell R750",
    server_type="generic",
    detector_mode=DetectorMode.MOCK
)

# Create engine
engine = TestEngine(config)

# Register progress handler
engine.on_progress(lambda event: print(
    f"Progress: {event.data['percentage']:.1f}%"
))

# Register default detectors
engine.register_default_detectors()

# Run tests
report = engine.run()

# Print summary
print(f"Total: {report.summary['total']}")
print(f"Passed: {report.summary['passed']}")
print(f"Failed: {report.summary['failed']}")
```

### 5.2 并行执行配置

```python
config = EngineConfig(
    server_sn="SN123456",
    server_model="Dell R750",
    server_type="generic",
    detector_mode=DetectorMode.REAL,
    scheduler_config=SchedulerConfig(
        strategy="parallel",
        max_workers=8,
        timeout_per_detector=60
    )
)

engine = TestEngine(config)
engine.register_default_detectors()
report = engine.run()
```

### 5.3 分组执行

```python
config = EngineConfig(
    scheduler_config=SchedulerConfig(
        strategy="grouped",
        detector_groups={
            "compute": ["CPUDetector", "MemoryDetector"],
            "storage": ["StorageDetector", "RAIDDetector", "NVMeHealthDetector"],
            "network": ["NetworkDetector", "IBDetector"],
            "management": ["BMCDetector", "ChassisDetector"]
        }
    )
)
```

---

## 6. 验收标准

- [ ] EventSystem 支持订阅/发布/取消订阅
- [ ] DetectorScheduler 支持顺序/并行/分组策略
- [ ] TestEngine 可以注册和运行所有 20 个检测器
- [ ] 进度事件正确触发（开始、完成、百分比）
- [ ] 测试报告正确生成
- [ ] 并行执行性能优于顺序执行
- [ ] 错误处理完善（单个检测器失败不影响整体）
- [ ] 单元测试覆盖率 > 80%

---

*设计文档完成，等待进入实现阶段*
