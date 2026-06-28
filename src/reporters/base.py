from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from src.core.state import TestReport


class BaseReporter(ABC):
    """Abstract base class for report generators."""

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Return the format name (e.g., 'json', 'html', 'csv')."""
        pass

    @abstractmethod
    def generate(self, report: TestReport) -> str:
        """Generate report content as string."""
        pass

    def save(self, report: TestReport, output_path: Union[str, Path]) -> Path:
        """Generate and save report to file."""
        output_path = Path(output_path)
        content = self.generate(report)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_path
