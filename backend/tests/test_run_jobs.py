import hashlib
import io
import json
import os
import subprocess
import threading
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app import jobs as jobs_module
from backend.app import main
from backend.app.bedrock import BedrockPolicy, DecisionValidationError
from backend.app.database import Store
from backend.app.jobs import JobCancelled, RunJobs
from backend.app.schemas import GENERIC
from backend.scripts.run_tribe import OFFICIAL_CODE_REVISION
from backend.scripts.run_tribe_local import MODEL_ID, MODEL_REVISION


@pytest.fixture
def client(tmp_path):
    app = main.create_app(tmp_path)
    with TestClient(app) as client:
        yield client
    app.state.run_jobs.shutdown()


def request(client, **extra):
    scenario = client.post("/api/scenarios", json={"population": 20, "duration_ticks": 12}).json()
    return {"scenario_id": scenario["id"], "warning_id": "generic", "idempotency_key": "test-request-unique", **extra}


def wait_job(client, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        value = client.get(f"/api/run-jobs/{job_id}").json()
        if value["status"] in {"completed", "failed", "cancelled", "interrupted"}:
            return value
        time.sleep(0.01)
    pytest.fail("Background test job did not terminate")


def test_background_job_is_idempotent_and_freezes_its_warning_and_scenario(client, monkeypatch):
    real = main.simulate
    started, release = threading.Event(), threading.Event()
    calls = []

    def blocked(*args, **kwargs):
        calls.append(1)
        started.set()
        assert release.wait(5)
        return real(*args, **kwargs)

    monkeypatch.setattr(main, "simulate", blocked)
    body = request(client)
    first = client.post("/api/run-jobs", json=body)
    assert first.status_code == 202
    job_id = first.json()["id"]
    assert started.wait(5)
    try:
        duplicate = client.post("/api/run-jobs", json=body)
        assert duplicate.status_code == 202 and duplicate.json()["id"] == job_id
        assert client.post("/api/run-jobs", json={**body, "warning_id": "actionable"}).status_code == 409
        client.put("/api/warnings/generic", json={**GENERIC.model_dump(), "text": "Edited while running."})
        client.put(f"/api/scenarios/{body['scenario_id']}", json={"population": 99, "seed": 99})
    finally:
        release.set()
    job = wait_job(client, job_id)
    assert job["status"] == "completed", job
    assert job["stage"] == "complete" and job["progress"]["tick"] == 12
    run = client.get(f"/api/runs/{job['run_id']}").json()
    assert run["warning"]["text"] == GENERIC.text
    assert run["configuration"]["population"] == 20 and run["seed"] == 42
    assert len(calls) == 1
    assert not {"snapshot", "worker_pid", "worker_token"} & job.keys()
    client.delete("/api/warnings/generic")
    assert client.post("/api/run-jobs", json=body).json()["id"] == job_id
    assert len(client.get("/api/run-jobs").json()) == 1


def test_job_analyzes_exact_text_before_resolving_nonzero_rules_coupling(client, monkeypatch):
    calls = []

    def predict(stimulus, path, output):
        calls.append(path.read_bytes())
        out = io.BytesIO()
        np.savez_compressed(out, predictions=np.ones((4, 8), dtype=np.float32), times=np.arange(4))
        return json.dumps({"warning_id": "generic", "stimulus_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
            "model_id": MODEL_ID, "model_revision": MODEL_REVISION, "code_revision": OFFICIAL_CODE_REVISION,
            "prediction_shape": [4, 8], "inference_timestamp": "2026-10-24T12:00:00Z", "provenance": "REAL_TRIBE",
            "sampling_information": {"TR_seconds": 1, "time_axis": "segment.start",
                "stimulus_protocol": "controlled_word_reading_v1", "words_per_second": 2.5}}), out.getvalue()

    monkeypatch.setattr(client.app.state.local_tribe, "predict", predict)
    body = request(client, analyze_warning=True, coupling_strength=0.2)
    response = client.post("/api/run-jobs", json=body)
    job = wait_job(client, response.json()["id"])
    assert job["status"] == "completed", job
    run = client.get(f"/api/runs/{job['run_id']}").json()
    assert run["neural_analysis_id"] == job["analysis_id"]
    assert run["notice_adjustment"] > 0
    assert calls == [GENERIC.text.encode()]


def test_running_job_cancellation_stops_before_more_simulation_or_saving(client, monkeypatch):
    started, release = threading.Event(), threading.Event()

    def blocked(*args, **kwargs):
        started.set()
        assert release.wait(5)
        kwargs["cancel_check"]()
        pytest.fail("Cancelled job should not continue")

    monkeypatch.setattr(main, "simulate", blocked)
    first = client.post("/api/run-jobs", json=request(client)).json()
    assert started.wait(5)
    try:
        cancelled = client.post(f"/api/run-jobs/{first['id']}/cancel").json()
        assert cancelled["cancel_requested"] is True
    finally:
        release.set()
    assert wait_job(client, first["id"])["status"] == "cancelled"
    assert client.get("/api/runs").json() == []


def test_invalid_model_round_is_a_failed_job_without_saved_fallback(client, monkeypatch):
    class Policy:
        def __init__(self, root):
            self.usage = {"model_id": "test-only"}

        def decide(self, *args):
            raise DecisionValidationError("The model omitted residents")

    monkeypatch.setattr(main, "BedrockPolicy", Policy)
    body = request(client)
    client.put(f"/api/scenarios/{body['scenario_id']}", json={"population": 20, "duration_ticks": 12,
                                                            "decision_mode": "bedrock"})
    job_id = client.post("/api/run-jobs", json=body).json()["id"]
    job = wait_job(client, job_id)
    assert job["status"] == "failed" and job["error"]["status"] == 502
    assert job["run_id"] is None and client.get("/api/runs").json() == []
    assert job["progress"]["decision_round"] == 1
    assert job["progress"]["decision_rounds_completed"] == 0


def test_abandoned_jobs_are_interrupted_and_never_restarted(tmp_path):
    store = Store(tmp_path)
    store.put("run_jobs", {"status": "running", "worker_pid": 999999999, "stage": "agent_decisions",
                           "progress": {"tick": 4}, "cancel_requested": False}, "abandoned")
    jobs = RunJobs(store)
    try:
        value = store.get("run_jobs", "abandoned")
        assert value["status"] == "interrupted"
        assert "not restarted automatically" in value["error"]["detail"]
        assert store.list("runs") == []
    finally:
        jobs.shutdown()


def test_live_worker_lease_preserves_another_managers_running_job(tmp_path):
    store = Store(tmp_path)
    owner = RunJobs(store)
    store.put("run_jobs", {"status": "running", "worker_pid": os.getpid(),
                           "worker_token": owner.worker_token, "stage": "agent_decisions"}, "live")
    observer = RunJobs(store)
    try:
        assert store.get("run_jobs", "live")["status"] == "running"
        assert store.list("runs") == []
    finally:
        observer.shutdown()
        owner.shutdown()


def test_released_worker_lease_recovers_job_even_when_pid_is_still_alive(tmp_path):
    store = Store(tmp_path)
    owner = RunJobs(store)
    store.put("run_jobs", {"status": "running", "worker_pid": os.getpid(),
                           "worker_token": owner.worker_token, "stage": "agent_decisions"}, "lost-lease")
    owner.shutdown()
    # The recorded PID is this live process: PID liveness alone cannot recover it.
    os.kill(os.getpid(), 0)
    observer = RunJobs(store)
    try:
        value = store.get("run_jobs", "lost-lease")
        assert value["status"] == "interrupted"
        assert value["stage"] == "interrupted" and value.get("run_id") is None
        assert store.list("runs") == []
    finally:
        observer.shutdown()


def test_legacy_zombie_worker_is_interrupted_without_replaying(tmp_path, monkeypatch):
    store = Store(tmp_path)
    store.put("run_jobs", {"status": "running", "worker_pid": 32630,
                           "stage": "agent_decisions"}, "legacy-zombie")
    monkeypatch.setattr(jobs_module.os, "kill", lambda pid, signal: None)
    observed = []

    def inspect_process(command, **kwargs):
        observed.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="Z+\n", stderr="")

    monkeypatch.setattr(jobs_module.subprocess, "run", inspect_process)
    jobs = RunJobs(store)
    try:
        assert store.get("run_jobs", "legacy-zombie")["status"] == "interrupted"
        assert observed == [["ps", "-p", "32630", "-o", "stat="]]
        assert store.list("runs") == []
    finally:
        jobs.shutdown()


def test_unavailable_legacy_process_inspection_preserves_a_potentially_live_job(tmp_path, monkeypatch):
    store = Store(tmp_path)
    store.put("run_jobs", {"status": "running", "worker_pid": 32630,
                           "stage": "agent_decisions"}, "legacy-live")
    monkeypatch.setattr(jobs_module.os, "kill", lambda pid, signal: None)

    def unavailable(*args, **kwargs):
        raise OSError("Process inspection is not permitted")

    monkeypatch.setattr(jobs_module.subprocess, "run", unavailable)
    jobs = RunJobs(store)
    try:
        assert store.get("run_jobs", "legacy-live")["status"] == "running"
    finally:
        jobs.shutdown()


def test_provider_cancellation_happens_before_a_budget_reservation_or_request(tmp_path):
    class Client:
        def converse(self, **kwargs):
            pytest.fail("Cancellation must prevent the paid call")

    policy = BedrockPolicy(tmp_path, client=Client())

    def cancelled():
        raise JobCancelled("Cancelled before sending")

    policy.cancel_check = cancelled
    with pytest.raises(JobCancelled):
        policy.decide([{"id": i, "available_actions": ["WAIT"]} for i in range(20)], {}, {}, 4)
    assert policy.usage["calls"] == 0


def test_queued_cancel_does_not_schedule_replacement_work(client, monkeypatch):
    entered = threading.Barrier(3)
    release = threading.Event()
    real = main.simulate
    calls = []

    def blocked(*args, **kwargs):
        calls.append(1)
        entered.wait(timeout=5)
        assert release.wait(5)
        return real(*args, **kwargs)

    monkeypatch.setattr(main, "simulate", blocked)
    body = request(client)
    first = client.post("/api/run-jobs", json=body).json()
    second = client.post("/api/run-jobs", json={**body, "idempotency_key": "second-request-key"}).json()
    entered.wait(timeout=5)
    try:
        third = client.post("/api/run-jobs", json={**body, "idempotency_key": "third-request-key"}).json()
        cancelled = client.post(f"/api/run-jobs/{third['id']}/cancel").json()
        assert cancelled["status"] == "cancelled"
    finally:
        release.set()
    assert wait_job(client, first["id"])["status"] == "completed"
    assert wait_job(client, second["id"])["status"] == "completed"
    assert wait_job(client, third["id"])["status"] == "cancelled"
    assert len(calls) == 2
