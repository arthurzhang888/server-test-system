import pytest
from src.stress_tests.base import (
    StressTestBase,
    ThresholdConfig,
    MetricResult,
    MetricStatus,
    StressTestResult
)


class TestThresholdConfig:
    def test_normal_value_within_range(self):
        config = ThresholdConfig(min_value=0, max_value=100)
        assert config.check_value(50) == MetricStatus.NORMAL

    def test_warning_near_upper_bound(self):
        config = ThresholdConfig(min_value=0, max_value=100, warning_pct=0.8, critical_pct=0.95)
        assert config.check_value(85) == MetricStatus.WARNING  # 85% of range

    def test_critical_exceeds_upper_bound(self):
        config = ThresholdConfig(min_value=0, max_value=100)
        assert config.check_value(110) == MetricStatus.CRITICAL

    def test_critical_below_lower_bound(self):
        config = ThresholdConfig(min_value=10, max_value=100)
        assert config.check_value(5) == MetricStatus.CRITICAL

    def test_no_lower_bound(self):
        config = ThresholdConfig(max_value=100)
        assert config.check_value(-50) == MetricStatus.NORMAL

    def test_no_upper_bound(self):
        config = ThresholdConfig(min_value=0)
        assert config.check_value(9999) == MetricStatus.NORMAL


class TestMetricResult:
    def test_metric_result_creation(self):
        result = MetricResult(
            name="temperature",
            value=75.5,
            unit="°C",
            status=MetricStatus.NORMAL
        )
        assert result.name == "temperature"
        assert result.value == 75.5
        assert result.unit == "°C"
        assert result.status == MetricStatus.NORMAL


class TestStressTestResult:
    def test_has_violations_with_critical(self):
        result = StressTestResult(
            test_name="cpu_stress",
            duration_seconds=60.0,
            status="failed",
            metrics=[
                MetricResult("temp", 95, "°C", MetricStatus.CRITICAL)
            ]
        )
        assert result.has_violations is True

    def test_no_violations_with_normal(self):
        result = StressTestResult(
            test_name="cpu_stress",
            duration_seconds=60.0,
            status="passed",
            metrics=[
                MetricResult("temp", 50, "°C", MetricStatus.NORMAL)
            ]
        )
        assert result.has_violations is False


class MockStressTest(StressTestBase):
    """Mock implementation for testing base class."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._started = False
        self._metrics_sequence = [
            {"temperature": 50.0, "utilization": 80.0},
            {"temperature": 60.0, "utilization": 90.0},
            {"temperature": 70.0, "utilization": 95.0},
        ]
        self._metric_index = 0

    @property
    def test_name(self) -> str:
        return "mock_stress"

    def start_stress(self) -> bool:
        self._started = True
        return True

    def stop_stress(self) -> None:
        self._started = False

    def collect_metrics(self) -> dict:
        metrics = self._metrics_sequence[self._metric_index % len(self._metrics_sequence)]
        self._metric_index += 1
        return metrics


class TestStressTestBase:
    def test_test_name_property(self):
        test = MockStressTest(duration_seconds=1, sample_interval_seconds=0.1)
        assert test.test_name == "mock_stress"

    def test_progress_callback(self):
        test = MockStressTest(duration_seconds=0.5, sample_interval_seconds=0.1)

        progress_calls = []
        def callback(pct, metrics):
            progress_calls.append((pct, metrics))

        test.set_progress_callback(callback)
        result = test.run()

        assert len(progress_calls) > 0
        assert result.status in ["passed", "failed"]

    def test_stop_early(self):
        test = MockStressTest(duration_seconds=10, sample_interval_seconds=0.1)

        import threading
        def stop_after_delay():
            import time
            time.sleep(0.3)
            test.stop()

        stop_thread = threading.Thread(target=stop_after_delay)
        stop_thread.start()

        result = test.run()
        stop_thread.join()

        assert result.duration_seconds < 5.0  # Should stop early
