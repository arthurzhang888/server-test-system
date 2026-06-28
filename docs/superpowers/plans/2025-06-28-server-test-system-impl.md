# 服务器测试系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现完整的服务器测试系统，支持 4 种服务器类型、7 类硬件检测、3 种报告格式，以及 mock/real 模式切换。

**Architecture:** 采用分层架构，核心引擎负责任务调度和状态管理，检测器采用抽象基类 + 具体实现模式，通过配置控制 mock/real 模式切换，报告生成器支持多种格式输出。

**Tech Stack:** Python 3.9+, Pydantic, Click, Rich, Jinja2, psutil, pytest

---

## 文件结构总览

| 文件路径 | 职责 |
|----------|------|
| `src/config/schemas.py` | Pydantic 配置数据模型 |
| `src/config/loader.py` | YAML 配置文件加载器 |
| `src/detectors/base.py` | 检测器抽象基类（含 mock/real 切换） |
| `src/detectors/cpu.py` | CPU 检测器实现 |
| `src/detectors/memory.py` | 内存检测器实现 |
| `src/core/state.py` | 测试状态管理（枚举 + 数据类） |
| `src/core/events.py` | 事件系统（进度通知） |
| `src/core/scheduler.py` | 任务调度器 |
| `src/core/engine.py` | 测试引擎主控 |
| `src/reporters/base.py` | 报告生成器基类 |
| `src/reporters/json_reporter.py` | JSON 报告生成 |
| `src/cli/app.py` | CLI 主入口 |
| `config/global.yaml` | 全局配置文件 |
| `config/server_types/generic.yaml` | 通用服务器配置 |

---

## Task 1: 配置系统 - 数据模型

**Files:**
- Create: `src/config/schemas.py`
- Test: `tests/test_config_schemas.py`

- [ ] **Step 1: 创建目录结构**

```bash
mkdir -p src/config src/detectors src/core src/reporters src/cli src/adapters config/server_types tests
```

- [ ] **Step 2: 编写配置数据模型测试**

Create `tests/test_config_schemas.py`:
```python
import pytest
from src.config.schemas import DetectorMode, ServerType, TestConfig, GlobalConfig

def test_detector_mode_enum():
    assert DetectorMode.MOCK.value == "mock"
    assert DetectorMode.REAL.value == "real"

def test_server_type_enum():
    assert ServerType.GENERIC.value == "generic"
    assert ServerType.STORAGE.value == "storage"
    assert ServerType.COMPUTE.value == "compute"
    assert ServerType.AI_SERVER.value == "ai_server"

def test_test_config_defaults():
    config = TestConfig(name="cpu_test")
    assert config.enabled is True
    assert config.params == {}

def test_test_config_with_params():
    config = TestConfig(
        name="cpu_test",
        enabled=True,
        params={"duration": 300, "threads": "auto"}
    )
    assert config.params["duration"] == 300

def test_global_config_minimal():
    config = GlobalConfig(
        server_type=ServerType.GENERIC,
        mode="auto",
        tests=[]
    )
    assert config.server_type == ServerType.GENERIC
    assert config.detector_mode == DetectorMode.REAL  # default
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_config_schemas.py -v
```

Expected: ImportError - module not found

- [ ] **Step 4: 实现配置数据模型**

Create `src/config/__init__.py`:
```python
from .schemas import DetectorMode, ServerType, TestConfig, GlobalConfig
from .loader import ConfigLoader

__all__ = ["DetectorMode", "ServerType", "TestConfig", "GlobalConfig", "ConfigLoader"]
```

Create `src/config/schemas.py`:
```python
from enum import Enum
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class DetectorMode(str, Enum):
    MOCK = "mock"
    REAL = "real"


class ServerType(str, Enum):
    GENERIC = "generic"
    STORAGE = "storage"
    COMPUTE = "compute"
    AI_SERVER = "ai_server"


class OutputConfig(BaseModel):
    formats: List[str] = Field(default=["json"], description="Output formats: json, html, csv")
    upload_to_ems: bool = Field(default=False)
    ems_endpoint: Optional[str] = None


class TestConfig(BaseModel):
    name: str
    enabled: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)


class GlobalConfig(BaseModel):
    server_type: ServerType
    mode: str = Field(default="auto", pattern="^(auto|interactive)$")
    detector_mode: DetectorMode = Field(default=DetectorMode.REAL)
    tests: List[TestConfig]
    output: OutputConfig = Field(default_factory=OutputConfig)
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_config_schemas.py -v
```

Expected: 5 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/config/ tests/
git commit -m "feat(config): add Pydantic schemas for configuration

- Define DetectorMode, ServerType enums
- Add TestConfig, OutputConfig, GlobalConfig models
- Add comprehensive unit tests

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 2: 配置系统 - 配置加载器

**Files:**
- Create: `src/config/loader.py`
- Create: `config/global.yaml`
- Create: `config/server_types/generic.yaml`
- Test: `tests/test_config_loader.py`

- [ ] **Step 1: 编写配置加载器测试**

Create `tests/test_config_loader.py`:
```python
import pytest
import tempfile
import os
from pathlib import Path
from src.config.loader import ConfigLoader
from src.config.schemas import ServerType, DetectorMode


class TestConfigLoader:
    def test_load_valid_global_config(self):
        yaml_content = """
server_type: generic
mode: auto
detector_mode: mock
tests:
  - name: cpu_test
    enabled: true
    params:
      duration: 300
output:
  formats: [json, html]
  upload_to_ems: false
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            loader = ConfigLoader()
            config = loader.load_global_config(config_path)
            assert config.server_type == ServerType.GENERIC
            assert config.mode == "auto"
            assert config.detector_mode == DetectorMode.MOCK
            assert len(config.tests) == 1
            assert config.tests[0].name == "cpu_test"
        finally:
            os.unlink(config_path)

    def test_load_nonexistent_file_raises_error(self):
        loader = ConfigLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_global_config("/nonexistent/path.yaml")
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_config_loader.py -v
```

Expected: ImportError - ConfigLoader not found

- [ ] **Step 3: 实现配置加载器**

Create `src/config/loader.py`:
```python
import yaml
from pathlib import Path
from typing import Union

from .schemas import GlobalConfig


class ConfigLoader:
    """Load and parse YAML configuration files."""

    def load_global_config(self, path: Union[str, Path]) -> GlobalConfig:
        """Load global configuration from YAML file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        return GlobalConfig(**data)

    def load_server_type_config(self, server_type: str, config_dir: Union[str, Path]) -> GlobalConfig:
        """Load configuration for a specific server type."""
        config_dir = Path(config_dir)
        config_path = config_dir / f"{server_type}.yaml"
        return self.load_global_config(config_path)
```

- [ ] **Step 4: 创建示例配置文件**

Create `config/global.yaml`:
```yaml
server_type: generic
mode: auto
detector_mode: mock
tests:
  - name: cpu_test
    enabled: true
    params:
      stress_duration: 300
      threads: auto

  - name: memory_test
    enabled: true
    params:
      capacity_check: true
      ecc_check: true
      stress_duration: 300

  - name: storage_test
    enabled: true
    params:
      test_nvme: true
      test_sata: true
      performance_test: true

  - name: network_test
    enabled: true
    params:
      test_ports: auto
      throughput_test: true

output:
  formats: [json, html, csv]
  upload_to_ems: true
  ems_endpoint: "http://localhost:8080/api/v1/results"
```

Create `config/server_types/generic.yaml`:
```yaml
server_type: generic
mode: auto
detector_mode: real
tests:
  - name: cpu_test
    enabled: true
    params:
      stress_duration: 300
      threads: auto

  - name: memory_test
    enabled: true
    params:
      capacity_check: true
      ecc_check: true
      stress_duration: 300

  - name: storage_test
    enabled: true
    params:
      test_nvme: true
      test_sata: true
      performance_test: false

  - name: network_test
    enabled: true
    params:
      test_ports: auto
      throughput_test: false

output:
  formats: [json]
  upload_to_ems: false
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_config_loader.py -v
```

Expected: 2 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/config/loader.py config/ tests/test_config_loader.py
git commit -m "feat(config): add YAML config loader with sample configs

- Implement ConfigLoader with load_global_config method
- Add global.yaml with full test suite configuration
- Add generic.yaml server type config
- Add unit tests for config loading

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 3: 检测器基类 - 抽象基类与模式切换

**Files:**
- Create: `src/detectors/base.py`
- Test: `tests/test_detectors/test_base.py`

- [ ] **Step 1: 编写检测器基类测试**

```bash
mkdir -p tests/test_detectors
```

Create `tests/test_detectors/test_base.py`:
```python
import pytest
from abc import ABC
from src.detectors.base import BaseDetector, DetectorMode


class TestDetectorMode:
    def test_mock_mode_value(self):
        assert DetectorMode.MOCK.value == "mock"

    def test_real_mode_value(self):
        assert DetectorMode.REAL.value == "real"


class ConcreteDetector(BaseDetector):
    """Concrete implementation for testing."""

    def detect_real(self) -> dict:
        return {"mode": "real", "data": "real_hardware_info"}

    def detect_mock(self) -> dict:
        return {"mode": "mock", "data": "simulated_info"}


class TestBaseDetector:
    def test_default_mode_is_real(self):
        detector = ConcreteDetector()
        assert detector.mode == DetectorMode.REAL

    def test_mock_mode_can_be_set(self):
        detector = ConcreteDetector(mode=DetectorMode.MOCK)
        assert detector.mode == DetectorMode.MOCK

    def test_detect_routes_to_real(self):
        detector = ConcreteDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert result["mode"] == "real"

    def test_detect_routes_to_mock(self):
        detector = ConcreteDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert result["mode"] == "mock"

    def test_is_abstract(self):
        assert issubclass(BaseDetector, ABC)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_base.py -v
```

Expected: ImportError - base module not found

- [ ] **Step 3: 实现检测器基类**

Create `src/detectors/__init__.py`:
```python
from .base import BaseDetector, DetectorMode

__all__ = ["BaseDetector", "DetectorMode"]
```

Create `src/detectors/base.py`:
```python
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
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_base.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/detectors/ tests/test_detectors/
git commit -m "feat(detectors): add BaseDetector with mock/real mode switching

- Abstract base class for all hardware detectors
- DetectorMode enum for mode control
- Unified detect() method routes to appropriate implementation
- Supports both testing (mock) and production (real) environments

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 4: CPU 检测器实现

**Files:**
- Create: `src/detectors/cpu.py`
- Test: `tests/test_detectors/test_cpu.py`

- [ ] **Step 1: 编写 CPU 检测器测试**

Create `tests/test_detectors/test_cpu.py`:
```python
import pytest
from src.detectors.cpu import CPUDetector
from src.detectors.base import DetectorMode


class TestCPUDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = CPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "model" in result
        assert "cores" in result
        assert "threads" in result
        assert "frequency_ghz" in result
        assert "architecture" in result

    def test_mock_cores_is_positive(self):
        detector = CPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["cores"], int)
        assert result["cores"] > 0

    def test_mock_threads_is_positive(self):
        detector = CPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["threads"], int)
        assert result["threads"] > 0

    def test_mock_frequency_is_reasonable(self):
        detector = CPUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["frequency_ghz"], (int, float))
        assert 1.0 <= result["frequency_ghz"] <= 5.0


class TestCPUDetectorReal:
    def test_real_returns_dict(self):
        detector = CPUDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_cpu.py -v
```

Expected: ImportError - cpu module not found

- [ ] **Step 3: 实现 CPU 检测器**

Update `src/detectors/__init__.py`:
```python
from .base import BaseDetector, DetectorMode
from .cpu import CPUDetector

__all__ = ["BaseDetector", "DetectorMode", "CPUDetector"]
```

Create `src/detectors/cpu.py`:
```python
import platform
import psutil
from typing import Dict, Any

from .base import BaseDetector, DetectorMode


class CPUDetector(BaseDetector):
    """Detect CPU information - model, cores, frequency, architecture."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect real CPU information using psutil and platform."""
        cpu_freq = psutil.cpu_freq()
        cpu_count = psutil.cpu_count(logical=False) or 1
        cpu_count_logical = psutil.cpu_count(logical=True) or cpu_count

        return {
            "model": platform.processor() or "Unknown",
            "brand": self._get_cpu_brand(),
            "cores": cpu_count,
            "threads": cpu_count_logical,
            "frequency_ghz": round(cpu_freq.current / 1000, 2) if cpu_freq else 0.0,
            "frequency_max_ghz": round(cpu_freq.max / 1000, 2) if cpu_freq and cpu_freq.max else 0.0,
            "architecture": platform.machine(),
            "byteorder": sys.byteorder if 'sys' in dir() else "unknown",
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated CPU data for testing."""
        return {
            "model": "Intel Xeon Gold 6448Y",
            "brand": "Intel",
            "cores": 32,
            "threads": 64,
            "frequency_ghz": 2.1,
            "frequency_max_ghz": 4.1,
            "architecture": "x86_64",
            "byteorder": "little",
        }

    def _get_cpu_brand(self) -> str:
        """Extract CPU brand from processor string."""
        processor = platform.processor().lower()
        if "intel" in processor:
            return "Intel"
        elif "amd" in processor:
            return "AMD"
        elif "arm" in processor:
            return "ARM"
        else:
            return "Unknown"
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_cpu.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/detectors/ tests/test_detectors/
git commit -m "feat(detectors): add CPUDetector with mock/real implementations

- Detect real CPU info using psutil and platform
- Mock mode returns realistic Xeon Gold data
- Returns model, cores, threads, frequency, architecture

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 5: 内存检测器实现

**Files:**
- Create: `src/detectors/memory.py`
- Test: `tests/test_detectors/test_memory.py`

- [ ] **Step 1: 编写内存检测器测试**

Create `tests/test_detectors/test_memory.py`:
```python
import pytest
from src.detectors.memory import MemoryDetector
from src.detectors.base import DetectorMode


class TestMemoryDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = MemoryDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "total_gb" in result
        assert "available_gb" in result
        assert "percent_used" in result
        assert "type" in result

    def test_mock_total_is_positive(self):
        detector = MemoryDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["total_gb"], (int, float))
        assert result["total_gb"] > 0

    def test_mock_available_less_than_total(self):
        detector = MemoryDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert result["available_gb"] <= result["total_gb"]

    def test_mock_percent_in_range(self):
        detector = MemoryDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert 0 <= result["percent_used"] <= 100
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_memory.py -v
```

Expected: ImportError - memory module not found

- [ ] **Step 3: 实现内存检测器**

Update `src/detectors/__init__.py`:
```python
from .base import BaseDetector, DetectorMode
from .cpu import CPUDetector
from .memory import MemoryDetector

__all__ = ["BaseDetector", "DetectorMode", "CPUDetector", "MemoryDetector"]
```

Create `src/detectors/memory.py`:
```python
import psutil
from typing import Dict, Any

from .base import BaseDetector, DetectorMode


class MemoryDetector(BaseDetector):
    """Detect memory information - total, available, type, ECC status."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect real memory information using psutil."""
        mem = psutil.virtual_memory()

        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "percent_used": mem.percent,
            "type": self._detect_memory_type(),
            "ecc": None,  # Would need dmidecode or similar for ECC detection
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated memory data for testing."""
        return {
            "total_gb": 512.0,
            "available_gb": 480.5,
            "used_gb": 31.5,
            "percent_used": 6.2,
            "type": "DDR4",
            "ecc": True,
            "speed_mhz": 3200,
            "slots_total": 16,
            "slots_used": 16,
        }

    def _detect_memory_type(self) -> str:
        """Attempt to detect memory type (DDR4/DDR5 etc)."""
        # Real implementation would use dmidecode or similar
        return "Unknown"
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_memory.py -v
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/detectors/ tests/test_detectors/
git commit -m "feat(detectors): add MemoryDetector with mock/real implementations

- Detect real memory using psutil
- Mock mode returns 512GB DDR4 ECC configuration
- Returns total, available, used, percent, type, ECC status

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 6: 核心状态管理

**Files:**
- Create: `src/core/state.py`
- Test: `tests/test_core/test_state.py`

- [ ] **Step 1: 编写状态管理测试**

```bash
mkdir -p tests/test_core
```

Create `tests/test_core/test_state.py`:
```python
import pytest
from datetime import datetime
from src.core.state import TestStatus, TestResult, TestReport


class TestTestStatus:
    def test_status_values(self):
        assert TestStatus.PASSED.value == "passed"
        assert TestStatus.FAILED.value == "failed"
        assert TestStatus.SKIPPED.value == "skipped"
        assert TestStatus.ERROR.value == "error"
        assert TestStatus.RUNNING.value == "running"


class TestTestResult:
    def test_result_creation(self):
        result = TestResult(
            name="cpu_test",
            status=TestStatus.PASSED,
            duration_ms=1500,
            message="CPU test completed successfully"
        )
        assert result.name == "cpu_test"
        assert result.status == TestStatus.PASSED
        assert result.duration_ms == 1500

    def test_result_defaults(self):
        result = TestResult(name="memory_test", status=TestStatus.FAILED)
        assert result.message == ""
        assert result.details == {}
        assert result.raw_output == ""


class TestTestReport:
    def test_report_creation(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        assert report.server_sn == "SN123456"
        assert report.server_model == "Dell R750"
        assert report.results == []
        assert report.summary["total"] == 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_core/test_state.py -v
```

Expected: ImportError - state module not found

- [ ] **Step 3: 实现状态管理**

Create `src/core/__init__.py`:
```python
from .state import TestStatus, TestResult, TestReport

__all__ = ["TestStatus", "TestResult", "TestReport"]
```

Create `src/core/state.py`:
```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


class TestStatus(str, Enum):
    """Status of a test execution."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    RUNNING = "running"


@dataclass
class TestResult:
    """Result of a single test execution."""
    name: str
    status: TestStatus
    duration_ms: int = 0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    raw_output: str = ""


@dataclass
class TestReport:
    """Complete test report for a server."""
    server_sn: str
    server_model: str
    server_type: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    results: List[TestResult] = field(default_factory=list)

    @property
    def summary(self) -> Dict[str, int]:
        """Generate summary statistics."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)
        errors = sum(1 for r in self.results if r.status == TestStatus.ERROR)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
        }

    @property
    def duration_seconds(self) -> float:
        """Calculate total test duration."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

    @property
    def overall_status(self) -> TestStatus:
        """Determine overall test status."""
        if not self.results:
            return TestStatus.SKIPPED

        if any(r.status == TestStatus.ERROR for r in self.results):
            return TestStatus.ERROR
        if any(r.status == TestStatus.FAILED for r in self.results):
            return TestStatus.FAILED
        if all(r.status == TestStatus.PASSED for r in self.results):
            return TestStatus.PASSED

        return TestStatus.SKIPPED
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_core/test_state.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/core/ tests/test_core/
git commit -m "feat(core): add test state management

- TestStatus enum: PASSED, FAILED, SKIPPED, ERROR, RUNNING
- TestResult dataclass for individual test results
- TestReport dataclass with summary and overall_status
- Calculates duration and statistics automatically

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 7: JSON 报告生成器

**Files:**
- Create: `src/reporters/base.py`
- Create: `src/reporters/json_reporter.py`
- Test: `tests/test_reporters/test_json_reporter.py`

- [ ] **Step 1: 编写 JSON 报告生成器测试**

```bash
mkdir -p tests/test_reporters
```

Create `tests/test_reporters/test_json_reporter.py`:
```python
import pytest
import json
import tempfile
import os
from datetime import datetime
from pathlib import Path

from src.core.state import TestStatus, TestResult, TestReport
from src.reporters.json_reporter import JSONReporter


class TestJSONReporter:
    def test_generate_returns_valid_json(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        reporter = JSONReporter()
        result = reporter.generate(report)

        # Should be valid JSON
        data = json.loads(result)
        assert "server_sn" in data
        assert data["server_sn"] == "SN123456"

    def test_generate_includes_results(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        report.results.append(TestResult(
            name="cpu_test",
            status=TestStatus.PASSED,
            duration_ms=1000
        ))

        reporter = JSONReporter()
        result = reporter.generate(report)
        data = json.loads(result)

        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "cpu_test"
        assert data["results"][0]["status"] == "passed"

    def test_save_to_file(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            reporter = JSONReporter()
            reporter.save(report, output_path)

            assert output_path.exists()
            with open(output_path) as f:
                data = json.load(f)
            assert data["server_sn"] == "SN123456"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_reporters/test_json_reporter.py -v
```

Expected: ImportError - reporters module not found

- [ ] **Step 3: 实现报告生成器基类和 JSON 报告生成器**

Create `src/reporters/__init__.py`:
```python
from .base import BaseReporter
from .json_reporter import JSONReporter

__all__ = ["BaseReporter", "JSONReporter"]
```

Create `src/reporters/base.py`:
```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from src.core.state import TestReport


class BaseReporter(ABC):
    """Abstract base class for report generators."""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Return the format name (e.g., 'json', 'html', 'csv')."""
        pass

    @abstractmethod
    def generate(self, report: TestReport) -> str:
        """Generate report content as string.

        Args:
            report: The test report to generate from.

        Returns:
            Report content as string.
        """
        pass

    def save(self, report: TestReport, output_path: Union[str, Path]) -> Path:
        """Generate and save report to file.

        Args:
            report: The test report to save.
            output_path: Path to save the report to.

        Returns:
            Path to the saved file.
        """
        output_path = Path(output_path)
        content = self.generate(report)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path
```

Create `src/reporters/json_reporter.py`:
```python
import json
from datetime import datetime
from typing import Any

from .base import BaseReporter
from src.core.state import TestReport, TestResult


class JSONReporter(BaseReporter):
    """Generate JSON format test reports."""

    @property
    def format_name(self) -> str:
        return "json"

    def generate(self, report: TestReport) -> str:
        """Generate JSON report from test results."""
        data = self._to_dict(report)
        return json.dumps(data, indent=2, ensure_ascii=False, default=self._json_serializer)

    def _to_dict(self, report: TestReport) -> dict:
        """Convert TestReport to dictionary."""
        return {
            "metadata": {
                "server_sn": report.server_sn,
                "server_model": report.server_model,
                "server_type": report.server_type,
                "start_time": report.start_time.isoformat(),
                "end_time": report.end_time.isoformat() if report.end_time else None,
                "duration_seconds": report.duration_seconds,
            },
            "summary": report.summary,
            "overall_status": report.overall_status.value,
            "results": [self._result_to_dict(r) for r in report.results],
        }

    def _result_to_dict(self, result: TestResult) -> dict:
        """Convert TestResult to dictionary."""
        return {
            "name": result.name,
            "status": result.status.value,
            "duration_ms": result.duration_ms,
            "message": result.message,
            "details": result.details,
            "raw_output": result.raw_output,
        }

    def _json_serializer(self, obj: Any) -> str:
        """Handle datetime serialization."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_reporters/test_json_reporter.py -v
```

Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/reporters/ tests/test_reporters/
git commit -m "feat(reporters): add JSON report generator

- BaseReporter abstract class with generate() and save() methods
- JSONReporter generates structured JSON with metadata, summary, results
- Handles datetime serialization
- Creates output directories automatically

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 8: CLI 主入口

**Files:**
- Create: `src/cli/app.py`
- Create: `src/main.py`
- Test: `tests/test_cli/test_app.py`

- [ ] **Step 1: 编写 CLI 测试**

```bash
mkdir -p tests/test_cli
```

Create `tests/test_cli/test_app.py`:
```python
import pytest
from click.testing import CliRunner
from src.cli.app import cli


class TestCLI:
    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Server Test System' in result.output

    def test_version_flag(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert 'version' in result.output.lower()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_cli/test_app.py -v
```

Expected: ImportError - cli module not found

- [ ] **Step 3: 实现 CLI 主入口**

Create `src/cli/__init__.py`:
```python
from .app import cli

__all__ = ["cli"]
```

Create `src/cli/app.py`:
```python
import click
from pathlib import Path

from src.config import ConfigLoader
from src.core.state import TestReport
from src.reporters import JSONReporter


@click.group()
@click.version_option(version="0.1.0")
@click.pass_context
def cli(ctx):
    """Server Test System - Hardware testing for production servers."""
    ctx.ensure_object(dict)


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to config file')
@click.option('--output', '-o', type=click.Path(), default='./reports', help='Output directory')
@click.option('--mock', is_flag=True, help='Use mock mode for testing')
def run(config, output, mock):
    """Run tests in automatic mode."""
    click.echo("Starting Server Test System...")

    # Load configuration
    loader = ConfigLoader()
    if config:
        cfg = loader.load_global_config(config)
    else:
        default_config = Path(__file__).parent.parent.parent / "config" / "global.yaml"
        cfg = loader.load_global_config(default_config)

    # Override with mock mode if specified
    if mock:
        from src.config.schemas import DetectorMode
        cfg.detector_mode = DetectorMode.MOCK
        click.echo("Running in MOCK mode (simulated hardware)")

    click.echo(f"Server type: {cfg.server_type.value}")
    click.echo(f"Mode: {cfg.mode}")
    click.echo(f"Tests to run: {len(cfg.tests)}")

    # TODO: Run actual tests (will be implemented in later tasks)
    # For now, create a minimal report
    report = TestReport(
        server_sn="UNKNOWN",
        server_model="Unknown Model",
        server_type=cfg.server_type.value
    )

    # Generate report
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    reporter = JSONReporter()
    report_file = output_path / "test_report.json"
    reporter.save(report, report_file)

    click.echo(f"\nReport saved to: {report_file}")
    click.echo("Test run completed.")


@cli.command()
def interactive():
    """Run tests in interactive wizard mode."""
    click.echo("Interactive mode - TODO: implement wizard")


if __name__ == '__main__':
    cli()
```

Create `src/main.py`:
```python
#!/usr/bin/env python3
"""Entry point for Server Test System."""

from src.cli.app import cli

if __name__ == '__main__':
    cli()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_cli/test_app.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: 验证 CLI 可运行**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m src.main --help
```

Expected: Shows help text with "Server Test System"

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m src.main run --mock
```

Expected: Shows startup message, config loaded, report saved

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/cli/ src/main.py tests/test_cli/
git commit -m "feat(cli): add command-line interface

- CLI with Click: --version, run, interactive commands
- run command: --config, --output, --mock options
- Loads config and generates JSON report
- Entry point at src/main.py

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 9: 依赖和项目配置

**Files:**
- Create: `requirements.txt`
- Create: `setup.py`
- Create: `README.md`

- [ ] **Step 1: 创建 requirements.txt**

Create `requirements.txt`:
```
# Core dependencies
pydantic>=2.0.0
pyyaml>=6.0
click>=8.0.0
rich>=13.0.0
psutil>=5.9.0
jinja2>=3.1.0

# Development dependencies
pytest>=7.0.0
pytest-cov>=4.0.0
black>=23.0.0
```

- [ ] **Step 2: 创建 setup.py**

Create `setup.py`:
```python
from setuptools import setup, find_packages

setup(
    name="server-test-system",
    version="0.1.0",
    description="Hardware testing system for production servers",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
        "click>=8.0.0",
        "rich>=13.0.0",
        "psutil>=5.9.0",
        "jinja2>=3.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
        ],
    },
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "server-test=main:cli",
        ],
    },
)
```

- [ ] **Step 3: 创建 README.md**

Create `README.md`:
```markdown
# Server Test System

Hardware testing system for production servers - supports generic, storage, compute, and AI server types.

## Features

- **4 Server Types**: Generic, Storage, Compute, AI Server
- **7 Hardware Detectors**: CPU, Memory, Storage, Network, GPU, BMC, PCIe
- **2 Test Modes**: Automatic (batch) and Interactive (wizard)
- **3 Report Formats**: JSON, HTML, CSV
- **Mock/Real Mode**: Test without hardware, deploy with real detection

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run in mock mode (no hardware required)
python -m src.main run --mock

# Run with specific config
python -m src.main run --config config/global.yaml

# Interactive wizard mode
python -m src.main interactive
```

## Project Structure

```
server-master/
├── src/
│   ├── config/      # Configuration management
│   ├── core/        # Test engine and state
│   ├── detectors/   # Hardware detectors
│   ├── reporters/   # Report generators
│   └── cli/         # Command-line interface
├── config/          # YAML configurations
├── tests/           # Unit tests
└── docs/            # Documentation
```

## Configuration

Edit `config/global.yaml` to customize:
- Server type
- Tests to run
- Output formats
- Mock/real mode

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src
```

## License

MIT
```

- [ ] **Step 4: 验证安装**

```bash
cd /Users/arthurzhang/dev/llm/server-master && pip install -r requirements.txt
```

Expected: Dependencies install successfully

- [ ] **Step 5: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add requirements.txt setup.py README.md
git commit -m "chore(project): add dependencies and project metadata

- requirements.txt with all runtime and dev dependencies
- setup.py for package installation
- README.md with quick start guide

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## 验收检查清单

| 验收项 | 验证命令 | 预期结果 |
|--------|----------|----------|
| 配置系统 | `pytest tests/test_config*.py -v` | 7 tests PASS |
| 检测器基类 | `pytest tests/test_detectors/test_base.py -v` | 6 tests PASS |
| CPU 检测器 | `pytest tests/test_detectors/test_cpu.py -v` | 5 tests PASS |
| 内存检测器 | `pytest tests/test_detectors/test_memory.py -v` | 4 tests PASS |
| 状态管理 | `pytest tests/test_core/test_state.py -v` | 5 tests PASS |
| JSON 报告 | `pytest tests/test_reporters/test_json_reporter.py -v` | 3 tests PASS |
| CLI | `pytest tests/test_cli/test_app.py -v` | 2 tests PASS |
| 完整测试 | `pytest` | 32 tests PASS |
| CLI 运行 | `python -m src.main run --mock` | 成功生成报告 |

---

*计划完成，准备执行*
