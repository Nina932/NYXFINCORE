"""
Simple in-memory job manager for background export tasks.

Note: This is intentionally lightweight for local dev. For production,
replace with a persistent job queue (Redis/Celery/RQ) and a jobs table.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger_name = "app.services.job_manager"
import logging
logger = logging.getLogger(logger_name)


@dataclass
class JobResult:
    job_id: str
    status: str = "pending"  # pending|running|success|failed
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    manifest: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, JobResult] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, job_id: str) -> JobResult:
        async with self._lock:
            jr = JobResult(job_id=job_id)
            self._jobs[job_id] = jr
            return jr

    async def set_running(self, job_id: str) -> None:
        async with self._lock:
            j = self._jobs.get(job_id)
            if j:
                j.status = "running"
                j.updated_at = time.time()

    async def set_success(self, job_id: str, manifest: Dict[str, Any]) -> None:
        async with self._lock:
            j = self._jobs.get(job_id)
            if j:
                j.status = "success"
                j.manifest = manifest
                j.updated_at = time.time()

    async def set_failed(self, job_id: str, error: str) -> None:
        async with self._lock:
            j = self._jobs.get(job_id)
            if j:
                j.status = "failed"
                j.error = error
                j.updated_at = time.time()

    async def get(self, job_id: str) -> Optional[JobResult]:
        return self._jobs.get(job_id)


# Global instance
job_manager = JobManager()


def compute_checksum(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
