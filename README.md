# Last Warning

**[Play the public demo →](https://last-warning-campus.zippybadge66.chatgpt.site)**

A pixel-art Ohio State campus simulator exploring how emergency warnings affect synthetic residents. Watch campus life, send a warning, and compare what happens next—all on one screen.

The public demo runs on ChatGPT Sites with an AWS-hosted simulation engine and Bedrock resident decisions. **TRIBE v2 Mini analysis is available in the local version; its inference controls are disabled in the hosted demo.**

## The simulator

- **A living campus:** pinned OpenStreetMap geography, generative characters, homes, classes, daily routines, families, cars, crossings, and scheduled shuttles. Teaching days, weekends, breaks, and closures follow different schedules.
- **Seven hazards:** flood, wildfire, tornado, blizzard, hailstorm, severe thunderstorm, and a deliberately nonspecific major public safety threat. Weather changes movement and exposure; tornado contact interrupts movement and shows impact/recovery poses.
- **Individual decisions:** Bedrock residents respond to the warning they actually receive, their activity, household, and surroundings. The local engine handles routes, buildings, traffic, timing, and exposure.
- **Replay and comparison:** inspect actions and explanations, follow a resident, and compare warnings from matching starting conditions. Saved replays use recorded decisions and make no new inference calls.

Choose an event, edit its warning, then **Run warning**. Use **Compare** for an alternative and **Runs** for saved recordings. **More** groups world settings, shuttle/crossing information, analysis, and sources. Sound defaults on after the first click or keypress; **More → Sound** remembers a manual mute. The Earth-to-Oval opening is skippable and respects reduced-motion settings.

## Run locally

Requires **Python 3.12**, **uv**, **Node.js 22.12+**, and AWS credentials with Bedrock access for LLM decisions.

```bash
uv sync --frozen --group dev
npm --prefix frontend ci
npm --prefix frontend run build
bash scripts/start.sh
```

Open [localhost:8000](http://127.0.0.1:8000) or the [API docs](http://127.0.0.1:8000/docs). For hot reload, use `bash scripts/dev.sh`.

The backend uses the normal AWS SDK credential chain. With an existing authenticated profile:

```bash
AWS_PROFILE=innovation-hub AWS_DEFAULT_REGION=us-east-2 bash scripts/start.sh
```

See [AWS credentials and budgets](docs/aws-budget.md) for temporary-session setup. Install the separate Apple Silicon inference runtime using the [local Mini guide](docs/tribe-local.md); it requires Hugging Face access to Llama 3.2 1B. Model weights, recordings, and predictions are not bundled. Without AWS, select **More → World settings → Resident decisions → Rules baseline**. If the local model runtime is not installed, disable **More → TRIBE Mini → Analyze the warning when running**.

## Models and limits

**Residents:** Amazon Nova Micro (`us.amazon.nova-micro-v1:0`, requested through `us-east-2`) supplies validated decisions and reasons. Daily routines run locally. Provider failures stop the run; rules are never substituted silently. Fresh generations can differ even with a fixed seed, while saved replay is exact.

**Neural analysis:** TRIBE v2 Mini predicts an average subject’s cortical fMRI response to the exact warning, presented at 2.5 words/second. On the tested M4/16 GB Mac, the brain encoder uses Metal and Llama text features use CPU. Matching text, model, and protocol can reuse saved analyses. Mini does not measure fear, comprehension, or evacuation success, and does not determine Bedrock actions. Neural coupling defaults off and is limited to Rules-baseline sensitivity experiments. Full-size CUDA inference remains unverified.

**Cost:** application limits are **$0.30/run**, **$5 for the Bedrock phase**, and **$30 for project requests**. These are request-accounting safeguards, not an AWS billing cap; hosting and other account activity are separate. Token usage and estimated costs are saved with each run. [Budget details](docs/aws-budget.md).

Residents are fictional, LLM behavior is uncalibrated, and hazard fields, shelter capacities, traffic, and the shuttle circuit are simplified. Comparisons are educational experiments, not validated forecasts or operational emergency guidance. See [simulation assumptions](docs/simulation-assumptions.md).

## Development

```bash
uv run pytest -q
npm --prefix frontend run build
node --test 'scripts/verify-*.mjs'
```

Tests use temporary storage and mocked providers; they require no paid AWS calls, model downloads, Torch, or GPU. Explicit Bedrock integration checks do incur charges under the app’s limits.

Runtime data lives in ignored `data/`; `LAST_WARNING_DATA_DIR` can relocate simulation data. **Preserve `data/agents/bedrock/spend.sqlite3` when clearing or moving runs**—the spending ledger stays under the project regardless of that setting. Runs snapshot their inputs, decisions, and usage; later warning edits do not alter recordings.

Public map assets and provenance are in `backend/app/data/`. Credentials, caches, runtime artifacts, private deployment files, and generated videos are excluded from Git. The local server binds to loopback without authentication; public hosting needs an access layer.

## Further reading

- [Local operation and detailed verification](docs/local-development.md) · [Current demo walkthrough](docs/video-demo-guide.md)
- [Architecture](docs/architecture.md) · [Campus emergency engine](docs/campus-emergency-engine.md) · [Campus scope and limits](docs/campus-implementation.md)
- [Character design](frontend/art/last-warning/characters.md) · [Mobility](docs/campus-mobility.md) · [Calendar and transit evidence](docs/research/campus-calendar-transit.md)
- [Behavior audit](docs/research/behavior-fidelity-audit.md) · [Open-source reuse](docs/open-source-reuse.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)
