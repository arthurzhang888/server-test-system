import pytest
import tempfile
import os
from pathlib import Path
from src.config.loader import ConfigLoader
from src.config.schemas import ServerType, DetectorMode


class TestConfigLoader:
    def test_load_valid_global_config(self):
        yaml_content = """
server_type: generic
mode: auto
detector_mode: mock
tests:
  - name: cpu_test
    enabled: true
    params:
      duration: 300
output:
  formats: [json, html]
  upload_to_ems: false
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            f.flush()
            config_path = f.name

        try:
            loader = ConfigLoader()
            config = loader.load_global_config(config_path)
            assert config.server_type == ServerType.GENERIC
            assert config.mode == "auto"
            assert config.detector_mode == DetectorMode.MOCK
            assert len(config.tests) == 1
            assert config.tests[0].name == "cpu_test"
        finally:
            os.unlink(config_path)

    def test_load_nonexistent_file_raises_error(self):
        loader = ConfigLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_global_config("/nonexistent/path.yaml")
