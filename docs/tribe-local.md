# TRIBE v2 Mini on Apple Silicon

Real pretrained inference is working on this MacBook Pro (Apple M4, 16 GB). The brain encoder uses Apple Metal (`mps`), and the Llama 3.2 1B text feature extractor runs on CPU. The official upstream packages and model implementation remain unmodified. No cloud instance or inference endpoint is needed.

## Use in the simulator

1. Choose a disaster and warning in the simulator, then click **Run warning**.
2. The app automatically registers the exact warning text and computes or reuses matching genuine Mini predictions before the simulation runs. It validates both text hashes, the pinned checkpoint/code, the reading protocol and artifact existence. Text edits invalidate the match.
3. Inspect the small response curve beside the city. Open **Advanced → TRIBE Mini & imports** for full model metadata, direct analysis, downloads, neural comparisons and external artifact imports.
4. The **Analyze the warning when running** setting can disable automatic inference. Experimental behavioral coupling is a separate control and defaults off.

All six built-in disaster warning texts have been evaluated and saved. Flood generic/actionable produced **5 × 20,484 / 8 × 20,484**; wildfire **5 × 20,484 / 10 × 20,484**; tornado **5 × 20,484 / 11 × 20,484**. Results were downloaded and checked against their exact text hashes. Cached short-warning jobs take seconds on this machine; runtime depends on text length and system load.

## What the local experiment means

This is a **text-only, controlled reading experiment**. Each whitespace-delimited word is assigned a 0.4-second presentation interval (2.5 words/second), preserving punctuation and preceding text as context. These are defined stimulus timings, not recorded or transcribed speech. The model predicts the average subject's cortical fMRI response to that schedule. No audio or video feature extractor runs; the official brain encoder handles absent modalities.

This protocol differs from the upstream text helper's TTS/transcription route. It is recorded in `sampling_information` and visible in the UI. Comparing results requires identical model IDs, revisions and sampling conventions. Mini results must not be relabeled as full-model results, measured human responses, panic scores, or validated evacuation behavior. Neural coupling stays off by default.

## Installation and direct execution

The separate runtime is in ignored `cache/tribe-env`; the pinned official Git checkout is in `cache/tribev2-source`. The normal app environment does not install or import Torch.

```bash
bash scripts/setup-tribe-local.sh
# Only needed if no Hugging Face login is configured; requires Llama 3.2 1B access:
uvx --from huggingface_hub hf auth login
cache/tribe-env/bin/python backend/scripts/run_tribe_local.py \
  --stimulus warning.txt --warning-id generic --output data/local-tribe/my-warning
```

Python 3.12, Torch 2.6.0 and all dependencies are pinned in `backend/requirements-tribe-mac.lock`. Setup targets Apple Silicon macOS. The existing Hugging Face login has been verified for the 1B model. First use downloads approximately 0.7 GB for Mini and 2.5 GB for the language encoder, plus package dependencies. Later jobs reuse cached weights/features. Limits: one web worker at a time, 200 words / 16 KB per text, and a ten-minute process timeout. `--device cpu` provides an explicit CPU alternative.

## Local HTTP API

The app binds to `127.0.0.1:8000`. Register text through the existing stimulus API, then pass its ID:

```bash
curl -F warning_id=generic -F file=@warning.txt http://127.0.0.1:8000/api/stimuli
curl -H 'Content-Type: application/json' -d '{"stimulus_id":"RETURNED_STIMULUS_ID"}' \
  http://127.0.0.1:8000/api/neural/local
```

The second request returns a saved analysis, metadata, numerical summary and response series. For the normal warning workflow, `POST /api/neural/analyze-warning` with `{"warning_id":"generic"}` registers exact text automatically and returns `{analysis, cached}`; add `"force":true` to recompute. Use `GET /api/neural/analyses/ANALYSIS_ID/download` for the complete NPZ array and `GET /api/neural/analyses/ANALYSIS_ID/metadata` for importable metadata. `GET /api/neural/local` reports availability/busy state. No public server or credentials are needed for local callers.

## Exact models and hosted alternatives

- [Official Mini checkpoint](https://huggingface.co/facebook/tribev2-mini): `f3463fd77b17d80e4f61636bc2674b375803e743`.
- Its actual pretrained text extractor is [Llama 3.2 1B](https://huggingface.co/meta-llama/Llama-3.2-1B), pinned to `4e20de362430cd3b72f300e6b0f18e50e7166e08`. The repository's training-grid `mini_config` uses Qwen, but that is not the released Mini checkpoint's configuration; we use the checkpoint's Llama features.
- [Official code](https://github.com/facebookresearch/tribev2/tree/af58661791a351a448a489042a28f6c37e1c14b7): `af58661791a351a448a489042a28f6c37e1c14b7`.

On 2026-10-24, Hugging Face listed no Inference Provider deployment for either official model. Community Spaces exist, but were not adopted as reliable APIs. Bedrock Nova Micro was successfully invoked in this AWS account, with 46 input and 20 output tokens costing an estimated $0.00000441. Bedrock's supported custom import architectures exclude TRIBE's brain encoder, so it cannot replace this worker. No additional AWS calls are needed for the local solution.
