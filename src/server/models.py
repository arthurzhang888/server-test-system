"""Pydantic models for central server."""

from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Test job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ClientStatus(str, Enum):
    """Client connection status."""
    OFFLINE = "offline"
    ONLINE = "online"
    TESTING = "testing"


class TestJob(BaseModel):
    """Test job configuration."""
    id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S"))
    client_id: str
    server_type: str = "generic"
    tests: List[str] = Field(default_factory=list)
    stress_enabled: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TestProgress(BaseModel):
    """Real-time test progress update."""
    job_id: str
    client_id: str
    test_name: str
    progress_percent: float
    status: str
    message: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class TestResult(BaseModel):
    """Complete test result from client."""
    job_id: str
    client_id: str
    server_sn: str
    server_model: str
    overall_status: str
    summary: Dict[str, int]
    results: List[Dict[str, Any]]
    duration_seconds: float
    report_urls: Dict[str, str] = Field(default_factory=dict)
    submitted_at: datetime = Field(default_factory=datetime.now)


class ClientInfo(BaseModel):
    """Connected client information."""
    id: str
    hostname: str
    ip_address: str
    status: ClientStatus
    current_job: Optional[str] = None
    last_seen: datetime = Field(default_factory=datetime.now)
    capabilities: Dict[str, Any] = Field(default_factory=dict)


class ServerStatus(BaseModel):
    """Central server status."""
    version: str = "1.0.0"
    uptime_seconds: float
    connected_clients: int
    active_jobs: int
    completed_jobs: int
    failed_jobs: int
