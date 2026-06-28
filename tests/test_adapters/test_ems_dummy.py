"""Tests for DummyEMSAdapter."""

import pytest
import requests
import time
import threading
from datetime import datetime

from src.adapters.ems_dummy import DummyEMSAdapter


class TestDummyEMSAdapter:
    """Test suite for DummyEMSAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create and start adapter for testing."""
        adapter = DummyEMSAdapter(host="127.0.0.1", port=18080)
        adapter.start()
        # Wait for server to start
        time.sleep(0.5)
        yield adapter
        adapter.stop()
        time.sleep(0.1)

    def test_adapter_stores_received_results(self, adapter):
        """Test that adapter stores results received via POST."""
        result_data = {
            "test_name": "cpu_test",
            "status": "passed",
            "duration_ms": 1000,
            "timestamp": datetime.now().isoformat()
        }

        response = requests.post(
            "http://127.0.0.1:18080/api/v1/results",
            json=result_data,
            timeout=5
        )

        assert response.status_code == 201
        assert len(adapter.get_results()) == 1
        assert adapter.get_results()[0]["test_name"] == "cpu_test"

    def test_get_results_endpoint_returns_all_results(self, adapter):
        """Test GET /api/v1/results returns all stored results."""
        # Add multiple results
        for i in range(3):
            requests.post(
                "http://127.0.0.1:18080/api/v1/results",
                json={
                    "test_name": f"test_{i}",
                    "status": "passed",
                    "duration_ms": 100
                },
                timeout=5
            )

        response = requests.get(
            "http://127.0.0.1:18080/api/v1/results",
            timeout=5
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 3
        assert data["count"] == 3

    def test_get_results_by_test_name(self, adapter):
        """Test filtering results by test name."""
        requests.post(
            "http://127.0.0.1:18080/api/v1/results",
            json={"test_name": "cpu_test", "status": "passed"},
            timeout=5
        )
        requests.post(
            "http://127.0.0.1:18080/api/v1/results",
            json={"test_name": "memory_test", "status": "failed"},
            timeout=5
        )

        response = requests.get(
            "http://127.0.0.1:18080/api/v1/results?test_name=cpu_test",
            timeout=5
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["test_name"] == "cpu_test"

    def test_post_invalid_data_returns_error(self, adapter):
        """Test that invalid data returns 422 error."""
        response = requests.post(
            "http://127.0.0.1:18080/api/v1/results",
            json={"invalid_field": "value"},
            timeout=5
        )

        assert response.status_code == 422

    def test_root_endpoint_returns_status(self, adapter):
        """Test root endpoint returns adapter status."""
        response = requests.get(
            "http://127.0.0.1:18080/",
            timeout=5
        )

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "adapter" in data

    def test_clear_results_endpoint(self, adapter):
        """Test clearing all results."""
        requests.post(
            "http://127.0.0.1:18080/api/v1/results",
            json={"test_name": "test1", "status": "passed"},
            timeout=5
        )

        assert len(adapter.get_results()) == 1

        response = requests.delete(
            "http://127.0.0.1:18080/api/v1/results",
            timeout=5
        )

        assert response.status_code == 200
        assert len(adapter.get_results()) == 0


class TestDummyEMSAdapterWithoutServer:
    """Tests that don't require running server."""

    def test_adapter_initialization(self):
        """Test adapter can be initialized."""
        adapter = DummyEMSAdapter(host="0.0.0.0", port=9000)
        assert adapter.host == "0.0.0.0"
        assert adapter.port == 9000
        assert adapter.get_results() == []

    def test_get_results_returns_copy(self):
        """Test get_results returns a copy of results list."""
        adapter = DummyEMSAdapter()
        adapter.results.append({"test": "data"})

        results = adapter.get_results()
        results.append({"new": "data"})

        assert len(adapter.get_results()) == 1
