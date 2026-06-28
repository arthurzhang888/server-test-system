import csv
import tempfile
import os
from datetime import datetime
from pathlib import Path

import pytest

from src.core.state import TestStatus, TestResult, TestReport
from src.reporters.csv_reporter import CSVReporter


class TestCSVReporter:
    def test_format_name(self):
        reporter = CSVReporter()
        assert reporter.format_name == "csv"

    def test_generate_returns_csv_string(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        reporter = CSVReporter()
        result = reporter.generate(report)

        # Should be valid CSV
        lines = result.strip().split('\n')
        assert len(lines) >= 1
        assert "Test Name" in lines[0]

    def test_generate_includes_headers(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        reporter = CSVReporter()
        result = reporter.generate(report)

        lines = result.strip().split('\n')
        headers = lines[0].split(',')
        assert "Test Name" in headers
        assert "Status" in headers
        assert "Duration (ms)" in headers
        assert "Message" in headers

    def test_generate_includes_results(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        report.results.append(TestResult(
            name="cpu_test",
            status=TestStatus.PASSED,
            duration_ms=1000,
            message="CPU test completed"
        ))
        report.results.append(TestResult(
            name="memory_test",
            status=TestStatus.FAILED,
            duration_ms=500,
            message="Memory error detected"
        ))

        reporter = CSVReporter()
        result = reporter.generate(report)

        reader = csv.DictReader(result.splitlines())
        rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["Test Name"] == "cpu_test"
        assert rows[0]["Status"] == "passed"
        assert rows[0]["Duration (ms)"] == "1000"
        assert rows[0]["Message"] == "CPU test completed"

        assert rows[1]["Test Name"] == "memory_test"
        assert rows[1]["Status"] == "failed"

    def test_save_to_file(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        report.results.append(TestResult(
            name="cpu_test",
            status=TestStatus.PASSED,
            duration_ms=1000
        ))

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.csv"
            reporter = CSVReporter()
            saved_path = reporter.save(report, output_path)

            assert saved_path.exists()
            with open(saved_path) as f:
                content = f.read()
                assert "Test Name" in content
                assert "cpu_test" in content

    def test_empty_results(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        reporter = CSVReporter()
        result = reporter.generate(report)

        lines = result.strip().split('\n')
        assert len(lines) == 1  # Only headers
