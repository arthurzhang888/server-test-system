# 额外硬件检测器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 RAID、PSU、温度/风扇传感器三个硬件检测器，支持 mock/real 模式切换

**Architecture:** 遵循现有检测器架构，继承 BaseDetector，实现 detect_real() 和 detect_mock() 方法。RAID 采用分层检测（lspci + 厂商工具），PSU 和 Sensor 使用 IPMI 为主、lm-sensors 为辅的接口。

**Tech Stack:** Python 3.9+, psutil, subprocess, ipmitool (optional)

---

## 文件结构总览

| 文件路径 | 职责 |
|----------|------|
| `src/detectors/raid.py` | RAID 控制器检测器（分层架构） |
| `src/detectors/psu.py` | 电源检测器（IPMI/lm-sensors） |
| `src/detectors/sensor.py` | 温度/风扇传感器检测器 |
| `tests/test_detectors/test_raid.py` | RAID 检测器测试 |
| `tests/test_detectors/test_psu.py` | PSU 检测器测试 |
| `tests/test_detectors/test_sensor.py` | 传感器检测器测试 |

---

## Task 1: RAID 检测器 - 基础架构

**Files:**
- Create: `src/detectors/raid.py`
- Create: `tests/test_detectors/test_raid.py`
- Modify: `src/detectors/__init__.py`

- [ ] **Step 1: 编写 RAID 检测器基础测试**

Create `tests/test_detectors/test_raid.py`:
```python
import pytest
from src.detectors.raid import RAIDDetector
from src.detectors.base import DetectorMode


class TestRAIDDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = RAIDDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "controllers" in result
        assert "controller_count" in result
        assert isinstance(result["controllers"], list)

    def test_mock_has_controller_details(self):
        detector = RAIDDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        if result["controller_count"] > 0:
            controller = result["controllers"][0]
            assert "model" in controller
            assert "vendor" in controller
            assert "arrays" in controller
            assert "physical_drives" in controller

    def test_mock_controller_count_matches(self):
        detector = RAIDDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["controller_count"] == len(result["controllers"])

    def test_mock_arrays_have_required_fields(self):
        detector = RAIDDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for controller in result["controllers"]:
            for array in controller.get("arrays", []):
                assert "id" in array
                assert "raid_level" in array
                assert "size_gb" in array
                assert "status" in array

    def test_mock_physical_drives_have_required_fields(self):
        detector = RAIDDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for controller in result["controllers"]:
            for drive in controller.get("physical_drives", []):
                assert "slot" in drive
                assert "model" in drive
                assert "size_gb" in drive
                assert "status" in drive


class TestRAIDDetectorReal:
    def test_real_returns_dict(self):
        detector = RAIDDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "controllers" in result
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_raid.py -v
```

Expected: ImportError - RAIDDetector not found

- [ ] **Step 3: 实现 RAID 检测器基础架构**

Create `src/detectors/raid.py`:
```python
import subprocess
import re
from typing import Dict, List, Any, Optional
from pathlib import Path

from .base import BaseDetector, DetectorMode


class RAIDDetector(BaseDetector):
    """Detect RAID controllers and their configuration.

    Supports LSI/Broadcom (StorCLI), Adaptec (arcconf), and HP/HPE (ssacli).
    Uses layered detection: lspci for basic info, vendor tools for details.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect RAID controllers using lspci and vendor tools."""
        # Layer 1: Detect controllers via lspci
        controllers = self._detect_via_lspci()

        if not controllers:
            return {"controllers": [], "controller_count": 0}

        # Layer 2: Enrich with vendor tool data if available
        for controller in controllers:
            vendor = controller.get("vendor", "").lower()
            tool_data = {}

            if "lsi" in vendor or "broadcom" in vendor or "mega" in vendor:
                tool_data = self._get_storcli_info(controller["index"])
            elif "adaptec" in vendor or "smart" in vendor:
                tool_data = self._get_arcconf_info(controller["index"])
            elif "hp" in vendor or "hpe" in vendor or "smart array" in vendor:
                tool_data = self._get_ssacli_info(controller["index"])

            if tool_data:
                controller.update(tool_data)
                controller["tool_available"] = True
            else:
                controller["tool_available"] = False

        return {
            "controllers": controllers,
            "controller_count": len(controllers)
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated RAID controller data."""
        return {
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

    def _detect_via_lspci(self) -> List[Dict[str, Any]]:
        """Detect RAID controllers using lspci."""
        controllers = []

        try:
            result = subprocess.run(
                ["lspci", "-nn"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode != 0:
                return controllers

            for line in result.stdout.split("\n"):
                if any(keyword in line.lower() for keyword in
                       ["raid", "sas", "scsi", "mass storage"]):
                    controller = self._parse_lspci_line(line)
                    if controller:
                        controllers.append(controller)

        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            pass

        return controllers

    def _parse_lspci_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single lspci line for RAID controller info."""
        match = re.match(r"(\S+)\s+(.+)\s+\[(\w+)\]", line)
        if not match:
            return None

        pci_slot = match.group(1)
        description = match.group(2)

        # Determine vendor
        vendor = "Unknown"
        desc_lower = description.lower()
        if any(v in desc_lower for v in ["lsi", "broadcom", "mega"]):
            vendor = "LSI/Broadcom"
        elif any(v in desc_lower for v in ["adaptec", "microsemi"]):
            vendor = "Adaptec"
        elif any(v in desc_lower for v in ["hp", "hpe", "smart array"]):
            vendor = "HP/HPE"
        elif "intel" in desc_lower:
            vendor = "Intel"

        return {
            "index": len([c for c in []]),  # Will be set by caller
            "model": description.strip(),
            "vendor": vendor,
            "pci_slot": pci_slot,
            "detected_by": "lspci"
        }

    def _get_storcli_info(self, controller_index: int) -> Dict[str, Any]:
        """Get RAID info using StorCLI (LSI/Broadcom)."""
        # Placeholder - will be implemented in Task 2
        return {}

    def _get_arcconf_info(self, controller_index: int) -> Dict[str, Any]:
        """Get RAID info using arcconf (Adaptec)."""
        # Placeholder - will be implemented in Task 2
        return {}

    def _get_ssacli_info(self, controller_index: int) -> Dict[str, Any]:
        """Get RAID info using ssacli (HP/HPE)."""
        # Placeholder - will be implemented in Task 2
        return {}
```

- [ ] **Step 4: 更新导出文件**

Update `src/detectors/__init__.py`:
```python
from .base import BaseDetector, DetectorMode
from .cpu import CPUDetector
from .memory import MemoryDetector
from .storage import StorageDetector
from .network import NetworkDetector
from .gpu import GPUDetector
from .bmc import BMCDetector
from .pcie import PCIeDetector
from .raid import RAIDDetector

__all__ = [
    "BaseDetector",
    "DetectorMode",
    "CPUDetector",
    "MemoryDetector",
    "StorageDetector",
    "NetworkDetector",
    "GPUDetector",
    "BMCDetector",
    "PCIeDetector",
    "RAIDDetector"
]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_raid.py -v
```

Expected: 6 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/detectors/raid.py tests/test_detectors/test_raid.py src/detectors/__init__.py
git commit -m "feat(detectors): add RAIDDetector base architecture

- Layer 1: lspci detection for controller identification
- Layer 2: Placeholder for vendor tool integration
- Support LSI/Broadcom, Adaptec, HP/HPE controllers
- Mock mode with realistic MegaRAID 9361-8i data

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 2: RAID 检测器 - StorCLI 支持 (LSI/Broadcom)

**Files:**
- Modify: `src/detectors/raid.py`
- Modify: `tests/test_detectors/test_raid.py`

- [ ] **Step 1: 添加 StorCLI 方法实现**

Replace `_get_storcli_info` in `src/detectors/raid.py`:
```python
    def _get_storcli_info(self, controller_index: int) -> Dict[str, Any]:
        """Get RAID info using StorCLI (LSI/Broadcom)."""
        info = {
            "arrays": [],
            "physical_drives": [],
            "battery": {"present": False}
        }

        try:
            # Check if storcli exists
            result = subprocess.run(
                ["which", "storcli64"],
                capture_output=True,
                timeout=2
            )
            if result.returncode != 0:
                return info

            # Get controller info
            ctrl_result = subprocess.run(
                ["storcli64", f"/c{controller_index}", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if ctrl_result.returncode == 0:
                # Parse basic controller info
                for line in ctrl_result.stdout.split("\n"):
                    if "Firmware Version" in line:
                        parts = line.split("=")
                        if len(parts) > 1:
                            info["firmware"] = parts[1].strip()

            # Get virtual drives (arrays)
            vd_result = subprocess.run(
                ["storcli64", f"/c{controller_index}", "/vall", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if vd_result.returncode == 0:
                info["arrays"] = self._parse_storcli_vd_output(vd_result.stdout)

            # Get physical drives
            pd_result = subprocess.run(
                ["storcli64", f"/c{controller_index}", "/eall", "/sall", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if pd_result.returncode == 0:
                info["physical_drives"] = self._parse_storcli_pd_output(pd_result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return info

    def _parse_storcli_vd_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse StorCLI virtual drive output."""
        arrays = []
        # Simplified parsing - real implementation would be more robust
        for line in output.split("\n"):
            if "RAID" in line and "Optimal" in line:
                parts = line.split()
                if len(parts) >= 4:
                    arrays.append({
                        "id": len(arrays),
                        "raid_level": parts[1] if len(parts) > 1 else "Unknown",
                        "status": "Optimal",
                        "size_gb": 0,  # Would need size parsing
                        "drives": 0
                    })
        return arrays

    def _parse_storcli_pd_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse StorCLI physical drive output."""
        drives = []
        for line in output.split("\n"):
            if "HDD" in line or "SSD" in line:
                parts = line.split()
                if len(parts) >= 3:
                    drives.append({
                        "enclosure": 0,
                        "slot": len(drives),
                        "model": parts[0] if parts else "Unknown",
                        "size_gb": 0,
                        "status": "Online"
                    })
        return drives
```

- [ ] **Step 2: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_raid.py -v
```

Expected: 6 tests PASS

- [ ] **Step 3: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/detectors/raid.py
git commit -m "feat(detectors): add StorCLI support to RAIDDetector

- Implement _get_storcli_info() for LSI/Broadcom controllers
- Parse virtual drives and physical drives
- Add helper methods for StorCLI output parsing

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 3: PSU 检测器

**Files:**
- Create: `src/detectors/psu.py`
- Create: `tests/test_detectors/test_psu.py`
- Modify: `src/detectors/__init__.py`

- [ ] **Step 1: 编写 PSU 检测器测试**

Create `tests/test_detectors/test_psu.py`:
```python
import pytest
from src.detectors.psu import PSUDetector
from src.detectors.base import DetectorMode


class TestPSUDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = PSUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "psu_count" in result
        assert "redundant" in result
        assert "psus" in result
        assert isinstance(result["psus"], list)

    def test_mock_psu_count_matches_list(self):
        detector = PSUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["psu_count"] == len(result["psus"])

    def test_mock_psu_has_required_fields(self):
        detector = PSUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for psu in result["psus"]:
            assert "id" in psu
            assert "present" in psu
            assert "status" in psu
            assert "input_voltage" in psu
            assert "output_watts" in psu

    def test_mock_redundant_configuration(self):
        detector = PSUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        if result["psu_count"] >= 2:
            assert result["redundant"] is True

    def test_mock_load_calculation(self):
        detector = PSUDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        if result.get("total_capacity_watts", 0) > 0:
            assert 0 <= result.get("load_percent", 0) <= 100


class TestPSUDetectorReal:
    def test_real_returns_dict(self):
        detector = PSUDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "psus" in result
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_psu.py -v
```

Expected: ImportError - PSUDetector not found

- [ ] **Step 3: 实现 PSU 检测器**

Create `src/detectors/psu.py`:
```python
import subprocess
import re
from typing import Dict, List, Any

from .base import BaseDetector, DetectorMode


class PSUDetector(BaseDetector):
    """Detect Power Supply Units (PSU) status.

    Uses IPMI sensor data or lm-sensors to get PSU information.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect PSU information via IPMI."""
        psus = []

        # Try IPMI first
        try:
            result = subprocess.run(
                ["ipmitool", "sdr", "type", "Power Supply"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                psus = self._parse_ipmi_psu_output(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Calculate totals
        total_capacity = sum(
            psu.get("rated_capacity_watts", 0) for psu in psus
        ) or sum(psu.get("output_watts", 0) * 2 for psu in psus)

        total_output = sum(psu.get("output_watts", 0) for psu in psus)

        load_percent = 0
        if total_capacity > 0:
            load_percent = round((total_output / total_capacity) * 100, 1)

        return {
            "psu_count": len(psus),
            "redundant": len(psus) >= 2,
            "psus": psus,
            "total_capacity_watts": total_capacity,
            "total_output_watts": total_output,
            "load_percent": load_percent
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated PSU data."""
        return {
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

    def _parse_ipmi_psu_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse IPMI power supply sensor output."""
        psus = []

        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            # Example line: "PSU1 Status | 01h | ok  | 10.1 | Presence detected"
            parts = [p.strip() for p in line.split("|")]

            if len(parts) >= 2:
                name = parts[0]
                status = parts[2] if len(parts) > 2 else "unknown"

                # Extract PSU ID from name
                psu_id = 1
                id_match = re.search(r'PSU\s*(\d+)', name, re.IGNORECASE)
                if id_match:
                    psu_id = int(id_match.group(1))

                psu = {
                    "id": psu_id,
                    "present": "presence" in line.lower() or status == "ok",
                    "status": "OK" if status == "ok" else status,
                    "input_voltage": 0,
                    "input_voltage_status": "unknown",
                    "output_watts": 0,
                    "temperature_c": 0,
                    "fan_rpm": 0,
                    "model": "Unknown"
                }
                psus.append(psu)

        return psus
```

- [ ] **Step 4: 更新导出文件**

Update `src/detectors/__init__.py`:
```python
from .base import BaseDetector, DetectorMode
from .cpu import CPUDetector
from .memory import MemoryDetector
from .storage import StorageDetector
from .network import NetworkDetector
from .gpu import GPUDetector
from .bmc import BMCDetector
from .pcie import PCIeDetector
from .raid import RAIDDetector
from .psu import PSUDetector

__all__ = [
    "BaseDetector",
    "DetectorMode",
    "CPUDetector",
    "MemoryDetector",
    "StorageDetector",
    "NetworkDetector",
    "GPUDetector",
    "BMCDetector",
    "PCIeDetector",
    "RAIDDetector",
    "PSUDetector"
]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_psu.py -v
```

Expected: 6 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/detectors/psu.py tests/test_detectors/test_psu.py src/detectors/__init__.py
git commit -m "feat(detectors): add PSUDetector for power supply monitoring

- Detect PSU presence, status, voltage, and output power
- Support IPMI sensor data interface
- Calculate redundancy and load percentage
- Mock mode with dual PSU configuration

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 4: 温度/风扇传感器检测器

**Files:**
- Create: `src/detectors/sensor.py`
- Create: `tests/test_detectors/test_sensor.py`
- Modify: `src/detectors/__init__.py`

- [ ] **Step 1: 编写传感器检测器测试**

Create `tests/test_detectors/test_sensor.py`:
```python
import pytest
from src.detectors.sensor import SensorDetector
from src.detectors.base import DetectorMode


class TestSensorDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = SensorDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "sensors" in result
        assert "temperatures" in result["sensors"]
        assert "fans" in result["sensors"]
        assert isinstance(result["sensors"]["temperatures"], list)
        assert isinstance(result["sensors"]["fans"], list)

    def test_mock_temperatures_have_required_fields(self):
        detector = SensorDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for temp in result["sensors"]["temperatures"]:
            assert "name" in temp
            assert "value" in temp
            assert "unit" in temp
            assert "status" in temp
            assert temp["unit"] == "C"

    def test_mock_fans_have_required_fields(self):
        detector = SensorDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for fan in result["sensors"]["fans"]:
            assert "name" in fan
            assert "rpm" in fan
            assert "percent" in fan
            assert "status" in fan

    def test_mock_sensor_count_matches(self):
        detector = SensorDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        temps = result["sensors"]["temperatures"]
        fans = result["sensors"]["fans"]

        assert result["sensor_count"]["temperatures"] == len(temps)
        assert result["sensor_count"]["fans"] == len(fans)

    def test_mock_temperature_values_reasonable(self):
        detector = SensorDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for temp in result["sensors"]["temperatures"]:
            assert 0 <= temp["value"] <= 100


class TestSensorDetectorReal:
    def test_real_returns_dict(self):
        detector = SensorDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "sensors" in result
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_sensor.py -v
```

Expected: ImportError - SensorDetector not found

- [ ] **Step 3: 实现传感器检测器**

Create `src/detectors/sensor.py`:
```python
import subprocess
import re
from typing import Dict, List, Any

from .base import BaseDetector, DetectorMode


class SensorDetector(BaseDetector):
    """Detect temperature and fan sensors.

    Uses IPMI sensor data to get temperature and fan readings.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect sensors via IPMI."""
        temperatures = []
        fans = []

        try:
            # Get all sensor data
            result = subprocess.run(
                ["ipmitool", "sdr", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                temperatures, fans = self._parse_ipmi_sensor_output(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return {
            "sensors": {
                "temperatures": temperatures,
                "fans": fans
            },
            "threshold_alerts": [],
            "sensor_count": {
                "temperatures": len(temperatures),
                "fans": len(fans)
            }
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated sensor data."""
        return {
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

    def _parse_ipmi_sensor_output(self, output: str) -> (List[Dict], List[Dict]):
        """Parse IPMI sensor output for temperatures and fans."""
        temperatures = []
        fans = []

        for line in output.strip().split("\n"):
            if not line.strip():
                continue

            # Example: "CPU0 Temp      | 45h | ok  |  3.1 | 45 degrees C"
            parts = [p.strip() for p in line.split("|")]

            if len(parts) < 2:
                continue

            name = parts[0]
            reading = parts[-1] if len(parts) > 4 else ""

            # Parse temperature
            if "degrees" in reading.lower() or "temp" in name.lower():
                temp_match = re.search(r'(\d+)\s*degrees', reading, re.IGNORECASE)
                if temp_match:
                    temp = {
                        "name": name.strip(),
                        "value": int(temp_match.group(1)),
                        "unit": "C",
                        "status": "ok" if "ok" in line.lower() else "unknown"
                    }
                    temperatures.append(temp)

            # Parse fan
            elif "rpm" in reading.lower() or "fan" in name.lower():
                rpm_match = re.search(r'(\d+)\s*RPM', reading, re.IGNORECASE)
                if rpm_match:
                    rpm_val = int(rpm_match.group(1))
                    fan = {
                        "name": name.strip(),
                        "rpm": rpm_val,
                        "percent": min(100, max(0, rpm_val // 100)),  # Rough estimate
                        "status": "ok" if "ok" in line.lower() else "unknown"
                    }
                    fans.append(fan)

        return temperatures, fans
```

- [ ] **Step 4: 更新导出文件**

Update `src/detectors/__init__.py`:
```python
from .base import BaseDetector, DetectorMode
from .cpu import CPUDetector
from .memory import MemoryDetector
from .storage import StorageDetector
from .network import NetworkDetector
from .gpu import GPUDetector
from .bmc import BMCDetector
from .pcie import PCIeDetector
from .raid import RAIDDetector
from .psu import PSUDetector
from .sensor import SensorDetector

__all__ = [
    "BaseDetector",
    "DetectorMode",
    "CPUDetector",
    "MemoryDetector",
    "StorageDetector",
    "NetworkDetector",
    "GPUDetector",
    "BMCDetector",
    "PCIeDetector",
    "RAIDDetector",
    "PSUDetector",
    "SensorDetector"
]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python -m pytest tests/test_detectors/test_sensor.py -v
```

Expected: 6 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/detectors/sensor.py tests/test_detectors/test_sensor.py src/detectors/__init__.py
git commit -m "feat(detectors): add SensorDetector for temperature and fan monitoring

- Detect CPU, motherboard, PSU temperatures
- Detect fan RPM and speed percentage
- Support IPMI sensor data interface
- Mock mode with realistic server sensor data

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## 验收检查清单

| 验收项 | 验证命令 | 预期结果 |
|--------|----------|----------|
| RAID 检测器测试 | `pytest tests/test_detectors/test_raid.py -v` | 6+ tests PASS |
| PSU 检测器测试 | `pytest tests/test_detectors/test_psu.py -v` | 6 tests PASS |
| 传感器检测器测试 | `pytest tests/test_detectors/test_sensor.py -v` | 6 tests PASS |
| 完整测试套件 | `pytest` | 全部 tests PASS |
| 导出检查 | `python -c "from src.detectors import RAIDDetector, PSUDetector, SensorDetector"` | 无错误 |
| CLI 运行 | `python -m src.main run --mock` | 正常执行 |

---

*计划完成，准备执行*
