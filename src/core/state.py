from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime


class TestStatus(str, Enum):
    """Status of a test execution."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    RUNNING = "running"


@dataclass
class TestResult:
    """Result of a single test execution."""
    name: str
    status: TestStatus
    duration_ms: int = 0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    raw_output: str = ""


@dataclass
class TestReport:
    """Complete test report for a server."""
    server_sn: str
    server_model: str
    server_type: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    results: List[TestResult] = field(default_factory=list)

    @property
    def summary(self) -> Dict[str, int]:
        """Generate summary statistics."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)
        errors = sum(1 for r in self.results if r.status == TestStatus.ERROR)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
        }

    @property
    def duration_seconds(self) -> float:
        """Calculate total test duration."""
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

    @property
    def overall_status(self) -> TestStatus:
        """Determine overall test status."""
        if not self.results:
            return TestStatus.SKIPPED

        if any(r.status == TestStatus.ERROR for r in self.results):
            return TestStatus.ERROR
        if any(r.status == TestStatus.FAILED for r in self.results):
            return TestStatus.FAILED
        if all(r.status == TestStatus.PASSED for r in self.results):
            return TestStatus.PASSED

        return TestStatus.SKIPPED
