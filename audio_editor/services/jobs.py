"""Small in-process job queue for long local media operations."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import time
from uuid import uuid4


class JobManager:
    def __init__(self, workers=2):
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="audio-job")
        self._jobs = {}
        self._lock = Lock()

    def submit(self, operation):
        job_id = uuid4().hex
        with self._lock:
            self._jobs[job_id] = {"id": job_id, "state": "queued", "completed": 0, "total": 0,
                                  "current_file": None, "created_at": time(), "result": None, "error": None,
                                  "cancel_requested": False}
        def progress(completed, total, current_file):
            with self._lock:
                job = self._jobs[job_id]
                job.update(completed=completed, total=total, current_file=current_file)
        def cancelled():
            with self._lock: return self._jobs[job_id]["cancel_requested"]
        def run():
            with self._lock:
                if self._jobs[job_id]["cancel_requested"]:
                    self._jobs[job_id]["state"] = "cancelled"
                    return
                self._jobs[job_id]["state"] = "running"
            try:
                result = operation(progress=progress, cancelled=cancelled)
                with self._lock:
                    was_cancelled = self._jobs[job_id]["cancel_requested"]
                    self._jobs[job_id].update(state="cancelled" if was_cancelled else "completed", result=result)
            except Exception as exc:
                with self._lock: self._jobs[job_id].update(state="failed", error=str(exc))
        self._executor.submit(run)
        return self.snapshot(job_id)

    def snapshot(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job: return None
            return {key: value for key, value in job.items() if key != "cancel_requested"}

    def cancel(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if not job: return None
            job["cancel_requested"] = True
            if job["state"] == "queued": job["state"] = "cancelled"
        return self.snapshot(job_id)


jobs = JobManager()
