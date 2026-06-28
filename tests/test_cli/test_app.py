import pytest
from click.testing import CliRunner
from src.cli.app import cli


class TestCLI:
    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'Server Test System' in result.output

    def test_version_flag(self):
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert 'version' in result.output.lower()
