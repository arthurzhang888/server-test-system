"""System information utilities."""

import os
import subprocess
from typing import Optional


def get_server_serial() -> str:
    """Get server serial number from DMI/BIOS.

    Tries multiple methods in order:
    1. /sys/class/dmi/id/product_serial (sysfs, no root needed)
    2. dmidecode -s system-serial-number (requires root)
    3. ipmitool mc info (BMC)
    4. Return "UNKNOWN" if all fail

    Returns:
        Server serial number or "UNKNOWN"
    """
    # Method 1: sysfs (no root required)
    dmi_path = "/sys/class/dmi/id/product_serial"
    try:
        if os.path.exists(dmi_path):
            with open(dmi_path, "r") as f:
                serial = f.read().strip()
                if serial and serial.lower() not in ["unknown", "to be filled by o.e.m.", "not specified", ""]:
                    return serial
    except (IOError, PermissionError):
        pass

    # Method 2: dmidecode (requires root)
    try:
        result = subprocess.run(
            ["dmidecode", "-s", "system-serial-number"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            serial = result.stdout.strip()
            if serial and serial.lower() not in ["unknown", "to be filled by o.e.m.", "not specified", ""]:
                return serial
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        pass

    # Method 3: ipmitool (BMC)
    try:
        result = subprocess.run(
            ["ipmitool", "mc", "info"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "Product Serial" in line:
                    parts = line.split(":")
                    if len(parts) > 1:
                        serial = parts[1].strip()
                        if serial and serial.lower() not in ["unknown", "", "none"]:
                            return serial
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        pass

    # Method 4: Try chassis_serial as fallback
    try:
        chassis_path = "/sys/class/dmi/id/chassis_serial"
        if os.path.exists(chassis_path):
            with open(chassis_path, "r") as f:
                serial = f.read().strip()
                if serial and serial.lower() not in ["unknown", "to be filled by o.e.m.", "not specified", ""]:
                    return serial
    except (IOError, PermissionError):
        pass

    return "UNKNOWN"


def get_server_model() -> str:
    """Get server model from DMI/BIOS.

    Tries multiple methods in order:
    1. /sys/class/dmi/id/product_name (sysfs)
    2. dmidecode -s system-product-name
    3. Return "Unknown Model" if all fail

    Returns:
        Server model name or "Unknown Model"
    """
    # Method 1: sysfs
    dmi_path = "/sys/class/dmi/id/product_name"
    try:
        if os.path.exists(dmi_path):
            with open(dmi_path, "r") as f:
                model = f.read().strip()
                if model and model.lower() not in ["unknown", "", "system product name"]:
                    return model
    except (IOError, PermissionError):
        pass

    # Method 2: dmidecode
    try:
        result = subprocess.run(
            ["dmidecode", "-s", "system-product-name"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            model = result.stdout.strip()
            if model and model.lower() not in ["unknown", "", "system product name", "to be filled by o.e.m."]:
                return model
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        pass

    return "Unknown Model"


def get_board_serial() -> str:
    """Get motherboard serial number.

    Returns:
        Motherboard serial number or "UNKNOWN"
    """
    dmi_path = "/sys/class/dmi/id/board_serial"
    try:
        if os.path.exists(dmi_path):
            with open(dmi_path, "r") as f:
                serial = f.read().strip()
                if serial and serial.lower() not in ["unknown", "to be filled by o.e.m.", "not specified", ""]:
                    return serial
    except (IOError, PermissionError):
        pass

    try:
        result = subprocess.run(
            ["dmidecode", "-s", "baseboard-serial-number"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            serial = result.stdout.strip()
            if serial and serial.lower() not in ["unknown", "", "to be filled by o.e.m.", "not specified"]:
                return serial
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        pass

    return "UNKNOWN"
