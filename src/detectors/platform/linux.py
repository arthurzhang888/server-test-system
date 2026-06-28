"""Linux platform implementation."""

import subprocess
import os
import re
from typing import Dict, List, Any, Optional

from .base import PlatformInterface


class LinuxPlatform(PlatformInterface):
    """Linux-specific platform implementation."""

    @property
    def name(self) -> str:
        return "linux"

    def execute_command(
        self,
        command: List[str],
        timeout: int = 30,
        capture_output: bool = True
    ) -> tuple[int, str, str]:
        """Execute command using subprocess."""
        try:
            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except FileNotFoundError:
            return -1, "", f"Command not found: {command[0]}"
        except Exception as e:
            return -1, "", str(e)

    def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU info from /proc/cpuinfo."""
        info = {}
        try:
            with open("/proc/cpuinfo", "r") as f:
                content = f.read()

            for line in content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    if key == "model name":
                        info["model"] = value
                    elif key == "cpu cores":
                        info["cores"] = int(value)
                    elif key == "siblings":
                        info["threads"] = int(value)
                    elif key == "cpu MHz":
                        info["frequency_mhz"] = float(value)
                    elif key == "vendor_id":
                        info["vendor"] = value

            # Count physical CPUs
            info["cpu_count"] = content.count("processor\t:")

        except Exception:
            pass

        return info

    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory info from /proc/meminfo."""
        info = {}
        try:
            with open("/proc/meminfo", "r") as f:
                content = f.read()

            for line in content.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip().split()[0]  # Get numeric value

                    if key == "MemTotal":
                        info["total_kb"] = int(value)
                    elif key == "MemFree":
                        info["free_kb"] = int(value)
                    elif key == "MemAvailable":
                        info["available_kb"] = int(value)

        except Exception:
            pass

        return info

    def get_storage_devices(self) -> List[Dict[str, Any]]:
        """Get storage devices using lsblk."""
        devices = []

        # Try lsblk
        returncode, stdout, _ = self.execute_command(
            ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MODEL,SERIAL,ROTA"]
        )

        if returncode == 0:
            try:
                import json
                data = json.loads(stdout)
                for device in data.get("blockdevices", []):
                    if device.get("type") == "disk":
                        devices.append({
                            "name": device.get("name", ""),
                            "size": device.get("size", ""),
                            "model": device.get("model", ""),
                            "serial": device.get("serial", ""),
                            "rotational": device.get("rota", True)
                        })
            except json.JSONDecodeError:
                pass

        return devices

    def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """Get network interfaces."""
        interfaces = []

        # Try ip command
        returncode, stdout, _ = self.execute_command(
            ["ip", "-j", "link", "show"]
        )

        if returncode == 0:
            try:
                import json
                data = json.loads(stdout)
                for iface in data:
                    name = iface.get("ifname", "")
                    if name.startswith("lo"):
                        continue

                    interfaces.append({
                        "name": name,
                        "mac": iface.get("address", ""),
                        "flags": iface.get("flags", []),
                        "state": "up" if "UP" in iface.get("flags", []) else "down"
                    })
            except json.JSONDecodeError:
                pass

        return interfaces

    def get_gpu_info(self) -> List[Dict[str, Any]]:
        """Get GPU information using various tools."""
        gpus = []

        # Try nvidia-smi
        returncode, stdout, _ = self.execute_command(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader"]
        )
        if returncode == 0:
            for line in stdout.strip().split("\n"):
                if "," in line:
                    parts = line.split(",")
                    gpus.append({
                        "vendor": "NVIDIA",
                        "name": parts[0].strip(),
                        "memory": parts[1].strip() if len(parts) > 1 else ""
                    })

        # Try rocm-smi for AMD
        returncode, stdout, _ = self.execute_command(
            ["rocm-smi", "--showproductname"]
        )
        if returncode == 0:
            for line in stdout.split("\n"):
                if "GPU" in line and ":" in line:
                    parts = line.split(":")
                    if len(parts) > 1:
                        gpus.append({
                            "vendor": "AMD",
                            "name": parts[1].strip(),
                            "memory": ""
                        })

        return gpus

    def get_pci_devices(self) -> List[Dict[str, Any]]:
        """Get PCI devices using lspci."""
        devices = []

        returncode, stdout, _ = self.execute_command(
            ["lspci", "-mm", "-nn"]
        )

        if returncode == 0:
            for line in stdout.split("\n"):
                # Parse lspci -mm output
                # Format: "Slot"	"Class"	"Vendor"	"Device"	"SVendor"	"SDevice"	"Rev"
                parts = line.split("\t")
                if len(parts) >= 4:
                    devices.append({
                        "slot": parts[0].strip('"'),
                        "class": parts[1].strip('"') if len(parts) > 1 else "",
                        "vendor": parts[2].strip('"') if len(parts) > 2 else "",
                        "device": parts[3].strip('"') if len(parts) > 3 else ""
                    })

        return devices

    def get_usb_devices(self) -> List[Dict[str, Any]]:
        """Get USB devices using lsusb."""
        devices = []

        returncode, stdout, _ = self.execute_command(["lsusb"])

        if returncode == 0:
            for line in stdout.split("\n"):
                if line.strip():
                    # Parse: Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
                    match = re.match(r"Bus (\d+) Device (\d+): ID ([0-9a-f]{4}):([0-9a-f]{4}) (.+)", line)
                    if match:
                        devices.append({
                            "bus": match.group(1),
                            "device": match.group(2),
                            "vendor_id": match.group(3),
                            "product_id": match.group(4),
                            "name": match.group(5).strip()
                        })

        return devices

    def get_dmi_info(self, dmi_type: int) -> Dict[str, str]:
        """Get DMI info using dmidecode."""
        info = {}

        returncode, stdout, _ = self.execute_command(
            ["dmidecode", "-t", str(dmi_type)]
        )

        if returncode == 0:
            current_key = None
            for line in stdout.split("\n"):
                line = line.rstrip()
                if not line.startswith("\t"):
                    continue

                line = line[1:]  # Remove leading tab

                if not line.startswith("\t") and ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    info[key] = value
                    current_key = key
                elif current_key and line.strip():
                    # Continuation of previous value
                    info[current_key] += " " + line.strip()

        return info

    def read_sysctl(self, key: str) -> Optional[str]:
        """Read sysctl value."""
        returncode, stdout, _ = self.execute_command(["sysctl", "-n", key])
        if returncode == 0:
            return stdout.strip()
        return None

    def path_exists(self, path: str) -> bool:
        """Check if path exists."""
        return os.path.exists(path)

    def read_file(self, path: str, default: str = "") -> str:
        """Read file contents."""
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except Exception:
            return default
