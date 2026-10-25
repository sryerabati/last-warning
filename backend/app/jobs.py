"""Durable local run jobs with explicit recovery and idempotent submission.

Jobs never replay automatically after interruption: an uncertain provider call
can already have been charged. The provider's existing ledger remains the source
of spending reservations and settled usage.
"""
import fcntl
import hashlib
import json
import logging
import os
import sqlite3
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from .database import identifier, now

TERMINAL = {"completed", "failed", "cancelled", "interrupted"}
logger = logging.getLogger(__name__)


class JobCancelled(RuntimeError):
    pass


class JobConflict(ValueError):
    pass


def _pid_is_alive(pid):
    """Legacy-owner check; a zombie still answers kill(pid, 0) on Unix."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        state = subprocess.run(["ps", "-p", str(pid), "-o", "stat="],
                               capture_output=True, text=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        # An unavailable process-inspection tool must not interrupt a live job.
        return True
    if state.returncode == 0 and state.stdout.strip():
        return not state.stdout.strip().startswith("Z")
    return not (state.returncode == 1 and not state.stderr.strip())


class RunJobs:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.neural_lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="last-warning-run")
        self.worker_token = identifier()
        self.worker_directory = store.root / "run-workers"
        self.worker_directory.mkdir(exist_ok=True)
        self.worker_lease = (self.worker_directory / f"{self.worker_token}.lock").open("a+b")
        fcntl.flock(self.worker_lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Existing records storage needs no schema migration.
        for job in store.list("run_jobs"):
            if job["status"] in TERMINAL:
                continue
            if not self._owner_is_alive(job):
                self.update(job["id"], status="interrupted", stage="interrupted", finished_at=now(),
                    error={"status": 409, "detail": "The server stopped during this job. It was not restarted automatically; review recorded provider spending before creating another run."})

    def _owner_is_alive(self, job):
        token = job.get("worker_token")
        if not token:
            return _pid_is_alive(job.get("worker_pid"))
        try:
            uuid.UUID(token)
        except (ValueError, TypeError, AttributeError):
            return False
        try:
            with (self.worker_directory / f"{token}.lock").open("a+b") as lease:
                try:
                    fcntl.flock(lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return True
                # The owning process released its descriptor or died. PID reuse
                # and zombie states cannot keep this kernel lease alive.
                fcntl.flock(lease.fileno(), fcntl.LOCK_UN)
                return False
        except OSError:
            return _pid_is_alive(job.get("worker_pid"))

    def shutdown(self):
        """Release ownership only after every queued or running task finishes."""
        self.pool.shutdown(wait=True)
        self.worker_lease.close()

    def update(self, key, **changes):
        with self.lock:
            value = self.store.get("run_jobs", key)
            if "progress" in changes:
                changes["progress"] = {**value.get("progress", {}), **changes["progress"]}
            return self.store.put("run_jobs", {**value, **changes, "updated_at": now()}, key)

    def check_cancel(self, key):
        if self.store.get("run_jobs", key).get("cancel_requested"):
            raise JobCancelled("Run cancelled. Calls already sent remain accounted; no further calls will be started.")

    def submit(self, request, snapshot, execute):
        encoded = json.dumps(request, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        token = request["idempotency_key"]
        with self.lock:
            try:
                old = self.store.get("run_job_keys", token)
            except KeyError:
                old = None
            if old:
                if old["request_hash"] != digest:
                    raise JobConflict("This idempotency key belongs to a different request. Use a fresh key for a new experiment.")
                return self.store.get("run_jobs", old["job_id"])
            if sum(j["status"] not in TERMINAL for j in self.store.list("run_jobs")) >= 8:
                raise BlockingIOError("Eight run jobs are already active or queued.")
            key = identifier()
            value = {"id": key, "status": "queued", "stage": "queued", "request": request,
                     "snapshot": snapshot, "run_id": None, "analysis_id": request.get("neural_analysis_id"),
                     "progress": {"tick": 0, "total_ticks": snapshot["configuration"]["duration_ticks"],
                                  "decision_rounds_completed": 0}, "cancel_requested": False,
                     "error": None, "worker_pid": os.getpid(), "worker_token": self.worker_token,
                     "created_at": now(), "updated_at": now()}
            try:
                with self.store.connect() as db:
                    db.execute("INSERT INTO records VALUES ('run_job_keys', ?, ?)",
                               (token, json.dumps({"job_id": key, "request_hash": digest})))
                    db.execute("INSERT INTO records VALUES ('run_jobs', ?, ?)", (key, json.dumps(value)))
            except sqlite3.IntegrityError:
                # Another process won the same unique idempotency key; only its
                # successful transaction is allowed to schedule the paid work.
                old = self.store.get("run_job_keys", token)
                if old["request_hash"] != digest:
                    raise JobConflict("This idempotency key belongs to a different request.") from None
                return self.store.get("run_jobs", old["job_id"])
            self.pool.submit(self._work, key, execute)
            return value

    def _work(self, key, execute):
        try:
            self.check_cancel(key)
            self.update(key, status="running", started_at=now())
            result = execute(key)
            self.update(key, status="completed", stage="complete", run_id=result["id"],
                        analysis_id=result.get("neural_analysis_id"), finished_at=now())
        except JobCancelled as error:
            self.update(key, status="cancelled", stage="cancelled", finished_at=now(),
                        error={"status": 409, "detail": str(error)})
        except Exception as error:
            logger.exception("Background run job failed", extra={"job_id": key})
            detail = getattr(error, "detail", str(error))
            self.update(key, status="failed", stage="failed", finished_at=now(),
                        error={"status": getattr(error, "status_code", 500), "detail": str(detail)[:4000]})

    def cancel(self, key):
        with self.lock:
            value = self.store.get("run_jobs", key)
            if value["status"] in TERMINAL:
                return value
            if value["status"] == "queued":
                return self.update(key, cancel_requested=True, status="cancelled", stage="cancelled", finished_at=now())
            return self.update(key, cancel_requested=True)

    def public(self, value):
        # Snapshots are kept durably for execution, while polling stays compact.
        return {k: v for k, v in value.items() if k not in {"snapshot", "worker_pid", "worker_token"}}
