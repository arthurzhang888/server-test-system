"""FastAPI central server for test management."""

import asyncio
import time
from typing import Dict, List, Set, Optional
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    TestJob, TestResult, TestProgress, ClientInfo,
    JobStatus, ClientStatus, ServerStatus
)


class ConnectionManager:
    """Manage WebSocket connections from test clients."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_info: Dict[str, ClientInfo] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        if client_id in self.client_info:
            self.client_info[client_id].status = ClientStatus.ONLINE
            self.client_info[client_id].last_seen = datetime.now()

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.client_info:
            self.client_info[client_id].status = ClientStatus.OFFLINE

    async def send_progress(self, client_id: str, progress: TestProgress):
        """Send progress update to specific client."""
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(progress.dict())

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = []
        for client_id, connection in self.active_connections.items():
            try:
                await connection.send_json(message)
            except:
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            self.disconnect(client_id)

    def update_client(self, client_info: ClientInfo):
        """Update or add client information."""
        self.client_info[client_info.id] = client_info

    def get_online_clients(self) -> List[ClientInfo]:
        """Get list of online clients."""
        return [
            client for client in self.client_info.values()
            if client.status != ClientStatus.OFFLINE
        ]


class JobManager:
    """Manage test jobs."""

    def __init__(self):
        self.jobs: Dict[str, TestJob] = {}
        self.results: Dict[str, TestResult] = {}
        self.client_jobs: Dict[str, List[str]] = {}

    def create_job(self, job: TestJob) -> TestJob:
        """Create a new test job."""
        self.jobs[job.id] = job
        if job.client_id not in self.client_jobs:
            self.client_jobs[job.client_id] = []
        self.client_jobs[job.client_id].append(job.id)
        return job

    def get_job(self, job_id: str) -> Optional[TestJob]:
        """Get job by ID."""
        return self.jobs.get(job_id)

    def update_job_status(self, job_id: str, status: JobStatus):
        """Update job status."""
        if job_id in self.jobs:
            self.jobs[job_id].status = status
            if status == JobStatus.RUNNING:
                self.jobs[job_id].started_at = datetime.now()
            elif status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                self.jobs[job_id].completed_at = datetime.now()

    def store_result(self, result: TestResult):
        """Store test result."""
        self.results[result.job_id] = result
        self.update_job_status(result.job_id, JobStatus.COMPLETED)

    def get_client_jobs(self, client_id: str) -> List[TestJob]:
        """Get all jobs for a client."""
        job_ids = self.client_jobs.get(client_id, [])
        return [self.jobs[jid] for jid in job_ids if jid in self.jobs]

    def get_pending_jobs(self, client_id: Optional[str] = None) -> List[TestJob]:
        """Get pending jobs, optionally filtered by client."""
        jobs = [
            job for job in self.jobs.values()
            if job.status == JobStatus.PENDING
        ]
        if client_id:
            jobs = [j for j in jobs if j.client_id == client_id]
        return jobs


# Global managers
manager = ConnectionManager()
job_manager = JobManager()
start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    # Startup
    print("Central Server starting...")
    yield
    # Shutdown
    print("Central Server shutting down...")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Server Test System - Central Server",
        description="Central management server for server testing",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def root():
        return {"message": "Server Test System Central Server", "version": "1.0.0"}

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "healthy"}

    @app.get("/api/v1/status", response_model=ServerStatus)
    async def get_status():
        """Get server status."""
        return ServerStatus(
            uptime_seconds=time.time() - start_time,
            connected_clients=len(manager.active_connections),
            active_jobs=sum(1 for j in job_manager.jobs.values() if j.status == JobStatus.RUNNING),
            completed_jobs=sum(1 for j in job_manager.jobs.values() if j.status == JobStatus.COMPLETED),
            failed_jobs=sum(1 for j in job_manager.jobs.values() if j.status == JobStatus.FAILED)
        )

    # Client management endpoints
    @app.get("/api/v1/clients", response_model=List[ClientInfo])
    async def get_clients():
        """Get all registered clients."""
        return list(manager.client_info.values())

    @app.get("/api/v1/clients/online", response_model=List[ClientInfo])
    async def get_online_clients():
        """Get online clients."""
        return manager.get_online_clients()

    @app.post("/api/v1/clients/register")
    async def register_client(client: ClientInfo):
        """Register a new test client."""
        manager.update_client(client)
        return {"status": "registered", "client_id": client.id}

    # Job management endpoints
    @app.post("/api/v1/jobs", response_model=TestJob)
    async def create_job(job: TestJob):
        """Create a new test job."""
        created_job = job_manager.create_job(job)

        # Notify client if online
        if job.client_id in manager.active_connections:
            await manager.active_connections[job.client_id].send_json({
                "type": "new_job",
                "job": created_job.dict()
            })

        return created_job

    @app.get("/api/v1/jobs/{job_id}", response_model=TestJob)
    async def get_job(job_id: str):
        """Get job details."""
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    @app.get("/api/v1/jobs", response_model=List[TestJob])
    async def list_jobs(client_id: Optional[str] = None, status: Optional[JobStatus] = None):
        """List jobs with optional filters."""
        jobs = list(job_manager.jobs.values())
        if client_id:
            jobs = [j for j in jobs if j.client_id == client_id]
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs

    @app.post("/api/v1/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        """Cancel a pending job."""
        job = job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
            raise HTTPException(status_code=400, detail="Job cannot be cancelled")

        job_manager.update_job_status(job_id, JobStatus.CANCELLED)

        # Notify client
        if job.client_id in manager.active_connections:
            await manager.active_connections[job.client_id].send_json({
                "type": "job_cancelled",
                "job_id": job_id
            })

        return {"status": "cancelled"}

    # Result endpoints
    @app.post("/api/v1/results")
    async def submit_result(result: TestResult):
        """Submit test result from client."""
        job_manager.store_result(result)
        return {"status": "received", "job_id": result.job_id}

    @app.get("/api/v1/results/{job_id}", response_model=TestResult)
    async def get_result(job_id: str):
        """Get test result."""
        result = job_manager.results.get(job_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        return result

    @app.get("/api/v1/results", response_model=List[TestResult])
    async def list_results(client_id: Optional[str] = None):
        """List results with optional filter."""
        results = list(job_manager.results.values())
        if client_id:
            results = [r for r in results if r.client_id == client_id]
        return results

    # Progress endpoint (for HTTP polling fallback)
    @app.post("/api/v1/progress")
    async def submit_progress(progress: TestProgress):
        """Submit progress update from client (HTTP fallback)."""
        # Update job status if needed
        job = job_manager.get_job(progress.job_id)
        if job and job.status == JobStatus.PENDING:
            job_manager.update_job_status(progress.job_id, JobStatus.RUNNING)

        # Broadcast to any connected monitoring clients
        await manager.broadcast({
            "type": "progress",
            "data": progress.dict()
        })

        return {"status": "received"}

    # WebSocket endpoint for real-time communication
    @app.websocket("/ws/{client_id}")
    async def websocket_endpoint(websocket: WebSocket, client_id: str):
        await manager.connect(client_id, websocket)
        try:
            while True:
                data = await websocket.receive_json()

                # Handle different message types
                msg_type = data.get("type")

                if msg_type == "register":
                    # Client registration
                    client = ClientInfo(
                        id=client_id,
                        hostname=data.get("hostname", ""),
                        ip_address=websocket.client.host,
                        status=ClientStatus.ONLINE,
                        capabilities=data.get("capabilities", {})
                    )
                    manager.update_client(client)
                    await websocket.send_json({"type": "registered"})

                elif msg_type == "progress":
                    # Progress update
                    progress = TestProgress(**data.get("data", {}))
                    if progress.job_id:
                        job = job_manager.get_job(progress.job_id)
                        if job and job.status == JobStatus.PENDING:
                            job_manager.update_job_status(progress.job_id, JobStatus.RUNNING)
                            manager.client_info[client_id].status = ClientStatus.TESTING
                            manager.client_info[client_id].current_job = progress.job_id

                    # Broadcast progress
                    await manager.broadcast({
                        "type": "progress",
                        "data": progress.dict()
                    })

                elif msg_type == "result":
                    # Test completion
                    result = TestResult(**data.get("data", {}))
                    job_manager.store_result(result)
                    manager.client_info[client_id].status = ClientStatus.ONLINE
                    manager.client_info[client_id].current_job = None

                    await manager.broadcast({
                        "type": "completed",
                        "data": result.dict()
                    })

                elif msg_type == "heartbeat":
                    # Client heartbeat
                    if client_id in manager.client_info:
                        manager.client_info[client_id].last_seen = datetime.now()
                    await websocket.send_json({"type": "heartbeat_ack"})

                elif msg_type == "get_job":
                    # Client requesting pending job
                    pending = job_manager.get_pending_jobs(client_id)
                    if pending:
                        await websocket.send_json({
                            "type": "job_assigned",
                            "job": pending[0].dict()
                        })
                    else:
                        await websocket.send_json({"type": "no_jobs"})

        except WebSocketDisconnect:
            manager.disconnect(client_id)

    return app


# Create default app instance
app = create_app()
