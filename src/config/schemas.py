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


class OutputConfig(BaseModel):
    formats: List[str] = Field(default=["json"], description="Output formats: json, html, csv")
    upload_to_ems: bool = Field(default=False)
    ems_endpoint: Optional[str] = None


class TestConfig(BaseModel):
    name: str
    enabled: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)


class GlobalConfig(BaseModel):
    server_type: ServerType
    mode: str = Field(default="auto", pattern="^(auto|interactive)$")
    detector_mode: DetectorMode = Field(default=DetectorMode.REAL)
    tests: List[TestConfig]
    output: OutputConfig = Field(default_factory=OutputConfig)
