import pytest
import json
import tempfile
import os
from datetime import datetime
from pathlib import Path

from src.core.state import TestStatus, TestResult, TestReport
from src.reporters.json_reporter import JSONReporter


class TestJSONReporter:
    def test_generate_returns_valid_json(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        reporter = JSONReporter()
        result = reporter.generate(report)

        # Should be valid JSON
        data = json.loads(result)
        assert "metadata" in data
        assert data["metadata"]["server_sn"] == "SN123456"

    def test_generate_includes_results(self):
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

        reporter = JSONReporter()
        result = reporter.generate(report)
        data = json.loads(result)

        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "cpu_test"
        assert data["results"][0]["status"] == "passed"

    def test_save_to_file(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.json"
            reporter = JSONReporter()
            reporter.save(report, output_path)

            assert output_path.exists()
            with open(output_path) as f:
                data = json.load(f)
            assert data["metadata"]["server_sn"] == "SN123456"
