import hashlib
import io
import json
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas import GENERIC, ScenarioConfig


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        yield c


def artifact(values=None, times=None):
    out = io.BytesIO()
    values = np.arange(32, dtype=np.float32).reshape(4, 8) / 32 if values is None else values
    times = np.arange(len(values), dtype=np.float32) if times is None else times
    np.savez_compressed(out, predictions=values, times=times)
    return out.getvalue()


def stimulus(client, warning_id="generic", raw=b"An emergency warning."):
    r = client.post("/api/stimuli", data={"warning_id": warning_id}, files={"file": ("warning.txt", raw, "text/plain")})
    assert r.status_code == 201, r.text
    return r.json()


def metadata(stim, **updates):
    return {"warning_id": stim["warning_id"], "stimulus_hash": stim["sha256"], "model_id": "facebook/tribev2",
            "model_revision": "test-fixture", "prediction_shape": [4, 8], "inference_timestamp": "2026-10-24T12:00:00Z",
            "sampling_information": {"TR_seconds": 1, "time_axis": "segment.start"}, "provenance": "TEST_FIXTURE", **updates}


def import_artifact(client, stim, meta=None, raw=None):
    return client.post("/api/neural/import", data={"stimulus_id": stim["id"], "metadata": json.dumps(meta or metadata(stim))},
                       files={"file": ("prediction.npz", raw or artifact(), "application/octet-stream")})


def small_scenario(client, **updates):
    s = ScenarioConfig(population=40, duration_ticks=50).model_dump(mode="json")
    return client.post("/api/scenarios", json={**s, **updates}).json()


def test_health_and_defaults(client):
    assert client.get("/api/health").json()["gpu_required"] is False
    warnings = {w["id"]: w for w in client.get("/api/warnings").json()}
    assert len(warnings) == 20
    for hazard in ("flood", "wildfire", "tornado", "blizzard", "hailstorm", "thunderstorm", "public_safety"):
        a, b = (warnings[f"campus-{mode}-{hazard}"] for mode in ("generic", "actionable"))
        assert a["text"] != b["text"]
        assert all(a[key] == b[key] for key in ("delivery_reach_probability", "notice_probability", "action_probability", "response_delay", "social_share_probability", "broadcast_tick", "channels"))
    assert client.get("/api/scenarios/osu-campus").json()["layout"] == "campus"
    assert client.get("/api/scenarios/riverside/preview").json()["frame"]["metrics"]["population"] == 300


def test_draft_preview_matches_unsaved_configuration(client):
    config = ScenarioConfig(population=25, hazard_origin=(10, 10), seed=9).model_dump(mode="json")
    preview = client.post("/api/scenarios/preview", json=config)
    assert preview.status_code == 200
    assert preview.json()["frame"]["metrics"]["population"] == 25
    assert preview.json()["frame"]["hazard_cells"] == [[10, 10]]
    assert client.get("/api/scenarios/riverside").json()["population"] == 300


def test_warning_crud_and_snapshot(client):
    warning = client.post("/api/warnings", json=GENERIC.model_dump()).json()
    assert warning["id"]
    config = GENERIC.model_dump()
    config["text"] = "Edited warning"
    assert client.put(f"/api/warnings/{warning['id']}", json=config).json()["text"] == "Edited warning"
    assert client.delete(f"/api/warnings/{warning['id']}").status_code == 204
    assert client.put(f"/api/warnings/{warning['id']}", json=config).status_code == 404


def test_invalid_requests(client):
    assert client.post("/api/runs", json={"scenario_id": "missing", "warning_id": "generic"}).status_code == 404
    assert client.post("/api/warnings", json={**GENERIC.model_dump(), "notice_probability": 2}).status_code == 422
    assert client.post("/api/scenarios", json={"population": 1000000}).status_code == 422
    assert client.post("/api/scenarios", json={"hazard_origin": [3, 3]}).status_code == 422
    assert client.get("/api/runs/missing/frames").status_code == 404
    assert client.get("/api/neural/analyses").json() == []


def test_branch_replay_and_persistence(client, tmp_path):
    scenario = small_scenario(client)
    a = client.post("/api/runs", json={"scenario_id": scenario["id"], "warning_id": "generic"}).json()
    # Changing the scenario after baseline must not contaminate a branch.
    client.put(f"/api/scenarios/{scenario['id']}", json={**ScenarioConfig().model_dump(), "population": 100, "seed": 99})
    b = client.post("/api/runs", json={"scenario_id": scenario["id"], "warning_id": "actionable", "baseline_run_id": a["id"]}).json()
    assert b["configuration"] == a["configuration"]
    assert a["initial_conditions_hash"] == b["initial_conditions_hash"]
    comparison = client.post("/api/comparisons", json={"baseline_run_id": a["id"], "alternative_run_id": b["id"]})
    assert comparison.status_code == 201
    c = comparison.json()
    assert c["deltas"]["evacuated"] == b["metrics"]["evacuated"] - a["metrics"]["evacuated"]
    assert c["assumptions"]["notice_probability"]["alternative"] == .9
    frames = client.get(f"/api/runs/{a['id']}/frames").json()
    for start, end in [(25, 30), (0, 1), (49, 51), (2, 5)]:
        assert client.get(f"/api/runs/{a['id']}/frames?start={start}&end={end}").json()["frames"] == frames["frames"][start:end]
    assert client.get(f"/api/runs/{a['id']}/frames?start=3&end=1").status_code == 422
    assert len(client.get(f"/api/runs/{a['id']}/metrics").json()) == 51
    assert client.get(f"/api/runs/{a['id']}/events").json()
    assert client.get(f"/api/runs/{a['id']}/export").status_code == 200
    with TestClient(create_app(tmp_path)) as restarted:
        assert restarted.get(f"/api/runs/{a['id']}/frames").json() == frames
        assert restarted.get(f"/api/comparisons/{c['id']}").json() == c
    # A recording contains the immutable original warning after library edits/deletion.
    client.delete("/api/warnings/generic")
    assert client.get(f"/api/runs/{a['id']}").json()["warning"]["text"] == GENERIC.text


def test_incompatible_comparison_rejected(client):
    scenario = small_scenario(client)
    a = client.post("/api/runs", json={"scenario_id": scenario["id"], "warning_id": "generic"}).json()
    scenario2 = small_scenario(client, seed=99)
    b = client.post("/api/runs", json={"scenario_id": scenario2["id"], "warning_id": "generic"}).json()
    assert client.post("/api/comparisons", json={"baseline_run_id": a["id"], "alternative_run_id": b["id"]}).status_code == 422
    assert client.post("/api/comparisons", json={"baseline_run_id": a["id"], "alternative_run_id": a["id"]}).status_code == 422
    assert client.post("/api/runs", json={"scenario_id": scenario2["id"], "warning_id": "generic", "baseline_run_id": a["id"]}).status_code == 422


def test_neural_roundtrip_and_exact_comparison(client):
    s = stimulus(client)
    assert s["sha256"] == hashlib.sha256(b"An emergency warning.").hexdigest()
    a = import_artifact(client, s)
    assert a.status_code == 201, a.text
    a = a.json()
    assert a["provenance"] == "TEST_FIXTURE"
    assert a["prediction_shape"] == [4, 8]
    assert len(a["series"]) == 4
    values = np.arange(32, dtype=np.float32).reshape(4, 8) / 32 + 2
    b = import_artifact(client, s, raw=artifact(values)).json()
    comparison = client.post("/api/neural/compare", json={"baseline_analysis_id": a["id"], "alternative_analysis_id": b["id"]})
    assert comparison.status_code == 200
    assert comparison.json()["aligned_samples"] == 4
    assert comparison.json()["mean_absolute_difference"] == pytest.approx(2)
    assert client.get(f"/api/neural/analyses/{a['id']}").json() == a
    assert client.get(f"/api/stimuli/{s['id']}/download").content == b"An emergency warning."


@pytest.mark.parametrize("change", [
    {"stimulus_hash": "0" * 64}, {"warning_id": "actionable"}, {"prediction_shape": [4, 9]},
    {"provenance": "NO_ANALYSIS"}, {"provenance": "REAL_TRIBE"},
    {"inference_timestamp": "yesterday"}, {"inference_timestamp": "2026-10-24T12:00:00"},
])
def test_invalid_neural_metadata(client, change):
    s = stimulus(client)
    assert import_artifact(client, s, meta=metadata(s, **change)).status_code == 422


@pytest.mark.parametrize("raw", [
    b"not a zip file", artifact(np.full((4, 8), np.nan)), artifact(times=np.array([0, 1, 1, 2])),
    artifact(np.array([[object()]], dtype=object)), artifact(np.ones(8)),
])
def test_invalid_arrays(client, raw):
    s = stimulus(client)
    assert import_artifact(client, s, raw=raw).status_code == 422


def test_deceptive_npy_header_rejected_before_allocation(client):
    s = stimulus(client)
    fake = io.BytesIO()
    np.lib.format.write_array_header_1_0(fake, {"descr": "<f4", "fortran_order": False, "shape": (1000000000, 8)})
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("predictions.npy", fake.getvalue())
        z.writestr("times.npy", fake.getvalue())
    assert import_artifact(client, s, raw=out.getvalue()).status_code == 422


def test_fixture_cannot_drive_coupling(client):
    s = stimulus(client)
    a = import_artifact(client, s).json()
    scenario = small_scenario(client)
    request = {"scenario_id": scenario["id"], "warning_id": "generic", "neural_analysis_id": a["id"], "coupling_strength": .2}
    assert client.post("/api/runs", json=request).status_code == 422
    request["neural_analysis_id"] = None
    assert client.post("/api/runs", json=request).status_code == 422


def test_real_provenance_and_stale_coupling(client):
    s = stimulus(client, raw=GENERIC.text.encode())
    meta = metadata(s, provenance="REAL_TRIBE", model_revision="a" * 40, code_revision="b" * 40)
    a = import_artifact(client, s, meta=meta).json()
    assert a["provenance"] == "REAL_TRIBE"
    assert "not independently" in a["provenance_note"]
    scenario = small_scenario(client)
    body = {"scenario_id": scenario["id"], "warning_id": "generic", "neural_analysis_id": a["id"], "coupling_strength": .2}
    assert client.post("/api/runs", json=body).status_code == 201
    client.put("/api/warnings/generic", json={**GENERIC.model_dump(), "text": "Changed after inference"})
    assert client.post("/api/runs", json=body).status_code == 422


def test_mismatched_neural_time_axes_rejected(client):
    s = stimulus(client)
    a = import_artifact(client, s).json()
    b = import_artifact(client, s, raw=artifact(times=np.arange(4) + 100)).json()
    assert client.post("/api/neural/compare", json={"baseline_analysis_id": a["id"], "alternative_analysis_id": b["id"]}).status_code == 422


def test_upload_validation(client):
    assert client.post("/api/stimuli", data={"warning_id": "generic"}, files={"file": ("attack.html", b"x")}).status_code == 422
    assert client.post("/api/stimuli", data={"warning_id": "generic"}, files={"file": ("empty.txt", b" ")}).status_code == 422
    assert client.post("/api/stimuli", data={"warning_id": "generic"}, files={"file": ("bad.txt", b"\xff\xfe")}).status_code == 422
