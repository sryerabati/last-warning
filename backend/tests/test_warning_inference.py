"""Exercise warning-to-inference orchestration with only the model process mocked.

The temporary stores and small arrays are test fixtures. No checkpoint downloads
or real model execution occur in these API contract tests.
"""
import hashlib
import io
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas import GENERIC, ScenarioConfig
from backend.scripts.run_tribe import OFFICIAL_CODE_REVISION
from backend.scripts.run_tribe_local import MODEL_ID, MODEL_REVISION, WORDS_PER_SECOND


@pytest.fixture
def experiment(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    calls = []

    def predict(stimulus, path, output):
        raw = path.read_bytes()
        calls.append({"stimulus": dict(stimulus), "raw": raw, "output": output})
        values = np.arange(32, dtype=np.float32).reshape(4, 8) / 32
        out = io.BytesIO()
        np.savez_compressed(out, predictions=values, times=np.arange(4, dtype=np.float32))
        metadata = {
            "warning_id": stimulus["warning_id"], "stimulus_hash": hashlib.sha256(raw).hexdigest(),
            "model_id": MODEL_ID, "model_revision": MODEL_REVISION,
            "code_revision": OFFICIAL_CODE_REVISION, "prediction_shape": [4, 8],
            "inference_timestamp": "2026-10-24T12:00:00Z", "provenance": "REAL_TRIBE",
            "sampling_information": {"TR_seconds": 1, "time_axis": "segment.start",
                "stimulus_protocol": "controlled_word_reading_v1", "words_per_second": WORDS_PER_SECOND},
            "notes": "Mock worker output isolated to this API test's temporary store.",
        }
        return json.dumps(metadata), out.getvalue()

    monkeypatch.setattr(app.state.local_tribe, "predict", predict)
    with TestClient(app) as client:
        yield client, app.state.store, calls


def analyze(client, warning_id="generic", **extra):
    response = client.post("/api/neural/analyze-warning", json={"warning_id": warning_id, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def small_scenario(client):
    response = client.post("/api/scenarios", json=ScenarioConfig(population=20, duration_ticks=12).model_dump())
    assert response.status_code == 201, response.text
    return response.json()["id"]


def run_with_analysis(client, analysis_id, **extra):
    return client.post("/api/runs", json={"scenario_id": small_scenario(client), "warning_id": "generic",
        "neural_analysis_id": analysis_id, "coupling_strength": 0, **extra})


def test_analyze_registers_exact_text_then_reuses_the_saved_prediction(experiment):
    client, store, calls = experiment
    text = "  Flash flood: leave Riverside.\nUse marked routes.  "
    response = client.put("/api/warnings/generic", json={**GENERIC.model_dump(), "text": text})
    assert response.status_code == 200
    first = analyze(client)
    assert first["cached"] is False
    assert len(calls) == 1
    assert calls[0]["raw"] == text.encode("utf-8")
    stimulus = calls[0]["stimulus"]
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert stimulus["sha256"] == stimulus["warning_text_hash"] == digest
    assert stimulus["warning_id"] == "generic"
    assert (store.root / "stimuli" / f"{stimulus['id']}.txt").read_bytes() == text.encode("utf-8")
    analysis = first["analysis"]
    assert analysis["stimulus_id"] == stimulus["id"]
    assert analysis["stimulus_hash"] == analysis["warning_text_hash"] == digest
    assert (store.root / "neural" / f"{analysis['id']}.npz").is_file()
    second = analyze(client)
    assert second == {"analysis": analysis, "cached": True}
    assert len(calls) == 1
    assert len(client.get("/api/stimuli").json()) == 1
    assert len(client.get("/api/neural/analyses").json()) == 1


@pytest.mark.parametrize("field,value", [
    ("model_id", "facebook/tribev2"),
    ("model_revision", "0" * 40),
    ("code_revision", "0" * 40),
    ("provenance", "TEST_FIXTURE"),
    ("warning_text_hash", "0" * 64),
    ("stimulus_hash", "0" * 64),
    ("stimulus_protocol", "different_reading_protocol"),
    ("words_per_second", WORDS_PER_SECOND + 0.5),
])
def test_cache_does_not_reuse_incompatible_or_mismatched_analyses(experiment, field, value):
    client, store, calls = experiment
    first = analyze(client)["analysis"]
    changed = dict(first)
    if field in {"stimulus_protocol", "words_per_second"}:
        changed["sampling_information"] = {**first["sampling_information"], field: value}
    else:
        changed[field] = value
    store.put("analyses", changed, first["id"])
    second = analyze(client)
    assert second["cached"] is False
    assert second["analysis"]["id"] != first["id"]
    assert len(calls) == 2
    assert second["analysis"]["stimulus_id"] == first["stimulus_id"]


def test_cache_requires_the_prediction_file_to_still_exist(experiment):
    client, store, calls = experiment
    first = analyze(client)["analysis"]
    (store.root / "neural" / f"{first['id']}.npz").unlink()
    second = analyze(client)
    assert second["cached"] is False
    assert second["analysis"]["id"] != first["id"]
    assert len(calls) == 2


def test_forced_analysis_recomputes_without_duplicating_the_stimulus(experiment):
    client, _, calls = experiment
    first = analyze(client)["analysis"]
    forced = analyze(client, force=True)
    assert forced["cached"] is False
    assert forced["analysis"]["id"] != first["id"]
    assert forced["analysis"]["stimulus_id"] == first["stimulus_id"]
    assert len(calls) == 2
    assert len(client.get("/api/stimuli").json()) == 1


def test_editing_warning_text_invalidates_cache_and_registers_the_new_text(experiment):
    client, _, calls = experiment
    first = analyze(client)["analysis"]
    updated = f"{GENERIC.text}\nLeave now."
    assert client.put("/api/warnings/generic", json={**GENERIC.model_dump(), "text": updated}).status_code == 200
    second = analyze(client)
    assert second["cached"] is False
    assert second["analysis"]["stimulus_id"] != first["stimulus_id"]
    assert calls[-1]["raw"] == updated.encode()
    assert second["analysis"]["stimulus_hash"] == hashlib.sha256(updated.encode()).hexdigest()
    assert len(calls) == 2


def test_unrelated_uploaded_text_cannot_attach_even_with_coupling_off(experiment):
    client, _, _ = experiment
    response = client.post("/api/stimuli", data={"warning_id": "generic"},
        files={"file": ("unrelated.txt", b"This is a different experimental stimulus.", "text/plain")})
    assert response.status_code == 201
    stimulus = response.json()
    assert stimulus["warning_text_hash"] == hashlib.sha256(GENERIC.text.encode()).hexdigest()
    analysis_response = client.post("/api/neural/local", json={"stimulus_id": stimulus["id"]})
    assert analysis_response.status_code == 201, analysis_response.text
    analysis = analysis_response.json()
    assert analysis["stimulus_hash"] != analysis["warning_text_hash"]
    run = run_with_analysis(client, analysis["id"])
    assert run.status_code == 422, run.text
    assert client.get("/api/runs").json() == []


def test_stale_analysis_is_rejected_even_with_coupling_off(experiment):
    client, _, _ = experiment
    analysis = analyze(client)["analysis"]
    assert client.put("/api/warnings/generic", json={**GENERIC.model_dump(), "text": "Edited after inference."}).status_code == 200
    response = run_with_analysis(client, analysis["id"])
    assert response.status_code == 422, response.text
    assert client.get("/api/runs").json() == []


def test_missing_analysis_is_rejected_even_with_coupling_off(experiment):
    client, _, _ = experiment
    response = run_with_analysis(client, "missing-analysis")
    assert response.status_code == 404, response.text
    assert client.get("/api/runs").json() == []


def test_missing_prediction_file_is_rejected_even_with_coupling_off(experiment):
    client, store, _ = experiment
    analysis = analyze(client)["analysis"]
    (store.root / "neural" / f"{analysis['id']}.npz").unlink()
    response = run_with_analysis(client, analysis["id"])
    assert response.status_code == 422, response.text
    assert client.get("/api/runs").json() == []


def test_other_warning_analysis_cannot_attach_with_coupling_off(experiment):
    client, _, _ = experiment
    analysis = analyze(client, warning_id="actionable")["analysis"]
    assert run_with_analysis(client, analysis["id"]).status_code == 422


def test_exact_analysis_attaches_without_affecting_zero_strength_simulation(experiment):
    client, store, calls = experiment
    analysis = analyze(client)["analysis"]
    scenario_id = small_scenario(client)
    plain = client.post("/api/runs", json={"scenario_id": scenario_id, "warning_id": "generic"})
    attached = client.post("/api/runs", json={"scenario_id": scenario_id, "warning_id": "generic",
        "neural_analysis_id": analysis["id"], "coupling_strength": 0})
    assert plain.status_code == attached.status_code == 201
    plain, attached = plain.json(), attached.json()
    assert attached["neural_analysis_id"] == analysis["id"]
    assert attached["notice_adjustment"] == 0
    assert attached["metrics"] == plain["metrics"]
    assert attached["initial_conditions_hash"] == plain["initial_conditions_hash"]
    a, b = store.recording(plain["id"]), store.recording(attached["id"])
    assert a["frames"] == b["frames"]
    assert a["events"] == b["events"]
    assert len(calls) == 1


def test_warning_changed_during_inference_is_reported_as_a_conflict(experiment, monkeypatch):
    client, store, _ = experiment
    original_predict = client.app.state.local_tribe.predict

    def edit_during_prediction(*args):
        result = original_predict(*args)
        warning = store.get("warnings", "generic")
        store.put("warnings", {**warning, "text": "A new warning written while the worker was running."}, "generic")
        return result

    monkeypatch.setattr(client.app.state.local_tribe, "predict", edit_during_prediction)
    response = client.post("/api/neural/analyze-warning", json={"warning_id": "generic"})
    assert response.status_code == 409, response.text
    saved = client.get("/api/neural/analyses").json()
    assert len(saved) == 1
    assert run_with_analysis(client, saved[0]["id"]).status_code == 422
