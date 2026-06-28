import os
import psutil
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class StorageDetector(BaseDetector):
    """Detect storage information - disk types, sizes, models."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect real storage information using psutil and os."""
        disks = self._detect_physical_disks()
        total_size = sum(disk["size_gb"] for disk in disks)

        return {
            "disks": disks,
            "total_size_gb": total_size,
            "disk_count": len(disks),
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated storage data for testing."""
        disks = [
            {"name": "nvme0n1", "type": "NVMe", "size_gb": 1920, "model": "Samsung PM1735"},
            {"name": "sda", "type": "SATA", "size_gb": 480, "model": "Intel SSD"},
        ]
        total_size = sum(disk["size_gb"] for disk in disks)

        return {
            "disks": disks,
            "total_size_gb": total_size,
            "disk_count": len(disks),
        }

    def _detect_physical_disks(self) -> List[Dict[str, Any]]:
        """Attempt to detect physical disk information."""
        disks = []

        try:
            # Get disk partitions to find mounted filesystems
            partitions = psutil.disk_partitions(all=False)

            # Track seen devices to avoid duplicates
            seen_devices = set()

            for partition in partitions:
                device = partition.device

                # Extract base device name (e.g., /dev/sda1 -> sda)
                base_device = self._get_base_device_name(device)

                if base_device and base_device not in seen_devices:
                    seen_devices.add(base_device)

                    # Detect disk type and size
                    disk_info = self._get_disk_info(device, base_device)
                    if disk_info:
                        disks.append(disk_info)

        except Exception:
            # Fallback: return info based on root filesystem only
            pass

        # If no disks detected, try fallback method
        if not disks:
            disks = self._fallback_disk_detection()

        return disks if disks else []

    def _get_base_device_name(self, device: str) -> str:
        """Extract base device name from partition device path."""
        # Remove /dev/ prefix
        if device.startswith("/dev/"):
            name = device[5:]
        else:
            name = device

        # Handle NVMe (nvme0n1p1 -> nvme0n1)
        if name.startswith("nvme"):
            parts = name.split("p")
            if len(parts) >= 2 and parts[1].isdigit():
                return parts[0]
            return name

        # Handle standard partitions (sda1 -> sda, hda1 -> hda)
        # Remove trailing digits
        base = name.rstrip("0123456789")
        return base if base else name

    def _get_disk_info(self, device: str, base_name: str) -> Dict[str, Any]:
        """Get information about a specific disk."""
        disk_type = self._detect_disk_type(base_name)

        # Try to get disk size
        size_gb = 0
        try:
            # Use disk_usage on the mount point if available
            mount_point = self._get_mount_point_for_device(device)
            if mount_point:
                usage = psutil.disk_usage(mount_point)
                # This is the partition size, not disk size
                size_gb = round(usage.total / (1024**3), 2)
        except Exception:
            pass

        return {
            "name": base_name,
            "type": disk_type,
            "size_gb": size_gb if size_gb > 0 else 100,  # Default if can't detect
            "model": self._get_disk_model(base_name),
        }

    def _get_mount_point_for_device(self, device: str) -> str:
        """Find mount point for a given device."""
        try:
            partitions = psutil.disk_partitions()
            for part in partitions:
                if part.device == device:
                    return part.mountpoint
        except Exception:
            pass
        return ""

    def _detect_disk_type(self, device_name: str) -> str:
        """Detect disk type based on device name."""
        name_lower = device_name.lower()

        if name_lower.startswith("nvme"):
            return "NVMe"
        elif name_lower.startswith("sd"):
            # Could be SATA or SAS, default to SATA
            return "SATA"
        elif name_lower.startswith("hd"):
            return "SATA"
        elif "iscsi" in name_lower or name_lower.startswith("dm-"):
            return "SAS"
        else:
            return "SATA"  # Default assumption

    def _get_disk_model(self, device_name: str) -> str:
        """Attempt to get disk model."""
        # Try to read from /sys/block if available
        sys_path = f"/sys/block/{device_name}/device/model"
        try:
            if os.path.exists(sys_path):
                with open(sys_path, "r") as f:
                    return f.read().strip()
        except Exception:
            pass

        # Fallback based on type
        if device_name.startswith("nvme"):
            return "NVMe SSD"
        elif device_name.startswith("sd") or device_name.startswith("hd"):
            return "SATA Drive"
        return "Unknown"

    def _fallback_disk_detection(self) -> List[Dict[str, Any]]:
        """Fallback method when detailed detection fails."""
        disks = []

        try:
            # Try to get at least root filesystem info
            root_usage = psutil.disk_usage("/")
            size_gb = round(root_usage.total / (1024**3), 2)

            disks.append({
                "name": "rootfs",
                "type": "Unknown",
                "size_gb": size_gb,
                "model": "System Disk",
            })
        except Exception:
            pass

        return disks
