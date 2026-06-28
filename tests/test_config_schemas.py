import pytest
from src.config.schemas import DetectorMode, ServerType, TestConfig, GlobalConfig


def test_detector_mode_enum():
    assert DetectorMode.MOCK.value == "mock"
    assert DetectorMode.REAL.value == "real"


def test_server_type_enum():
    assert ServerType.GENERIC.value == "generic"
    assert ServerType.STORAGE.value == "storage"
    assert ServerType.COMPUTE.value == "compute"
    assert ServerType.AI_SERVER.value == "ai_server"


def test_test_config_defaults():
    config = TestConfig(name="cpu_test")
    assert config.enabled is True
    assert config.params == {}


def test_test_config_with_params():
    config = TestConfig(
        name="cpu_test",
        enabled=True,
        params={"duration": 300, "threads": "auto"}
    )
    assert config.params["duration"] == 300


def test_global_config_minimal():
    config = GlobalConfig(
        server_type=ServerType.GENERIC,
        mode="auto",
        tests=[]
    )
    assert config.server_type == ServerType.GENERIC
    assert config.detector_mode == DetectorMode.REAL  # default
