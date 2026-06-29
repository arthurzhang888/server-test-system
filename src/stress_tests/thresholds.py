"""Threshold loading utilities for stress tests."""

from typing import Dict, Any, Optional
from dataclasses import dataclass

from src.stress_tests.base import ThresholdConfig
from src.stress_tests.cpu_stress import CPUThresholds
from src.stress_tests.gpu_stress import GPUThresholds
from src.stress_tests.nvme_stress import NVMeThresholds


def load_threshold_config(config_data: Dict[str, Any]) -> ThresholdConfig:
    """Load threshold config from dictionary.

    Args:
        config_data: Dictionary with min_value, max_value, warning_pct, critical_pct

    Returns:
        ThresholdConfig instance
    """
    return ThresholdConfig(
        min_value=config_data.get("min_value"),
        max_value=config_data.get("max_value"),
        warning_pct=config_data.get("warning_pct", 0.8),
        critical_pct=config_data.get("critical_pct", 0.95)
    )


def load_cpu_thresholds(config: Optional[Dict[str, Any]]) -> CPUThresholds:
    """Load CPU stress test thresholds from configuration.

    Args:
        config: Configuration dictionary with threshold values

    Returns:
        CPUThresholds instance with configured values
    """
    if not config:
        return CPUThresholds()  # Return defaults

    thresholds = CPUThresholds()

    if "temperature" in config:
        thresholds.temperature = load_threshold_config(config["temperature"])
    if "utilization" in config:
        thresholds.utilization = load_threshold_config(config["utilization"])
    if "frequency" in config:
        thresholds.frequency = load_threshold_config(config["frequency"])
    if "power" in config:
        thresholds.power = load_threshold_config(config["power"])

    return thresholds


def load_gpu_thresholds(config: Optional[Dict[str, Any]]) -> GPUThresholds:
    """Load GPU stress test thresholds from configuration.

    Args:
        config: Configuration dictionary with threshold values

    Returns:
        GPUThresholds instance with configured values
    """
    if not config:
        return GPUThresholds()  # Return defaults

    thresholds = GPUThresholds()

    if "temperature" in config:
        thresholds.temperature = load_threshold_config(config["temperature"])
    if "memory_temperature" in config:
        thresholds.memory_temperature = load_threshold_config(config["memory_temperature"])
    if "utilization" in config:
        thresholds.utilization = load_threshold_config(config["utilization"])
    if "power" in config:
        thresholds.power = load_threshold_config(config["power"])
    if "memory_usage" in config:
        thresholds.memory_usage = load_threshold_config(config["memory_usage"])

    return thresholds


def load_nvme_thresholds(config: Optional[Dict[str, Any]]) -> NVMeThresholds:
    """Load NVMe stress test thresholds from configuration.

    Args:
        config: Configuration dictionary with threshold values

    Returns:
        NVMeThresholds instance with configured values
    """
    if not config:
        return NVMeThresholds()  # Return defaults

    thresholds = NVMeThresholds()

    if "temperature" in config:
        thresholds.temperature = load_threshold_config(config["temperature"])
    if "health_percent" in config:
        thresholds.health_percent = load_threshold_config(config["health_percent"])
    if "spare_percent" in config:
        thresholds.spare_percent = load_threshold_config(config["spare_percent"])
    if "media_errors" in config:
        thresholds.media_errors = load_threshold_config(config["media_errors"])
    if "power_on_hours" in config:
        thresholds.power_on_hours = load_threshold_config(config["power_on_hours"])

    return thresholds


@dataclass
class StressTestThresholds:
    """Container for all stress test thresholds."""
    cpu: CPUThresholds = None
    gpu: GPUThresholds = None
    nvme: NVMeThresholds = None

    def __post_init__(self):
        if self.cpu is None:
            self.cpu = CPUThresholds()
        if self.gpu is None:
            self.gpu = GPUThresholds()
        if self.nvme is None:
            self.nvme = NVMeThresholds()


def load_all_thresholds(config: Optional[Dict[str, Dict[str, Any]]]) -> StressTestThresholds:
    """Load all stress test thresholds from configuration.

    Args:
        config: Configuration dictionary with 'cpu', 'gpu', 'nvme' sections

    Returns:
        StressTestThresholds container with all loaded thresholds
    """
    if not config:
        return StressTestThresholds()

    return StressTestThresholds(
        cpu=load_cpu_thresholds(config.get("cpu")),
        gpu=load_gpu_thresholds(config.get("gpu")),
        nvme=load_nvme_thresholds(config.get("nvme"))
    )
