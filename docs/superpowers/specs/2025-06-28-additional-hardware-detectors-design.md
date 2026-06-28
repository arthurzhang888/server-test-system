# 额外硬件检测器设计文档

## 文档信息
- **日期**: 2025-06-28
- **版本**: v1.0
- **状态**: 已批准
- **目标**: 添加 RAID、PSU、温度/风扇传感器检测器

---

## 1. 概述

### 1.1 背景
服务器测试系统已实现对 CPU、内存、存储、网络、GPU、BMC、PCIe 的检测。本设计补充 RAID 控制器、PSU 电源、温度/风扇传感器的检测能力。

### 1.2 新增检测器

| 检测器 | 检测内容 | 主要接口 |
|--------|----------|----------|
| RAIDDetector | RAID 控制器、阵列配置、物理磁盘 | lspci + StorCLI/arcconf/ssacli |
| PSUDetector | 电源状态、电压、功率、冗余 | IPMI + lm-sensors |
| SensorDetector | 温度、风扇转速、阈值告警 | IPMI 传感器接口 |

---

## 2. RAID 卡检测器设计

### 2.1 分层检测架构

```
┌─────────────────────────────────────────┐
│           RAIDDetector                  │
├─────────────────────────────────────────┤
│  Layer 1: lspci 检测                    │
│  └── 识别 RAID 控制器型号、厂商          │
│  └── 输出: 控制器存在、PCI 地址          │
├─────────────────────────────────────────┤
│  Layer 2: 详细配置（如有工具）           │
│  ├── StorCLI (LSI/Broadcom)            │
│  ├── arcconf (Adaptec)                 │
│  └── ssacli (HP/HPE)                   │
│  └── 输出: 完整阵列信息                  │
└─────────────────────────────────────────┘
```

### 2.2 支持的控制器

| 厂商 | 工具 | 常见型号 | 检测命令 |
|------|------|----------|----------|
| LSI/Broadcom | storcli64 | MegaRAID 9361/9380/95xx/96xx | `storcli64 /c0 show` |
| Adaptec | arcconf | SmartRAID 3154/3162 | `arcconf getconfig 1` |
| HP/HPE | ssacli | Smart Array P408i/P816i | `ssacli ctrl all show config` |

### 2.3 输出数据结构

```python
{
    "controllers": [
        {
            "index": 0,
            "model": "LSI MegaRAID 9361-8i",
            "vendor": "LSI/Broadcom",
            "firmware": "4.680.00-8188",
            "driver": "megaraid_sas",
            "pci_slot": "0000:05:00.0",
            "detected_by": "lspci",  # or "storcli"
            "tool_available": True,
            "arrays": [
                {
                    "id": 0,
                    "raid_level": "RAID5",
                    "size_gb": 5760,
                    "status": "Optimal",
                    "drives": 3,
                    "cache_policy": "WriteBack"
                }
            ],
            "physical_drives": [
                {
                    "enclosure": 0,
                    "slot": 0,
                    "model": "ST2000NM0008",
                    "size_gb": 1920,
                    "status": "Online",
                    "health": "Good",
                    "temperature_c": 35
                }
            ],
            "battery": {
                "present": True,
                "status": "Optimal",
                "charge_percent": 98,
                "temperature_c": 28
            }
        }
    ],
    "controller_count": 1
}
```

### 2.4 Mock 数据

```python
{
    "controllers": [
        {
            "index": 0,
            "model": "LSI MegaRAID 9361-8i",
            "vendor": "LSI/Broadcom",
            "firmware": "4.680.00-8188",
            "driver": "megaraid_sas",
            "pci_slot": "0000:05:00.0",
            "detected_by": "storcli",
            "tool_available": True,
            "arrays": [
                {
                    "id": 0,
                    "raid_level": "RAID5",
                    "size_gb": 5760,
                    "status": "Optimal",
                    "drives": 3
                }
            ],
            "physical_drives": [
                {
                    "enclosure": 0,
                    "slot": 0,
                    "model": "ST2000NM0008",
                    "size_gb": 1920,
                    "status": "Online",
                    "health": "Good"
                },
                {
                    "enclosure": 0,
                    "slot": 1,
                    "model": "ST2000NM0008",
                    "size_gb": 1920,
                    "status": "Online",
                    "health": "Good"
                },
                {
                    "enclosure": 0,
                    "slot": 2,
                    "model": "ST2000NM0008",
                    "size_gb": 1920,
                    "status": "Online",
                    "health": "Good"
                }
            ],
            "battery": {
                "present": True,
                "status": "Optimal",
                "charge_percent": 98
            }
        }
    ],
    "controller_count": 1
}
```

---

## 3. PSU 电源检测器设计

### 3.1 检测方式

| 方式 | 接口 | 优先级 |
|------|------|--------|
| IPMI/Redfish | `ipmitool sdr type "Power Supply"` | 高 |
| lm-sensors | `/sys/class/hwmon/` | 中 |
| D-Bus/UPower | 桌面环境 | 低 |

### 3.2 输出数据结构

```python
{
    "psu_count": 2,
    "redundant": True,
    "psus": [
        {
            "id": 1,
            "present": True,
            "status": "OK",  # OK, Failed, Not Present
            "input_voltage": 220,
            "input_voltage_status": "ok",
            "output_watts": 450,
            "temperature_c": 35,
            "fan_rpm": 3200,
            "model": "DPS-750AB-1",
            "serial": "ABC123456",
            "part_number": "865408-B21"
        },
        {
            "id": 2,
            "present": True,
            "status": "OK",
            "input_voltage": 220,
            "input_voltage_status": "ok",
            "output_watts": 420,
            "temperature_c": 33,
            "fan_rpm": 3100,
            "model": "DPS-750AB-1",
            "serial": "ABC123457",
            "part_number": "865408-B21"
        }
    ],
    "total_capacity_watts": 1500,
    "total_output_watts": 870,
    "load_percent": 58
}
```

### 3.3 Mock 数据

```python
{
    "psu_count": 2,
    "redundant": True,
    "psus": [
        {
            "id": 1,
            "present": True,
            "status": "OK",
            "input_voltage": 220,
            "input_voltage_status": "ok",
            "output_watts": 450,
            "temperature_c": 35,
            "fan_rpm": 3200,
            "model": "DPS-750AB-1",
            "serial": "ABC123456"
        },
        {
            "id": 2,
            "present": True,
            "status": "OK",
            "input_voltage": 220,
            "input_voltage_status": "ok",
            "output_watts": 420,
            "temperature_c": 33,
            "fan_rpm": 3100,
            "model": "DPS-750AB-1",
            "serial": "ABC123457"
        }
    ],
    "total_capacity_watts": 1500,
    "total_output_watts": 870,
    "load_percent": 58
}
```

---

## 4. 温度/风扇传感器检测器设计

### 4.1 检测方式

通过 IPMI 传感器数据记录（SDR）获取：

| 传感器类型 | IPMI 类型标识 | 示例名称 |
|------------|---------------|----------|
| CPU 温度 | Processor/CPU | "CPU0 Temp", "CPU1 Temp" |
| 系统温度 | Systemboard | "Systemboard", "Inlet Temp" |
| PCH 温度 | PCH | "PCH Temp" |
| 硬盘温度 | Drive Slot | "HDD Temp" |
| 风扇转速 | Fan | "Fan 1", "Fan 2" |
| 电源温度 | Power Supply | "PSU1 Temp" |

### 4.2 输出数据结构

```python
{
    "sensors": {
        "temperatures": [
            {
                "name": "CPU0 Temp",
                "value": 45,
                "unit": "C",
                "status": "ok",  # ok, warning, critical
                "threshold_lower_non_critical": 5,
                "threshold_upper_non_critical": 80,
                "threshold_upper_critical": 85
            },
            {
                "name": "CPU1 Temp",
                "value": 43,
                "unit": "C",
                "status": "ok",
                "threshold_upper_non_critical": 80,
                "threshold_upper_critical": 85
            },
            {
                "name": "Inlet Temp",
                "value": 25,
                "unit": "C",
                "status": "ok"
            },
            {
                "name": "PCH Temp",
                "value": 52,
                "unit": "C",
                "status": "ok"
            }
        ],
        "fans": [
            {
                "name": "Fan 1",
                "rpm": 3200,
                "percent": 40,
                "status": "ok",
                "threshold_lower_non_critical": 500,
                "threshold_lower_critical": 200
            },
            {
                "name": "Fan 2",
                "rpm": 3150,
                "percent": 40,
                "status": "ok"
            },
            {
                "name": "Fan 3",
                "rpm": 0,
                "percent": 0,
                "status": "absent"  # absent, failed, ok
            }
        ]
    },
    "threshold_alerts": [],  # 当前触发的告警
    "sensor_count": {
        "temperatures": 4,
        "fans": 3
    }
}
```

### 4.3 Mock 数据

```python
{
    "sensors": {
        "temperatures": [
            {"name": "CPU0 Temp", "value": 45, "unit": "C", "status": "ok"},
            {"name": "CPU1 Temp", "value": 43, "unit": "C", "status": "ok"},
            {"name": "Inlet Temp", "value": 25, "unit": "C", "status": "ok"},
            {"name": "PCH Temp", "value": 52, "unit": "C", "status": "ok"},
            {"name": "PSU1 Temp", "value": 35, "unit": "C", "status": "ok"},
            {"name": "PSU2 Temp", "value": 33, "unit": "C", "status": "ok"}
        ],
        "fans": [
            {"name": "Fan 1 Front", "rpm": 3200, "percent": 40, "status": "ok"},
            {"name": "Fan 2 Front", "rpm": 3150, "percent": 40, "status": "ok"},
            {"name": "Fan 3 Front", "rpm": 3100, "percent": 40, "status": "ok"},
            {"name": "Fan 4 Rear", "rpm": 3300, "percent": 42, "status": "ok"},
            {"name": "Fan 5 Rear", "rpm": 3250, "percent": 42, "status": "ok"}
        ]
    },
    "threshold_alerts": [],
    "sensor_count": {
        "temperatures": 6,
        "fans": 5
    }
}
```

---

## 5. 通用设计原则

### 5.1 错误处理

所有检测器遵循相同的错误处理策略：

1. **工具不可用**: 返回基础信息 + `tool_available: False`
2. **命令执行失败**: 记录错误日志，返回已获取的部分数据
3. **权限不足**: 抛出 PermissionError，提示需要 root/ipmi 权限

### 5.2 权限要求

| 检测器 | 权限要求 |
|--------|----------|
| RAIDDetector | root 或 storcli 权限 |
| PSUDetector | root 或 ipmi 组权限 |
| SensorDetector | root 或 ipmi 组权限 |

### 5.3 性能考虑

- 每个检测器执行时间控制在 5 秒内
- 使用超时机制防止命令挂起
- 支持并发执行（不互相阻塞）

---

## 6. 验收标准

- [ ] RAIDDetector 支持 LSI、Adaptec、HP 三种控制器
- [ ] PSUDetector 支持 IPMI 和 lm-sensors 两种接口
- [ ] SensorDetector 支持温度、风扇、阈值告警
- [ ] 每个检测器都有 mock 和 real 两种模式
- [ ] 每个检测器都有 5+ 个单元测试
- [ ] 代码有适当注释和文档字符串

---

*设计文档完成，等待进入实现阶段*
