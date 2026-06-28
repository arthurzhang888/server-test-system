import json
from datetime import datetime
from typing import Any

from .base import BaseReporter
from src.core.state import TestReport, TestResult


class JSONReporter(BaseReporter):
    """Generate JSON format test reports."""

    @property
    def format_name(self) -> str:
        return "json"

    def generate(self, report: TestReport) -> str:
        """Generate JSON report from test results."""
        data = self._to_dict(report)
        return json.dumps(data, indent=2, ensure_ascii=False, default=self._json_serializer)

    def _to_dict(self, report: TestReport) -> dict:
        """Convert TestReport to dictionary."""
        return {
            "metadata": {
                "server_sn": report.server_sn,
                "server_model": report.server_model,
                "server_type": report.server_type,
                "start_time": report.start_time.isoformat(),
                "end_time": report.end_time.isoformat() if report.end_time else None,
                "duration_seconds": report.duration_seconds,
            },
            "summary": report.summary,
            "overall_status": report.overall_status.value,
            "results": [self._result_to_dict(r) for r in report.results],
        }

    def _result_to_dict(self, result: TestResult) -> dict:
        """Convert TestResult to dictionary."""
        return {
            "name": result.name,
            "status": result.status.value,
            "duration_ms": result.duration_ms,
            "message": result.message,
            "details": result.details,
            "raw_output": result.raw_output,
        }

    def _json_serializer(self, obj: Any) -> str:
        """Handle datetime serialization."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
