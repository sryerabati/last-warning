"""Isolated, single-worker local Mini inference; the web app never imports Torch."""
import os
import subprocess
import threading
from pathlib import Path

from backend.scripts.run_tribe_local import MAX_WORDS, MODEL_ID, MODEL_REVISION, WORDS_PER_SECOND, word_events


class LocalTribe:
    def __init__(self, project_root):
        root = Path(project_root)
        self.python = root / "cache" / "tribe-env" / "bin" / "python"
        self.script = root / "backend" / "scripts" / "run_tribe_local.py"
        self.root = root
        self.slot = threading.Lock()

    def status(self):
        return {"available": self.python.is_file(), "running": self.slot.locked(), "model_id": MODEL_ID,
                "model_revision": MODEL_REVISION, "max_words": MAX_WORDS,
                "words_per_second": WORDS_PER_SECOND, "protocol": "controlled_word_reading_v1"}

    def predict(self, stimulus, path, output):
        if not self.python.is_file():
            raise FileNotFoundError("Local TRIBE environment is missing. Run scripts/setup-tribe-local.sh first.")
        if stimulus["suffix"] != ".txt" or stimulus["size"] > 16000:
            raise ValueError("Local Mini accepts UTF-8 text stimuli up to 16 KB and 200 words")
        word_events(path.read_text(encoding="utf-8"))
        if not self.slot.acquire(blocking=False):
            raise BlockingIOError("A local TRIBE job is already running. Wait for it to finish.")
        try:
            output.mkdir(parents=True, exist_ok=True)
            with (output / "worker.log").open("w") as log:
                result = subprocess.run([str(self.python), "-u", str(self.script), "--stimulus", str(path),
                    "--warning-id", stimulus["warning_id"], "--output", str(output)], check=False, cwd=self.root,
                    stdout=log, stderr=subprocess.STDOUT, timeout=600,
                    env={**os.environ, "TOKENIZERS_PARALLELISM": "false", "PYTORCH_ENABLE_MPS_FALLBACK": "1"})
            if result.returncode:
                tail = (output / "worker.log").read_text()[-1800:]
                raise RuntimeError(f"Local TRIBE inference failed. {tail}")
            return (output / "metadata.json").read_text(), (output / "predictions.npz").read_bytes()
        finally:
            self.slot.release()
