# 安全与系统硬件检测器设计文档

## 文档信息
- **日期**: 2025-06-28
- **版本**: v1.0
- **状态**: 已批准
- **目标**: 添加 TPM、BIOS/UEFI、USB 检测器

---

## 1. 概述

### 1.1 背景
服务器测试系统已覆盖主要硬件模块。本设计补充安全相关硬件（TPM）、系统固件（BIOS/UEFI）和外围接口（USB）的检测能力。

### 1.2 新增检测器

| 检测器 | 检测内容 | 主要接口 |
|--------|----------|----------|
| TPMDetector | TPM 版本、状态、EK 证书 | /sys/class/tpm/tpm0 |
| BIOSDetector | BIOS/UEFI 版本、日期、厂商 | dmidecode / sysfs |
| USBDetector | USB 控制器、Hub、连接设备 | lsusb / sysfs |

---

## 2. TPM 检测器设计

### 2.1 检测方式

| 方式 | 路径/命令 | 优先级 |
|------|-----------|--------|
| sysfs | `/sys/class/tpm/tpm0/` | 高 |
| tpm2_tools | `tpm2_getcap` | 中 |

### 2.2 输出数据结构

```python
{
    "present": True,
    "version": "2.0",  # 1.2, 2.0
    "vendor": "Intel",
    "firmware_version": "7.2.2.0",
    "status": "active",  # active, disabled, deactivated
    "ek_certificate_present": True,
    "pcr_banks": ["sha256", "sha384"],
    "pcr_count": 24,
    "nvram_size_kb": 48,
    "clear_control": "locked"  # locked, unlocked
}
```

### 2.3 Mock 数据

```python
{
    "present": True,
    "version": "2.0",
    "vendor": "Intel",
    "firmware_version": "7.2.2.0",
    "status": "active",
    "ek_certificate_present": True,
    "pcr_banks": ["sha256", "sha384"],
    "pcr_count": 24,
    "nvram_size_kb": 48,
    "clear_control": "locked"
}
```

---

## 3. BIOS/UEFI 检测器设计

### 3.1 检测方式

| 方式 | 路径/命令 | 优先级 |
|------|-----------|--------|
| dmidecode | `dmidecode -t 0,13` | 高 |
| sysfs | `/sys/class/dmi/id/` | 中 |

### 3.2 输出数据结构

```python
{
    "type": "UEFI",  # UEFI, Legacy BIOS
    "vendor": "Dell Inc.",
    "version": "2.8.1",
    "date": "2024-03-15",
    "rom_size_mb": 32,
    "characteristics": [
        "ACPI",
        "USB Legacy",
        "UEFI Boot",
        "Secure Boot"
    ],
    "secure_boot": {
        "supported": True,
        "enabled": True,
        "mode": "user"  # user, setup, audit, deployed
    },
    "boot_mode": "UEFI",  # UEFI, Legacy
    "system_serial": "ABC123456",
    "system_uuid": "4c4c4544-0035-4d10-8051-c7c04f503432",
    "sku_number": "PE-R750",
    "family": "PowerEdge"
}
```

### 3.3 Mock 数据

```python
{
    "type": "UEFI",
    "vendor": "Dell Inc.",
    "version": "2.8.1",
    "date": "2024-03-15",
    "rom_size_mb": 32,
    "characteristics": [
        "ACPI",
        "USB Legacy",
        "UEFI Boot",
        "Secure Boot"
    ],
    "secure_boot": {
        "supported": True,
        "enabled": True,
        "mode": "user"
    },
    "boot_mode": "UEFI",
    "system_serial": "ABC123456",
    "system_uuid": "4c4c4544-0035-4d10-8051-c7c04f503432",
    "sku_number": "PE-R750",
    "family": "PowerEdge"
}
```

---

## 4. USB 检测器设计

### 4.1 检测方式

| 方式 | 命令 | 优先级 |
|------|------|--------|
| lsusb | `lsusb -v` | 高 |
| sysfs | `/sys/bus/usb/devices/` | 中 |

### 4.2 输出数据结构

```python
{
    "controllers": [
        {
            "bus": 1,
            "id": "1d6b:0002",
            "vendor": "Linux Foundation",
            "product": "2.0 root hub",
            "speed": "480M",  # 480M, 5000M, 10000M
            "usb_version": "2.0"
        },
        {
            "bus": 2,
            "id": "1d6b:0003",
            "vendor": "Linux Foundation",
            "product": "3.0 root hub",
            "speed": "5000M",
            "usb_version": "3.0"
        }
    ],
    "devices": [
        {
            "bus": 1,
            "device": 2,
            "id": "046b:ff01",
            "vendor": "American Power Conversion",
            "product": "UPS",
            "speed": "1.5M",
            "class": "HID",
            "connected": True
        },
        {
            "bus": 2,
            "device": 3,
            "id": "0781:5567",
            "vendor": "SanDisk Corp.",
            "product": "Cruzer Blade",
            "speed": "480M",
            "class": "Mass Storage",
            "connected": True
        }
    ],
    "controller_count": 2,
    "device_count": 4
}
```

### 4.3 Mock 数据

```python
{
    "controllers": [
        {
            "bus": 1,
            "id": "1d6b:0002",
            "vendor": "Linux Foundation",
            "product": "2.0 root hub",
            "speed": "480M",
            "usb_version": "2.0"
        },
        {
            "bus": 2,
            "id": "1d6b:0003",
            "vendor": "Linux Foundation",
            "product": "3.0 root hub",
            "speed": "5000M",
            "usb_version": "3.0"
        }
    ],
    "devices": [
        {
            "bus": 1,
            "device": 2,
            "id": "046b:ff01",
            "vendor": "American Power Conversion",
            "product": "UPS",
            "speed": "1.5M",
            "class": "HID",
            "connected": True
        },
        {
            "bus": 2,
            "device": 3,
            "id": "0781:5567",
            "vendor": "SanDisk Corp.",
            "product": "Cruzer Blade",
            "speed": "480M",
            "class": "Mass Storage",
            "connected": True
        }
    ],
    "controller_count": 2,
    "device_count": 2
}
```

---

## 5. 通用设计原则

### 5.1 错误处理

1. **硬件不存在**: 返回 `{"present": False}` 或空结构
2. **权限不足**: 捕获 PermissionError，返回部分可用数据
3. **命令执行失败**: 记录错误，返回已获取的部分数据

### 5.2 权限要求

| 检测器 | 权限要求 |
|--------|----------|
| TPMDetector | root 或 tpm 组权限 |
| BIOSDetector | root (dmidecode 需要) |
| USBDetector | 无特殊要求 |

---

## 6. 验收标准

- [ ] TPMDetector 支持 TPM 1.2 和 2.0
- [ ] BIOSDetector 支持 UEFI 和 Legacy BIOS
- [ ] USBDetector 支持 USB 2.0/3.0/3.1 控制器和设备
- [ ] 每个检测器都有 mock 和 real 两种模式
- [ ] 每个检测器都有 5+ 个单元测试
- [ ] 代码有适当注释和文档字符串

---

*设计文档完成，等待进入实现阶段*
