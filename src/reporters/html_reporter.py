"""HTML Reporter implementation using Jinja2 templates."""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .base import BaseReporter
from src.core.state import TestReport, TestResult, TestStatus


class HTMLReporter(BaseReporter):
    """Generate HTML reports using Jinja2 templates.

    Supports:
    - Custom templates in templates/ directory
    - Template inheritance
    - Responsive design
    - Static asset copying
    """

    @property
    def format_name(self) -> str:
        """Return the format name."""
        return "html"

    def __init__(self, template_dir: str = None):
        """Initialize HTML reporter with template directory.

        Args:
            template_dir: Path to template directory. If None, uses default templates.
        """
        if template_dir is None:
            # Find templates relative to this file
            template_dir = Path(__file__).parent.parent.parent / "templates"

        self.template_dir = Path(template_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )

        # Add custom filters
        self.env.filters['tojson'] = json.dumps

    def generate(self, report: TestReport) -> str:
        """Generate HTML report as string."""
        template = self.env.get_template("report.html")

        # Prepare context
        context = {
            "server_sn": report.server_sn,
            "server_model": report.server_model,
            "server_type": report.server_type,
            "overall_status": report.overall_status.value,
            "summary": report.summary,
            "results": [self._result_to_dict(r) for r in report.results],
            "duration_seconds": report.duration_seconds,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": "1.0.0",
            "year": datetime.now().year
        }

        return template.render(**context)

    def save(self, report: TestReport, output_path: Path) -> None:
        """Save HTML report to file with static assets."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate HTML
        html_content = self.generate(report)

        # Write HTML file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Copy static assets
        self._copy_static_assets(output_path.parent)

    def _result_to_dict(self, result: TestResult) -> dict:
        """Convert TestResult to dictionary for template."""
        return {
            "name": result.name,
            "status": result.status.value,
            "duration_ms": result.duration_ms,
            "message": result.message,
            "details": result.details,
            "raw_output": result.raw_output
        }

    def _copy_static_assets(self, output_dir: Path) -> None:
        """Copy static assets (CSS, JS) to output directory."""
        static_src = self.template_dir / "static"
        static_dst = output_dir / "static"

        if static_src.exists():
            if static_dst.exists():
                shutil.rmtree(static_dst)
            shutil.copytree(static_src, static_dst)

    def generate_summary_table(self, report: TestReport) -> str:
        """Generate a simple HTML summary table (for email/embed)."""
        rows = ""
        for result in report.results:
            status_color = "green" if result.status == TestStatus.PASSED else "red"
            rows += f"""
            <tr>
                <td>{result.name}</td>
                <td style="color: {status_color}">{result.status.value}</td>
                <td>{result.duration_ms}ms</td>
            </tr>
            """

        return f"""
        <table border="1" cellpadding="5" cellspacing="0">
            <thead>
                <tr>
                    <th>Test</th>
                    <th>Status</th>
                    <th>Duration</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        """
