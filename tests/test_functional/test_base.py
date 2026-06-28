"""Tests for functional test base class."""

import pytest
from src.tests.base import (
    FunctionalTestBase,
    TestResult,
    TestStatus,
    TestConfig
)


class MockFunctionalTest(FunctionalTestBase):
    """Mock implementation for testing."""

    @property
    def test_name(self) -> str:
        return "mock_test"

    def run(self) -> TestResult:
        self._start_timer()
        return self._create_result(
            TestStatus.PASSED,
            "Mock test passed",
            {"key": "value"},
            {"metric1": 100.0}
        )


class TestTestResult:
    def test_result_creation(self):
        result = TestResult(
            name="test1",
            status=TestStatus.PASSED,
            duration_seconds=1.5,
            message="Test passed",
            details={"info": "detail"},
            metrics={"speed": 100.0}
        )
        assert result.name == "test1"
        assert result.status == TestStatus.PASSED
        assert result.duration_seconds == 1.5


class TestFunctionalTestBase:
    def test_test_name_property(self):
        test = MockFunctionalTest()
        assert test.test_name == "mock_test"

    def test_create_result(self):
        test = MockFunctionalTest()
        test._start_timer()
        result = test._create_result(
            TestStatus.PASSED,
            "All good",
            {"data": "value"}
        )
        assert result.status == TestStatus.PASSED
        assert result.message == "All good"
        assert result.details["data"] == "value"

    def test_validate_threshold(self):
        test = MockFunctionalTest()

        # Within range
        valid, msg = test._validate_threshold(50, 0, 100)
        assert valid is True
        assert msg == ""

        # Below min
        valid, msg = test._validate_threshold(-5, 0, 100)
        assert valid is False
        assert "below minimum" in msg

        # Above max
        valid, msg = test._validate_threshold(150, 0, 100)
        assert valid is False
        assert "above maximum" in msg

    def test_run_mock_test(self):
        test = MockFunctionalTest()
        result = test.run()
        assert result.status == TestStatus.PASSED
        assert result.message == "Mock test passed"
