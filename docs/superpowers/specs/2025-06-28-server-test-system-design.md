# 服务器测试系统设计文档

## 文档信息
- **日期**: 2025-06-28
- **版本**: v1.0
- **状态**: 已批准

---

## 1. 概述

### 1.1 项目目标
开发一套通用的服务器测试系统，支持通用服务器、存储服务器、算力服务器、AI服务器的产线测试出货。

### 1.2 支持的服务器类型
| 类型 | 描述 | 特殊硬件 |
|------|------|----------|
| 通用服务器 | 标准机架/塔式服务器 | 标准配置 |
| 存储服务器 | 大容量存储服务器 | 多盘位、SAS卡、RAID卡 |
| 算力服务器 | 高性能计算服务器 | 多路CPU、高速网络 |
| AI服务器 | 人工智能训练/推理服务器 | GPU/国产AI加速卡 |

### 1.3 支持的硬件检测
- **CPU**: 型号、核心数、频率、压力测试
- **内存**: 容量、类型、ECC校验、压力测试
- **存储**: NVMe/SATA/SAS硬盘、RAID卡、读写性能
- **网络**: 网卡型号、端口数量、吞吐量测试
- **GPU/AI卡**: NVIDIA、AMD、海光、寒武纪、昇腾
- **BMC/IPMI**: 带外管理、传感器读取
- **PCIe**: 扩展槽检测、带宽验证

---

## 2. 系统架构

### 2.1 整体架构
```
┌─────────────────────────────────────────────────────────────┐
│                    Server Test System                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   Client    │  │   Server    │  │     EMS Adapter     │  │
│  │  (被测机)    │  │  (中央管理)  │  │   (Dummy/真实EMS)   │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘  │
│         │                │                                    │
│         └────────────────┘                                    │
│              API (HTTP/WebSocket)                             │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌─────────┐     ┌─────────┐     ┌─────────┐
        │  JSON   │     │  HTML   │     │   CSV   │
        │  Report │     │  Report │     │  Export │
        └─────────┘     └─────────┘     └─────────┘
```

### 2.2 运行模式
1. **单机独立模式**: 不依赖网络，测试完成后本地生成报告，支持上传EMS
2. **客户端-服务器模式**: 被测机连接中央测试服务器，集中管理
3. **混合模式**: 支持上述两种模式动态切换

---

## 3. 模块设计

### 3.1 模块职责

| 模块 | 路径 | 职责 |
|------|------|------|
| 配置管理 | `src/config/` | 服务器类型配置、全局配置、配置验证 |
| 核心引擎 | `src/core/` | 测试执行、任务调度、状态管理 |
| 硬件检测 | `src/detectors/` | 各硬件组件的检测逻辑 |
| 测试用例 | `src/tests/` | 具体测试实现（压力、性能、功能） |
| 报告生成 | `src/reporters/` | JSON/HTML/CSV报告生成 |
| 外部适配 | `src/adapters/` | EMS系统对接（Dummy + 真实接口） |
| 命令行界面 | `src/cli/` | 自动模式/向导模式界面 |
| 中央服务器 | `src/server/` | 可选的中央管理服务器 |

### 3.2 核心流程

**全自动模式流程:**
```
启动 → 加载配置 → 检测服务器类型 → 执行测试项 → 生成报告 → 上传EMS
```

**向导模式流程:**
```
启动 → 选择服务器类型 → 选择测试项 → 逐项执行 → 显示结果
     → 继续/重试/跳过 → 生成报告 → 上传EMS（可选）
```

---

## 4. 配置设计

### 4.1 配置文件结构
```yaml
# config/server_types/ai_server.yaml
server_type: ai_server
mode: auto  # auto | interactive

tests:
  - name: cpu_test
    enabled: true
    params:
      stress_duration: 300
      threads: auto  # auto = 核心数

  - name: memory_test
    enabled: true
    params:
      capacity_check: true
      ecc_check: true
      stress_duration: 300

  - name: gpu_test
    enabled: true
    params:
      detect_nvidia: true
      detect_amd: true
      detect_domestic: [海光, 寒武纪, 昇腾]
      memory_test: true

  - name: storage_test
    enabled: true
    params:
      test_nvme: true
      test_sas: true
      performance_test: true

  - name: network_test
    enabled: true
    params:
      test_ports: auto  # auto = 检测到的所有网口
      throughput_test: true

  - name: bmc_test
    enabled: true
    params:
      ipmi_check: true
      sensor_check: true

output:
  formats: [json, html, csv]
  upload_to_ems: true
  ems_endpoint: "http://ems-dummy:8080/api/v1/results"
```

### 4.2 服务器类型配置
- `generic.yaml` - 通用服务器
- `storage.yaml` - 存储服务器
- `compute.yaml` - 算力服务器
- `ai_server.yaml` - AI服务器

---

## 5. 报告格式

### 5.1 JSON报告
结构化数据，包含：
- 服务器基本信息（SN、型号、MAC等）
- 各测试项详细结果
- 通过/失败状态
- 测试时间戳
- 原始数据

### 5.2 HTML报告
可视化报告，包含：
- 测试概览仪表板
- 各组件详细结果
- 性能图表
- 通过/失败状态标识

### 5.3 CSV报告
表格格式，包含：
- 关键指标汇总
- 便于导入Excel/数据库

---

## 6. EMS对接

### 6.1 Dummy EMS
- 用于开发和测试阶段
- 模拟EMS接口接收测试结果
- 记录上传日志

### 6.2 真实EMS接口
- 预留接口待实现
- 配置文件中切换

---

## 7. 技术栈

- **语言**: Python 3.9+
- **依赖库**:
  - `psutil` - 系统信息采集
  - `pynvml` - NVIDIA GPU检测
  - `pyipmi` - IPMI/BMC通信
  - `pyyaml` - 配置解析
  - `jinja2` - HTML模板
  - `click` - 命令行界面
  - `fastapi` - 中央服务器API（可选）
  - `rich` - 终端UI美化

---

## 8. 项目结构

```
server-master/
├── src/
│   ├── __init__.py
│   ├── main.py                 # 程序入口
│   ├── config/                 # 配置管理
│   │   ├── __init__.py
│   │   ├── loader.py
│   │   └── schemas.py
│   ├── core/                   # 核心引擎
│   │   ├── __init__.py
│   │   ├── engine.py           # 测试引擎
│   │   ├── scheduler.py        # 任务调度
│   │   └── state.py            # 状态管理
│   ├── detectors/              # 硬件检测
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── cpu.py
│   │   ├── memory.py
│   │   ├── storage.py
│   │   ├── network.py
│   │   ├── gpu.py
│   │   ├── bmc.py
│   │   └── pcie.py
│   ├── tests/                  # 测试用例
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── cpu_test.py
│   │   ├── memory_test.py
│   │   ├── storage_test.py
│   │   ├── network_test.py
│   │   ├── gpu_test.py
│   │   ├── bmc_test.py
│   │   └── pcie_test.py
│   ├── reporters/              # 报告生成
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── json_reporter.py
│   │   ├── html_reporter.py
│   │   └── csv_reporter.py
│   ├── adapters/               # 外部适配
│   │   ├── __init__.py
│   │   ├── ems_dummy.py        # Dummy EMS
│   │   └── ems_adapter.py      # 真实EMS接口（待实现）
│   └── cli/                    # 命令行界面
│       ├── __init__.py
│       ├── app.py
│       ├── interactive.py      # 向导模式
│       └── auto.py             # 自动模式
├── config/
│   ├── server_types/           # 服务器类型配置
│   │   ├── generic.yaml
│   │   ├── storage.yaml
│   │   ├── compute.yaml
│   │   └── ai_server.yaml
│   └── global.yaml             # 全局配置
├── templates/                  # HTML报告模板
├── tests/                      # 单元测试
├── docs/                       # 文档
├── requirements.txt
├── setup.py
└── README.md
```

---

## 9. 验收标准

- [ ] 支持4种服务器类型的配置
- [ ] 支持7类硬件检测
- [ ] 支持全自动和向导两种模式
- [ ] 生成JSON、HTML、CSV三种格式报告
- [ ] Dummy EMS可接收测试结果
- [ ] 代码有单元测试覆盖
- [ ] 支持Linux（CentOS/Ubuntu）和Windows
