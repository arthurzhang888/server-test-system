"""Windows platform implementation using WMI and PowerShell."""

import subprocess
import os
from typing import Dict, List, Any, Optional

from .base import PlatformInterface


class WindowsPlatform(PlatformInterface):
    """Windows-specific platform implementation using WMI and PowerShell."""

    @property
    def name(self) -> str:
        return "windows"

    def execute_command(
        self,
        command: List[str],
        timeout: int = 30,
        capture_output: bool = True
    ) -> tuple[int, str, str]:
        """Execute command using subprocess on Windows."""
        try:
            # On Windows, use shell=True for built-in commands
            use_shell = command[0].lower() in ["powershell", "cmd", "wmic"]

            result = subprocess.run(
                command,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                shell=use_shell
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except FileNotFoundError:
            return -1, "", f"Command not found: {command[0]}"
        except Exception as e:
            return -1, "", str(e)

    def _run_powershell(self, script: str) -> tuple[int, str, str]:
        """Run PowerShell script and return output."""
        return self.execute_command(
            ["powershell", "-ExecutionPolicy", "Bypass", "-Command", script],
            timeout=60
        )

    def _run_wmic(self, alias: str, fields: str) -> List[Dict[str, str]]:
        """Run WMIC command and parse output."""
        returncode, stdout, _ = self.execute_command(
            ["wmic", alias, "get", fields, "/format:csv"]
        )

        results = []
        if returncode == 0:
            lines = stdout.strip().split("\n")
            if len(lines) >= 2:
                # First line after empty lines is header
                for line in lines[1:]:
                    line = line.strip()
                    if line and not line.startswith("Node,"):
                        parts = line.split(",")
                        if len(parts) > 1:
                            # Create dict from field names and values
                            # WMIC CSV format: Node,Field1,Field2,...
                            # Values: SERVERNAME,Value1,Value2,...
                            result = {}
                            for i, field in enumerate(fields.split(",")):
                                field = field.strip()
                                if i + 1 < len(parts):
                                    result[field] = parts[i + 1].strip()
                            if result:
                                results.append(result)

        return results

    def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU info using WMI."""
        info = {}

        # Use PowerShell for better output
        script = """
        Get-WmiObject Win32_Processor | ForEach-Object {
            [PSCustomObject]@{
                Name = $_.Name
                Cores = $_.NumberOfCores
                Threads = $_.NumberOfLogicalProcessors
                MaxClockSpeed = $_.MaxClockSpeed
                Manufacturer = $_.Manufacturer
                SocketCount = (Get-WmiObject Win32_Processor).Count
            }
        } | ConvertTo-Json
        """

        returncode, stdout, _ = self._run_powershell(script)

        if returncode == 0:
            try:
                import json
                data = json.loads(stdout)
                if isinstance(data, list) and data:
                    data = data[0]

                info["model"] = data.get("Name", "")
                info["cores"] = data.get("Cores", 0)
                info["threads"] = data.get("Threads", 0)
                info["frequency_mhz"] = data.get("MaxClockSpeed", 0)
                info["vendor"] = data.get("Manufacturer", "")
                info["cpu_count"] = data.get("SocketCount", 1)

            except json.JSONDecodeError:
                pass

        return info

    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory info using WMI."""
        info = {}

        script = """
        $total = (Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory
        $avail = (Get-WmiObject Win32_OperatingSystem).FreePhysicalMemory * 1024
        [PSCustomObject]@{
            TotalBytes = $total
            FreeBytes = $avail
            TotalKB = [math]::Floor($total / 1KB)
            FreeKB = [math]::Floor($avail / 1KB)
        } | ConvertTo-Json
        """

        returncode, stdout, _ = self._run_powershell(script)

        if returncode == 0:
            try:
                import json
                data = json.loads(stdout)
                info["total_kb"] = data.get("TotalKB", 0)
                info["free_kb"] = data.get("FreeKB", 0)
                info["total_bytes"] = data.get("TotalBytes", 0)
                info["free_bytes"] = data.get("FreeBytes", 0)
            except json.JSONDecodeError:
                pass

        return info

    def get_storage_devices(self) -> List[Dict[str, Any]]:
        """Get storage devices using WMI."""
        devices = []

        script = """
        Get-WmiObject Win32_DiskDrive | ForEach-Object {
            [PSCustomObject]@{
                DeviceID = $_.DeviceID
                Model = $_.Model
                Size = $_.Size
                MediaType = $_.MediaType
                InterfaceType = $_.InterfaceType
                SerialNumber = $_.SerialNumber
            }
        } | ConvertTo-Json
        """

        returncode, stdout, _ = self._run_powershell(script)

        if returncode == 0:
            try:
                import json
                data = json.loads(stdout)
                if not isinstance(data, list):
                    data = [data]

                for disk in data:
                    if disk:
                        size_bytes = disk.get("Size", 0)
                        size_gb = int(size_bytes) / (1024**3) if size_bytes else 0

                        devices.append({
                            "name": disk.get("DeviceID", "").replace("\\", "").replace(".", ""),
                            "model": disk.get("Model", ""),
                            "size": f"{size_gb:.0f}GB" if size_gb > 0 else "",
                            "serial": disk.get("SerialNumber", "").strip(),
                            "interface": disk.get("InterfaceType", ""),
                            "media_type": disk.get("MediaType", "")
                        })
            except (json.JSONDecodeError, ValueError):
                pass

        return devices

    def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """Get network interfaces using WMI."""
        interfaces = []

        script = """
        Get-WmiObject Win32_NetworkAdapter | Where-Object {
            $_.NetConnectionStatus -eq 2 -and $_.PhysicalAdapter -eq $true
        } | ForEach-Object {
            $config = $_.GetRelated('Win32_NetworkAdapterConfiguration')
            [PSCustomObject]@{
                Name = $_.Name
                MACAddress = $_.MACAddress
                Speed = $_.Speed
                AdapterType = $_.AdapterType
            }
        } | ConvertTo-Json
        """

        returncode, stdout, _ = self._run_powershell(script)

        if returncode == 0:
            try:
                import json
                data = json.loads(stdout)
                if not isinstance(data, list):
                    data = [data] if data else []

                for adapter in data:
                    if adapter:
                        speed = adapter.get("Speed", 0)
                        speed_mbps = int(speed) / 1000000 if speed else 0

                        interfaces.append({
                            "name": adapter.get("Name", ""),
                            "mac": adapter.get("MACAddress", ""),
                            "speed_mbps": speed_mbps,
                            "type": adapter.get("AdapterType", ""),
                            "state": "up"
                        })
            except json.JSONDecodeError:
                pass

        return interfaces

    def get_gpu_info(self) -> List[Dict[str, Any]]:
        """Get GPU information using WMI."""
        gpus = []

        script = """
        Get-WmiObject Win32_VideoController | ForEach-Object {
            [PSCustomObject]@{
                Name = $_.Name
                AdapterRAM = $_.AdapterRAM
                VideoProcessor = $_.VideoProcessor
                DriverVersion = $_.DriverVersion
            }
        } | ConvertTo-Json
        """

        returncode, stdout, _ = self._run_powershell(script)

        if returncode == 0:
            try:
                import json
                data = json.loads(stdout)
                if not isinstance(data, list):
                    data = [data] if data else []

                for gpu in data:
                    if gpu:
                        vram = gpu.get("AdapterRAM", 0)
                        vram_mb = int(vram) / (1024*1024) if vram else 0

                        name = gpu.get("Name", "")
                        vendor = "Unknown"
                        if "NVIDIA" in name.upper():
                            vendor = "NVIDIA"
                        elif "AMD" in name.upper() or "RADEON" in name.upper():
                            vendor = "AMD"
                        elif "INTEL" in name.upper():
                            vendor = "Intel"

                        gpus.append({
                            "vendor": vendor,
                            "name": name,
                            "memory_mb": int(vram_mb),
                            "driver": gpu.get("DriverVersion", "")
                        })
            except json.JSONDecodeError:
                pass

        return gpus

    def get_pci_devices(self) -> List[Dict[str, Any]]:
        """Get PCI devices using Win32_PnPEntity."""
        devices = []

        script = """
        Get-WmiObject Win32_PnPEntity | Where-Object {
            $_.PNPDeviceID -like "PCI*"
        } | ForEach-Object {
            [PSCustomObject]@{
                Name = $_.Name
                DeviceID = $_.DeviceID
                Manufacturer = $_.Manufacturer
                Status = $_.Status
            }
        } | ConvertTo-Json
        """

        returncode, stdout, _ = self._run_powershell(script)

        if returncode == 0:
            try:
                import json
                data = json.loads(stdout)
                if not isinstance(data, list):
                    data = [data] if data else []

                for device in data:
                    if device:
                        devices.append({
                            "name": device.get("Name", ""),
                            "device_id": device.get("DeviceID", ""),
                            "vendor": device.get("Manufacturer", ""),
                            "status": device.get("Status", "")
                        })
            except json.JSONDecodeError:
                pass

        return devices

    def get_usb_devices(self) -> List[Dict[str, Any]]:
        """Get USB devices using WMI."""
        devices = []

        script = """
        Get-WmiObject Win32_USBControllerDevice | ForEach-Object {
            [wmi]$_.Dependent
        } | Select-Object Name, DeviceID, Manufacturer | ConvertTo-Json
        """

        returncode, stdout, _ = self._run_powershell(script)

        if returncode == 0:
            try:
                import json
                data = json.loads(stdout)
                if not isinstance(data, list):
                    data = [data] if data else []

                for device in data:
                    if device:
                        devices.append({
                            "name": device.get("Name", ""),
                            "device_id": device.get("DeviceID", ""),
                            "vendor": device.get("Manufacturer", ""),
                            "vendor_id": "",
                            "product_id": ""
                        })
            except json.JSONDecodeError:
                pass

        return devices

    def get_dmi_info(self, dmi_type: int) -> Dict[str, str]:
        """Get SMBIOS/DMI info using WMI."""
        info = {}

        # Map DMI types to WMI classes
        wmi_classes = {
            0: "Win32_BIOS",
            1: "Win32_ComputerSystemProduct",
            2: "Win32_BaseBoard",
            3: "Win32_SystemEnclosure",
            4: "Win32_Processor",
        }

        wmi_class = wmi_classes.get(dmi_type)
        if not wmi_class:
            return info

        script = f"""
        Get-WmiObject {wmi_class} | Select-Object * | ConvertTo-Json
        """

        returncode, stdout, _ = self._run_powershell(script)

        if returncode == 0:
            try:
                import json
                data = json.loads(stdout)
                if isinstance(data, list) and data:
                    data = data[0]

                # Convert all properties to strings
                for key, value in data.items():
                    if value is not None:
                        info[key] = str(value)

            except json.JSONDecodeError:
                pass

        return info

    def read_sysctl(self, key: str) -> Optional[str]:
        """Read registry value (Windows equivalent of sysctl)."""
        # Map common sysctl keys to registry paths
        registry_map = {
            "hw.physmem": r"HKLM\HARDWARE\RESOURCEMAP\System Resources\Physical Memory",
        }

        reg_path = registry_map.get(key)
        if not reg_path:
            return None

        script = f"""
        try {{
            Get-ItemProperty -Path "Registry::{reg_path}" -ErrorAction Stop | Select-Object -First 1
        }} catch {{
            $null
        }}
        """

        returncode, stdout, _ = self._run_powershell(script)
        if returncode == 0 and stdout.strip():
            return stdout.strip()

        return None

    def path_exists(self, path: str) -> bool:
        """Check if path exists (Windows-style paths)."""
        # Convert forward slashes to backslashes
        path = path.replace("/", "\\")
        return os.path.exists(path)

    def read_file(self, path: str, default: str = "") -> str:
        """Read file contents on Windows."""
        try:
            path = path.replace("/", "\\")
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read().strip()
        except Exception:
            return default
