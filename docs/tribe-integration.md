# Official TRIBE v2 pipeline

## Verified and remaining

The worker adapter follows [Meta's official API](https://github.com/facebookresearch/tribev2/blob/af58661791a351a448a489042a28f6c37e1c14b7/tribev2/demo_utils.py). Text, audio and video entrypoints, immutable checkpoint download, source-commit checks, export schema, hash validation, import, time-series aggregation, timestamp-aligned differences, and optional coupling are implemented.

**Official TRIBE v2 Mini inference now runs on the M4 Mac, and both warning analyses are saved in Neural Lab.** The separate local worker uses Apple Metal for the brain encoder and CPU for Llama 3.2 1B. See [the local Mini guide](tribe-local.md) for the working UI, CLI, HTTP API, exact revisions and controlled reading protocol.

The full-model CUDA route below remains unverified because AWS rejected the GPU launches on quota grounds. Dry-run input validation and numerical serialization/import pass without Torch; its dependency graph resolved for Python 3.12 / Linux x86_64. Hugging Face access to the gated 3B Llama is confirmed. Mini and full-model results keep distinct model IDs and cannot be compared as if they were the same checkpoint.

## Current AWS blocker

The user explicitly authorized a paid GPU job under the $30 project ceiling. AWS accepted the launch permission dry run but rejected real On-Demand GPU launches in both `us-east-2` and `us-east-1` with `VcpuLimitExceeded` and a current quota of zero. Ohio Spot returned `MaxSpotInstanceCountExceeded`. The automatic `RequestServiceQuotaIncrease` call was explicitly denied by the organization service control policy.

The Innovation Hub administrator needs to raise **Running On-Demand G and VT instances**, quota code **L-DB2E81BA**, to **16 vCPUs in us-east-2** for the prepared single `g5.4xlarge` job. No running worker or paid storage was left behind. The two exact warning texts have been registered as stimuli and staged in ignored `data/gpu-job/` with their hashes.

The prepared launcher `backend/scripts/aws_gpu_job.py` restricts the job to one evaluated GPU instance, three hours, encrypted 100 GiB gp3 storage that is deleted on termination, IMDSv2, SSH from the operator's single IP, and an absolute persistent shutdown timer. It journals resource IDs, cleans failed launches, and reconciles a lost launch response before cleanup. At the originally checked Ohio price of $1.624/hour, its conservative three-hour job estimate was $5.92 including disk, IPv4 and a $1 buffer. Verify the current price before any new launch. The bootstrap script is prepared but could not be executed on a GPU host.

Meta's README states that average-subject predictions map to fsaverage5 and have a five-second hemodynamic offset already handled by the official pipeline. The worker preserves actual `Segment.start` values; it never substitutes a fabricated uniform time axis. No invented brain anatomy is rendered.

## GPU setup

The optional AWS launcher includes no account, network, or image IDs. Set the following environment variables to your verified configuration, authenticate through your normal AWS credential chain, and supply every value explicitly:

```bash
python backend/scripts/aws_gpu_job.py launch \
  --expected-account "${AWS_EXPECTED_ACCOUNT_ID:?Set your intended AWS account ID}" \
  --region us-east-2 \
  --vpc-id "${AWS_GPU_VPC_ID:?Set the VPC ID}" \
  --subnet-id "${AWS_GPU_SUBNET_ID:?Set a public subnet ID in that VPC}" \
  --ami-id "${AWS_GPU_AMI_ID:?Set an Amazon-owned x86_64 DLAMI ID}" \
  --public-key "${AWS_GPU_PUBLIC_KEY:?Set the path to your SSH public key}" \
  --hourly-price "${AWS_GPU_HOURLY_PRICE:?Set the verified hourly instance price}" \
  --max-hours 1
```

Missing or malformed account, VPC, subnet, or AMI arguments stop before authentication. The launcher checks the authenticated account before looking up the operator IP or accessing EC2 resources, verifies that the available subnet belongs to the supplied VPC, and accepts only an available Amazon-owned x86_64 image without marketplace product codes. Select a CUDA-compatible DLAMI and verify that the chosen subnet has working public internet routing; those properties are not inferred from an ID. Keep the ignored resource journal for `status`, `terminate`, and `cleanup`; those actions reuse its region and resource IDs.

Use a separate NVIDIA Linux host with CUDA-compatible drivers, Python 3.12, ffmpeg, git, adequate disk space for checkpoints/features, and internet access. A 24 GiB GPU is a candidate, not a tested minimum; feature-extractor memory and CPU RAM must be checked during the first job. Keep the ordinary app running locally.

```bash
python3.12 -m venv tribe-env
source tribe-env/bin/activate
python -m pip install --upgrade pip
git clone https://github.com/facebookresearch/tribev2.git /tmp/last-warning-tribev2
git -C /tmp/last-warning-tribev2 checkout af58661791a351a448a489042a28f6c37e1c14b7
python -m pip install -r backend/requirements-tribe.lock
python -m pip install --no-deps -e /tmp/last-warning-tribev2
ffmpeg -version
python -c 'import torch; from tribev2 import TribeModel; assert torch.cuda.is_available(); print(torch.cuda.get_device_name())'
```

Run these from the copied Last Warning repository. The exact resolved requirements have not been installation-tested. The constraints in `backend/requirements-tribe.txt` keep Torch within the official supported range, NumPy at its official version and Transformers below v5. If installation fails, resolve the actual error before launching inference; never silently replace the model.

Authenticate Hugging Face using an environment token or the standard local login. The account must have access to the Llama 3.2 feature extractor used by the official checkpoint. The token is never included in model metadata. The official `.txt` preparation uses gTTS and transcription; speech synthesis needs external network access. Uploaded audio can be used with the same official preprocessing flow.

## Prepare the two warning stimuli

In Neural Lab, choose the relevant warning and upload its `.txt`, `.wav` or supported video. Each registered stimulus records its exact SHA-256, warning ID, and warning text revision. Download the registered file and copy it to the GPU host. Use the same bytes for inference and registration.

```bash
# Validate only; no Torch/model download/GPU required.
python backend/scripts/run_tribe.py --stimulus generic.txt --warning-id generic --dry-run

# Genuine official inference; fails clearly if CUDA or gated weights are unavailable.
python backend/scripts/run_tribe.py --stimulus generic.txt --warning-id generic --output generic-output
python backend/scripts/run_tribe.py --stimulus actionable.txt --warning-id actionable --output actionable-output
```

The worker resolves `facebook/tribev2` to an immutable model commit, downloads `config.yaml` and `best.ckpt`, then calls:

```python
model = TribeModel.from_pretrained(checkpoint_dir, cache_folder=cache, device="cuda")
events = model.get_events_dataframe(text_path=stimulus_path)  # or the official audio_path/video_path
predictions, segments = model.predict(events=events)
```

For a repeated experiment, pass `--model-revision` with the exact commit from the first job. The official source checkout must remain clean at the pinned commit. Each output folder contains:

- `predictions.npz`: numeric `predictions` (time × vertices) and `times` (actual segment starts).
- `metadata.json`: warning ID, stimulus hash, immutable model/code revisions, prediction shape, inference timestamp, sampling convention, and declared `REAL_TRIBE` provenance.

Copy both folders back before terminating the GPU host. Select the corresponding registered stimulus in Neural Lab, choose the two output files, and click **Validate & import**. No GPU is needed after import.

## Numerical comparisons

Select two analyses produced by the same model revision and sampling convention. The API aligns their actual shared timestamps, verifies matching vertex counts, and computes per-time mean/absolute differences across corresponding vertices. It does not subtract unrelated timepoints or compare mismatched checkpoints. Different durations yield comparisons over their timestamp intersection.

## Import trust and safety

The importer refuses pickle/object arrays, nonfinite values, wrong shapes, invalid timestamps, excessive decompressed sizes, deceptive NPY dimensions, mismatched stimulus hashes, and missing provenance fields. Imported `REAL_TRIBE` metadata is an assertion from the producer, not independent proof of GPU execution. `TEST_FIXTURE` remains visibly labeled and cannot control simulation behavior. Tests generate such fixtures only in temporary directories.

TRIBE is CC-BY-NC-4.0. Cite d'Ascoli et al., *A foundation model of vision, audition, and language for in-silico neuroscience*, arXiv:2605.04326, and preserve Meta's license. The separate base feature extractors may have their own gated terms.
