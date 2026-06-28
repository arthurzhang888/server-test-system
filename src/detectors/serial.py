import os
import glob
from typing import Dict, Any, List, Optional

from .base import BaseDetector, DetectorMode


class SerialDetector(BaseDetector):
    """Detect serial ports and their configuration.

    Uses /sys/class/tty/ to discover serial ports including:
    - Standard serial ports (/dev/ttyS*, /dev/ttyAMA*)
    - USB serial adapters (/dev/ttyUSB*, /dev/ttyACM*)
    """

    def detect_real(self) -> Dict[str, Any]:
        """Detect real serial ports via sysfs."""
        ports = self._detect_ports()

        return {
            "ports": ports,
            "port_count": len(ports),
            "standard_count": len([p for p in ports if p["type"] == "standard"]),
            "usb_count": len([p for p in ports if p["type"] == "usb"]),
        }

    def detect_mock(self) -> Dict[str, Any]:
        """Return simulated serial port data for testing."""
        ports = [
            {
                "name": "ttyS0",
                "device": "/dev/ttyS0",
                "type": "standard",
                "driver": "serial",
                "port": 0x3f8,
                "irq": 4,
                "baud_base": 115200,
                "flags": "SPD_NORMAL",
                "status": "available",
                "connected": False,
            },
            {
                "name": "ttyUSB0",
                "device": "/dev/ttyUSB0",
                "type": "usb",
                "driver": "ftdi_sio",
                "vendor_id": "0403",
                "product_id": "6001",
                "manufacturer": "FTDI",
                "product": "FT232 USB-Serial",
                "baud_base": 115200,
                "status": "available",
                "connected": True,
            },
            {
                "name": "ttyACM0",
                "device": "/dev/ttyACM0",
                "type": "usb",
                "driver": "cdc_acm",
                "vendor_id": "2341",
                "product_id": "0043",
                "manufacturer": "Arduino",
                "product": "Uno R3",
                "baud_base": 115200,
                "status": "available",
                "connected": True,
            },
        ]

        return {
            "ports": ports,
            "port_count": len(ports),
            "standard_count": 1,
            "usb_count": 2,
        }

    def _detect_ports(self) -> List[Dict[str, Any]]:
        """Detect all serial ports from sysfs."""
        ports = []
        sys_tty_path = "/sys/class/tty"

        try:
            if os.path.exists(sys_tty_path):
                for tty_name in os.listdir(sys_tty_path):
                    port_info = self._get_port_info(tty_name)
                    if port_info:
                        ports.append(port_info)
            else:
                # Fallback: check /dev for serial devices
                ports = self._fallback_port_detection()

        except (OSError, PermissionError):
            pass

        return ports

    def _get_port_info(self, tty_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a serial port."""
        sys_path = f"/sys/class/tty/{tty_name}"
        device_path = f"/dev/{tty_name}"

        # Skip if device node doesn't exist
        if not os.path.exists(device_path):
            return None

        port_type = self._classify_port_type(tty_name)
        if not port_type:
            return None

        port_info = {
            "name": tty_name,
            "device": device_path,
            "type": port_type,
            "status": self._get_port_status(tty_name),
            "connected": False,  # Would need ioctl to determine actual connection
        }

        # Add driver information
        driver = self._get_driver_info(tty_name)
        port_info.update(driver)

        # Add port configuration
        config = self._get_port_config(tty_name)
        port_info.update(config)

        # Add USB-specific info for USB serial devices
        if port_type == "usb":
            usb_info = self._get_usb_info(tty_name)
            port_info.update(usb_info)
        else:
            # Add hardware port info for standard serial ports
            hw_info = self._get_hardware_info(tty_name)
            port_info.update(hw_info)

        return port_info

    def _classify_port_type(self, tty_name: str) -> Optional[str]:
        """Classify the type of serial port based on name."""
        # USB serial adapters
        if tty_name.startswith("ttyUSB") or tty_name.startswith("ttyACM"):
            return "usb"

        # Standard serial ports (16550A compatible)
        if tty_name.startswith("ttyS"):
            return "standard"

        # ARM AMBA serial ports
        if tty_name.startswith("ttyAMA"):
            return "standard"

        # OMAP serial ports
        if tty_name.startswith("ttyO"):
            return "standard"

        # Platform serial ports
        if tty_name.startswith("ttyPS"):
            return "standard"

        # High speed serial
        if tty_name.startswith("ttyHS"):
            return "standard"

        # Skip console, pty, and other virtual terminals
        return None

    def _get_port_status(self, tty_name: str) -> str:
        """Get the status of a serial port."""
        device_path = f"/dev/{tty_name}"

        try:
            if os.path.exists(device_path):
                # Check if device is readable/writable
                if os.access(device_path, os.R_OK | os.W_OK):
                    return "available"
                elif os.access(device_path, os.R_OK):
                    return "read-only"
                else:
                    return "busy"
        except OSError:
            pass

        return "unknown"

    def _get_driver_info(self, tty_name: str) -> Dict[str, str]:
        """Get driver information for a serial port."""
        sys_path = f"/sys/class/tty/{tty_name}"
        driver_info = {"driver": "unknown"}

        try:
            # Try to read driver link
            driver_link = f"{sys_path}/device/driver"
            if os.path.islink(driver_link):
                driver_name = os.path.basename(os.readlink(driver_link))
                driver_info["driver"] = driver_name
            elif os.path.exists(f"{sys_path}/driver"):
                driver_link = f"{sys_path}/driver"
                if os.path.islink(driver_link):
                    driver_name = os.path.basename(os.readlink(driver_link))
                    driver_info["driver"] = driver_name
        except (OSError, PermissionError):
            pass

        return driver_info

    def _get_port_config(self, tty_name: str) -> Dict[str, Any]:
        """Get port configuration from sysfs."""
        config = {
            "baud_base": 115200,  # Default value
        }

        sys_path = f"/sys/class/tty/{tty_name}"

        # Try to read various configuration files
        config_files = {
            "baud_base": "baud_base",
            "flags": "flags",
            "xmit_fifo_size": "xmit_fifo_size",
            "close_delay": "close_delay",
            "closing_wait": "closing_wait",
        }

        for key, filename in config_files.items():
            filepath = f"{sys_path}/{filename}"
            try:
                if os.path.exists(filepath):
                    with open(filepath, "r") as f:
                        value = f.read().strip()
                        try:
                            config[key] = int(value)
                        except ValueError:
                            config[key] = value
            except (OSError, PermissionError):
                pass

        return config

    def _get_usb_info(self, tty_name: str) -> Dict[str, str]:
        """Get USB-specific information for USB serial devices."""
        usb_info = {
            "vendor_id": "unknown",
            "product_id": "unknown",
            "manufacturer": "unknown",
            "product": "unknown",
        }

        try:
            # Navigate through sysfs to find USB device info
            sys_path = f"/sys/class/tty/{tty_name}"

            # For ttyUSB devices
            if tty_name.startswith("ttyUSB"):
                device_path = os.path.join(sys_path, "device")
                if os.path.islink(device_path):
                    real_path = os.path.realpath(device_path)
                    # Navigate up to find USB device
                    parent = os.path.dirname(real_path)
                    for _ in range(5):  # Look up to 5 levels
                        id_vendor_path = os.path.join(parent, "idVendor")
                        id_product_path = os.path.join(parent, "idProduct")
                        manufacturer_path = os.path.join(parent, "manufacturer")
                        product_path = os.path.join(parent, "product")

                        if os.path.exists(id_vendor_path):
                            with open(id_vendor_path, "r") as f:
                                usb_info["vendor_id"] = f.read().strip().lower()
                            with open(id_product_path, "r") as f:
                                usb_info["product_id"] = f.read().strip().lower()

                            if os.path.exists(manufacturer_path):
                                with open(manufacturer_path, "r") as f:
                                    usb_info["manufacturer"] = f.read().strip()
                            if os.path.exists(product_path):
                                with open(product_path, "r") as f:
                                    usb_info["product"] = f.read().strip()
                            break
                        parent = os.path.dirname(parent)

            # For ttyACM devices
            elif tty_name.startswith("ttyACM"):
                device_path = os.path.join(sys_path, "device")
                if os.path.exists(device_path):
                    # ACM devices have idVendor/idProduct in device directory
                    id_vendor_path = os.path.join(device_path, "idVendor")
                    id_product_path = os.path.join(device_path, "idProduct")
                    manufacturer_path = os.path.join(device_path, "manufacturer")
                    product_path = os.path.join(device_path, "product")

                    if os.path.exists(id_vendor_path):
                        with open(id_vendor_path, "r") as f:
                            usb_info["vendor_id"] = f.read().strip().lower()
                        with open(id_product_path, "r") as f:
                            usb_info["product_id"] = f.read().strip().lower()

                    if os.path.exists(manufacturer_path):
                        with open(manufacturer_path, "r") as f:
                            usb_info["manufacturer"] = f.read().strip()
                    if os.path.exists(product_path):
                        with open(product_path, "r") as f:
                            usb_info["product"] = f.read().strip()

        except (OSError, PermissionError):
            pass

        return usb_info

    def _get_hardware_info(self, tty_name: str) -> Dict[str, Any]:
        """Get hardware information for standard serial ports."""
        hw_info = {}

        sys_path = f"/sys/class/tty/{tty_name}"

        # Try to read port and irq information
        try:
            port_path = f"{sys_path}/port"
            if os.path.exists(port_path):
                with open(port_path, "r") as f:
                    port_str = f.read().strip()
                    if port_str.startswith("0x"):
                        hw_info["port"] = int(port_str, 16)
                    else:
                        try:
                            hw_info["port"] = int(port_str, 16)
                        except ValueError:
                            hw_info["port"] = port_str

            irq_path = f"{sys_path}/irq"
            if os.path.exists(irq_path):
                with open(irq_path, "r") as f:
                    hw_info["irq"] = int(f.read().strip())

            io_type_path = f"{sys_path}/io_type"
            if os.path.exists(io_type_path):
                with open(io_type_path, "r") as f:
                    hw_info["io_type"] = f.read().strip()

            uart_path = f"{sys_path}/uart"
            if os.path.exists(uart_path):
                with open(uart_path, "r") as f:
                    hw_info["uart"] = f.read().strip()

        except (OSError, PermissionError, ValueError):
            pass

        return hw_info

    def _fallback_port_detection(self) -> List[Dict[str, Any]]:
        """Fallback method to detect ports by checking /dev."""
        ports = []

        patterns = [
            "/dev/ttyS[0-9]*",
            "/dev/ttyAMA[0-9]*",
            "/dev/ttyUSB[0-9]*",
            "/dev/ttyACM[0-9]*",
            "/dev/ttyO[0-9]*",
            "/dev/ttyPS[0-9]*",
            "/dev/ttyHS[0-9]*",
        ]

        seen = set()
        for pattern in patterns:
            for device_path in glob.glob(pattern):
                if device_path in seen:
                    continue
                seen.add(device_path)

                tty_name = os.path.basename(device_path)
                port_type = self._classify_port_type(tty_name)

                if port_type:
                    port_info = {
                        "name": tty_name,
                        "device": device_path,
                        "type": port_type,
                        "status": self._get_port_status(tty_name),
                        "driver": "unknown",
                    }

                    # Try to get additional info
                    config = self._get_port_config(tty_name)
                    port_info.update(config)

                    if port_type == "usb":
                        usb_info = self._get_usb_info(tty_name)
                        port_info.update(usb_info)
                    else:
                        hw_info = self._get_hardware_info(tty_name)
                        port_info.update(hw_info)

                    ports.append(port_info)

        return ports
