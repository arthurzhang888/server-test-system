# 专用与扩展硬件检测器设计文档

## 文档信息
- **日期**: 2025-06-28
- **版本**: v1.0
- **状态**: 已批准
- **目标**: 添加 InfiniBand、FPGA、Security、Chassis、DIMM、NVMeHealth、Serial 检测器

---

## 1. 概述

### 1.1 背景
服务器测试系统已覆盖主流硬件模块。本设计补充高性能计算专用硬件（InfiniBand、FPGA）、安全特性（SGX/SEV）、资产管理（Chassis）以及精细化监控（DIMM、NVMeHealth、Serial）的检测能力。

### 1.2 新增检测器

| 优先级 | 检测器 | 检测内容 | 主要接口 |
|--------|--------|----------|----------|
| 中级 | IBDetector | InfiniBand 网卡、速率、端口 | ibstat / ibstatus |
| 中级 | FPGADetector | FPGA 加速卡、固件、温度 | lspci / vendor tools |
| 中级 | SecurityDetector | Intel SGX、AMD SEV、安全启动 | cpuid / sysfs |
| 中级 | ChassisDetector | 机箱型号、资产标签、位置 | dmidecode / ipmitool |
| 低级 | DIMMDetector | 单条内存详情、温度、位置 | dmidecode / ipmi-sensors |
| 低级 | NVMeHealthDetector | NVMe SMART、寿命、写入量 | nvme-cli / smartctl |
| 低级 | SerialDetector | 串口配置、波特率、设备 | setserial / sysfs |

---

## 2. InfiniBand 检测器设计

### 2.1 检测方式

| 方式 | 命令 | 说明 |
|------|------|------|
| ibstat | `ibstat` | 显示 IB 设备状态和端口信息 |
| ibstatus | `ibstatus` | 显示端口详细状态 |
| sysfs | `/sys/class/infiniband/` | 设备属性读取 |

### 2.2 输出数据结构

```python
{
    "present": True,
    "device_count": 2,
    "devices": [
        {
            "name": "mlx5_0",
            "guid": "0x0002c90300a0e7c0",
            "vendor": "Mellanox",
            "model": "ConnectX-6",
            "firmware_version": "20.28.4512",
            "ports": [
                {
                    "port_num": 1,
                    "state": "Active",
                    "phys_state": "LinkUp",
                    "rate": "200 Gb/sec",
                    "lid": 12,
                    "gid": "fe80:0000:0000:0000:0002:c903:00a0:e7c0"
                }
            ]
        }
    ]
}
```

### 2.3 Mock 数据

```python
{
    "present": True,
    "device_count": 2,
    "devices": [
        {
            "name": "mlx5_0",
            "guid": "0x0002c90300a0e7c0",
            "vendor": "Mellanox",
            "model": "ConnectX-6",
            "firmware_version": "20.28.4512",
            "ports": [
                {
                    "port_num": 1,
                    "state": "Active",
                    "phys_state": "LinkUp",
                    "rate": "200 Gb/sec",
                    "lid": 12
                }
            ]
        },
        {
            "name": "mlx5_1",
            "guid": "0x0002c90300a0e7c1",
            "vendor": "Mellanox",
            "model": "ConnectX-6",
            "firmware_version": "20.28.4512",
            "ports": [
                {
                    "port_num": 1,
                    "state": "Active",
                    "phys_state": "LinkUp",
                    "rate": "200 Gb/sec",
                    "lid": 13
                }
            ]
        }
    ]
}
```

---

## 3. FPGA 检测器设计

### 3.1 检测方式

| 厂商 | 工具 | 检测方式 |
|------|------|----------|
| Xilinx/AMD | `xbutil` | Alveo 加速卡 |
| Intel | `aocl` / `sycl-ls` | Stratix/Agilex |
| 通用 | `lspci` | 设备ID检测 |

### 3.2 输出数据结构

```python
{
    "present": True,
    "device_count": 2,
    "devices": [
        {
            "index": 0,
            "vendor": "Xilinx",
            "model": "Alveo U280",
            "pci_slot": "0000:3b:00.0",
            "firmware_version": "golden",
            "shell_version": "xilinx_u280_gen3x16_xdma_base_1",
            "temperature_c": 52,
            "power_watts": 45,
            "memory_gb": 32,
            "memory_type": "HBM2",
            "serial": "XFL1A0B2C3D4",
            "status": "healthy"  # healthy, overheated, power-off
        }
    ]
}
```

### 3.3 Mock 数据

```python
{
    "present": True,
    "device_count": 2,
    "devices": [
        {
            "index": 0,
            "vendor": "Xilinx",
            "model": "Alveo U280",
            "pci_slot": "0000:3b:00.0",
            "firmware_version": "golden",
            "shell_version": "xilinx_u280_gen3x16_xdma_base_1",
            "temperature_c": 52,
            "power_watts": 45,
            "memory_gb": 32,
            "memory_type": "HBM2",
            "serial": "XFL1A0B2C3D4",
            "status": "healthy"
        },
        {
            "index": 1,
            "vendor": "Intel",
            "model": "Stratix 10 MX",
            "pci_slot": "0000:d8:00.0",
            "firmware_version": "1.2.3",
            "shell_version": "intel_s10mx_pcie_ed",
            "temperature_c": 48,
            "power_watts": 55,
            "memory_gb": 16,
            "memory_type": "DDR4",
            "serial": "INTEL5678",
            "status": "healthy"
        }
    ]
}
```

---

## 4. 安全特性检测器设计

### 4.1 检测方式

| 特性 | 检测方式 | 路径/命令 |
|------|----------|-----------|
| Intel SGX | cpuid / sysfs | `/sys/devices/system/cpu/sgx/` |
| AMD SEV | cpuid / sysfs | `/sys/devices/system/cpu/sev/` |
| AMD SEV-ES | cpuid | - |
| AMD SEV-SNP | cpuid | - |
| TXT (Trusted Execution) | sysfs | `/sys/firmware/txt/` |

### 4.2 输出数据结构

```python
{
    "sgx": {
        "supported": True,
        "enabled": True,
        "flc": True,  # Flexible Launch Control
        "kss": True,  # Key Separation and Sharing
        "epc_size_mb": 256,
        "enclave_size_max": 128,
        "enclaves_active": 5
    },
    "sev": {
        "supported": True,
        "enabled": True,
        "es_supported": True,  # Encrypted State
        "snp_supported": True,  # Secure Nested Paging
        "firmware_version": "1.51.3",
        "guests_active": 3,
        "guests_max": 500
    },
    "txt": {
        "supported": True,
        "enabled": False,
        "status": "uninitialized"
    },
    "memory_encryption": {
        "tme_supported": True,  # Total Memory Encryption
        "mktme_supported": True,  # Multi-Key TME
        "sme_supported": False  # Secure Memory Encryption (AMD)
    }
}
```

### 4.3 Mock 数据

```python
{
    "sgx": {
        "supported": True,
        "enabled": True,
        "flc": True,
        "kss": True,
        "epc_size_mb": 256,
        "enclave_size_max": 128,
        "enclaves_active": 5
    },
    "sev": {
        "supported": False,
        "enabled": False,
        "es_supported": False,
        "snp_supported": False,
        "firmware_version": None,
        "guests_active": 0,
        "guests_max": 0
    },
    "txt": {
        "supported": True,
        "enabled": False,
        "status": "uninitialized"
    },
    "memory_encryption": {
        "tme_supported": True,
        "mktme_supported": True,
        "sme_supported": False
    }
}
```

---

## 5. 机箱检测器设计

### 5.1 检测方式

| 信息类型 | 来源 | 命令/路径 |
|----------|------|-----------|
| 机箱类型 | dmidecode | `dmidecode -t 3` |
| 资产标签 | dmidecode | `dmidecode -t 3` |
| 服务标签 | dmidecode / sysfs | `/sys/class/dmi/id/chassis_serial` |
| 机架位置 | ipmitool | `ipmitool fru` |
| 电源状态 | ipmitool | `ipmitool chassis status` |

### 5.2 输出数据结构

```python
{
    "chassis_type": "Rack Mount Chassis",
    "manufacturer": "Dell Inc.",
    "model": "PowerEdge R750",
    "serial": "ABC123456",
    "asset_tag": "SERVER-R750-001",
    "service_tag": "5D3XYZ1",
    "rack_location": "A12-U05",
    "power_state": "on",
    "led_status": {
        "identify": False,
        "fault": False,
        "power": True
    },
    "lock_status": "unlocked",
    "sku": "7G5T2A2",
    "boot_up_state": "safe",
    "power_supply_state": "safe",
    "thermal_state": "safe"
}
```

### 5.3 Mock 数据

```python
{
    "chassis_type": "Rack Mount Chassis",
    "manufacturer": "Dell Inc.",
    "model": "PowerEdge R750",
    "serial": "ABC123456",
    "asset_tag": "SERVER-R750-001",
    "service_tag": "5D3XYZ1",
    "rack_location": "A12-U05",
    "power_state": "on",
    "led_status": {
        "identify": False,
        "fault": False,
        "power": True
    },
    "lock_status": "unlocked",
    "sku": "7G5T2A2",
    "boot_up_state": "safe",
    "power_supply_state": "safe",
    "thermal_state": "safe"
}
```

---

## 6. DIMM 检测器设计

### 6.1 检测方式

| 信息 | 来源 | 命令 |
|------|------|------|
| DIMM 位置 | dmidecode | `dmidecode -t 17` |
| 容量 | dmidecode | `dmidecode -t 17` |
| 速度 | dmidecode | `dmidecode -t 17` |
| 温度 | ipmitool | `ipmitool sdr type Memory` |
| SN/PN | dmidecode | `dmidecode -t 17` |

### 6.2 输出数据结构

```python
{
    "dimm_count": 16,
    "populated_slots": 16,
    "total_capacity_gb": 512,
    "dimms": [
        {
            "slot": "A1",
            "bank": "BANK 0",
            "size_gb": 32,
            "type": "DDR4",
            "speed_mhz": 3200,
            "manufacturer": "Samsung",
            "serial": "S123456789",
            "part_number": "M393A4K40DB3-CWE",
            "rank": "2R",
            "configured_voltage": "1.2V",
            "temperature_c": 42,
            "status": "ok",  # ok, error, absent
            "ecc_errors": 0
        }
    ]
}
```

### 6.3 Mock 数据

```python
{
    "dimm_count": 16,
    "populated_slots": 16,
    "total_capacity_gb": 512,
    "dimms": [
        {
            "slot": "A1",
            "bank": "BANK 0",
            "size_gb": 32,
            "type": "DDR4",
            "speed_mhz": 3200,
            "manufacturer": "Samsung",
            "serial": "S123456789",
            "part_number": "M393A4K40DB3-CWE",
            "rank": "2R",
            "configured_voltage": "1.2V",
            "temperature_c": 42,
            "status": "ok",
            "ecc_errors": 0
        },
        {
            "slot": "A2",
            "bank": "BANK 1",
            "size_gb": 32,
            "type": "DDR4",
            "speed_mhz": 3200,
            "manufacturer": "Samsung",
            "serial": "S123456790",
            "part_number": "M393A4K40DB3-CWE",
            "rank": "2R",
            "configured_voltage": "1.2V",
            "temperature_c": 43,
            "status": "ok",
            "ecc_errors": 0
        }
    ]
}
```

---

## 7. NVMe 健康检测器设计

### 7.1 检测方式

| 工具 | 命令 | 说明 |
|------|------|------|
| nvme-cli | `nvme smart-log /dev/nvme0` | NVMe SMART 日志 |
| smartctl | `smartctl -a /dev/nvme0` | 通用 SMART 工具 |
| sysfs | `/sys/class/nvme/nvme0/` | 设备属性 |

### 7.2 输出数据结构

```python
{
    "device_count": 4,
    "devices": [
        {
            "device": "/dev/nvme0",
            "model": "Samsung PM1735",
            "serial": "S4CKN90W123456",
            "firmware": "MPN8K2Q",
            "capacity_gb": 1920,
            "health": {
                "percentage": 98,  # 0-100%
                "status": "good",  # good, warning, critical
                "temperature_c": 45,
                "available_spare": 100,  # %
                "available_spare_threshold": 10,
                "percentage_used": 2,  # % of estimated life used
                "data_units_read_tb": 1250.5,
                "data_units_written_tb": 850.2,
                "host_read_commands": 15000000,
                "host_write_commands": 12000000,
                "controller_busy_time_hours": 8760,
                "power_cycles": 150,
                "power_on_hours": 8760,
                "unsafe_shutdowns": 3,
                "media_errors": 0,
                "num_err_log_entries": 0
            },
            "critical_warning": [],  # temperature, degraded, read-only, volatile_memory
            "predicted_life_days": 1460  # estimated remaining life
        }
    ]
}
```

### 7.3 Mock 数据

```python
{
    "device_count": 2,
    "devices": [
        {
            "device": "/dev/nvme0",
            "model": "Samsung PM1735",
            "serial": "S4CKN90W123456",
            "firmware": "MPN8K2Q",
            "capacity_gb": 1920,
            "health": {
                "percentage": 98,
                "status": "good",
                "temperature_c": 45,
                "available_spare": 100,
                "available_spare_threshold": 10,
                "percentage_used": 2,
                "data_units_read_tb": 1250.5,
                "data_units_written_tb": 850.2,
                "host_read_commands": 15000000,
                "host_write_commands": 12000000,
                "controller_busy_time_hours": 8760,
                "power_cycles": 150,
                "power_on_hours": 8760,
                "unsafe_shutdowns": 3,
                "media_errors": 0,
                "num_err_log_entries": 0
            },
            "critical_warning": [],
            "predicted_life_days": 1460
        },
        {
            "device": "/dev/nvme1",
            "model": "Intel P5800X",
            "serial": "PHAB1234001P2M3G",
            "firmware": "L0310100",
            "capacity_gb": 800,
            "health": {
                "percentage": 95,
                "status": "good",
                "temperature_c": 52,
                "available_spare": 100,
                "available_spare_threshold": 10,
                "percentage_used": 5,
                "data_units_read_tb": 2500.0,
                "data_units_written_tb": 2100.0,
                "host_read_commands": 25000000,
                "host_write_commands": 18000000,
                "controller_busy_time_hours": 7200,
                "power_cycles": 200,
                "power_on_hours": 7200,
                "unsafe_shutdowns": 1,
                "media_errors": 0,
                "num_err_log_entries": 1
            },
            "critical_warning": [],
            "predicted_life_days": 1095
        }
    ]
}
```

---

## 8. 串口检测器设计

### 8.1 检测方式

| 信息 | 来源 | 命令/路径 |
|------|------|-----------|
| 串口设备 | setserial | `setserial -g /dev/ttyS*` |
| 波特率 | stty | `stty -F /dev/ttyS0` |
| 内核信息 | dmesg | `dmesg \| grep tty` |
| sysfs | /sys/class/tty/ | 设备属性 |

### 8.2 输出数据结构

```python
{
    "port_count": 2,
    "ports": [
        {
            "device": "/dev/ttyS0",
            "type": "UART",
            "uart_type": "16550A",
            "irq": 4,
            "io_port": "0x3f8",
            "baud_base": 115200,
            "current_baud": 115200,
            "data_bits": 8,
            "stop_bits": 1,
            "parity": "none",
            "flow_control": "none",
            "status": "available",  # available, in-use, error
            "description": "COM1"
        }
    ],
    "usb_serial_adapters": [
        {
            "device": "/dev/ttyUSB0",
            "usb_id": "067b:2303",
            "vendor": "Prolific",
            "model": "PL2303",
            "driver": "pl2303",
            "status": "connected"
        }
    ]
}
```

### 8.3 Mock 数据

```python
{
    "port_count": 2,
    "ports": [
        {
            "device": "/dev/ttyS0",
            "type": "UART",
            "uart_type": "16550A",
            "irq": 4,
            "io_port": "0x3f8",
            "baud_base": 115200,
            "current_baud": 115200,
            "data_bits": 8,
            "stop_bits": 1,
            "parity": "none",
            "flow_control": "none",
            "status": "available",
            "description": "COM1"
        },
        {
            "device": "/dev/ttyS1",
            "type": "UART",
            "uart_type": "16550A",
            "irq": 3,
            "io_port": "0x2f8",
            "baud_base": 115200,
            "current_baud": 9600,
            "data_bits": 8,
            "stop_bits": 1,
            "parity": "none",
            "flow_control": "rts/cts",
            "status": "in-use",
            "description": "COM2 - BMC Console"
        }
    ],
    "usb_serial_adapters": [
        {
            "device": "/dev/ttyUSB0",
            "usb_id": "067b:2303",
            "vendor": "Prolific",
            "model": "PL2303",
            "driver": "pl2303",
            "status": "connected"
        }
    ]
}
```

---

## 9. 通用设计原则

### 9.1 错误处理

1. **硬件不存在**: 返回 `{"present": False}` 或空结构
2. **工具不可用**: 返回基础信息 + `tool_available: False`
3. **权限不足**: 捕获 PermissionError，返回部分可用数据

### 9.2 权限要求

| 检测器 | 权限要求 |
|--------|----------|
| IBDetector | root (ibstat 需要) |
| FPGADetector | root (xbutil/aocl 需要) |
| SecurityDetector | root (SGX/SEV sysfs 需要) |
| ChassisDetector | root (dmidecode 需要) |
| DIMMDetector | root (dmidecode 需要) |
| NVMeHealthDetector | root (nvme-cli 需要) 或普通用户（有权限） |
| SerialDetector | 无特殊要求 |

---

## 10. 验收标准

- [ ] IBDetector 支持 Mellanox 设备检测
- [ ] FPGADetector 支持 Xilinx/Intel FPGA
- [ ] SecurityDetector 支持 SGX/SEV/TXT 检测
- [ ] ChassisDetector 支持资产标签和机架位置
- [ ] DIMMDetector 支持单条内存详情
- [ ] NVMeHealthDetector 支持 SMART 健康度
- [ ] SerialDetector 支持串口和 USB 串口
- [ ] 每个检测器都有 mock 和 real 两种模式
- [ ] 每个检测器都有 5+ 个单元测试
- [ ] 代码有适当注释和文档字符串

---

*设计文档完成，等待进入实现阶段*
