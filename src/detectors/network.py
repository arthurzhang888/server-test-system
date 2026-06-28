import psutil
from typing import Dict, Any, List

from .base import BaseDetector, DetectorMode


class NetworkDetector(BaseDetector):
    """Detect network interface information - name, MAC address, speed, type."""

    def detect_real(self) -> Dict[str, Any]:
        """Detect real network interface information using psutil."""
        interfaces = []

        # Get network addresses (MAC, IP, etc.)
        addrs = psutil.net_if_addrs()
        # Get network stats (speed, duplex, etc.)
        stats = psutil.net_if_stats()

        for name, addr_list in addrs.items():
            interface_info = self._parse_interface(name, addr_list, stats.get(name))
            if interface_info:
                interfaces.append(interface_info)

        return {
            "interfaces": interfaces,
            "interface_count": len(interfaces),
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated network interface data for testing."""
        return {
            "interfaces": [
                {
                    "name": "eth0",
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "speed_mbps": 10000,
                    "type": "Ethernet",
                },
                {
                    "name": "eth1",
                    "mac": "aa:bb:cc:dd:ee:00",
                    "speed_mbps": 10000,
                    "type": "Ethernet",
                },
            ],
            "interface_count": 2,
        }

    def _parse_interface(
        self, name: str, addr_list: List, stats
    ) -> Dict[str, Any]:
        """Parse interface information from psutil data."""
        # Find MAC address (AF_LINK on Unix, AF_PACKET on Linux)
        mac = None
        for addr in addr_list:
            # psutil.AF_LINK is available on both Unix and Windows
            if hasattr(psutil, "AF_LINK") and addr.family == psutil.AF_LINK:
                mac = addr.address
                break
            # Fallback for Linux (AF_PACKET)
            elif addr.family.value == 17 if hasattr(addr.family, "value") else addr.family == 17:
                mac = addr.address
                break

        # Get speed from stats if available
        speed_mbps = 0
        if stats and hasattr(stats, "speed"):
            speed_mbps = stats.speed

        # Determine interface type
        interface_type = self._determine_interface_type(name)

        return {
            "name": name,
            "mac": mac or "00:00:00:00:00:00",
            "speed_mbps": speed_mbps,
            "type": interface_type,
        }

    def _determine_interface_type(self, name: str) -> str:
        """Determine network interface type based on name."""
        name_lower = name.lower()

        if name_lower.startswith("eth") or name_lower.startswith("en"):
            return "Ethernet"
        elif name_lower.startswith("wlan") or name_lower.startswith("wl"):
            return "Wireless"
        elif name_lower.startswith("lo") or name_lower == "loopback":
            return "Loopback"
        elif name_lower.startswith("docker") or name_lower.startswith("br-"):
            return "Bridge"
        elif name_lower.startswith("veth"):
            return "Virtual"
        elif name_lower.startswith("tun") or name_lower.startswith("tap"):
            return "Tunnel"
        else:
            return "Unknown"
