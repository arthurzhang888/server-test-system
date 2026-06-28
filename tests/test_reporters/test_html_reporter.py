import pytest
import tempfile
import os
from datetime import datetime
from pathlib import Path

from src.core.state import TestStatus, TestResult, TestReport
from src.reporters.html_reporter import HTMLReporter


class TestHTMLReporter:
    def test_format_name(self):
        reporter = HTMLReporter()
        assert reporter.format_name == "html"

    def test_generate_contains_html_structure(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        reporter = HTMLReporter()
        result = reporter.generate(report)

        # Should contain basic HTML structure
        assert "<!DOCTYPE html>" in result
        assert "<html>" in result
        assert "<head>" in result
        assert "<body>" in result
        assert "</html>" in result

    def test_generate_contains_server_info(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        reporter = HTMLReporter()
        result = reporter.generate(report)

        # Should contain server information
        assert "SN123456" in result
        assert "Dell R750" in result
        assert "generic" in result

    def test_generate_contains_summary(self):
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
        report.results.append(TestResult(
            name="memory_test",
            status=TestStatus.FAILED,
            duration_ms=500
        ))
        report.results.append(TestResult(
            name="disk_test",
            status=TestStatus.SKIPPED,
            duration_ms=0
        ))

        reporter = HTMLReporter()
        result = reporter.generate(report)

        # Should contain summary statistics
        assert "Total" in result or "total" in result.lower()
        assert "Passed" in result or "passed" in result.lower()
        assert "Failed" in result or "failed" in result.lower()
        assert "Skipped" in result or "skipped" in result.lower()

    def test_generate_contains_results_table(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        report.results.append(TestResult(
            name="cpu_test",
            status=TestStatus.PASSED,
            duration_ms=1000,
            message="CPU test passed"
        ))

        reporter = HTMLReporter()
        result = reporter.generate(report)

        # Should contain results table
        assert "<table" in result
        assert "cpu_test" in result
        assert "passed" in result.lower()
        assert "1000" in result

    def test_generate_contains_all_status_types(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        report.results.append(TestResult(name="test1", status=TestStatus.PASSED, duration_ms=100))
        report.results.append(TestResult(name="test2", status=TestStatus.FAILED, duration_ms=200))
        report.results.append(TestResult(name="test3", status=TestStatus.SKIPPED, duration_ms=0))
        report.results.append(TestResult(name="test4", status=TestStatus.ERROR, duration_ms=50))

        reporter = HTMLReporter()
        result = reporter.generate(report)

        # Should contain all test names
        assert "test1" in result
        assert "test2" in result
        assert "test3" in result
        assert "test4" in result

    def test_generate_contains_css_styles(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        reporter = HTMLReporter()
        result = reporter.generate(report)

        # Should contain CSS styles
        assert "<style>" in result or "style=" in result

    def test_save_to_file(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "report.html"
            reporter = HTMLReporter()
            reporter.save(report, output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "<!DOCTYPE html>" in content
            assert "SN123456" in content

    def test_empty_report(self):
        report = TestReport(
            server_sn="SN789012",
            server_model="HP DL380",
            server_type="generic"
        )

        reporter = HTMLReporter()
        result = reporter.generate(report)

        assert "<!DOCTYPE html>" in result
        assert "SN789012" in result
        assert "Total" in result or "total" in result.lower()
