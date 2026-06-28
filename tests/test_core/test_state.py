import pytest
from datetime import datetime
from src.core.state import TestStatus, TestResult, TestReport


class TestTestStatus:
    def test_status_values(self):
        assert TestStatus.PASSED.value == "passed"
        assert TestStatus.FAILED.value == "failed"
        assert TestStatus.SKIPPED.value == "skipped"
        assert TestStatus.ERROR.value == "error"
        assert TestStatus.RUNNING.value == "running"


class TestTestResult:
    def test_result_creation(self):
        result = TestResult(
            name="cpu_test",
            status=TestStatus.PASSED,
            duration_ms=1500,
            message="CPU test completed successfully"
        )
        assert result.name == "cpu_test"
        assert result.status == TestStatus.PASSED
        assert result.duration_ms == 1500

    def test_result_defaults(self):
        result = TestResult(name="memory_test", status=TestStatus.FAILED)
        assert result.message == ""
        assert result.details == {}
        assert result.raw_output == ""


class TestTestReport:
    def test_report_creation(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        assert report.server_sn == "SN123456"
        assert report.server_model == "Dell R750"
        assert report.results == []
        assert report.summary["total"] == 0
