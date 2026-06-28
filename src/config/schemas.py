from enum import Enum
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class DetectorMode(str, Enum):
    MOCK = "mock"
    REAL = "real"


class ServerType(str, Enum):
    GENERIC = "generic"
    STORAGE = "storage"
    COMPUTE = "compute"
    AI_SERVER = "ai_server"


class EMSAdapterConfig(BaseModel):
    """EMS adapter configuration."""
    type: str = Field(default="http", description="Adapter type: http, webhook")
    endpoint: Optional[str] = None
    webhook_url: Optional[str] = None
    auth_type: str = Field(default="api_key", description="Auth: api_key, bearer_token, basic_auth")
    api_key: Optional[str] = None
    bearer_token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5
    secret: Optional[str] = None  # For webhook signature


class OutputConfig(BaseModel):
    formats: List[str] = Field(default=["json"], description="Output formats: json, html, csv")
    upload_to_ems: bool = Field(default=False)
    ems_endpoint: Optional[str] = None
    ems_adapter: EMSAdapterConfig = Field(default_factory=EMSAdapterConfig)


class TestConfig(BaseModel):
    name: str
    enabled: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)


class StressThresholdConfig(BaseModel):
    """Threshold configuration for stress tests."""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    warning_pct: float = 0.8
    critical_pct: float = 0.95


class StressTestConfig(BaseModel):
    """Configuration for hardware stress tests."""
    enabled: bool = False
    duration_seconds: int = 300
    sample_interval_seconds: int = 5


class CPUStressConfig(StressTestConfig):
    """CPU stress test configuration."""
    threads: Optional[int] = None  # None = auto (CPU count)
    thresholds: Dict[str, StressThresholdConfig] = Field(default_factory=dict)


class GPUStressConfig(StressTestConfig):
    """GPU stress test configuration."""
    gpu_indices: List[int] = Field(default_factory=list)  # Empty = all GPUs
    thresholds: Dict[str, StressThresholdConfig] = Field(default_factory=dict)


class NVMeStressConfig(StressTestConfig):
    """NVMe stress test configuration."""
    devices: List[str] = Field(default_factory=list)  # Empty = auto-detect
    test_file_size_gb: int = 10
    write_ratio: float = 0.3  # 30% writes, 70% reads
    thresholds: Dict[str, StressThresholdConfig] = Field(default_factory=dict)


class GlobalConfig(BaseModel):
    server_type: ServerType
    mode: str = Field(default="auto", pattern="^(auto|interactive)$")
    detector_mode: DetectorMode = Field(default=DetectorMode.REAL)
    tests: List[TestConfig]
    output: OutputConfig = Field(default_factory=OutputConfig)
    # Stress test configurations
    cpu_stress: CPUStressConfig = Field(default_factory=CPUStressConfig)
    gpu_stress: GPUStressConfig = Field(default_factory=GPUStressConfig)
    nvme_stress: NVMeStressConfig = Field(default_factory=NVMeStressConfig)
