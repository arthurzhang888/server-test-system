"""HTML Reporter implementation for generating test reports."""

from jinja2 import Template

from .base import BaseReporter
from src.core.state import TestReport, TestResult, TestStatus


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Server Test Report</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 30px;
        }
        h1 {
            color: #2c3e50;
            margin-bottom: 10px;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin: 25px 0 15px 0;
        }
        .server-info {
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
        .server-info p {
            margin: 5px 0;
            color: #555;
        }
        .server-info strong {
            color: #2c3e50;
            display: inline-block;
            width: 120px;
        }
        .summary-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .summary-card {
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            color: white;
            font-weight: bold;
        }
        .summary-card.total {
            background-color: #3498db;
        }
        .summary-card.passed {
            background-color: #27ae60;
        }
        .summary-card.failed {
            background-color: #e74c3c;
        }
        .summary-card.skipped {
            background-color: #f39c12;
        }
        .summary-card.errors {
            background-color: #9b59b6;
        }
        .summary-card .number {
            font-size: 2.5em;
            display: block;
            margin-bottom: 5px;
        }
        .summary-card .label {
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            background-color: #fff;
            border-radius: 6px;
            overflow: hidden;
        }
        thead {
            background-color: #34495e;
            color: white;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 0.5px;
        }
        tbody tr:hover {
            background-color: #f8f9fa;
        }
        tbody tr:last-child td {
            border-bottom: none;
        }
        .status {
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            text-transform: uppercase;
        }
        .status.passed {
            background-color: #d4edda;
            color: #155724;
        }
        .status.failed {
            background-color: #f8d7da;
            color: #721c24;
        }
        .status.skipped {
            background-color: #fff3cd;
            color: #856404;
        }
        .status.error {
            background-color: #f5c6cb;
            color: #721c24;
        }
        .status.running {
            background-color: #d1ecf1;
            color: #0c5460;
        }
        .duration {
            font-family: 'Courier New', monospace;
            color: #666;
        }
        .message {
            color: #666;
            font-size: 0.9em;
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .overall-status {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .overall-status.passed {
            background-color: #d4edda;
            color: #155724;
        }
        .overall-status.failed {
            background-color: #f8d7da;
            color: #721c24;
        }
        .overall-status.skipped {
            background-color: #fff3cd;
            color: #856404;
        }
        .overall-status.error {
            background-color: #f5c6cb;
            color: #721c24;
        }
        .timestamp {
            color: #7f8c8d;
            font-size: 0.9em;
            margin-top: 5px;
        }
        .no-results {
            text-align: center;
            padding: 40px;
            color: #7f8c8d;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Test Report</h1>

        <div class="server-info">
            <p><strong>Server SN:</strong> {{ report.server_sn }}</p>
            <p><strong>Model:</strong> {{ report.server_model }}</p>
            <p><strong>Type:</strong> {{ report.server_type }}</p>
            <p><strong>Overall Status:</strong> <span class="overall-status {{ report.overall_status.value }}">{{ report.overall_status.value.upper() }}</span></p>
            {% if report.start_time %}
            <p class="timestamp"><strong>Start Time:</strong> {{ report.start_time.strftime('%Y-%m-%d %H:%M:%S') }}</p>
            {% endif %}
            {% if report.end_time %}
            <p class="timestamp"><strong>End Time:</strong> {{ report.end_time.strftime('%Y-%m-%d %H:%M:%S') }}</p>
            {% endif %}
            {% if report.duration_seconds > 0 %}
            <p class="timestamp"><strong>Duration:</strong> {{ '%.2f'|format(report.duration_seconds) }} seconds</p>
            {% endif %}
        </div>

        <h2>Summary</h2>
        <div class="summary-cards">
            <div class="summary-card total">
                <span class="number">{{ summary.total }}</span>
                <span class="label">Total</span>
            </div>
            <div class="summary-card passed">
                <span class="number">{{ summary.passed }}</span>
                <span class="label">Passed</span>
            </div>
            <div class="summary-card failed">
                <span class="number">{{ summary.failed }}</span>
                <span class="label">Failed</span>
            </div>
            <div class="summary-card skipped">
                <span class="number">{{ summary.skipped }}</span>
                <span class="label">Skipped</span>
            </div>
            {% if summary.errors > 0 %}
            <div class="summary-card errors">
                <span class="number">{{ summary.errors }}</span>
                <span class="label">Errors</span>
            </div>
            {% endif %}
        </div>

        <h2>Test Results</h2>
        {% if results %}
        <table>
            <thead>
                <tr>
                    <th>Test Name</th>
                    <th>Status</th>
                    <th>Duration (ms)</th>
                    <th>Message</th>
                </tr>
            </thead>
            <tbody>
                {% for result in results %}
                <tr>
                    <td>{{ result.name }}</td>
                    <td><span class="status {{ result.status.value }}">{{ result.status.value.upper() }}</span></td>
                    <td class="duration">{{ result.duration_ms }}</td>
                    <td class="message" title="{{ result.message }}">{{ result.message or '-' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p class="no-results">No test results available.</p>
        {% endif %}
    </div>
</body>
</html>
"""


class HTMLReporter(BaseReporter):
    """Generate HTML format test reports using Jinja2 templates."""

    @property
    def format_name(self) -> str:
        return "html"

    def generate(self, report: TestReport) -> str:
        """Generate HTML report from test results."""
        template = Template(HTML_TEMPLATE)
        return template.render(
            report=report,
            summary=report.summary,
            results=report.results
        )
