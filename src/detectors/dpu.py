"""DPU (Data Processing Unit) detector for NVIDIA BlueField BF3/BF4."""

import subprocess
import re
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

from .base import BaseDetector, DetectorMode


class DPUDetector(BaseDetector):
    """Detect NVIDIA BlueField DPU cards (BF3/BF4).

    DPU is a SmartNIC with integrated ARM cores, memory, and accelerators.
    BF3: BlueField-3 (ARM A78, 16 cores max, 200Gbps network)
    BF4: BlueField-4 (Next-gen, 400Gbps network)

    Detection methods:
    1. lspci - PCI device enumeration
    2. mstflint/mlxfwmanager - Mellanox firmware tools
    3. bf-reg - BlueField register access (on DPU)
    4. bfaux - BlueField auxiliary commands
    5. ip link / devlink - Network interface detection
    6. rshim - DPU console access (if available)
    """

    # Mellanox/NVIDIA DPU PCI IDs
    DPU_PCI_IDS = {
        # BlueField-3
        "0xa2dc": "BlueField-3",
        "0xa2dd": "BlueField-3",
        "0xa2d6": "BlueField-3",
        "0xa2d8": "BlueField-3",
        "0xa2d9": "BlueField-3",
        "0xa2da": "BlueField-3",
        "0xa2db": "BlueField-3",
        # BlueField-2 (for reference)
        "0xa2d2": "BlueField-2",
        "0xa2d3": "BlueField-2",
    }

    # BF4 PCI IDs (when available)
    BF4_PCI_IDS = {
        "0xa2f0": "BlueField-4",  # Placeholder
    }

    def detect_real(self) -> Dict[str, Any]:
        """Detect DPU via PCI and Mellanox tools."""
        devices = []

        # Method 1: PCI enumeration
        pci_devices = self._detect_pci_dpus()

        for pci_dev in pci_devices:
            # Enrich with firmware info
            firmware = self._get_firmware_info(pci_dev["pci_slot"])
            pci_dev.update(firmware)

            # Get network interfaces
            netdevs = self._get_netdev_info(pci_dev["pci_slot"])
            pci_dev["network_interfaces"] = netdevs

            # Get DPU mode (DPU vs NIC)
            mode = self._get_dpu_mode(pci_dev["pci_slot"])
            pci_dev["mode"] = mode

            # Get temperature/health if available
            health = self._get_health_info(pci_dev["pci_slot"])
            pci_dev["health"] = health

            devices.append(pci_dev)

        return {
            "present": len(devices) > 0,
            "device_count": len(devices),
            "devices": devices
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated DPU data."""
        return {
            "present": True,
            "device_count": 2,
            "devices": [
                {
                    "name": "mlx5_0",
                    "pci_slot": "0000:03:00.0",
                    "vendor": "NVIDIA",
                    "model": "BlueField-3",
                    "product_name": "MBF3H516A-CEEOT",
                    "device_id": "0xa2dc",
                    "firmware_version": "32.38.1000",
                    "bmc_version": "4.3.0",
                    "mode": "dpu",
                    "arm_cores": 8,
                    "arm_memory_gb": 16,
                    "emmc_storage_gb": 64,
                    "network_interfaces": [
                        {
                            "name": "p0",
                            "type": "physical",
                            "state": "up",
                            "speed": "200Gb/s",
                            "mac": "94:6d:ae:00:01:02"
                        },
                        {
                            "name": "p1",
                            "type": "physical",
                            "state": "up",
                            "speed": "200Gb/s",
                            "mac": "94:6d:ae:00:01:03"
                        },
                        {
                            "name": "ovsbr0",
                            "type": "ovs_bridge",
                            "state": "up",
                            "hw_offload": True
                        }
                    ],
                    "accelerators": {
                        "crypto": True,
                        "compression": True,
                        "regex": True
                    },
                    "health": {
                        "status": "healthy",
                        "temperature_c": 62,
                        "power_watts": 65,
                        "fan_rpm": 8000
                    },
                    "features": {
                        "sr_iov": True,
                        "virtio_net": True,
                        "rdma": True,
                        "dpdk": True
                    }
                },
                {
                    "name": "mlx5_1",
                    "pci_slot": "0000:04:00.0",
                    "vendor": "NVIDIA",
                    "model": "BlueField-3",
                    "product_name": "MBF3H516A-CEEOT",
                    "device_id": "0xa2dc",
                    "firmware_version": "32.38.1000",
                    "bmc_version": "4.3.0",
                    "mode": "dpu",
                    "arm_cores": 8,
                    "arm_memory_gb": 16,
                    "emmc_storage_gb": 64,
                    "network_interfaces": [
                        {
                            "name": "p0",
                            "type": "physical",
                            "state": "up",
                            "speed": "200Gb/s",
                            "mac": "94:6d:ae:00:02:02"
                        }
                    ],
                    "accelerators": {
                        "crypto": True,
                        "compression": True,
                    },
                    "health": {
                        "status": "healthy",
                        "temperature_c": 58,
                        "power_watts": 60
                    },
                    "features": {
                        "sr_iov": True,
                        "rdma": True
                    }
                }
            ]
        }

    def _detect_pci_dpus(self) -> List[Dict[str, Any]]:
        """Detect DPU via lspci."""
        devices = []

        try:
            result = subprocess.run(
                ["lspci", "-nn", "-D"],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    # Look for Mellanox/NVIDIA network controllers
                    if "Mellanox" in line or "NVIDIA" in line:
                        # Check if it's a DPU
                        for dev_id, model in {**self.DPU_PCI_IDS, **self.BF4_PCI_IDS}.items():
                            if dev_id.lower() in line.lower():
                                slot = line.split()[0]
                                devices.append({
                                    "name": f"dpu{len(devices)}",
                                    "pci_slot": slot,
                                    "vendor": "NVIDIA",
                                    "model": model,
                                    "device_id": dev_id,
                                    "raw_pci_info": line
                                })
                                break

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return devices

    def _get_firmware_info(self, pci_slot: str) -> Dict[str, Any]:
        """Get firmware version using mstflint or mlxfwmanager."""
        info = {
            "firmware_version": "unknown",
            "bmc_version": "unknown",
            "product_name": "unknown"
        }

        # Try mstflint
        try:
            result = subprocess.run(
                ["mstflint", "-d", pci_slot, "q"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "FW Version:" in line:
                        info["firmware_version"] = line.split(":")[1].strip()
                    elif "PSID" in line:
                        info["psid"] = line.split(":")[1].strip()

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Try mlxfwmanager for product name
        try:
            result = subprocess.run(
                ["mlxfwmanager", "--query", "-d", pci_slot],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Name:" in line and "BlueField" in line:
                        info["product_name"] = line.split(":")[1].strip()

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return info

    def _get_netdev_info(self, pci_slot: str) -> List[Dict[str, Any]]:
        """Get network interface information."""
        interfaces = []

        # Map PCI slot to netdev
        try:
            result = subprocess.run(
                ["devlink", "dev", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if pci_slot in line:
                        # Parse devlink output
                        parts = line.split()
                        if parts:
                            devlink_name = parts[0]
                            # Get port info
                            interfaces.extend(
                                self._get_devlink_ports(devlink_name)
                            )

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Fallback: look for mlx5 interfaces
        if not interfaces:
            interfaces = self._get_mlx5_interfaces()

        return interfaces

    def _get_devlink_ports(self, devlink_name: str) -> List[Dict[str, Any]]:
        """Get port info via devlink."""
        ports = []

        try:
            result = subprocess.run(
                ["devlink", "port", "show", devlink_name],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "netdev" in line:
                        # Parse: pci/0000:03:00.0/1: type eth netdev p0
                        match = re.search(r"netdev\s+(\w+)", line)
                        if match:
                            netdev = match.group(1)
                            port_info = {
                                "name": netdev,
                                "type": "physical",
                                "state": self._get_iface_state(netdev)
                            }

                            # Get speed
                            speed = self._get_iface_speed(netdev)
                            if speed:
                                port_info["speed"] = speed

                            # Get MAC
                            mac = self._get_iface_mac(netdev)
                            if mac:
                                port_info["mac"] = mac

                            ports.append(port_info)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return ports

    def _get_mlx5_interfaces(self) -> List[Dict[str, Any]]:
        """Get mlx5 network interfaces."""
        interfaces = []

        try:
            result = subprocess.run(
                ["ip", "-j", "link", "show"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                for iface in data:
                    name = iface.get("ifname", "")
                    # Look for mlx5 interfaces
                    if name.startswith("mlx") or name.startswith("p"):
                        # Check if it's a DPU interface
                        if self._is_dpu_interface(name):
                            interfaces.append({
                                "name": name,
                                "type": "physical",
                                "state": "up" if "UP" in iface.get("flags", []) else "down",
                                "mac": iface.get("address", "")
                            })

        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
            pass

        return interfaces

    def _is_dpu_interface(self, ifname: str) -> bool:
        """Check if interface belongs to DPU."""
        # Check device type via ethtool or sysfs
        try:
            device_path = Path(f"/sys/class/net/{ifname}/device")
            if device_path.exists():
                vendor = (device_path / "vendor").read_text().strip()
                device = (device_path / "device").read_text().strip()

                # Mellanox vendor ID
                if vendor.lower() in ["0x15b3", "15b3"]:
                    # Check if device ID is DPU
                    if device.lower() in [d.lower() for d in self.DPU_PCI_IDS.keys()]:
                        return True

        except (FileNotFoundError, PermissionError):
            pass

        return False

    def _get_iface_state(self, ifname: str) -> str:
        """Get interface state."""
        try:
            result = subprocess.run(
                ["ip", "link", "show", ifname],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                if "state UP" in result.stdout:
                    return "up"
                elif "state DOWN" in result.stdout:
                    return "down"

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return "unknown"

    def _get_iface_speed(self, ifname: str) -> Optional[str]:
        """Get interface speed via ethtool."""
        try:
            result = subprocess.run(
                ["ethtool", ifname],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Speed:" in line:
                        return line.split(":")[1].strip()

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return None

    def _get_iface_mac(self, ifname: str) -> Optional[str]:
        """Get interface MAC address."""
        try:
            addr_file = Path(f"/sys/class/net/{ifname}/address")
            if addr_file.exists():
                return addr_file.read_text().strip()

        except (FileNotFoundError, PermissionError):
            pass

        return None

    def _get_dpu_mode(self, pci_slot: str) -> str:
        """Detect DPU operating mode (DPU vs NIC)."""
        # Check if DPU is in SmartNIC mode or DPU mode
        # In DPU mode, ARM cores are active and running OS
        # In NIC mode, it behaves like a regular ConnectX card

        mode = "unknown"

        # Try to detect via rshim (DPU console access)
        try:
            rshim_path = Path("/dev/rshim0")
            if rshim_path.exists():
                # Rshim exists, likely in DPU mode
                mode = "dpu"

                # Try to get more info from rshim
                misc_file = Path("/dev/rshim0/misc")
                if misc_file.exists():
                    content = misc_file.read_text()
                    if "BOOT_MODE" in content:
                        # Parse boot mode
                        pass

        except (FileNotFoundError, PermissionError):
            pass

        # Check for DPU OS via mst status
        if mode == "unknown":
            try:
                result = subprocess.run(
                    ["mst", "status"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    # If we see DPU-specific devices, it's in DPU mode
                    if "rshim" in result.stdout.lower():
                        mode = "dpu"
                    elif "bluefield" in result.stdout.lower():
                        mode = "dpu"

            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # Default to nic mode if we can't detect
        if mode == "unknown":
            mode = "nic"

        return mode

    def _get_health_info(self, pci_slot: str) -> Dict[str, Any]:
        """Get DPU health information."""
        health = {
            "status": "unknown",
            "temperature_c": None,
            "power_watts": None
        }

        # Try to get temperature via hwmon
        try:
            hwmon_paths = list(Path("/sys/class/hwmon").glob("hwmon*"))
            for hwmon in hwmon_paths:
                name_file = hwmon / "name"
                if name_file.exists():
                    name = name_file.read_text().strip()
                    if "mlx" in name or "dpu" in name:
                        # Found DPU hwmon
                        temp_input = hwmon / "temp1_input"
                        if temp_input.exists():
                            temp = int(temp_input.read_text().strip()) / 1000
                            health["temperature_c"] = temp
                            health["status"] = "healthy" if temp < 85 else "warning"
                            break

        except (FileNotFoundError, PermissionError):
            pass

        # Try mstflint for health info
        try:
            result = subprocess.run(
                ["mstflint", "-d", pci_slot, "--health"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                if "healthy" in result.stdout.lower():
                    health["status"] = "healthy"

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return health

    def run_dpu_stress_test(self, pci_slot: str, duration: int = 60) -> Dict[str, Any]:
        """Run stress test on DPU.

        Tests:
        - ARM core load
        - Network throughput
        - Crypto acceleration
        - Temperature under load
        """
        return {
            "test_type": "dpu_stress",
            "pci_slot": pci_slot,
            "duration": duration,
            "status": "not_implemented",
            "message": "DPU stress test requires DPU SDK and tools installed on host or DPU"
        }

    def get_dpu_logs(self, pci_slot: str) -> List[str]:
        """Retrieve DPU system logs via rshim."""
        logs = []

        try:
            # Try to read from rshim console
            rshim_cons = Path("/dev/rshim0/console")
            if rshim_cons.exists():
                # This would need actual implementation
                # to read and parse the console
                logs.append("DPU console access available via /dev/rshim0/console")

        except (FileNotFoundError, PermissionError):
            pass

        return logs
