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
def run(config, output, mock):
    """Run tests in automatic mode."""
    click.echo("Starting Server Test System...")

    # Load configuration
    loader = ConfigLoader()
    if config:
        cfg = loader.load_global_config(config)
    else:
        default_config = Path(__file__).parent.parent.parent / "config" / "global.yaml"
        cfg = loader.load_global_config(default_config)

    # Override with mock mode if specified
    if mock:
        from src.config.schemas import DetectorMode
        cfg.detector_mode = DetectorMode.MOCK
        click.echo("Running in MOCK mode (simulated hardware)")

    click.echo(f"Server type: {cfg.server_type.value}")
    click.echo(f"Mode: {cfg.mode}")
    click.echo(f"Tests to run: {len(cfg.tests)}")

    # TODO: Run actual tests (will be implemented in later tasks)
    # For now, create a minimal report
    report = TestReport(
        server_sn="UNKNOWN",
        server_model="Unknown Model",
        server_type=cfg.server_type.value
    )

    # Generate report
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    reporter = JSONReporter()
    report_file = output_path / "test_report.json"
    reporter.save(report, report_file)

    click.echo(f"\nReport saved to: {report_file}")
    click.echo("Test run completed.")


@cli.command()
def interactive():
    """Run tests in interactive wizard mode."""
    click.echo("Interactive mode - TODO: implement wizard")


if __name__ == '__main__':
    cli()
