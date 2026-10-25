from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.hosted_server import PrivateOrigin
from backend.app import day_preview


def test_private_origin_requires_secret_and_blocks_local_inference():
    upstream = FastAPI()

    @upstream.get("/api/health")
    def health():
        return {"status": "ok"}

    client = TestClient(PrivateOrigin(upstream, "a" * 48))
    assert client.get("/api/health").status_code == 401
    assert client.get("/api/health", headers={"X-Last-Warning-Key": "wrong"}).status_code == 401
    headers = {"X-Last-Warning-Key": "a" * 48}
    assert client.get("/api/health", headers=headers).json() == {"status": "ok"}
    for path in ["/api/neural/local-status", "/api/stimuli", "/docs"]:
        assert client.get(path, headers=headers).status_code == 404


def test_hosted_jobs_reject_neural_inference_before_scheduling(tmp_path, monkeypatch):
    monkeypatch.setenv("LAST_WARNING_NEURAL_INFERENCE", "0")
    app = create_app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/run-jobs", json={"scenario_id": "riverside", "warning_id": "generic", "idempotency_key": "hosted-no-neural", "analyze_warning": True})
        assert response.status_code == 422
        assert app.state.store.list("run_jobs") == []
        response = client.post("/api/runs", json={"scenario_id": "riverside", "warning_id": "generic", "neural_analysis_id": "unavailable"})
        assert response.status_code == 422
        assert app.state.store.list("runs") == []
    app.state.run_jobs.shutdown()


def test_hosted_preview_streams_valid_json_and_reuses_disk_cache(tmp_path, monkeypatch):
    from backend.app.schemas import ScenarioConfig

    calls = []
    value = {"city": {"layout": "campus"}, "frames": [{"tick": 0}], "profiles": [], "states": ["routine"], "minutes_per_tick": 2}
    monkeypatch.setattr(day_preview, "campus_day", lambda *args, **kwargs: calls.append(args) or value)
    config = ScenarioConfig(layout="campus", town_life=True, population=10)
    assert day_preview.cached_campus_day(tmp_path, config) == value
    assert day_preview.cached_campus_day(tmp_path, config) == value
    assert len(calls) == 1
    monkeypatch.setenv("LAST_WARNING_NEURAL_INFERENCE", "0")
    app = create_app(tmp_path)
    with TestClient(app) as client:
        response = client.post("/api/town-life/preview", json=config.model_dump(mode="json"))
        assert response.status_code == 200
        assert response.headers["content-encoding"] == "gzip"
        assert response.json() == value
        preview = client.post("/api/scenarios/preview", json=config.model_dump(mode="json"))
        assert preview.status_code == 200
        assert preview.json()["frame"] == {"tick": 0}
        assert len(calls) == 1
    app.state.run_jobs.shutdown()
