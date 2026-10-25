"""Validated NPZ artifacts. Never executes pickles or invents predictions."""
import io
import math
import re
import zipfile

import numpy as np
from pydantic import Field, model_validator

from .schemas import StrictModel

MAX_ARTIFACT_BYTES = 160 * 1024 * 1024
SUPPORTED = {".txt", ".wav", ".mp3", ".flac", ".ogg", ".mp4", ".avi", ".mkv", ".mov", ".webm"}


class SamplingInformation(StrictModel):
    TR_seconds: float = Field(gt=0, le=120)
    time_axis: str = Field(min_length=1, max_length=200)
    hemodynamic_offset_seconds: float | None = None
    hemodynamic_offset_applied_by: str | None = None
    mesh: str | None = None
    subject: str | None = None
    empty_segments_removed: bool | None = None
    stimulus_protocol: str | None = Field(default=None, max_length=200)
    words_per_second: float | None = Field(default=None, gt=0, le=20)


class AnalysisMetadata(StrictModel):
    warning_id: str
    stimulus_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    model_id: str = "facebook/tribev2"
    model_revision: str = Field(min_length=1, max_length=120)
    code_revision: str | None = None
    prediction_shape: tuple[int, int]
    inference_timestamp: str
    sampling_information: SamplingInformation
    provenance: str
    notes: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def provenance_valid(self):
        if self.provenance not in {"REAL_TRIBE", "TEST_FIXTURE"}:
            raise ValueError("Provenance must be REAL_TRIBE or TEST_FIXTURE")
        if self.provenance == "REAL_TRIBE":
            if self.model_id not in {"facebook/tribev2", "facebook/tribev2-mini"} or not re.fullmatch(r"[0-9a-f]{40}", self.model_revision):
                raise ValueError("REAL_TRIBE requires an official TRIBE v2 model and an immutable 40-character model revision")
            if not self.code_revision or not re.fullmatch(r"[0-9a-f]{40}", self.code_revision):
                raise ValueError("REAL_TRIBE requires an immutable official code revision")
        from datetime import datetime
        if datetime.fromisoformat(self.inference_timestamp).tzinfo is None:
            raise ValueError("Inference timestamp must include a timezone")
        return self


def validate_artifact(raw: bytes, metadata: AnalysisMetadata):
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError("Artifact exceeds 160 MiB")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if {x.filename for x in entries} != {"predictions.npy", "times.npy"} or len(entries) != 2:
                raise ValueError("NPZ must contain exactly predictions and times arrays")
            if sum(x.file_size for x in entries) > MAX_ARTIFACT_BYTES:
                raise ValueError("Uncompressed artifact exceeds 160 MiB")
            for entry in entries:
                with archive.open(entry) as source:
                    version = np.lib.format.read_magic(source)
                    if version == (1, 0):
                        shape, _, dtype = np.lib.format.read_array_header_1_0(source)
                    elif version == (2, 0):
                        shape, _, dtype = np.lib.format.read_array_header_2_0(source)
                    else:
                        raise ValueError("Unsupported NPY array version")
                    count = math.prod(shape)
                    if dtype.kind not in "fi" or count > MAX_ARTIFACT_BYTES // max(1, dtype.itemsize):
                        raise ValueError("Array header declares unsafe dimensions or a nonnumeric dtype")
                    if source.tell() + count * dtype.itemsize != entry.file_size:
                        raise ValueError("Array byte length does not match its header")
        with np.load(io.BytesIO(raw), allow_pickle=False) as artifact:
            values, times = artifact["predictions"], artifact["times"]
    except (OSError, KeyError, zipfile.BadZipFile, EOFError) as e:
        raise ValueError("Unreadable NPZ artifact") from e
    if values.dtype.kind not in "fi" or times.dtype.kind not in "fi":
        raise ValueError("Arrays must contain real numerical values")
    if values.ndim != 2 or not all(values.shape) or values.shape[0] > 10000 or values.shape[1] > 100000:
        raise ValueError("Predictions must be a nonempty time × vertex matrix (max 10k × 100k)")
    if tuple(values.shape) != metadata.prediction_shape:
        raise ValueError("Prediction shape does not match metadata")
    if times.ndim != 1 or len(times) != len(values) or not np.all(np.diff(times) > 0):
        raise ValueError("Times must be strictly increasing with one value per prediction")
    if not np.isfinite(values).all() or not np.isfinite(times).all():
        raise ValueError("Predictions and times must be finite")
    # Metadata is an imported assertion of origin, never cryptographic verification of Meta's execution.
    summary = {
        "mean": float(values.mean()), "std": float(values.std()),
        "min": float(values.min()), "max": float(values.max()),
        "mean_absolute_response": float(np.abs(values).mean()),
        "normalized_feature": float(np.tanh(np.abs(values).mean())),
    }
    stride = max(1, int(np.ceil(len(values) / 1000)))
    series = [{"time": float(times[i]), "mean": float(values[i].mean()),
               "mean_absolute": float(np.abs(values[i]).mean()), "std": float(values[i].std())}
              for i in range(0, len(values), stride)]
    return summary, series


def compare_arrays(a_path, b_path, a_meta, b_meta):
    if a_meta["model_id"] != b_meta["model_id"] or a_meta["model_revision"] != b_meta["model_revision"]:
        raise ValueError("Neural comparisons require identical model IDs and revisions")
    if a_meta["provenance"] != b_meta["provenance"]:
        raise ValueError("Cannot compare a fixture with real inference")
    if a_meta["sampling_information"] != b_meta["sampling_information"]:
        raise ValueError("Neural comparisons require identical sampling conventions")
    with np.load(a_path, allow_pickle=False) as a, np.load(b_path, allow_pickle=False) as b:
        av, bv, at, bt = a["predictions"], b["predictions"], a["times"], b["times"]
        if av.shape[1] != bv.shape[1]:
            raise ValueError("Neural comparisons require matching vertex dimensions")
        # Align at actual shared timestamps rather than silently subtracting mismatched rows.
        times, ai, bi = np.intersect1d(np.round(at, 6), np.round(bt, 6), return_indices=True)
        if len(times) == 0:
            raise ValueError("No shared neural timestamps")
        difference = bv[bi].astype(np.float64) - av[ai].astype(np.float64)
        stride = max(1, int(np.ceil(len(times) / 1000)))
        return {
            "aligned_samples": len(times), "mean_absolute_difference": float(np.abs(difference).mean()),
            "series": [{"time": float(times[i]), "mean_difference": float(difference[i].mean()),
                        "mean_absolute_difference": float(np.abs(difference[i]).mean())}
                       for i in range(0, len(times), stride)],
            "provenance": a_meta["provenance"],
        }
