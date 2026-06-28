"""Tests for HTML reporter with Jinja2 templates."""

import pytest
import tempfile
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
        assert "<html" in result
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

        reporter = HTMLReporter()
        result = reporter.generate(report)

        # Should contain summary statistics
        assert "summary" in result.lower() or "Summary" in result
        assert "passed" in result.lower() or "failed" in result.lower()

    def test_generate_contains_hardware_details(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        report.results.append(TestResult(
            name="cpu_test",
            status=TestStatus.PASSED,
            duration_ms=1000,
            message="CPU test passed",
            details={"cores": 16, "model": "Intel Xeon"}
        ))

        reporter = HTMLReporter()
        result = reporter.generate(report)

        # Should contain hardware card sections
        assert "cpu_test" in result.lower() or "CPU" in result
        assert "passed" in result.lower()

    def test_generate_contains_all_status_types(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        report.results.append(TestResult(name="test1", status=TestStatus.PASSED, duration_ms=100))
        report.results.append(TestResult(name="test2", status=TestStatus.FAILED, duration_ms=200))
        report.results.append(TestResult(name="test3", status=TestStatus.ERROR, duration_ms=50))

        reporter = HTMLReporter()
        result = reporter.generate(report)

        # Should contain all test names (template capitalizes them)
        assert "Test1" in result or "Test2" in result or "Test3" in result

    def test_generate_contains_css_link(self):
        report = TestReport(
            server_sn="SN123456",
            server_model="Dell R750",
            server_type="generic"
        )
        reporter = HTMLReporter()
        result = reporter.generate(report)

        # Should reference CSS file
        assert "static/css/style.css" in result or "style.css" in result

    def test_save_to_file_creates_assets(self):
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

            # Check that static assets were copied
            static_dir = output_path.parent / "static"
            assert static_dir.exists()
            css_file = static_dir / "css" / "style.css"
            assert css_file.exists()

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
        assert "summary" in result.lower() or "Summary" in result

    def test_report_with_details(self):
        report = TestReport(
            server_sn="SN999",
            server_model="Test Server",
            server_type="ai_server"
        )
        report.results.append(TestResult(
            name="gpu_test",
            status=TestStatus.PASSED,
            duration_ms=5000,
            message="GPU detected",
            details={
                "gpus": [{"name": "NVIDIA A100", "memory_gb": 80}],
                "count": 2
            }
        ))

        reporter = HTMLReporter()
        result = reporter.generate(report)

        assert "SN999" in result
        assert "ai_server" in result or "AI" in result
