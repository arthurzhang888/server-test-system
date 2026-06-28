"""Interactive wizard mode for server testing."""

import click
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.config import ConfigLoader, GlobalConfig, ServerType
from src.config.schemas import TestConfig, CPUStressConfig, GPUStressConfig, NVMeStressConfig
from src.core.engine import TestEngine, EngineConfig
from src.core.stress_engine import StressTestEngine, StressEngineConfig
from src.core.state import TestStatus
from src.detectors.base import DetectorMode
from src.reporters import JSONReporter, HTMLReporter


class TestWizard:
    """Interactive test wizard for server testing."""

    def __init__(self):
        self.config: Optional[GlobalConfig] = None
        self.server_type: Optional[ServerType] = None
        self.selected_tests: List[str] = []
        self.detector_mode = DetectorMode.REAL
        self.output_dir = "./reports"
        self.results: List[Dict[str, Any]] = []

    def run(self) -> None:
        """Run the interactive wizard."""
        click.clear()
        self._show_banner()

        # Step 1: Select server type
        self._select_server_type()

        # Step 2: Select test mode
        self._select_detector_mode()

        # Step 3: Select tests to run
        self._select_tests()

        # Step 4: Configure stress tests (if selected)
        self._configure_stress_tests()

        # Step 5: Confirm and run
        if not self._confirm_run():
            click.echo("Cancelled.")
            return

        # Step 6: Run tests
        self._run_tests()

        # Step 7: Show summary
        self._show_summary()

    def _show_banner(self) -> None:
        """Show welcome banner."""
        click.echo("=" * 60)
        click.echo("  Server Test System - Interactive Mode")
        click.echo("=" * 60)
        click.echo()

    def _select_server_type(self) -> None:
        """Select server type."""
        click.echo("Step 1: Select Server Type")
        click.echo("-" * 40)

        server_types = [
            ("generic", "Generic Server - Standard rack/tower server"),
            ("storage", "Storage Server - High capacity storage server"),
            ("compute", "Compute Server - HPC server with high-speed network"),
            ("ai_server", "AI Server - AI training/inference with GPU/NPU"),
        ]

        for idx, (key, desc) in enumerate(server_types, 1):
            click.echo(f"  {idx}. {desc}")

        click.echo()
        choice = click.prompt("Select server type", type=int, default=1)

        if 1 <= choice <= len(server_types):
            self.server_type = ServerType(server_types[choice - 1][0])
        else:
            self.server_type = ServerType.GENERIC

        click.echo(f"Selected: {self.server_type.value}")
        click.echo()

    def _select_detector_mode(self) -> None:
        """Select detector mode (real/mock)."""
        click.echo("Step 2: Select Test Mode")
        click.echo("-" * 40)
        click.echo("  1. Real Mode - Test actual hardware (for production)")
        click.echo("  2. Mock Mode - Simulate hardware (for testing/demo)")
        click.echo()

        choice = click.prompt("Select mode", type=int, default=1)

        if choice == 2:
            self.detector_mode = DetectorMode.MOCK
            click.echo("Selected: Mock Mode")
        else:
            self.detector_mode = DetectorMode.REAL
            click.echo("Selected: Real Mode")

        click.echo()

    def _select_tests(self) -> None:
        """Select which tests to run."""
        click.echo("Step 3: Select Tests to Run")
        click.echo("-" * 40)

        available_tests = [
            ("hardware_detection", "Hardware Detection - Detect all hardware components"),
            ("cpu_stress", "CPU Stress Test - CPU load and thermal test"),
            ("gpu_stress", "GPU Stress Test - GPU load and thermal test"),
            ("nvme_stress", "NVMe Stress Test - SSD health and performance test"),
            ("memory_test", "Memory Test - ECC and stress test"),
            ("network_test", "Network Test - Throughput and connectivity"),
            ("storage_test", "Storage Test - Disk performance test"),
        ]

        click.echo("Available tests:")
        for idx, (key, desc) in enumerate(available_tests, 1):
            click.echo(f"  {idx}. {desc}")

        click.echo()
        click.echo("Enter test numbers (comma-separated, e.g., 1,2,3) or 'all'")
        selection = click.prompt("Select tests", default="all")

        if selection.lower() == "all":
            self.selected_tests = [t[0] for t in available_tests]
        else:
            try:
                indices = [int(x.strip()) for x in selection.split(",")]
                self.selected_tests = [
                    available_tests[i - 1][0]
                    for i in indices
                    if 1 <= i <= len(available_tests)
                ]
            except (ValueError, IndexError):
                self.selected_tests = ["hardware_detection"]

        click.echo(f"Selected {len(self.selected_tests)} test(s)")
        click.echo()

    def _configure_stress_tests(self) -> None:
        """Configure stress test parameters."""
        stress_tests = [t for t in self.selected_tests if "stress" in t or t in ["memory_test", "network_test", "storage_test"]]

        if not stress_tests:
            return

        click.echo("Step 4: Configure Stress Tests")
        click.echo("-" * 40)

        self.stress_configs = {}

        if "cpu_stress" in self.selected_tests:
            duration = click.prompt("CPU stress duration (seconds)", type=int, default=300)
            self.stress_configs["cpu"] = {"duration": duration}

        if "gpu_stress" in self.selected_tests:
            duration = click.prompt("GPU stress duration (seconds)", type=int, default=300)
            self.stress_configs["gpu"] = {"duration": duration}

        if "nvme_stress" in self.selected_tests:
            duration = click.prompt("NVMe stress duration (seconds)", type=int, default=300)
            self.stress_configs["nvme"] = {"duration": duration}

        click.echo()

    def _confirm_run(self) -> bool:
        """Show configuration summary and confirm."""
        click.echo("Step 5: Configuration Summary")
        click.echo("-" * 40)
        click.echo(f"Server Type: {self.server_type.value}")
        click.echo(f"Test Mode: {self.detector_mode.value}")
        click.echo(f"Tests: {', '.join(self.selected_tests)}")

        if hasattr(self, 'stress_configs'):
            for test, config in self.stress_configs.items():
                click.echo(f"  {test} stress: {config['duration']}s")

        click.echo()
        return click.confirm("Start testing?", default=True)

    def _run_tests(self) -> None:
        """Execute selected tests."""
        click.clear()
        click.echo("Running Tests...")
        click.echo("=" * 60)
        click.echo()

        # Hardware Detection
        if "hardware_detection" in self.selected_tests:
            self._run_hardware_detection()

        # Stress Tests
        stress_tests_to_run = [t for t in self.selected_tests if "stress" in t]
        if stress_tests_to_run:
            self._run_stress_tests(stress_tests_to_run)

        # Other tests would go here
        click.echo()

    def _run_hardware_detection(self) -> None:
        """Run hardware detection."""
        click.echo("Hardware Detection")
        click.echo("-" * 40)

        engine_config = EngineConfig(
            server_sn="UNKNOWN",
            server_model="Unknown",
            server_type=self.server_type.value,
            detector_mode=self.detector_mode,
            output_dir=self.output_dir
        )

        engine = TestEngine(engine_config)
        engine.register_default_detectors()

        # Progress callback
        completed = 0
        total = len(engine.detectors)

        def on_progress(event):
            nonlocal completed
            completed += 1
            pct = event.data.get("percentage", 0)
            detector = event.data.get("current_detector", "")
            click.echo(f"  [{completed}/{total}] {detector} - {pct:.1f}%")

        engine.on_progress(on_progress)

        report = engine.run()

        # Store results
        self.results.append({
            "name": "hardware_detection",
            "status": report.overall_status.value,
            "summary": report.summary
        })

        click.echo(f"  Result: {report.overall_status.value}")
        click.echo(f"  Passed: {report.summary['passed']}/{report.summary['total']}")
        click.echo()

    def _run_stress_tests(self, stress_tests: List[str]) -> None:
        """Run stress tests."""
        click.echo("Stress Tests")
        click.echo("-" * 40)

        stress_config = StressEngineConfig(
            run_cpu_stress="cpu_stress" in stress_tests,
            run_gpu_stress="gpu_stress" in stress_tests,
            run_nvme_stress="nvme_stress" in stress_tests,
            cpu_duration_seconds=self.stress_configs.get("cpu", {}).get("duration", 300),
            gpu_duration_seconds=self.stress_configs.get("gpu", {}).get("duration", 300),
            nvme_duration_seconds=self.stress_configs.get("nvme", {}).get("duration", 300),
        )

        stress_engine = StressTestEngine(stress_config)

        def on_progress(test_name, percentage, metrics):
            metric_str = ", ".join([f"{k}={v:.1f}" for k, v in list(metrics.items())[:2]])
            click.echo(f"  {test_name}: {percentage:.1f}% - {metric_str}")

        stress_engine.add_progress_callback(on_progress)

        results = stress_engine.run_all_stress_tests()

        for result in results:
            self.results.append({
                "name": result.test_name,
                "status": result.status,
                "violations": result.has_violations
            })

            status_icon = "✓" if result.status == "passed" else "✗"
            click.echo(f"  {status_icon} {result.test_name}: {result.status}")

            for metric in result.metrics:
                if metric.status.value in ["warning", "critical"]:
                    click.echo(f"    ! {metric.name}: {metric.value}{metric.unit}")

        click.echo()

    def _show_summary(self) -> None:
        """Show final summary."""
        click.echo("=" * 60)
        click.echo("Test Summary")
        click.echo("=" * 60)

        passed = sum(1 for r in self.results if r["status"] in ["passed", "completed"])
        failed = sum(1 for r in self.results if r["status"] in ["failed", "error"])

        for result in self.results:
            status = "✓" if result["status"] in ["passed", "completed"] else "✗"
            click.echo(f"  {status} {result['name']}: {result['status']}")

        click.echo()
        click.echo(f"Total: {len(self.results)}, Passed: {passed}, Failed: {failed}")
        click.echo()
        click.echo(f"Report saved to: {self.output_dir}/")


def run_interactive() -> None:
    """Entry point for interactive mode."""
    wizard = TestWizard()
    wizard.run()
