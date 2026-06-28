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
def run(config, output, mock, parallel, workers):
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


@cli.command()
def interactive():
    """Run tests in interactive wizard mode."""
    click.echo("Interactive mode - TODO: implement wizard")


if __name__ == '__main__':
    cli()
