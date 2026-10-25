import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from backend.app.neuroscience import AnalysisMetadata, validate_artifact
from backend.scripts.run_tribe import OFFICIAL_CODE_REVISION, export_predictions

WORKER = Path(__file__).parents[1] / "scripts" / "run_tribe.py"


def test_worker_dry_run_needs_no_gpu(tmp_path):
    source = tmp_path / "warning.txt"
    source.write_text("Move to high ground now.")
    result = subprocess.run([sys.executable, str(WORKER), "--stimulus", str(source), "--warning-id", "generic", "--dry-run"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    job = json.loads(result.stdout)
    assert job["inference_executed"] is False
    assert job["input_parameter"] == "text_path"
    assert job["stimulus_hash"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert job["code_revision"] == OFFICIAL_CODE_REVISION


def test_worker_refuses_invalid_input(tmp_path):
    result = subprocess.run([sys.executable, str(WORKER), "--stimulus", str(tmp_path / "missing.txt"), "--warning-id", "generic", "--dry-run"], capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert "existing TRIBE-compatible" in result.stderr


def test_worker_serialization_contract_with_synthetic_array(tmp_path):
    # This tests serialization only. No file from this test is shipped as real inference.
    values = np.arange(24, dtype=np.float32).reshape(3, 8)
    segments = [SimpleNamespace(start=0), SimpleNamespace(start=1), SimpleNamespace(start=3)]
    meta = export_predictions(tmp_path, values, segments, "generic", "a" * 64, "b" * 40, 1)
    assert meta["prediction_shape"] == [3, 8]
    summary, series = validate_artifact((tmp_path / "predictions.npz").read_bytes(), AnalysisMetadata(**meta))
    assert [s["time"] for s in series] == [0, 1, 3]
    assert summary["mean"] == pytest.approx(values.mean())
    assert json.loads((tmp_path / "metadata.json").read_text()) == meta


def test_worker_rejects_misaligned_segments(tmp_path):
    with pytest.raises(ValueError):
        export_predictions(tmp_path, np.ones((3, 8)), [SimpleNamespace(start=0)], "generic", "a" * 64, "b" * 40, 1)
