# Last Warning

A pixel-art campus simulator for exploring how emergency warnings affect synthetic residents. The default world recreates Ohio State’s academic core from pinned OpenStreetMap geography. Amazon Bedrock supplies individual resident decisions during emergencies; the local engine controls movement, buildings, vehicles, route closures and exposure.

Students, professors, neighbors and families have persistent generative character designs, homes, daily routines and real car trips. A complete day includes walking, crossing queues, car trips, scheduled shuttle rides, conversations and returning home. Teaching days, weekends, class breaks and university closures have different schedules. **TRIBE v2 Mini** runs locally on the Mac for the exact warning text. All controls, comparisons, saved replays and advanced tools live in one simulator page.

Campus engine 3.1 uses physical-second warning and response timing, separate from replay sampling. Tornado contact records movement interruption, knockdown/bracing and recovery poses. **More → Shuttle & crossings** shows actual stops, queues, buses and passengers; the route is an educational CC corridor circuit, not the full official CABS service. See [movement coordination](docs/campus-mobility.md), [calendar and transit sources](docs/research/campus-calendar-transit.md), and the [behavior audit](docs/research/behavior-fidelity-audit.md).

See the [campus implementation and limits](docs/campus-implementation.md), [character system](frontend/art/last-warning/characters.md), and [campus emergency architecture](docs/campus-emergency-engine.md).

## Start

Requires Python 3.12 (selected by uv), uv, Node.js 22.12+, and working AWS credentials with Bedrock access. The AWS SDK is an application dependency.

```bash
uv sync --frozen --group dev
npm --prefix frontend ci
npm --prefix frontend run build
bash scripts/start.sh
```

The server uses the normal AWS SDK environment/profile credential chain. For an existing configured profile:

```bash
AWS_PROFILE=innovation-hub AWS_DEFAULT_REGION=us-east-2 bash scripts/start.sh
```

Alternatively, authenticate and start with temporary credentials entered through hidden input:

```bash
uv run python backend/scripts/serve_with_aws.py --credential-parts 4
```

The launcher accepts four consecutive parts of one JSON credential dictionary, verifies STS authentication, then holds the session in process memory. See [AWS setup and budget](docs/aws-budget.md) for its input format and limits. No credential values belong in source files.

Open [Last Warning](http://127.0.0.1:8000). FastAPI serves the UI and [API documentation](http://127.0.0.1:8000/docs). For hot reload, use `bash scripts/dev.sh` with AWS credentials available to its backend process.

## Use

1. Watch the town's daily life, pause or change its speed, and jump to morning, noon, evening or night. Select a resident or occupied building to inspect an actual household, home and destination.
2. Open the event dropdown and choose **Flood**, **Wildfire**, **Tornado**, **Blizzard**, **Hailstorm**, **Severe thunderstorm**, or **Major public safety threat**, select a warning, and edit its message. **Run warning** freezes the visible town time and resident positions, computes or reuses a real Mini result for the exact text, then requests emergency decisions from Bedrock.
3. Pan or zoom the city, inspect a recorded action and explanation, follow a resident, and replay the run along its recorded routes. **Return to town** restores your daily-life viewing position.
4. Click **Compare**, choose or create an alternative, and **Run alternative**. The city, population, disaster, decision mode and seed remain fixed; both worlds use one canvas and a synchronized clock.
5. Use **More** for grouped World, Analysis and Reference tools, plus the sound toggle. **Sources & methods** separates the simulation explanation, dated evidence and model details. **Runs** reopens recordings and comparisons without inference charges.

The skippable opening continuously zooms from pixel Earth through Ohio and Columbus into the live Oval, with no map fade or screenshot swap. The surrounding neighborhoods share the campus palette and geometry, with an irregular detail blend instead of a rectangular reveal. Sound is **on by default**, including the opening flight, interface cues, warning broadcasts and weather. Browsers require a click or keypress before audio can start. **More → Sound** mutes it, and an explicit mute preference is remembered. It plays once per browser session and can be replayed from **More → Replay opening** in a single campus view. Reduced-motion settings bypass the automatic animation; manual replay shows a static globe. Names, biographies and household appearances describe fictional residents. New campus runs exclude names and cosmetic identity from Bedrock decision inputs. See the [UI and identity audit](docs/ui-identity-opening-audit.md) and [continuous opening implementation](docs/continuous-opening.md).

The run panel shows actual local-analysis, decision-round/batch and simulation-tick progress. Refreshing reconnects to the same durable job. **Stop run** prevents future requests; already sent model requests can finish and remain accounted. Interrupted jobs are explicit and are never automatically billed again.

Bedrock agents choose **Wait**, **Prepare**, **Share**, **Evacuate**, or—in living-town experiments—**Continue routine** at recorded checkpoints. They receive their actual activity, household and home/work context. Daily itineraries run locally without cloud calls; emergency decisions and reasons come from Bedrock. Alert channels, delivery reach and broadcast timing determine which warnings residents receive. Notice/action/sharing probabilities and preparation-delay presets belong to the optional **Rules baseline** and do not drive Bedrock decisions.

A fresh Bedrock generation can differ even with the same seed. **Saved replay is exact**: it reads stored frames, decisions and explanations without calling a model again. Comparisons control starting conditions; they are not calibrated predictions of human behavior.

## Resident models and budget

**More → World settings → Resident decisions** switches between the default Bedrock agents and the explicit offline Rules baseline. A Bedrock failure stops the run with an error; the app never silently substitutes rules.

The provider is `us.amazon.nova-micro-v1:0`, requested through `us-east-2`. Durable local accounting limits each run to **$0.30**, this Bedrock phase to **$5**, and project requests to the **$30** ceiling. Token usage and estimated cost are saved with each run. The budget also accounts conservatively for uncertain requests and includes the earlier $0.00000441 smoke test in the project estimate. These are application safeguards and estimates, not an AWS billing statement or verified credit balance. See [budget details](docs/aws-budget.md).

## Local TRIBE Mini

The working local setup uses the MacBook Pro’s M4/16 GB: the brain encoder uses Apple Metal, while Llama 3.2 1B text features use CPU. Model checkpoints, local recordings, and prediction artifacts are not included in this public repository. The campus edition uses explicitly simulated warning texts, each requiring its own matching analysis. New text requires a matching analysis; exact text and checkpoint/protocol matches can reuse saved results.

**More → TRIBE Mini** contains response curves, revisions, provenance, downloads and external imports. Setup and CLI/API instructions are in the [local Mini guide](docs/tribe-local.md).

Text is presented at 2.5 words per second using defined reading times, without audio/video features, speech synthesis or transcription. Mini predicts an average subject’s cortical fMRI response; it does not measure fear, comprehension or evacuation success. Its results do not determine Bedrock actions. Neural coupling is off by default and available only as a Rules-baseline sensitivity experiment.

Full-size TRIBE CUDA inference remains unverified. Earlier AWS GPU launches failed because the account has zero GPU quota; temporary launch records were cleaned up. Bedrock hosts the resident language model, while Mini runs locally. [GPU background](docs/tribe-integration.md).

## Tests and verification

```bash
uv run pytest -q
npm --prefix frontend run build
node --test 'scripts/verify-*.mjs'
```

Tests use temporary storage and mocked provider boundaries; they do not make paid AWS calls or require checkpoint downloads, Torch or a GPU. See [living-town verification](docs/living-town-qa.md) for current checks and their decision mode, [earlier integration evidence](docs/verification.md), and the [demo guide](docs/demo-guide.md) for the walkthrough. Earlier deterministic Rules-baseline results must not be presented as Bedrock-agent outcomes.

Isolated provider tests cover complete eligible decisions, exact model-output parsing, missing-resident recovery, atomic round application, bounded retries, request auditing and persistent spending limits. Legacy experiments use `nova_resident_json_v4`; living-town experiments use `nova_resident_json_life_v1` with the additional routine action. The campus protocol adds shelter, postponed travel, area evacuation and household coordination. All use ordinary Converse text with validated JSON responses, without tool calls.

`python scripts/verify_living_town.py` independently checks the complete local day: reachable homes, connected routes, actual co-location, indoor occupancy and the midnight loop. `--run-disasters flood wildfire tornado` also checks both warnings with the offline Rules baseline and real Mini artifacts. Selecting `--decision-mode bedrock` explicitly makes paid calls under the app's caps; `--resume` reconnects to the jobs in its saved report without purchasing replacements.

## Data and architecture

SQLite metadata, gzip recordings, stimuli and prediction artifacts live in ignored `data/`. `LAST_WARNING_DATA_DIR` relocates simulation data. The spending ledger deliberately remains at `data/agents/bedrock/spend.sqlite3` under this project, including when a verification run uses another data directory. Preserve it when backing up or moving the project; resetting simulation data must not reset spending history.

Public campus geography, provenance and licenses are bundled in `backend/app/data/`. Credentials, local runtime data, model caches, private deployment bundles, and generated video deliveries are excluded from Git. Configure AWS and Hugging Face access on your own machine; never commit their tokens.

Initial schema changes apply automatically and preserve existing records. Runs snapshot their warning, scenario, decision mode, model decisions and usage. Later edits or warning deletion do not alter replay.

The server binds to loopback without authentication and is intended for a local demo. Internet deployment requires an authentication/access layer.

- [Architecture](docs/architecture.md)
- [Simulation assumptions](docs/simulation-assumptions.md)
- [Open-source reuse](docs/open-source-reuse.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

Limits: a bounded campus map slice, authored disaster fields and shelter capacities, simplified pedestrian/vehicle motion; uncalibrated LLM behavior; no validated neuroscience-to-behavior link; local Mini text limited to 200 words. Scientific forecasting and operational emergency use are not established by a successful demo.
