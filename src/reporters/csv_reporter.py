import csv
import io

from .base import BaseReporter
from src.core.state import TestReport


class CSVReporter(BaseReporter):
    """Generate CSV format test reports."""

    @property
    def format_name(self) -> str:
        return "csv"

    def generate(self, report: TestReport) -> str:
        """Generate CSV report from test results."""
        output = io.StringIO()

        fieldnames = ["Test Name", "Status", "Duration (ms)", "Message"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)

        writer.writeheader()

        for result in report.results:
            writer.writerow({
                "Test Name": result.name,
                "Status": result.status.value,
                "Duration (ms)": result.duration_ms,
                "Message": result.message,
            })

        return output.getvalue()
