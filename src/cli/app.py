import click
from pathlib import Path

from src.config import ConfigLoader
from src.core.state import TestReport
from src.reporters import JSONReporter


@click.group()
@click.version_option(version="0.1.0")
@click.pass_context
def cli(ctx):
    """Server Test System - Hardware testing for production servers."""
    ctx.ensure_object(dict)


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Path to config file')
@click.option('--output', '-o', type=click.Path(), default='./reports', help='Output directory')
@click.option('--mock', is_flag=True, help='Use mock mode for testing')
@click.option('--parallel/--sequential', default=True, help='Execution mode')
@click.option('--workers', '-w', type=int, default=4, help='Number of parallel workers')
@click.option('--stress', is_flag=True, help='Run stress tests after detection')
@click.option('--cpu-stress-duration', type=int, default=300, help='CPU stress duration in seconds')
@click.option('--gpu-stress-duration', type=int, default=300, help='GPU stress duration in seconds')
@click.option('--nvme-stress-duration', type=int, default=300, help='NVMe stress duration in seconds')
def run(config, output, mock, parallel, workers, stress, cpu_stress_duration, gpu_stress_duration, nvme_stress_duration):
    """Run hardware detection tests."""
    from src.core.engine import TestEngine, EngineConfig
    from src.core.scheduler import SchedulerConfig
    from src.detectors.base import DetectorMode
    from src.core.events import EventType

    click.echo("Starting Server Test System...")

    # Configure engine
    detector_mode = DetectorMode.MOCK if mock else DetectorMode.REAL
    strategy = "parallel" if parallel else "sequential"

    engine_config = EngineConfig(
        server_sn="UNKNOWN",  # Could detect from BIOS
        server_model="Unknown Model",
        server_type="generic",
        detector_mode=detector_mode,
        scheduler_config=SchedulerConfig(
            strategy=strategy,
            max_workers=workers
        ),
        output_dir=output
    )

    engine = TestEngine(engine_config)

    # Register progress callback
    engine.on_progress(lambda e: click.echo(
        f"Progress: {e.data['completed']}/{e.data['total']} "
        f"({e.data['percentage']:.1f}%) - {e.data['current_detector']}"
    ))

    # Register and run detectors
    engine.register_default_detectors()

    click.echo(f"Running {len(engine.detectors)} detectors in {strategy} mode...")

    report = engine.run()

    # Print summary
    click.echo("\n" + "=" * 50)
    click.echo("Test Summary")
    click.echo("=" * 50)
    click.echo(f"Total: {report.summary['total']}")
    click.echo(f"Passed: {report.summary['passed']}")
    click.echo(f"Failed: {report.summary['failed']}")
    click.echo(f"Errors: {report.summary['errors']}")
    click.echo(f"Duration: {report.duration_seconds:.2f}s")
    click.echo(f"Overall: {report.overall_status.value}")
    click.echo("=" * 50)
    click.echo(f"\nReport saved to: {output}/test_report.json")

    # Run stress tests if requested
    if stress:
        click.echo("\n" + "=" * 50)
        click.echo("Starting Stress Tests")
        click.echo("=" * 50)

        from src.core.stress_engine import StressTestEngine, StressEngineConfig
        from src.stress_tests.base import ThresholdConfig

        stress_config = StressEngineConfig(
            run_cpu_stress=True,
            run_gpu_stress=True,
            run_nvme_stress=True,
            cpu_duration_seconds=cpu_stress_duration,
            gpu_duration_seconds=gpu_stress_duration,
            nvme_duration_seconds=nvme_stress_duration,
            sample_interval_seconds=5,
            # Example thresholds - in production these would come from config file
            cpu_thresholds=None,  # Use defaults
            gpu_thresholds=None,
            nvme_thresholds=None
        )

        stress_engine = StressTestEngine(stress_config, engine.events)

        # Progress callback for stress tests
        def on_stress_progress(test_name: str, percentage: float, metrics: dict):
            metric_str = ", ".join([f"{k}={v:.1f}" for k, v in list(metrics.items())[:3]])
            click.echo(f"  {test_name}: {percentage:.1f}% - {metric_str}")

        stress_engine.add_progress_callback(on_stress_progress)

        # Run stress tests
        stress_results = stress_engine.run_all_stress_tests()

        # Convert and add to report
        stress_test_results = stress_engine.convert_to_test_results(stress_results)
        report.results.extend(stress_test_results)

        # Print stress test summary
        click.echo("\n" + "=" * 50)
        click.echo("Stress Test Summary")
        click.echo("=" * 50)
        for sr in stress_results:
            status_icon = "✓" if sr.status == "passed" else "✗"
            click.echo(f"{status_icon} {sr.test_name}: {sr.status} ({sr.duration_seconds:.1f}s)")
            for metric in sr.metrics:
                if metric.status.value in ["warning", "critical"]:
                    click.echo(f"  ! {metric.name}: {metric.value}{metric.unit} [{metric.status.value}]")
        click.echo("=" * 50)


@cli.command()
def interactive():
    """Run tests in interactive wizard mode."""
    click.echo("Interactive mode - TODO: implement wizard")


if __name__ == '__main__':
    cli()
