# 服务器测试系统实现设计文档

## 文档信息
- **日期**: 2025-06-28
- **版本**: v1.0
- **状态**: 已批准
- **目标**: 完整实现服务器测试系统，支持 mock/real 模式切换

---

## 1. 核心架构设计

### 1.1 模拟/真实切换机制

关键设计，确保测试和发布代码完全一致：

```python
# src/detectors/base.py
from abc import ABC, abstractmethod
from enum import Enum

class DetectorMode(Enum):
    MOCK = "mock"      # 测试阶段 - 返回模拟数据
    REAL = "real"      # 发布阶段 - 检测真实硬件

class BaseDetector(ABC):
    def __init__(self, mode: DetectorMode = DetectorMode.REAL):
        self.mode = mode

    @abstractmethod
    def detect_real(self) -> dict:
        """真实硬件检测实现"""
        pass

    @abstractmethod
    def detect_mock(self) -> dict:
        """模拟数据返回（用于测试）"""
        pass

    def detect(self) -> dict:
        """统一入口，根据配置自动切换"""
        if self.mode == DetectorMode.MOCK:
            return self.detect_mock()
        return self.detect_real()
```

### 1.2 配置控制切换

```yaml
# config/global.yaml
system:
  detector_mode: mock    # 切换这行：mock 或 real

  # 其他配置...
```

---

## 2. 模块划分与目录结构

```
server-master/
├── src/
│   ├── __init__.py
│   ├── main.py                    # 程序入口
│   ├── config/                    # 配置管理
│   │   ├── __init__.py
│   │   ├── loader.py              # 配置文件加载
│   │   ├── schemas.py             # 配置数据模型(Pydantic)
│   │   └── validator.py           # 配置验证
│   ├── core/                      # 核心引擎
│   │   ├── __init__.py
│   │   ├── engine.py              # 测试引擎主控
│   │   ├── scheduler.py           # 任务调度器
│   │   ├── state.py               # 测试状态管理
│   │   └── events.py              # 事件系统（进度通知）
│   ├── detectors/                 # 硬件检测（模拟/真实双实现）
│   │   ├── __init__.py
│   │   ├── base.py                # 抽象基类
│   │   ├── cpu.py                 # CPU检测器
│   │   ├── memory.py              # 内存检测器
│   │   ├── storage.py             # 存储检测器
│   │   ├── network.py             # 网络检测器
│   │   ├── gpu.py                 # GPU检测器
│   │   ├── bmc.py                 # BMC/IPMI检测器
│   │   └── pcie.py                # PCIe检测器
│   ├── tests/                     # 测试用例（压力/性能/功能）
│   │   ├── __init__.py
│   │   ├── base.py                # 测试基类
│   │   ├── cpu_test.py
│   │   ├── memory_test.py
│   │   ├── storage_test.py
│   │   ├── network_test.py
│   │   ├── gpu_test.py
│   │   ├── bmc_test.py
│   │   └── pcie_test.py
│   ├── reporters/                 # 报告生成
│   │   ├── __init__.py
│   │   ├── base.py                # 报告基类
│   │   ├── json_reporter.py
│   │   ├── html_reporter.py
│   │   └── csv_reporter.py
│   ├── adapters/                  # 外部系统适配
│   │   ├── __init__.py
│   │   ├── base.py                # 适配器基类
│   │   ├── ems_dummy.py           # Dummy EMS（开发测试）
│   │   └── ems_adapter.py         # 真实EMS接口（预留）
│   └── cli/                       # 命令行界面
│       ├── __init__.py
│       ├── app.py                 # CLI主入口
│       ├── interactive.py         # 向导模式
│       └── auto.py                # 自动模式
├── config/                        # 配置文件
│   ├── server_types/
│   │   ├── generic.yaml
│   │   ├── storage.yaml
│   │   ├── compute.yaml
│   │   └── ai_server.yaml
│   └── global.yaml
├── templates/                     # HTML报告模板
│   └── report_template.html
├── tests/                         # 单元测试
│   ├── __init__.py
│   ├── test_detectors/
│   ├── test_core/
│   └── test_reporters/
├── docs/                          # 文档
├── requirements.txt
├── setup.py
├── README.md
└── .gitignore
```

---

## 3. 数据流设计

```
┌─────────────┐    加载配置    ┌─────────────┐
│   main.py   │ ─────────────▶ │   Config    │
│   (入口)     │                │   Loader    │
└──────┬──────┘                └──────┬──────┘
       │                              │
       │ 实例化引擎                     │ 解析server_type
       ▼                              ▼
┌─────────────┐    获取测试项列表    ┌─────────────┐
│ TestEngine  │ ◀──────────────── │   Config    │
│  (核心引擎)  │                   │  (配置对象)  │
└──────┬──────┘                   └─────────────┘
       │
       │ 遍历测试项
       ▼
┌─────────────┐    检测硬件      ┌─────────────┐
│  Scheduler  │ ──────────────▶ │  Detectors  │
│  (调度器)    │ ◀────────────── │  (检测器)    │
└──────┬──────┘    返回结果      └─────────────┘
       │
       │ 执行测试
       ▼
┌─────────────┐    生成报告      ┌─────────────┐
│ TestCases   │ ──────────────▶ │  Reporters  │
│  (测试用例)  │                │  (报告生成器) │
└─────────────┘                └──────┬──────┘
                                      │
                                      ▼
                               ┌─────────────┐
                               │  输出到文件   │
                               │ + 上传EMS   │
                               └─────────────┘
```

### 3.1 核心数据模型

```python
# 测试结果统一结构
class TestResult:
    name: str              # 测试项名称，如 "cpu_test"
    status: Status         # PASSED / FAILED / SKIPPED / ERROR
    duration_ms: int       # 执行耗时
    message: str           # 状态说明
    details: dict          # 详细数据（各检测器返回的结构化数据）
    raw_output: str        # 原始命令输出（如有）

# 完整报告结构
class TestReport:
    metadata: ReportMeta   # SN、型号、测试时间、服务器类型等
    summary: Summary       # 总项数、通过/失败/跳过数
    results: List[TestResult]  # 各测试项结果
```

### 3.2 报告格式内容

| 格式 | 内容 | 用途 |
|------|------|------|
| **JSON** | 完整结构化数据，含所有原始字段 | 系统集成、自动化处理 |
| **HTML** | 可视化仪表板，含状态图标、简要数据 | 人工查看、产线展示 |
| **CSV** | 关键指标汇总表格 | 导入Excel/数据库分析 |

---

## 4. 技术细节

### 4.1 模拟数据生成策略

```python
# 每个检测器的 mock 数据基于真实硬件规格范围
class CPUDetector(BaseDetector):
    def detect_mock(self) -> dict:
        # 基于常见服务器CPU规格的模拟数据
        return {
            "model": "Intel Xeon Gold 6448Y",
            "cores": 32,
            "threads": 64,
            "frequency_ghz": 2.1,
            "cache_mb": 60,
            "architecture": "x86_64"
        }
```

### 4.2 依赖库选择

| 用途 | 库 | 说明 |
|------|-----|------|
| 系统信息 | `psutil` | CPU、内存、基础信息 |
| GPU | `pynvml` | NVIDIA GPU检测 |
| IPMI | `pyipmi` / `ipmitool` 包装 | BMC通信 |
| 配置 | `pydantic` | 配置验证 |
| CLI | `click` + `rich` | 命令行 + 美观输出 |
| 报告 | `jinja2` | HTML模板 |

### 4.3 并发策略

- 无依赖的检测并行执行（如 CPU + 内存可同时进行）
- 存储检测串行（避免 IO 冲突）
- 网络测试独立（可能占用端口）

---

## 5. 验收标准

| 验收项 | 实现方式 | 验证方法 |
|--------|----------|----------|
| 4种服务器类型配置 | config/server_types/*.yaml | 加载各配置无错误 |
| 7类硬件检测 | detectors/*.py + mock/real 双实现 | mock模式输出有效数据 |
| 全自动/向导模式 | cli/auto.py + cli/interactive.py | 命令行可正常启动 |
| 3种格式报告 | reporters/*.py | 生成文件内容正确 |
| Dummy EMS | adapters/ems_dummy.py | 可接收并记录测试结果 |
| 单元测试 | tests/ 目录 | pytest 通过 |
| 跨平台 | 兼容代码 + 平台检测 | Linux/Windows 均可运行 |

---

## 6. 实现阶段划分

1. **基础设施**: 项目结构、配置系统、抽象基类
2. **检测器实现**: 7类硬件检测器（mock + real）
3. **核心引擎**: 调度器、状态管理、事件系统
4. **测试用例**: 各类硬件的压力/功能测试
5. **报告生成**: JSON/HTML/CSV 三种格式
6. **CLI界面**: 自动模式 + 向导模式
7. **EMS对接**: Dummy + 预留真实接口
8. **集成测试**: 端到端验证

---

*设计文档完成，等待进入实现阶段*
