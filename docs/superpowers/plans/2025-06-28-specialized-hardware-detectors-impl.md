# 专用与扩展硬件检测器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 InfiniBand、FPGA、Security、Chassis、DIMM、NVMeHealth、Serial 七个专用硬件检测器

**Architecture:** 遵循现有检测器架构，继承 BaseDetector，实现 detect_real() 和 detect_mock() 方法

**Tech Stack:** Python 3.9+, subprocess, sysfs parsing, regex

---

## 文件结构总览

| 文件路径 | 职责 |
|----------|------|
| `src/detectors/infiniband.py` | InfiniBand 检测器 |
| `src/detectors/fpga.py` | FPGA 检测器 |
| `src/detectors/security.py` | 安全特性检测器 |
| `src/detectors/chassis.py` | 机箱检测器 |
| `src/detectors/dimm.py` | DIMM 内存检测器 |
| `src/detectors/nvme_health.py` | NVMe 健康度检测器 |
| `src/detectors/serial.py` | 串口检测器 |
| `tests/test_detectors/test_*.py` | 各检测器测试文件 |

---

## Task 1: InfiniBand 检测器

**Files:**
- Create: `src/detectors/infiniband.py`
- Create: `tests/test_detectors/test_infiniband.py`
- Modify: `src/detectors/__init__.py`

**Implementation:**

```python
import subprocess
import re
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class IBDetector(BaseDetector):
    """Detect InfiniBand network devices."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect InfiniBand via ibstat."""
        devices = []

        try:
            result = subprocess.run(
                ["ibstat"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                devices = self._parse_ibstat_output(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return {
            "present": len(devices) > 0,
            "device_count": len(devices),
            "devices": devices
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated IB data."""
        return {
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
                }
            ]
        }

    def _parse_ibstat_output(self, output: str) -> List[Dict]:
        """Parse ibstat output."""
        devices = []
        current_device = None

        for line in output.split("\n"):
            # Parse device name
            if "CA '" in line:
                match = re.search(r"CA '(\w+)'", line)
                if match:
                    if current_device:
                        devices.append(current_device)
                    current_device = {
                        "name": match.group(1),
                        "guid": "",
                        "vendor": "Mellanox",
                        "model": "Unknown",
                        "firmware_version": "",
                        "ports": []
                    }
            elif current_device:
                if "CA type:" in line:
                    current_device["model"] = line.split(":")[1].strip()
                elif "Firmware version:" in line:
                    current_device["firmware_version"] = line.split(":")[1].strip()
                elif "Port" in line and ":" in line:
                    port_match = re.search(r"Port (\d+):", line)
                    if port_match:
                        current_device["ports"].append({
                            "port_num": int(port_match.group(1)),
                            "state": "Unknown",
                            "phys_state": "Unknown",
                            "rate": "Unknown",
                            "lid": 0
                        })

        if current_device:
            devices.append(current_device)

        return devices
```

**Tests:** 6 tests (5 mock + 1 real)

---

## Task 2: FPGA 检测器

**Files:**
- Create: `src/detectors/fpga.py`
- Create: `tests/test_detectors/test_fpga.py`
- Modify: `src/detectors/__init__.py`

**Implementation:**

```python
import subprocess
import re
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class FPGADetector(BaseDetector):
    """Detect FPGA accelerator cards."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect FPGA via lspci and vendor tools."""
        devices = []

        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                devices = self._parse_fpga_devices(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return {
            "present": len(devices) > 0,
            "device_count": len(devices),
            "devices": devices
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated FPGA data."""
        return {
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
                }
            ]
        }

    def _parse_fpga_devices(self, output: str) -> List[Dict]:
        """Parse FPGA from lspci output."""
        devices = []
        fpga_patterns = [
            (r"Xilinx.*Alveo", "Xilinx"),
            (r"Xilinx.*VU", "Xilinx"),
            (r"Intel.*Stratix", "Intel"),
            (r"Intel.*Agilex", "Intel"),
            (r"Altera", "Intel"),
        ]

        for line in output.split("\n"):
            for pattern, vendor in fpga_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    match = re.match(r"(\S+)\s+(.+)", line)
                    if match:
                        devices.append({
                            "index": len(devices),
                            "vendor": vendor,
                            "model": "Unknown",
                            "pci_slot": match.group(1),
                            "firmware_version": "Unknown",
                            "shell_version": "Unknown",
                            "temperature_c": 0,
                            "power_watts": 0,
                            "memory_gb": 0,
                            "memory_type": "Unknown",
                            "serial": "Unknown",
                            "status": "unknown"
                        })

        return devices
```

**Tests:** 6 tests (5 mock + 1 real)

---

## Task 3: 安全特性检测器

**Files:**
- Create: `src/detectors/security.py`
- Create: `tests/test_detectors/test_security.py`
- Modify: `src/detectors/__init__.py`

**Implementation:**

```python
import os
from typing import Dict, Any

from .base import BaseDetector, DetectorMode


class SecurityDetector(BaseDetector):
    """Detect security features: SGX, SEV, TXT."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect security features via sysfs."""
        return {
            "sgx": self._detect_sgx(),
            "sev": self._detect_sev(),
            "txt": self._detect_txt(),
            "memory_encryption": self._detect_memory_encryption()
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated security data."""
        return {
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

    def _detect_sgx(self) -> Dict[str, Any]:
        """Detect Intel SGX."""
        sgx = {
            "supported": False,
            "enabled": False,
            "flc": False,
            "kss": False,
            "epc_size_mb": 0,
            "enclave_size_max": 0,
            "enclaves_active": 0
        }

        sgx_path = "/sys/devices/system/cpu/sgx"
        if os.path.exists(sgx_path):
            sgx["supported"] = True
            sgx["enabled"] = os.path.exists(f"{sgx_path}/enclave") or os.path.exists(f"{sgx_path}/provision")

            # Try to read EPC size
            epc_path = "/sys/firmware/sgx/epc_size"
            if os.path.exists(epc_path):
                try:
                    with open(epc_path, "r") as f:
                        epc_bytes = int(f.read().strip())
                        sgx["epc_size_mb"] = epc_bytes // (1024 * 1024)
                except (IOError, ValueError):
                    pass

        return sgx

    def _detect_sev(self) -> Dict[str, Any]:
        """Detect AMD SEV."""
        sev = {
            "supported": False,
            "enabled": False,
            "es_supported": False,
            "snp_supported": False,
            "firmware_version": None,
            "guests_active": 0,
            "guests_max": 0
        }

        sev_path = "/sys/devices/system/cpu/sev"
        if os.path.exists(sev_path):
            sev["supported"] = True

        return sev

    def _detect_txt(self) -> Dict[str, Any]:
        """Detect Intel TXT."""
        txt = {
            "supported": False,
            "enabled": False,
            "status": "unknown"
        }

        txt_path = "/sys/firmware/txt"
        if os.path.exists(txt_path):
            txt["supported"] = True
            txt["enabled"] = os.path.exists(f"{txt_path}/enabled")

        return txt

    def _detect_memory_encryption(self) -> Dict[str, Any]:
        """Detect memory encryption features."""
        return {
            "tme_supported": False,
            "mktme_supported": False,
            "sme_supported": False
        }
```

**Tests:** 6 tests (5 mock + 1 real)

---

## Task 4: 机箱检测器

**Files:**
- Create: `src/detectors/chassis.py`
- Create: `tests/test_detectors/test_chassis.py`
- Modify: `src/detectors/__init__.py`

**Implementation:**

```python
import os
import subprocess
from typing import Dict, Any

from .base import BaseDetector, DetectorMode


class ChassisDetector(BaseDetector):
    """Detect chassis information and status."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect chassis info via dmidecode and sysfs."""
        info = {
            "chassis_type": "Unknown",
            "manufacturer": "Unknown",
            "model": "Unknown",
            "serial": "Unknown",
            "asset_tag": "Unknown",
            "service_tag": "Unknown",
            "rack_location": "Unknown",
            "power_state": "unknown",
            "led_status": {
                "identify": False,
                "fault": False,
                "power": True
            },
            "lock_status": "unknown",
            "sku": "Unknown",
            "boot_up_state": "unknown",
            "power_supply_state": "unknown",
            "thermal_state": "unknown"
        }

        # Try sysfs first
        dmi_path = "/sys/class/dmi/id"
        if os.path.exists(dmi_path):
            info["chassis_type"] = self._read_dmi_file(f"{dmi_path}/chassis_type")
            info["manufacturer"] = self._read_dmi_file(f"{dmi_path}/chassis_vendor")
            info["serial"] = self._read_dmi_file(f"{dmi_path}/chassis_serial")
            info["asset_tag"] = self._read_dmi_file(f"{dmi_path}/chassis_asset_tag")
            info["sku"] = self._read_dmi_file(f"{dmi_path}/chassis_sku")
            info["model"] = self._read_dmi_file(f"{dmi_path}/product_name")
            info["service_tag"] = self._read_dmi_file(f"{dmi_path}/product_serial")

        return info

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated chassis data."""
        return {
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

    def _read_dmi_file(self, path: str) -> str:
        """Read DMI file from sysfs."""
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    return f.read().strip()
        except (IOError, FileNotFoundError, PermissionError):
            pass
        return "Unknown"
```

**Tests:** 6 tests (5 mock + 1 real)

---

## Task 5: DIMM 检测器

**Files:**
- Create: `src/detectors/dimm.py`
- Create: `tests/test_detectors/test_dimm.py`
- Modify: `src/detectors/__init__.py`

**Implementation:**

```python
import subprocess
import re
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class DIMMDetector(BaseDetector):
    """Detect individual DIMM information."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect DIMM via dmidecode."""
        dimms = []

        try:
            result = subprocess.run(
                ["dmidecode", "-t", "17"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                dimms = self._parse_dmidecode_output(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        total_capacity = sum(d.get("size_gb", 0) for d in dimms)

        return {
            "dimm_count": len(dimms),
            "populated_slots": len([d for d in dimms if d.get("size_gb", 0) > 0]),
            "total_capacity_gb": total_capacity,
            "dimms": dimms
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated DIMM data."""
        dimms = [
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

        return {
            "dimm_count": 16,
            "populated_slots": 16,
            "total_capacity_gb": 512,
            "dimms": dimms
        }

    def _parse_dmidecode_output(self, output: str) -> List[Dict]:
        """Parse dmidecode -t 17 output."""
        dimms = []
        current_dimm = None

        for line in output.split("\n"):
            line = line.strip()

            if line.startswith("Memory Device"):
                if current_dimm:
                    dimms.append(current_dimm)
                current_dimm = {
                    "slot": "Unknown",
                    "bank": "Unknown",
                    "size_gb": 0,
                    "type": "Unknown",
                    "speed_mhz": 0,
                    "manufacturer": "Unknown",
                    "serial": "Unknown",
                    "part_number": "Unknown",
                    "rank": "Unknown",
                    "configured_voltage": "Unknown",
                    "temperature_c": 0,
                    "status": "ok",
                    "ecc_errors": 0
                }
            elif current_dimm:
                if "Locator:" in line:
                    current_dimm["slot"] = line.split(":", 1)[1].strip()
                elif "Bank Locator:" in line:
                    current_dimm["bank"] = line.split(":", 1)[1].strip()
                elif "Size:" in line and "No Module" not in line:
                    size_match = re.search(r'(\d+)\s*MB', line)
                    if size_match:
                        current_dimm["size_gb"] = int(size_match.group(1)) / 1024
                elif "Type:" in line and "Detail" not in line:
                    current_dimm["type"] = line.split(":", 1)[1].strip()
                elif "Speed:" in line:
                    speed_match = re.search(r'(\d+)\s*MHz', line)
                    if speed_match:
                        current_dimm["speed_mhz"] = int(speed_match.group(1))
                elif "Manufacturer:" in line:
                    current_dimm["manufacturer"] = line.split(":", 1)[1].strip()
                elif "Serial Number:" in line:
                    current_dimm["serial"] = line.split(":", 1)[1].strip()
                elif "Part Number:" in line:
                    current_dimm["part_number"] = line.split(":", 1)[1].strip()

        if current_dimm:
            dimms.append(current_dimm)

        return dimms
```

**Tests:** 6 tests (5 mock + 1 real)

---

## Task 6: NVMe 健康检测器

**Files:**
- Create: `src/detectors/nvme_health.py`
- Create: `tests/test_detectors/test_nvme_health.py`
- Modify: `src/detectors/__init__.py`

**Implementation:**

```python
import subprocess
import re
import glob
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class NVMeHealthDetector(BaseDetector):
    """Detect NVMe device health and SMART data."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect NVMe health via nvme-cli."""
        devices = []

        # Find NVMe devices
        nvme_devices = glob.glob("/dev/nvme*[0-9]")

        for device in nvme_devices:
            device_info = self._get_nvme_health(device)
            if device_info:
                devices.append(device_info)

        return {
            "device_count": len(devices),
            "devices": devices
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated NVMe health data."""
        return {
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
                }
            ]
        }

    def _get_nvme_health(self, device: str) -> Dict[str, Any]:
        """Get health info for single NVMe device."""
        info = {
            "device": device,
            "model": "Unknown",
            "serial": "Unknown",
            "firmware": "Unknown",
            "capacity_gb": 0,
            "health": {
                "percentage": 100,
                "status": "unknown",
                "temperature_c": 0,
                "available_spare": 100,
                "available_spare_threshold": 10,
                "percentage_used": 0,
                "data_units_read_tb": 0,
                "data_units_written_tb": 0,
                "host_read_commands": 0,
                "host_write_commands": 0,
                "controller_busy_time_hours": 0,
                "power_cycles": 0,
                "power_on_hours": 0,
                "unsafe_shutdowns": 0,
                "media_errors": 0,
                "num_err_log_entries": 0
            },
            "critical_warning": [],
            "predicted_life_days": 0
        }

        try:
            result = subprocess.run(
                ["nvme", "smart-log", device],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                info["health"] = self._parse_smart_log(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return info

    def _parse_smart_log(self, output: str) -> Dict[str, Any]:
        """Parse nvme smart-log output."""
        health = {
            "percentage": 100,
            "status": "good",
            "temperature_c": 0,
            "available_spare": 100,
            "available_spare_threshold": 10,
            "percentage_used": 0,
            "data_units_read_tb": 0,
            "data_units_written_tb": 0,
            "host_read_commands": 0,
            "host_write_commands": 0,
            "controller_busy_time_hours": 0,
            "power_cycles": 0,
            "power_on_hours": 0,
            "unsafe_shutdowns": 0,
            "media_errors": 0,
            "num_err_log_entries": 0
        }

        for line in output.split("\n"):
            line = line.strip()

            if "temperature" in line.lower():
                temp_match = re.search(r'(\d+)', line)
                if temp_match:
                    health["temperature_c"] = int(temp_match.group(1)) - 273 if int(temp_match.group(1)) > 200 else int(temp_match.group(1))
            elif "percentage used" in line.lower():
                used_match = re.search(r'(\d+)', line)
                if used_match:
                    health["percentage_used"] = int(used_match.group(1))
                    health["percentage"] = max(0, 100 - health["percentage_used"])
            elif "available spare" in line.lower():
                spare_match = re.search(r'(\d+)', line)
                if spare_match:
                    health["available_spare"] = int(spare_match.group(1))

        # Determine status
        if health["percentage"] < 10 or health["available_spare"] < health.get("available_spare_threshold", 10):
            health["status"] = "critical"
        elif health["percentage"] < 50:
            health["status"] = "warning"
        else:
            health["status"] = "good"

        return health
```

**Tests:** 6 tests (5 mock + 1 real)

---

## Task 7: 串口检测器

**Files:**
- Create: `src/detectors/serial.py`
- Create: `tests/test_detectors/test_serial.py`
- Modify: `src/detectors/__init__.py`

**Implementation:**

```python
import os
import glob
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class SerialDetector(BaseDetector):
    """Detect serial ports and USB serial adapters."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect serial ports via sysfs."""
        ports = []
        usb_adapters = []

        # Detect standard serial ports
        tty_devices = glob.glob("/dev/ttyS*") + glob.glob("/dev/ttyAMA*")
        for device in sorted(tty_devices):
            port_info = self._get_port_info(device)
            if port_info:
                ports.append(port_info)

        # Detect USB serial adapters
        usb_devices = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
        for device in sorted(usb_devices):
            adapter_info = self._get_usb_adapter_info(device)
            if adapter_info:
                usb_adapters.append(adapter_info)

        return {
            "port_count": len(ports),
            "ports": ports,
            "usb_serial_adapters": usb_adapters
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated serial data."""
        return {
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

    def _get_port_info(self, device: str) -> Dict[str, Any]:
        """Get info for standard serial port."""
        port_name = os.path.basename(device)

        return {
            "device": device,
            "type": "UART",
            "uart_type": "16550A",
            "irq": 0,
            "io_port": "Unknown",
            "baud_base": 115200,
            "current_baud": 0,
            "data_bits": 8,
            "stop_bits": 1,
            "parity": "none",
            "flow_control": "none",
            "status": "available",
            "description": port_name
        }

    def _get_usb_adapter_info(self, device: str) -> Dict[str, Any]:
        """Get info for USB serial adapter."""
        return {
            "device": device,
            "usb_id": "Unknown",
            "vendor": "Unknown",
            "model": "Unknown",
            "driver": "Unknown",
            "status": "connected"
        }
```

**Tests:** 6 tests (5 mock + 1 real)

---

## 验收检查清单

| 验收项 | 验证命令 | 预期结果 |
|--------|----------|----------|
| IB 检测器 | `pytest tests/test_detectors/test_infiniband.py -v` | 6 tests PASS |
| FPGA 检测器 | `pytest tests/test_detectors/test_fpga.py -v` | 6 tests PASS |
| Security 检测器 | `pytest tests/test_detectors/test_security.py -v` | 6 tests PASS |
| Chassis 检测器 | `pytest tests/test_detectors/test_chassis.py -v` | 6 tests PASS |
| DIMM 检测器 | `pytest tests/test_detectors/test_dimm.py -v` | 6 tests PASS |
| NVMeHealth 检测器 | `pytest tests/test_detectors/test_nvme_health.py -v` | 6 tests PASS |
| Serial 检测器 | `pytest tests/test_detectors/test_serial.py -v` | 6 tests PASS |
| 完整测试套件 | `pytest` | 全部 tests PASS |
| 导出检查 | `python -c "from src.detectors import ..."` | 无错误 |

---

*计划完成，准备执行*
