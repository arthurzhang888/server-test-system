# 安全与系统硬件检测器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 TPM、BIOS/UEFI、USB 三个安全与系统硬件检测器，支持 mock/real 模式切换

**Architecture:** 遵循现有检测器架构，继承 BaseDetector，实现 detect_real() 和 detect_mock() 方法。TPM 使用 sysfs 接口，BIOS 使用 dmidecode，USB 使用 lsusb。

**Tech Stack:** Python 3.9+, subprocess, sysfs parsing

---

## 文件结构总览

| 文件路径 | 职责 |
|----------|------|
| `src/detectors/tpm.py` | TPM 检测器（版本、状态、PCR） |
| `src/detectors/bios.py` | BIOS/UEFI 检测器（版本、安全启动） |
| `src/detectors/usb.py` | USB 检测器（控制器、设备） |
| `tests/test_detectors/test_tpm.py` | TPM 检测器测试 |
| `tests/test_detectors/test_bios.py` | BIOS 检测器测试 |
| `tests/test_detectors/test_usb.py` | USB 检测器测试 |

---

## Task 1: TPM 检测器

**Files:**
- Create: `src/detectors/tpm.py`
- Create: `tests/test_detectors/test_tpm.py`
- Modify: `src/detectors/__init__.py`

- [ ] **Step 1: 编写 TPM 检测器测试**

Create `tests/test_detectors/test_tpm.py`:
```python
import pytest
from src.detectors.tpm import TPMDetector
from src.detectors.base import DetectorMode


class TestTPMDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = TPMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "present" in result
        assert "version" in result
        assert "status" in result

    def test_mock_present_is_boolean(self):
        detector = TPMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["present"], bool)

    def test_mock_version_format(self):
        detector = TPMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        if result["present"]:
            assert result["version"] in ["1.2", "2.0"]

    def test_mock_has_vendor(self):
        detector = TPMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        if result["present"]:
            assert "vendor" in result
            assert isinstance(result["vendor"], str)

    def test_mock_pcr_banks_is_list(self):
        detector = TPMDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        if result["present"]:
            assert "pcr_banks" in result
            assert isinstance(result["pcr_banks"], list)


class TestTPMDetectorReal:
    def test_real_returns_dict(self):
        detector = TPMDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "present" in result
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_detectors/test_tpm.py -v
```

Expected: ImportError - TPMDetector not found

- [ ] **Step 3: 实现 TPM 检测器**

Create `src/detectors/tpm.py`:
```python
import os
import subprocess
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class TPMDetector(BaseDetector):
    """Detect Trusted Platform Module (TPM) information.

    Supports TPM 1.2 and 2.0 via sysfs interface.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect TPM via sysfs."""
        tpm_path = "/sys/class/tpm/tpm0"

        if not os.path.exists(tpm_path):
            return {"present": False}

        info = {
            "present": True,
            "version": self._detect_version(tpm_path),
            "vendor": "Unknown",
            "firmware_version": "Unknown",
            "status": "unknown",
            "ek_certificate_present": False,
            "pcr_banks": [],
            "pcr_count": 0,
            "nvram_size_kb": 0,
            "clear_control": "unknown"
        }

        # Read TPM version
        try:
            with open(f"{tpm_path}/tpm_version_major", "r") as f:
                major = f.read().strip()
                info["version"] = f"{major}.0" if major == "2" else "1.2"
        except (IOError, FileNotFoundError):
            pass

        # Read device info if available (vendor, fw version)
        caps_path = f"{tpm_path}/device/caps"
        if os.path.exists(caps_path):
            try:
                with open(caps_path, "r") as f:
                    for line in f:
                        if "Manufacturer" in line:
                            parts = line.split(":")
                            if len(parts) > 1:
                                info["vendor"] = parts[1].strip()
            except (IOError, FileNotFoundError):
                pass

        # Try to get PCR info via tpm2_getcap if available
        info["pcr_banks"], info["pcr_count"] = self._get_pcr_info()

        # Check for EK certificate
        info["ek_certificate_present"] = os.path.exists(f"{tpm_path}/device/endorsement_key")

        return info

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated TPM 2.0 data."""
        return {
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

    def _detect_version(self, tpm_path: str) -> str:
        """Detect TPM version from sysfs."""
        try:
            version_path = f"{tpm_path}/tpm_version_major"
            if os.path.exists(version_path):
                with open(version_path, "r") as f:
                    major = f.read().strip()
                    return f"{major}.0" if major == "2" else "1.2"

            # Fallback: check for tpm2 specific files
            if os.path.exists(f"{tpm_path}/device/tpm2"):
                return "2.0"

        except (IOError, FileNotFoundError):
            pass

        return "unknown"

    def _get_pcr_info(self) -> (List[str], int):
        """Get PCR bank algorithms and count."""
        banks = []
        pcr_count = 0

        # Try tpm2_getcap if available
        try:
            result = subprocess.run(
                ["tpm2_getcap", "pcrs"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                if "sha256" in output:
                    banks.append("sha256")
                if "sha384" in output:
                    banks.append("sha384")
                if "sha1" in output:
                    banks.append("sha1")

                # Count PCRs from output
                pcr_count = output.count("pcr_")
                if pcr_count == 0:
                    pcr_count = 24  # Default for TPM 2.0

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Default values if tpm2_getcap not available
        if not banks:
            banks = ["sha256"]
        if pcr_count == 0:
            pcr_count = 24

        return banks, pcr_count
```

- [ ] **Step 4: 更新导出文件**

Update `src/detectors/__init__.py`:
```python
from .base import BaseDetector, DetectorMode
from .bmc import BMCDetector
from .cpu import CPUDetector
from .gpu import GPUDetector
from .memory import MemoryDetector
from .network import NetworkDetector
from .pcie import PCIeDetector
from .psu import PSUDetector
from .raid import RAIDDetector
from .sensor import SensorDetector
from .storage import StorageDetector
from .tpm import TPMDetector

__all__ = [
    "BaseDetector",
    "DetectorMode",
    "BMCDetector",
    "CPUDetector",
    "GPUDetector",
    "MemoryDetector",
    "NetworkDetector",
    "PCIeDetector",
    "PSUDetector",
    "RAIDDetector",
    "SensorDetector",
    "StorageDetector",
    "TPMDetector"
]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_detectors/test_tpm.py -v
```

Expected: 6 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/detectors/tpm.py tests/test_detectors/test_tpm.py src/detectors/__init__.py
git commit -m "feat(detectors): add TPMDetector for Trusted Platform Module

- Detect TPM 1.2 and 2.0 via sysfs
- Support PCR banks detection via tpm2_getcap
- Check EK certificate presence
- Mock mode with Intel TPM 2.0 data

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 2: BIOS/UEFI 检测器

**Files:**
- Create: `src/detectors/bios.py`
- Create: `tests/test_detectors/test_bios.py`
- Modify: `src/detectors/__init__.py`

- [ ] **Step 1: 编写 BIOS 检测器测试**

Create `tests/test_detectors/test_bios.py`:
```python
import pytest
from src.detectors.bios import BIOSDetector
from src.detectors.base import DetectorMode


class TestBIOSDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = BIOSDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "type" in result
        assert "vendor" in result
        assert "version" in result
        assert "date" in result

    def test_mock_type_is_valid(self):
        detector = BIOSDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert result["type"] in ["UEFI", "Legacy BIOS"]

    def test_mock_secure_boot_structure(self):
        detector = BIOSDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "secure_boot" in result
        assert "supported" in result["secure_boot"]
        assert "enabled" in result["secure_boot"]

    def test_mock_characteristics_is_list(self):
        detector = BIOSDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert "characteristics" in result
        assert isinstance(result["characteristics"], list)

    def test_mock_system_info_present(self):
        detector = BIOSDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert "system_serial" in result
        assert "system_uuid" in result


class TestBIOSDetectorReal:
    def test_real_returns_dict(self):
        detector = BIOSDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "type" in result
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_detectors/test_bios.py -v
```

Expected: ImportError - BIOSDetector not found

- [ ] **Step 3: 实现 BIOS 检测器**

Create `src/detectors/bios.py`:
```python
import os
import re
import subprocess
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class BIOSDetector(BaseDetector):
    """Detect BIOS/UEFI firmware information.

    Uses dmidecode or sysfs to gather BIOS, system, and secure boot info.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect BIOS info via dmidecode and sysfs."""
        info = {
            "type": "Unknown",
            "vendor": "Unknown",
            "version": "Unknown",
            "date": "Unknown",
            "rom_size_mb": 0,
            "characteristics": [],
            "secure_boot": {
                "supported": False,
                "enabled": False,
                "mode": "unknown"
            },
            "boot_mode": "unknown",
            "system_serial": "Unknown",
            "system_uuid": "Unknown",
            "sku_number": "Unknown",
            "family": "Unknown"
        }

        # Try sysfs first (no root required)
        dmi_path = "/sys/class/dmi/id"
        if os.path.exists(dmi_path):
            info["vendor"] = self._read_dmi_file(f"{dmi_path}/bios_vendor")
            info["version"] = self._read_dmi_file(f"{dmi_path}/bios_version")
            info["date"] = self._read_dmi_file(f"{dmi_path}/bios_date")
            info["system_serial"] = self._read_dmi_file(f"{dmi_path}/product_serial")
            info["system_uuid"] = self._read_dmi_file(f"{dmi_path}/product_uuid")
            info["sku_number"] = self._read_dmi_file(f"{dmi_path}/product_sku")
            info["family"] = self._read_dmi_file(f"{dmi_path}/product_family")

        # Try dmidecode for more details
        dmi_info = self._get_dmidecode_info()
        info.update(dmi_info)

        # Detect UEFI vs Legacy and Secure Boot
        info["boot_mode"] = self._detect_boot_mode()
        info["secure_boot"] = self._detect_secure_boot()
        info["type"] = "UEFI" if info["boot_mode"] == "UEFI" else "Legacy BIOS"

        return info

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated UEFI data."""
        return {
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

    def _read_dmi_file(self, path: str) -> str:
        """Read DMI file from sysfs."""
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    return f.read().strip()
        except (IOError, FileNotFoundError, PermissionError):
            pass
        return "Unknown"

    def _get_dmidecode_info(self) -> Dict[str, Any]:
        """Get BIOS info via dmidecode."""
        info = {
            "characteristics": [],
            "rom_size_mb": 0
        }

        try:
            result = subprocess.run(
                ["dmidecode", "-t", "0,1"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                output = result.stdout

                # Parse characteristics
                if "ACPI" in output or "is supported" in output:
                    info["characteristics"].append("ACPI")
                if "USB Legacy" in output:
                    info["characteristics"].append("USB Legacy")
                if "UEFI" in output:
                    info["characteristics"].append("UEFI Boot")
                if "Secure Boot" in output:
                    info["characteristics"].append("Secure Boot")

                # Parse ROM size
                size_match = re.search(r'ROM Size: (\d+)\s*(kB|MB)', output, re.IGNORECASE)
                if size_match:
                    size = int(size_match.group(1))
                    unit = size_match.group(2).lower()
                    info["rom_size_mb"] = size if unit == "mb" else size // 1024

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return info

    def _detect_boot_mode(self) -> str:
        """Detect UEFI or Legacy boot mode."""
        # Check for EFI vars
        if os.path.exists("/sys/firmware/efi"):
            return "UEFI"

        # Check efivars if mounted
        if os.path.exists("/sys/firmware/efi/efivars"):
            return "UEFI"

        return "Legacy"

    def _detect_secure_boot(self) -> Dict[str, Any]:
        """Detect Secure Boot status."""
        secure_boot = {
            "supported": False,
            "enabled": False,
            "mode": "unknown"
        }

        # Check SecureBoot variable
        sb_path = "/sys/firmware/efi/efivars/SecureBoot-*"
        try:
            import glob
            sb_files = glob.glob(sb_path)
            if sb_files:
                secure_boot["supported"] = True
                try:
                    with open(sb_files[0], "rb") as f:
                        data = f.read()
                        # SecureBoot variable is 5 bytes: 4 byte attr + 1 byte value
                        if len(data) >= 5:
                            secure_boot["enabled"] = data[4] == 1
                except (IOError, PermissionError):
                    pass

        except Exception:
            pass

        return secure_boot
```

- [ ] **Step 4: 更新导出文件**

Update `src/detectors/__init__.py`:
```python
from .base import BaseDetector, DetectorMode
from .bios import BIOSDetector
from .bmc import BMCDetector
from .cpu import CPUDetector
from .gpu import GPUDetector
from .memory import MemoryDetector
from .network import NetworkDetector
from .pcie import PCIeDetector
from .psu import PSUDetector
from .raid import RAIDDetector
from .sensor import SensorDetector
from .storage import StorageDetector
from .tpm import TPMDetector

__all__ = [
    "BaseDetector",
    "DetectorMode",
    "BIOSDetector",
    "BMCDetector",
    "CPUDetector",
    "GPUDetector",
    "MemoryDetector",
    "NetworkDetector",
    "PCIeDetector",
    "PSUDetector",
    "RAIDDetector",
    "SensorDetector",
    "StorageDetector",
    "TPMDetector"
]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_detectors/test_bios.py -v
```

Expected: 6 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/detectors/bios.py tests/test_detectors/test_bios.py src/detectors/__init__.py
git commit -m "feat(detectors): add BIOSDetector for firmware information

- Detect BIOS/UEFI version, vendor, date via sysfs/dmidecode
- Secure Boot status detection
- Boot mode detection (UEFI/Legacy)
- System serial, UUID, SKU detection
- Mock mode with Dell PowerEdge UEFI data

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## Task 3: USB 检测器

**Files:**
- Create: `src/detectors/usb.py`
- Create: `tests/test_detectors/test_usb.py`
- Modify: `src/detectors/__init__.py`

- [ ] **Step 1: 编写 USB 检测器测试**

Create `tests/test_detectors/test_usb.py`:
```python
import pytest
from src.detectors.usb import USBDetector
from src.detectors.base import DetectorMode


class TestUSBDetectorMock:
    def test_mock_returns_valid_structure(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert "controllers" in result
        assert "devices" in result
        assert "controller_count" in result
        assert "device_count" in result

    def test_mock_controllers_is_list(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["controllers"], list)

    def test_mock_devices_is_list(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()
        assert isinstance(result["devices"], list)

    def test_mock_controller_has_required_fields(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for ctrl in result["controllers"]:
            assert "bus" in ctrl
            assert "id" in ctrl
            assert "vendor" in ctrl
            assert "product" in ctrl
            assert "speed" in ctrl

    def test_mock_device_has_required_fields(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        for dev in result["devices"]:
            assert "bus" in dev
            assert "device" in dev
            assert "id" in dev
            assert "vendor" in dev
            assert "class" in dev

    def test_mock_counts_match_lists(self):
        detector = USBDetector(mode=DetectorMode.MOCK)
        result = detector.detect()

        assert result["controller_count"] == len(result["controllers"])
        assert result["device_count"] == len(result["devices"])


class TestUSBDetectorReal:
    def test_real_returns_dict(self):
        detector = USBDetector(mode=DetectorMode.REAL)
        result = detector.detect()
        assert isinstance(result, dict)
        assert "controllers" in result
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_detectors/test_usb.py -v
```

Expected: ImportError - USBDetector not found

- [ ] **Step 3: 实现 USB 检测器**

Create `src/detectors/usb.py`:
```python
import subprocess
import re
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class USBDetector(BaseDetector):
    """Detect USB controllers and connected devices.

    Uses lsusb to gather USB bus, controller, and device information.
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect USB via lsusb."""
        controllers = []
        devices = []

        try:
            result = subprocess.run(
                ["lsusb"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                controllers, devices = self._parse_lsusb_output(result.stdout)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return {
            "controllers": controllers,
            "devices": devices,
            "controller_count": len(controllers),
            "device_count": len(devices)
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated USB data."""
        return {
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

    def _parse_lsusb_output(self, output: str) -> (List[Dict], List[Dict]):
        """Parse lsusb output into controllers and devices."""
        controllers = []
        devices = []

        for line in output.strip().split("\n"):
            # Parse: Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
            match = re.match(
                r'Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+([0-9a-f]{4}):([0-9a-f]{4})\s+(.+)',
                line,
                re.IGNORECASE
            )

            if match:
                bus = int(match.group(1))
                device = int(match.group(2))
                vendor_id = match.group(3).lower()
                product_id = match.group(4).lower()
                name = match.group(5).strip()

                # Parse vendor and product from name
                parts = name.split(" ", 1)
                vendor = parts[0] if parts else "Unknown"
                product = parts[1] if len(parts) > 1 else "Unknown"

                usb_id = f"{vendor_id}:{product_id}"

                # Determine if controller (root hub) or device
                if "root hub" in name.lower():
                    # Estimate USB version from product ID
                    usb_version = "2.0"
                    speed = "480M"
                    if product_id == "0003":
                        usb_version = "3.0"
                        speed = "5000M"
                    elif product_id == "0004":
                        usb_version = "3.1"
                        speed = "10000M"

                    controllers.append({
                        "bus": bus,
                        "id": usb_id,
                        "vendor": vendor,
                        "product": product,
                        "speed": speed,
                        "usb_version": usb_version
                    })
                else:
                    # Regular USB device
                    # Estimate speed (would need lsusb -v for accurate speed)
                    device_class = self._guess_device_class(name)

                    devices.append({
                        "bus": bus,
                        "device": device,
                        "id": usb_id,
                        "vendor": vendor,
                        "product": product,
                        "speed": "Unknown",  # Would need detailed query
                        "class": device_class,
                        "connected": True
                    })

        return controllers, devices

    def _guess_device_class(self, name: str) -> str:
        """Guess device class from product name."""
        name_lower = name.lower()

        if any(kw in name_lower for kw in ["keyboard", "mouse", "hid"]):
            return "HID"
        elif any(kw in name_lower for kw in ["storage", "disk", "flash", "ssd"]):
            return "Mass Storage"
        elif any(kw in name_lower for kw in ["camera", "webcam", "video"]):
            return "Video"
        elif any(kw in name_lower for kw in ["audio", "sound", "headset", "mic"]):
            return "Audio"
        elif any(kw in name_lower for kw in ["ups", "battery", "power"]):
            return "Power"
        elif any(kw in name_lower for kw in ["ethernet", "network", "wifi", "wireless"]):
            return "Network"
        elif any(kw in name_lower for kw in ["bluetooth"]):
            return "Bluetooth"
        elif any(kw in name_lower for kw in ["hub"]):
            return "Hub"
        else:
            return "Unknown"
```

- [ ] **Step 4: 更新导出文件**

Update `src/detectors/__init__.py`:
```python
from .base import BaseDetector, DetectorMode
from .bios import BIOSDetector
from .bmc import BMCDetector
from .cpu import CPUDetector
from .gpu import GPUDetector
from .memory import MemoryDetector
from .network import NetworkDetector
from .pcie import PCIeDetector
from .psu import PSUDetector
from .raid import RAIDDetector
from .sensor import SensorDetector
from .storage import StorageDetector
from .tpm import TPMDetector
from .usb import USBDetector

__all__ = [
    "BaseDetector",
    "DetectorMode",
    "BIOSDetector",
    "BMCDetector",
    "CPUDetector",
    "GPUDetector",
    "MemoryDetector",
    "NetworkDetector",
    "PCIeDetector",
    "PSUDetector",
    "RAIDDetector",
    "SensorDetector",
    "StorageDetector",
    "TPMDetector",
    "USBDetector"
]
```

- [ ] **Step 5: 运行测试确认通过**

```bash
cd /Users/arthurzhang/dev/llm/server-master && python3 -m pytest tests/test_detectors/test_usb.py -v
```

Expected: 7 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/arthurzhang/dev/llm/server-master
git add src/detectors/usb.py tests/test_detectors/test_usb.py src/detectors/__init__.py
git commit -m "feat(detectors): add USBDetector for USB controllers and devices

- Detect USB controllers (root hubs) with version and speed
- Detect connected USB devices with vendor/product info
- Device class guessing from product names
- Mock mode with USB 2.0/3.0 controllers and sample devices

Co-Authored-by: qianfan-code-latest <noreply@anthropic.com>"
```

---

## 验收检查清单

| 验收项 | 验证命令 | 预期结果 |
|--------|----------|----------|
| TPM 检测器测试 | `pytest tests/test_detectors/test_tpm.py -v` | 6 tests PASS |
| BIOS 检测器测试 | `pytest tests/test_detectors/test_bios.py -v` | 6 tests PASS |
| USB 检测器测试 | `pytest tests/test_detectors/test_usb.py -v` | 7 tests PASS |
| 完整测试套件 | `pytest` | 全部 tests PASS |
| 导出检查 | `python -c "from src.detectors import TPMDetector, BIOSDetector, USBDetector"` | 无错误 |
| CLI 运行 | `python -m src.main run --mock` | 正常执行 |

---

*计划完成，准备执行*
