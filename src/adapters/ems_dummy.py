"""Dummy EMS Adapter for simulating Enterprise Management System."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from threading import Thread

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from src.adapters.base import BaseAdapter


logger = logging.getLogger(__name__)


class TestResultInput(BaseModel):
    """Model for test result input data."""

    test_name: str = Field(..., description="Name of the test")
    status: str = Field(..., description="Test status (passed/failed/skipped/error)")
    duration_ms: Optional[int] = Field(None, description="Test duration in milliseconds")
    message: Optional[str] = Field(None, description="Additional test message")
    timestamp: Optional[str] = Field(None, description="ISO format timestamp")
    server_sn: Optional[str] = Field(None, description="Server serial number")
    component: Optional[str] = Field(None, description="Component being tested")


class TestResultStored(TestResultInput):
    """Model for stored test result with generated fields."""

    id: str = Field(..., description="Unique result ID")
    received_at: str = Field(..., description="When result was received")


class ResultsResponse(BaseModel):
    """Response model for results query."""

    results: List[Dict[str, Any]]
    count: int


class DummyEMSAdapter(BaseAdapter):
    """Dummy EMS Adapter that provides HTTP endpoints for receiving test results.

    This adapter simulates an Enterprise Management System by providing
    RESTful APIs to receive, store, and query test results.

    Example:
        adapter = DummyEMSAdapter(host="0.0.0.0", port=8080)
        adapter.start()
        # ... use adapter ...
        adapter.stop()
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        """Initialize the Dummy EMS Adapter.

        Args:
            host: Host address to bind the server to.
            port: Port number to listen on.
        """
        super().__init__(name="dummy_ems")
        self.host = host
        self.port = port
        self.results: List[Dict[str, Any]] = []
        self._app = FastAPI(
            title="Dummy EMS Adapter",
            description="Simulates EMS for receiving test results",
            version="1.0.0"
        )
        self._server: Optional[Thread] = None
        self._uvicorn_server: Optional[uvicorn.Server] = None
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Configure FastAPI routes."""

        @self._app.get("/", response_class=JSONResponse)
        async def root():
            """Root endpoint returning adapter status."""
            return {
                "status": "running" if self._is_running else "stopped",
                "adapter": "DummyEMSAdapter",
                "version": "1.0.0",
                "results_count": len(self.results)
            }

        @self._app.get("/health", response_class=JSONResponse)
        async def health():
            """Health check endpoint."""
            return self.health_check()

        @self._app.post("/api/v1/results", status_code=201)
        async def receive_result(result: TestResultInput):
            """Receive a test result via POST.

            Args:
                result: Test result data.

            Returns:
                Stored result with generated ID and timestamp.
            """
            stored_result = {
                "id": str(uuid.uuid4()),
                "test_name": result.test_name,
                "status": result.status,
                "duration_ms": result.duration_ms,
                "message": result.message,
                "timestamp": result.timestamp or datetime.now().isoformat(),
                "server_sn": result.server_sn,
                "component": result.component,
                "received_at": datetime.now().isoformat()
            }
            self.results.append(stored_result)
            logger.info(
                f"Received test result: {result.test_name} - {result.status}"
            )
            return stored_result

        @self._app.get("/api/v1/results", response_model=ResultsResponse)
        async def get_results(
            test_name: Optional[str] = Query(None, description="Filter by test name"),
            status: Optional[str] = Query(None, description="Filter by status"),
            server_sn: Optional[str] = Query(None, description="Filter by server serial number")
        ):
            """Get all stored test results with optional filtering.

            Args:
                test_name: Optional filter by test name.
                status: Optional filter by test status.
                server_sn: Optional filter by server serial number.

            Returns:
                List of matching results.
            """
            filtered_results = self.results.copy()

            if test_name:
                filtered_results = [
                    r for r in filtered_results if r["test_name"] == test_name
                ]
            if status:
                filtered_results = [
                    r for r in filtered_results if r["status"] == status
                ]
            if server_sn:
                filtered_results = [
                    r for r in filtered_results if r.get("server_sn") == server_sn
                ]

            return ResultsResponse(
                results=filtered_results,
                count=len(filtered_results)
            )

        @self._app.delete("/api/v1/results")
        async def clear_results():
            """Clear all stored results.

            Returns:
                Success message with count of cleared results.
            """
            count = len(self.results)
            self.results.clear()
            logger.info(f"Cleared {count} test results")
            return {"message": "Results cleared", "count": count}

        @self._app.get("/ui", response_class=HTMLResponse)
        async def web_interface():
            """Simple web interface to view results."""
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Dummy EMS - Test Results</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    h1 { color: #333; }
                    table { border-collapse: collapse; width: 100%; margin-top: 20px; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                    th { background-color: #4CAF50; color: white; }
                    tr:nth-child(even) { background-color: #f2f2f2; }
                    .status-passed { color: green; font-weight: bold; }
                    .status-failed { color: red; font-weight: bold; }
                    .status-skipped { color: orange; font-weight: bold; }
                    .status-error { color: darkred; font-weight: bold; }
                    .refresh-btn {
                        background-color: #4CAF50;
                        color: white;
                        padding: 10px 20px;
                        border: none;
                        cursor: pointer;
                        margin-bottom: 20px;
                    }
                    .refresh-btn:hover { background-color: #45a049; }
                    .clear-btn {
                        background-color: #f44336;
                        color: white;
                        padding: 10px 20px;
                        border: none;
                        cursor: pointer;
                        margin-left: 10px;
                    }
                    .clear-btn:hover { background-color: #da190b; }
                    .info { color: #666; margin-bottom: 10px; }
                </style>
                <script>
                    async function loadResults() {
                        const response = await fetch('/api/v1/results');
                        const data = await response.json();
                        const tbody = document.getElementById('results-body');
                        tbody.innerHTML = '';

                        data.results.forEach(result => {
                            const row = tbody.insertRow();
                            row.innerHTML = `
                                <td>${result.id.substring(0, 8)}...</td>
                                <td>${result.test_name}</td>
                                <td class="status-${result.status}">${result.status}</td>
                                <td>${result.component || '-'}</td>
                                <td>${result.server_sn || '-'}</td>
                                <td>${result.duration_ms || '-'} ms</td>
                                <td>${result.received_at}</td>
                                <td>${result.message || '-'}</td>
                            `;
                        });

                        document.getElementById('count').textContent = data.count;
                    }

                    async function clearResults() {
                        if (confirm('Clear all results?')) {
                            await fetch('/api/v1/results', { method: 'DELETE' });
                            loadResults();
                        }
                    }

                    setInterval(loadResults, 5000);
                    window.onload = loadResults;
                </script>
            </head>
            <body>
                <h1>Dummy EMS - Test Results</h1>
                <p class="info">
                    Total Results: <span id="count">0</span> |
                    Auto-refresh every 5 seconds
                </p>
                <button class="refresh-btn" onclick="loadResults()">Refresh Now</button>
                <button class="clear-btn" onclick="clearResults()">Clear All</button>

                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Test Name</th>
                            <th>Status</th>
                            <th>Component</th>
                            <th>Server SN</th>
                            <th>Duration</th>
                            <th>Received At</th>
                            <th>Message</th>
                        </tr>
                    </thead>
                    <tbody id="results-body">
                    </tbody>
                </table>
            </body>
            </html>
            """
            return html_content

    def start(self) -> None:
        """Start the HTTP server in a background thread."""
        if self._is_running:
            logger.warning("Adapter is already running")
            return

        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="warning"
        )
        self._uvicorn_server = uvicorn.Server(config)

        def run_server():
            self._uvicorn_server.run()

        self._server = Thread(target=run_server, daemon=True)
        self._server.start()
        self._is_running = True
        logger.info(f"DummyEMSAdapter started on http://{self.host}:{self.port}")
        logger.info(f"Web interface available at http://{self.host}:{self.port}/ui")

    def stop(self) -> None:
        """Stop the HTTP server."""
        if not self._is_running:
            return

        if self._uvicorn_server:
            self._uvicorn_server.should_exit = True

        self._is_running = False
        logger.info("DummyEMSAdapter stopped")

    def is_running(self) -> bool:
        """Check if adapter is running.

        Returns:
            True if server is active, False otherwise.
        """
        return self._is_running

    def get_results(self) -> List[Dict[str, Any]]:
        """Get all stored results.

        Returns:
            Copy of the results list.
        """
        return self.results.copy()

    def clear_results(self) -> int:
        """Clear all stored results.

        Returns:
            Number of results cleared.
        """
        count = len(self.results)
        self.results.clear()
        return count
