import pytest
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any

from src.core.engine import TestEngine, EngineConfig
from src.core.state import TestStatus
from src.core.events import EventType
from src.detectors.base import DetectorMode


class TestEngineConfig:
    def test_default_config(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic"
        )
        assert config.server_sn == "SN123"
        assert config.detector_mode == DetectorMode.MOCK


class TestTestEngineBasic:
    def test_engine_creation(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic"
        )
        engine = TestEngine(config)
        assert engine.config == config

    def test_register_default_detectors(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic"
        )
        engine = TestEngine(config)
        engine.register_default_detectors()
        assert len(engine.detectors) > 0

    def test_run_mock_mode(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic",
            detector_mode=DetectorMode.MOCK
        )
        engine = TestEngine(config)
        engine.register_default_detectors()
        engine.detectors = engine.detectors[:3]

        report = engine.run()

        assert report.server_sn == "SN123"
        assert len(report.results) == 3
        assert all(r.status == TestStatus.PASSED for r in report.results)

    def test_progress_events(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic",
            detector_mode=DetectorMode.MOCK
        )
        engine = TestEngine(config)
        engine.register_default_detectors()
        engine.detectors = engine.detectors[:2]

        progress_events = []
        engine.on_progress(lambda e: progress_events.append(e))

        engine.run()

        assert len(progress_events) > 0

    def test_report_summary(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic",
            detector_mode=DetectorMode.MOCK
        )
        engine = TestEngine(config)
        engine.register_default_detectors()
        engine.detectors = engine.detectors[:3]

        report = engine.run()

        assert report.summary["total"] == 3
        assert report.summary["passed"] == 3
        assert report.overall_status == TestStatus.PASSED

    def test_run_specific_detector(self):
        config = EngineConfig(
            server_sn="SN123",
            server_model="Test Model",
            server_type="generic",
            detector_mode=DetectorMode.MOCK
        )
        engine = TestEngine(config)
        engine.register_default_detectors()

        result = engine.run_detector("cpu")

        assert result.name == "cpu"
        assert result.status == TestStatus.PASSED
        assert "model" in result.details
