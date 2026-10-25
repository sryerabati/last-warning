import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.neuroscience import AnalysisMetadata, validate_artifact
from backend.scripts.run_tribe import export_predictions
from backend.scripts.run_tribe_local import MODEL_ID, MODEL_REVISION, word_events


def test_reading_schedule_preserves_punctuation_and_context():
    records = word_events("Leave now.\n  Use North Road!")
    assert [r["text"] for r in records] == ["Leave", "now.", "Use", "North", "Road!"]
    assert [r["start"] for r in records] == [0, .4, .8, 1.2, 1.6]
    assert records[-1]["context"] == "Leave now.\n  Use North Road!"
    assert all(r["modality"] == "read" and r["duration"] == .4 for r in records)


@pytest.mark.parametrize("text", ["", "  \n", "word " * 201])
def test_reading_schedule_rejects_unsupported_lengths(text):
    with pytest.raises(ValueError):
        word_events(text)


def test_mini_serialization_preserves_model_and_reading_protocol(tmp_path):
    # Serialization fixture only, never shipped as real model output.
    meta = export_predictions(tmp_path, np.zeros((2, 4)), [SimpleNamespace(start=0), SimpleNamespace(start=1)],
        "generic", "a" * 64, MODEL_REVISION, 1, model_id=MODEL_ID,
        sampling_extra={"stimulus_protocol": "controlled_word_reading_v1", "words_per_second": 2.5})
    parsed = AnalysisMetadata(**meta)
    assert parsed.model_id == "facebook/tribev2-mini"
    assert parsed.sampling_information.words_per_second == 2.5
    validate_artifact((tmp_path / "predictions.npz").read_bytes(), parsed)
    with pytest.raises(ValueError):
        AnalysisMetadata(**{**meta, "model_id": "unrelated-model"})


def test_local_api_reports_missing_runtime_and_rejects_unknown_stimuli(tmp_path):
    app = create_app(tmp_path)
    app.state.local_tribe.python = tmp_path / "missing-python"
    with TestClient(app) as client:
        assert client.get("/api/neural/local").json()["available"] is False
        assert client.post("/api/neural/local", json={"stimulus_id": "missing"}).status_code == 404
        stim = client.post("/api/stimuli", data={"warning_id": "generic"},
                           files={"file": ("warning.txt", b"Leave now.")}).json()
        assert client.post("/api/neural/local", json={"stimulus_id": stim["id"]}).status_code == 503


def test_local_api_limits_words_and_concurrent_workers(tmp_path):
    app = create_app(tmp_path)
    worker = app.state.local_tribe
    worker.python = Path(sys.executable)
    with TestClient(app) as client:
        long = client.post("/api/stimuli", data={"warning_id": "generic"},
                           files={"file": ("long.txt", b"word " * 201)}).json()
        assert client.post("/api/neural/local", json={"stimulus_id": long["id"]}).status_code == 422
        stim = client.post("/api/stimuli", data={"warning_id": "generic"},
                           files={"file": ("warning.txt", b"Leave now.")}).json()
        worker.slot.acquire()
        try:
            assert client.post("/api/neural/local", json={"stimulus_id": stim["id"]}).status_code == 409
        finally:
            worker.slot.release()


def test_local_api_validates_worker_artifact_before_saving(tmp_path, monkeypatch):
    app = create_app(tmp_path)
    with TestClient(app) as client:
        raw = b"Leave now."
        stim = client.post("/api/stimuli", data={"warning_id": "generic"},
                           files={"file": ("warning.txt", raw)}).json()
        def fake_worker(stimulus, path, output):
            # Isolated serialization fixture; no model runs in unit tests.
            meta = export_predictions(output, np.ones((2, 4)), [SimpleNamespace(start=0), SimpleNamespace(start=1)],
                "generic", hashlib.sha256(raw).hexdigest(), MODEL_REVISION, 1, model_id=MODEL_ID)
            return json.dumps(meta), (output / "predictions.npz").read_bytes()
        monkeypatch.setattr(app.state.local_tribe, "predict", fake_worker)
        saved = client.post("/api/neural/local", json={"stimulus_id": stim["id"]})
        assert saved.status_code == 201, saved.text
        assert saved.json()["model_id"] == MODEL_ID
        assert saved.json()["summary"]["mean"] == 1
        assert client.get("/api/neural/analyses").json()[0]["id"] == saved.json()["id"]
        wrong = {**stim, "sha256": "0" * 64}
        app.state.store.put("stimuli", wrong, stim["id"])
        assert client.post("/api/neural/local", json={"stimulus_id": stim["id"]}).status_code == 422
