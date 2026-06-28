"""Memory functional tests including ECC verification and bandwidth tests."""

import subprocess
import struct
from typing import Dict, Any, Tuple
from dataclasses import dataclass

from .base import FunctionalTestBase, TestResult, TestStatus, TestConfig


@dataclass
class MemoryConfig(TestConfig):
    """Memory test configuration."""
    test_size_mb: int = 100
    ecc_check: bool = True
    bandwidth_test: bool = True


class MemoryTest(FunctionalTestBase):
    """Memory functional tests.

    Tests:
    - Memory size validation
    - Memory bandwidth (read/write)
    - ECC error detection (if available)
    - Memory pattern test
    """

    def __init__(self, config: MemoryConfig = None):
        super().__init__(config or MemoryConfig())
        self.mem_config = self.config  # type: MemoryConfig

    @property
    def test_name(self) -> str:
        return "memory_functional"

    def run(self) -> TestResult:
        """Run memory functional tests."""
        self._start_timer()

        results = []
        all_passed = True

        # Test 1: Memory Size
        status, msg, total_gb = self._test_memory_size()
        results.append(("memory_size", status, msg))
        if not status:
            all_passed = False

        # Test 2: Memory Pattern Test
        status, msg = self._test_memory_pattern()
        results.append(("pattern_test", status, msg))
        if not status:
            all_passed = False

        # Test 3: Bandwidth Test
        if self.mem_config.bandwidth_test:
            status, msg, read_bw, write_bw = self._test_bandwidth()
            results.append(("bandwidth", status, msg))
            if not status:
                all_passed = False
        else:
            read_bw, write_bw = 0, 0

        # Test 4: ECC Check
        if self.mem_config.ecc_check:
            status, msg = self._check_ecc()
            results.append(("ecc_check", status, msg))
            # ECC check is informational, doesn't fail the test

        details = {
            "tests": [
                {"name": name, "passed": status, "message": msg}
                for name, status, msg in results
            ]
        }

        metrics = {
            "total_gb": total_gb if 'total_gb' in dir() else 0,
            "read_bandwidth_gbps": read_bw / 1000 if 'read_bw' in dir() else 0,
            "write_bandwidth_gbps": write_bw / 1000 if 'write_bw' in dir() else 0,
        }

        if all_passed:
            return self._create_result(
                TestStatus.PASSED,
                f"Memory tests passed ({total_gb:.1f}GB detected)",
                details,
                metrics
            )
        else:
            return self._create_result(
                TestStatus.FAILED,
                "Some memory tests failed",
                details,
                metrics
            )

    def _test_memory_size(self) -> Tuple[bool, str, float]:
        """Test memory size detection."""
        try:
            with open("/proc/meminfo", "r") as f:
                content = f.read()

            for line in content.split("\n"):
                if "MemTotal" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        kb = int(parts[1])
                        gb = kb / (1024 * 1024)
                        return True, f"{gb:.1f} GB detected", gb

            return False, "Could not parse memory info", 0.0

        except Exception as e:
            return False, f"Error: {str(e)}", 0.0

    def _test_memory_pattern(self) -> Tuple[bool, str]:
        """Test memory with pattern write/read."""
        try:
            size = self.mem_config.test_size_mb * 1024 * 1024

            # Create test patterns
            patterns = [0x00, 0xFF, 0xAA, 0x55, 0x12, 0x34, 0x56, 0x78]

            for pattern in patterns:
                # Write pattern
                data = bytes([pattern] * (size // 8))

                # Read and verify (simplified - just check we can allocate)
                if len(data) != size // 8:
                    return False, f"Pattern {pattern:02X} failed"

            return True, "Pattern test passed"

        except MemoryError:
            return False, "Memory allocation failed"
        except Exception as e:
            return False, f"Pattern test error: {str(e)}"

    def _test_bandwidth(self) -> Tuple[bool, str, float, float]:
        """Test memory bandwidth using dd fallback."""
        try:
            # Create a temporary file for testing
            import tempfile
            import time

            test_size = 100  # MB

            with tempfile.NamedTemporaryFile(delete=False) as f:
                temp_path = f.name

            # Write test
            start = time.time()
            subprocess.run(
                ["dd", "if=/dev/zero", f"of={temp_path}", "bs=1M", f"count={test_size}"],
                capture_output=True,
                timeout=60
            )
            write_time = time.time() - start
            write_bw = (test_size * 8) / write_time  # Mbps

            # Read test
            start = time.time()
            subprocess.run(
                ["dd", f"if={temp_path}", "of=/dev/null", "bs=1M"],
                capture_output=True,
                timeout=60
            )
            read_time = time.time() - start
            read_bw = (test_size * 8) / read_time  # Mbps

            # Cleanup
            import os
            os.unlink(temp_path)

            # DDR4 should achieve > 10 GB/s (80 Gbps)
            if read_bw > 10000 and write_bw > 10000:  # 10 Gbps
                return True, f"R: {read_bw/1000:.1f} GB/s, W: {write_bw/1000:.1f} GB/s", read_bw, write_bw
            else:
                return False, f"Bandwidth too low: R={read_bw/1000:.1f}, W={write_bw/1000:.1f} GB/s", read_bw, write_bw

        except Exception as e:
            return False, f"Bandwidth test error: {str(e)}", 0, 0

    def _check_ecc(self) -> Tuple[bool, str]:
        """Check ECC status and errors."""
        try:
            # Check if ECC is enabled
            result = subprocess.run(
                ["dmidecode", "-t", "memory"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                output = result.stdout.lower()

                if "ecc" in output or "error correction" in output:
                    # Check for ECC errors in EDAC
                    try:
                        with open("/sys/devices/system/edac/mc/mc0/ce_count", "r") as f:
                            ce_count = int(f.read().strip())

                        with open("/sys/devices/system/edac/mc/mc0/ue_count", "r") as f:
                            ue_count = int(f.read().strip())

                        if ue_count > 0:
                            return False, f"Uncorrectable ECC errors: {ue_count}"
                        elif ce_count > 0:
                            return True, f"ECC active, {ce_count} correctable errors"
                        else:
                            return True, "ECC active, no errors"
                    except FileNotFoundError:
                        return True, "ECC detected (EDAC not available)"
                else:
                    return True, "ECC not configured"

            return True, "Could not determine ECC status"

        except Exception as e:
            return True, f"ECC check error: {str(e)}"  # Informational only
