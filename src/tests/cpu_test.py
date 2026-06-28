"""CPU functional tests including floating point and integer benchmarks."""

import subprocess
import time
import os
from typing import Dict, Any, List
from dataclasses import dataclass

from .base import FunctionalTestBase, TestResult, TestStatus, TestConfig


@dataclass
class CPUConfig(TestConfig):
    """CPU test configuration."""
    stress_duration: int = 60
    threads: int = 0  # 0 = auto (CPU count)
    fp_benchmark_iterations: int = 1000000
    int_benchmark_iterations: int = 10000000


class CPUTest(FunctionalTestBase):
    """CPU functional and performance tests.

    Tests:
    - CPU information validation
    - Floating point performance
    - Integer performance
    - Multi-threading capability
    - Thermal stability (if run with stress)
    """

    def __init__(self, config: CPUConfig = None):
        super().__init__(config or CPUConfig())
        self.cpu_config = self.config  # type: CPUConfig

    @property
    def test_name(self) -> str:
        return "cpu_functional"

    def run(self) -> TestResult:
        """Run CPU functional tests."""
        self._start_timer()

        results = []
        all_passed = True

        # Test 1: CPU Info Validation
        status, msg = self._test_cpu_info()
        results.append(("cpu_info", status, msg))
        if not status:
            all_passed = False

        # Test 2: Single-thread FP Performance
        status, msg, fp_score = self._test_fp_performance()
        results.append(("fp_performance", status, msg))
        if not status:
            all_passed = False

        # Test 3: Single-thread Integer Performance
        status, msg, int_score = self._test_int_performance()
        results.append(("int_performance", status, msg))
        if not status:
            all_passed = False

        # Test 4: Multi-thread Scaling
        status, msg, scaling = self._test_mt_scaling()
        results.append(("mt_scaling", status, msg))
        if not status:
            all_passed = False

        # Compile results
        details = {
            "tests": [
                {"name": name, "passed": status, "message": msg}
                for name, status, msg in results
            ]
        }

        metrics = {
            "fp_score": fp_score if 'fp_score' in dir() else 0,
            "int_score": int_score if 'int_score' in dir() else 0,
            "mt_scaling": scaling if 'scaling' in dir() else 0,
        }

        if all_passed:
            return self._create_result(
                TestStatus.PASSED,
                "All CPU tests passed",
                details,
                metrics
            )
        else:
            return self._create_result(
                TestStatus.FAILED,
                "Some CPU tests failed",
                details,
                metrics
            )

    def _test_cpu_info(self) -> tuple[bool, str]:
        """Test CPU information retrieval."""
        try:
            with open("/proc/cpuinfo", "r") as f:
                content = f.read()

            if "model name" in content:
                # Extract CPU model
                for line in content.split("\n"):
                    if "model name" in line:
                        model = line.split(":")[1].strip()
                        return True, f"Detected: {model}"

            return False, "Could not parse CPU info"

        except Exception as e:
            return False, f"Error reading CPU info: {str(e)}"

    def _test_fp_performance(self) -> tuple[bool, str, float]:
        """Test floating point performance."""
        try:
            start = time.time()

            # Simple FP benchmark
            result = 0.0
            for i in range(self.cpu_config.fp_benchmark_iterations):
                result += (i * 3.14159) / 2.71828

            elapsed = time.time() - start
            score = self.cpu_config.fp_benchmark_iterations / elapsed

            # Score should be reasonable for modern CPUs (> 1M ops/sec)
            if score > 1000000:
                return True, f"FP score: {score:.0f} ops/sec", score
            else:
                return False, f"FP performance too low: {score:.0f} ops/sec", score

        except Exception as e:
            return False, f"FP test error: {str(e)}", 0.0

    def _test_int_performance(self) -> tuple[bool, str, float]:
        """Test integer performance."""
        try:
            start = time.time()

            # Simple integer benchmark
            result = 0
            for i in range(self.cpu_config.int_benchmark_iterations):
                result += i * 17 + 42

            elapsed = time.time() - start
            score = self.cpu_config.int_benchmark_iterations / elapsed

            # Score should be reasonable (> 10M ops/sec)
            if score > 10000000:
                return True, f"INT score: {score:.0f} ops/sec", score
            else:
                return False, f"INT performance too low: {score:.0f} ops/sec", score

        except Exception as e:
            return False, f"INT test error: {str(e)}", 0.0

    def _test_mt_scaling(self) -> tuple[bool, str, float]:
        """Test multi-thread scaling."""
        import threading

        cpu_count = os.cpu_count() or 4

        def work():
            total = 0
            for i in range(1000000):
                total += i
            return total

        # Single thread baseline
        start = time.time()
        work()
        single_time = time.time() - start

        # Multi-thread test
        threads = []
        start = time.time()
        for _ in range(cpu_count):
            t = threading.Thread(target=work)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        multi_time = time.time() - start

        # Calculate scaling efficiency
        scaling = (single_time * cpu_count) / multi_time

        # Should achieve at least 50% scaling efficiency
        if scaling >= 0.5 * cpu_count:
            return True, f"MT scaling: {scaling:.1f}x on {cpu_count} cores", scaling
        else:
            return False, f"Poor MT scaling: {scaling:.1f}x on {cpu_count} cores", scaling
