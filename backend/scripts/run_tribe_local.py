#!/usr/bin/env python3
"""Run official TRIBE v2 Mini on a controlled, text-only reading stimulus locally.

Words are presented at 2.5 words/second. These are defined presentation times,
not measured speech timings. No audio/video models, TTS or transcription run.
The pretrained brain encoder and contextual Llama features are unchanged.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

if __package__:
    from .run_tribe import OFFICIAL_CODE_REVISION, export_predictions
else:
    from run_tribe import OFFICIAL_CODE_REVISION, export_predictions

MODEL_ID = "facebook/tribev2-mini"
MODEL_REVISION = "f3463fd77b17d80e4f61636bc2674b375803e743"
TEXT_MODEL_ID = "meta-llama/Llama-3.2-1B"
TEXT_MODEL_REVISION = "4e20de362430cd3b72f300e6b0f18e50e7166e08"
WORDS_PER_SECOND = 2.5
MAX_WORDS = 200


def word_events(text):
    """Explicit reading schedule; preserve punctuation and preceding text context."""
    matches = list(re.finditer(r"\S+", text))
    if not 1 <= len(matches) <= MAX_WORDS:
        raise ValueError(f"Local reading experiments require 1–{MAX_WORDS} words")
    return [{"type": "Word", "text": m.group(), "context": text[:m.end()],
             "start": i / WORDS_PER_SECOND, "duration": 1 / WORDS_PER_SECOND,
             "timeline": "controlled-reading", "subject": "default", "language": "en",
             "modality": "read"} for i, m in enumerate(matches)]


def stage(name, **details):
    print(json.dumps({"stage": name, **details}), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stimulus", required=True, type=Path)
    parser.add_argument("--warning-id", required=True)
    parser.add_argument("--output", type=Path, default=Path("data/local-tribe/output"))
    parser.add_argument("--cache", type=Path, default=Path("cache/tribe-local"))
    parser.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    args = parser.parse_args(argv)
    if args.stimulus.suffix.lower() != ".txt" or args.stimulus.stat().st_size > 16000:
        raise ValueError("Local inference accepts UTF-8 .txt files up to 16 KB")
    raw = args.stimulus.read_bytes()
    records = word_events(raw.decode("utf-8"))
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    stage("loading_runtime", word_count=len(records))
    import pandas as pd
    import torch
    import tribev2
    from huggingface_hub import snapshot_download
    from tribev2 import TribeModel

    torch.set_num_threads(4)
    device = ("mps" if torch.backends.mps.is_available() else "cpu") if args.device == "auto" else args.device
    if device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("Apple Metal acceleration is unavailable")
    code_root = Path(tribev2.__file__).resolve().parent.parent
    revision = subprocess.check_output(["git", "-C", str(code_root), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(code_root), "status", "--porcelain", "--untracked-files=no"], text=True).strip()
    if revision != OFFICIAL_CODE_REVISION or dirty:
        raise RuntimeError("The local worker requires the clean, pinned official TRIBE source")
    stage("loading_checkpoints", brain_device=device, text_device="cpu")
    checkpoint = snapshot_download(MODEL_ID, revision=MODEL_REVISION, allow_patterns=["config.yaml", "best.ckpt"])
    text_checkpoint = snapshot_download(TEXT_MODEL_ID, revision=TEXT_MODEL_REVISION,
                                       allow_patterns=["*.json", "*.safetensors", "tokenizer.model"])
    cache = args.cache.resolve()
    cache.mkdir(parents=True, exist_ok=True)
    model = TribeModel.from_pretrained(checkpoint, cache_folder=cache, device=device,
        config_update={"data.text_feature.device": "cpu", "data.text_feature.batch_size": 2,
                       "data.features_to_use": ["text"], "data.num_workers": 0, "data.batch_size": 1})
    # Use the exact downloaded text checkpoint, rather than a moving HF main revision.
    model.data.text_feature.model_name = text_checkpoint
    stage("predicting", model_id=MODEL_ID, model_revision=MODEL_REVISION)
    predictions, segments = model.predict(events=pd.DataFrame(records))
    metadata = export_predictions(args.output, predictions, segments, args.warning_id,
        hashlib.sha256(raw).hexdigest(), MODEL_REVISION, model.data.TR, model_id=MODEL_ID,
        sampling_extra={"stimulus_protocol": "controlled_word_reading_v1", "words_per_second": WORDS_PER_SECOND},
        notes=f"Official TRIBE v2 Mini; text-only controlled reading at {WORDS_PER_SECOND} words/s. "
              f"Audio/video absent, handled by the official model. Text encoder {TEXT_MODEL_ID}@{TEXT_MODEL_REVISION} "
              f"on CPU; brain encoder on {device}, float32. Presentation times are defined, not transcribed. "
              "No neural-to-evacuation relationship has been validated.")
    stage("complete", output=str(args.output.resolve()), prediction_shape=metadata["prediction_shape"],
          model_id=MODEL_ID, device=device)


if __name__ == "__main__":
    main()
