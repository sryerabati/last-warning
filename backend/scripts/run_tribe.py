#!/usr/bin/env python3
"""One-shot official TRIBE v2 inference. Does not provision resources.

Run in the separate Python 3.11/3.12 GPU environment from requirements-tribe.txt.
Outputs predictions.npz + metadata.json, both accepted by Last Warning's importer.
"""
import argparse
import hashlib
import inspect
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

OFFICIAL_CODE_REVISION = "af58661791a351a448a489042a28f6c37e1c14b7"
MODEL_ID = "facebook/tribev2"
SUFFIXES = {
    ".txt": "text_path", ".wav": "audio_path", ".mp3": "audio_path", ".flac": "audio_path",
    ".ogg": "audio_path", ".mp4": "video_path", ".avi": "video_path", ".mkv": "video_path",
    ".mov": "video_path", ".webm": "video_path",
}


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stimulus", required=True, type=Path)
    parser.add_argument("--warning-id", required=True, help="Warning ID from the Last Warning API")
    parser.add_argument("--output", type=Path, default=Path("tribe-output"))
    parser.add_argument("--cache", type=Path, default=Path("cache/tribe"))
    parser.add_argument("--model-revision", help="Immutable Hugging Face commit; resolved from model_info if omitted")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--dry-run", action="store_true", help="Validate input and print job details without loading weights")
    return parser.parse_args(argv)


def export_predictions(output, predictions, segments, warning_id, stimulus_hash, revision, tr_seconds,
                       *, model_id=MODEL_ID, notes=None, sampling_extra=None):
    import numpy as np

    values = np.asarray(predictions, dtype=np.float32)
    times = np.asarray([float(segment.start) for segment in segments], dtype=np.float64)
    if values.ndim != 2 or not all(values.shape) or len(times) != len(values):
        raise ValueError("Official model returned an unexpected prediction or segment shape")
    if not np.isfinite(values).all() or not np.isfinite(times).all() or not np.all(np.diff(times) > 0):
        raise ValueError("Official predictions must be finite with strictly increasing segment times")
    output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "warning_id": warning_id, "stimulus_hash": stimulus_hash,
        "model_id": model_id, "model_revision": revision, "code_revision": OFFICIAL_CODE_REVISION,
        "prediction_shape": list(values.shape), "inference_timestamp": datetime.now(UTC).isoformat(),
        "sampling_information": {
            "TR_seconds": float(tr_seconds), "time_axis": "official segment.start, seconds",
            "hemodynamic_offset_seconds": -5, "hemodynamic_offset_applied_by": "official TRIBE pipeline",
            "mesh": "fsaverage5", "subject": "average", "empty_segments_removed": True,
            **(sampling_extra or {}),
        },
        "provenance": "REAL_TRIBE",
        "notes": notes or "Official pretrained inference; no neural-to-evacuation relationship has been validated.",
    }
    # Write atomically so interrupted jobs cannot leave an apparently complete artifact.
    temp = output / "predictions.tmp"
    with temp.open("wb") as f:
        np.savez_compressed(f, predictions=values, times=times)
    temp.replace(output / "predictions.npz")
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main(argv=None):
    args = arguments(argv)
    stimulus = args.stimulus.resolve()
    if not stimulus.is_file() or stimulus.suffix.lower() not in SUFFIXES:
        raise ValueError("Provide an existing TRIBE-compatible .txt, audio, or video stimulus")
    if not stimulus.stat().st_size:
        raise ValueError("Stimulus is empty")
    if stimulus.suffix.lower() == ".txt" and not stimulus.read_text(encoding="utf-8").strip():
        raise ValueError("Text stimulus is empty")
    digest = hashlib.sha256(stimulus.read_bytes()).hexdigest()
    if args.model_revision and not re.fullmatch(r"[a-f0-9]{40}", args.model_revision):
        raise ValueError("--model-revision must be an immutable 40-character Hugging Face commit")
    job = {"stimulus": str(stimulus), "stimulus_hash": digest, "warning_id": args.warning_id,
           "input_parameter": SUFFIXES[stimulus.suffix.lower()], "model_id": MODEL_ID,
           "code_revision": OFFICIAL_CODE_REVISION, "device": args.device}
    if args.dry_run:
        print(json.dumps({**job, "status": "INPUT_VALIDATED", "inference_executed": False}, indent=2))
        return

    # Lazy imports keep every ordinary application/test path independent of Torch and GPU access.
    import torch
    import tribev2
    from huggingface_hub import HfApi, snapshot_download
    from tribev2 import TribeModel

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable. Use the documented GPU worker environment.")
    code_root = Path(tribev2.__file__).resolve().parent.parent
    code_revision = subprocess.check_output(["git", "-C", str(code_root), "rev-parse", "HEAD"], text=True).strip()
    if code_revision != OFFICIAL_CODE_REVISION:
        raise RuntimeError(f"Install the pinned official TRIBE revision {OFFICIAL_CODE_REVISION} in editable mode")
    if subprocess.check_output(["git", "-C", str(code_root), "status", "--porcelain", "--untracked-files=no"], text=True).strip():
        raise RuntimeError("Official TRIBE checkout has tracked modifications; refusing to label it pinned inference")
    required = {"checkpoint_dir", "cache_folder", "device"}
    if not required <= set(inspect.signature(TribeModel.from_pretrained).parameters):
        raise RuntimeError("Installed official TRIBE API differs from the audited interface")
    token = os.environ.get("HF_TOKEN")  # Used by HF clients, never written to exported metadata.
    revision = args.model_revision or HfApi(token=token).model_info(MODEL_ID).sha
    if not revision or not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise RuntimeError("Could not resolve an immutable model revision")
    checkpoint_dir = snapshot_download(MODEL_ID, revision=revision,
                                       allow_patterns=["config.yaml", "best.ckpt"], token=token)
    args.cache.mkdir(parents=True, exist_ok=True)
    model = TribeModel.from_pretrained(checkpoint_dir, cache_folder=str(args.cache.resolve()), device=args.device)
    events = model.get_events_dataframe(**{SUFFIXES[stimulus.suffix.lower()]: str(stimulus)})
    predictions, segments = model.predict(events=events)
    meta = export_predictions(args.output, predictions, segments, args.warning_id, digest, revision, model.data.TR)
    print(json.dumps({"status": "INFERENCE_COMPLETE", "output": str(args.output.resolve()),
                      "prediction_shape": meta["prediction_shape"], "model_revision": revision}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"TRIBE worker failed: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
