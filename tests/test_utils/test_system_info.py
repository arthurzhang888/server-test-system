"""Tests for system info utilities."""

import pytest
from unittest.mock import patch, mock_open, MagicMock

from src.utils.system_info import get_server_serial, get_server_model, get_board_serial


class TestGetServerSerial:
    """Tests for get_server_serial function."""

    @patch("os.path.exists")
    @patch("builtins.open", mock_open(read_data="ABC123456"))
    def test_get_serial_from_sysfs(self, mock_exists):
        """Test reading serial from sysfs."""
        mock_exists.return_value = True
        serial = get_server_serial()
        assert serial == "ABC123456"

    @patch("os.path.exists")
    @patch("builtins.open", mock_open(read_data="Unknown"))
    def test_get_serial_unknown_fallback(self, mock_exists):
        """Test fallback when serial is 'Unknown'."""
        mock_exists.return_value = True
        serial = get_server_serial()
        # Should return UNKNOWN since 'Unknown' is not a valid serial
        assert serial == "UNKNOWN"

    @patch("os.path.exists")
    @patch("src.utils.system_info.subprocess.run")
    def test_get_serial_from_dmidecode(self, mock_run, mock_exists):
        """Test reading serial from dmidecode."""
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="SN123456\n"
        )
        serial = get_server_serial()
        assert serial == "SN123456"

    @patch("os.path.exists")
    def test_get_serial_all_fail(self, mock_exists):
        """Test returns UNKNOWN when all methods fail."""
        mock_exists.return_value = False
        serial = get_server_serial()
        assert serial == "UNKNOWN"


class TestGetServerModel:
    """Tests for get_server_model function."""

    @patch("os.path.exists")
    @patch("builtins.open", mock_open(read_data="Dell PowerEdge R750"))
    def test_get_model_from_sysfs(self, mock_exists):
        """Test reading model from sysfs."""
        mock_exists.return_value = True
        model = get_server_model()
        assert model == "Dell PowerEdge R750"

    @patch("os.path.exists")
    @patch("src.utils.system_info.subprocess.run")
    def test_get_model_from_dmidecode(self, mock_run, mock_exists):
        """Test reading model from dmidecode."""
        mock_exists.return_value = False
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="PowerEdge R750\n"
        )
        model = get_server_model()
        assert model == "PowerEdge R750"

    @patch("os.path.exists")
    def test_get_model_default(self, mock_exists):
        """Test returns default when all methods fail."""
        mock_exists.return_value = False
        model = get_server_model()
        assert model == "Unknown Model"


class TestGetBoardSerial:
    """Tests for get_board_serial function."""

    @patch("os.path.exists")
    @patch("builtins.open", mock_open(read_data="CNA123456789"))
    def test_get_board_serial_from_sysfs(self, mock_exists):
        """Test reading board serial from sysfs."""
        mock_exists.return_value = True
        serial = get_board_serial()
        assert serial == "CNA123456789"
