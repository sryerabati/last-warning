# End-to-end demo

Start with the [README setup](../README.md), valid AWS credentials and the [local Mini runtime](tribe-local.md). Everything happens in the simulator workspace. The UI starts with **Bedrock agents**; the default city has 300 residents, seed 42, 120 ticks and five seconds per tick.

## Explore daily life

The town opens at 08:00 with residents leaving home and walking to work, school and shops. Use **Time of day** to jump to noon, evening or night; a time jump pauses the scene. The clock has its own play and speed controls. Select a person to see their name, actual home, destination, household and daily routine. Click an occupied building to inspect someone inside; repeated clicks cycle its actual occupants. Meeting bubbles represent residents who are at the same place.

The winding river, paths, bridges and buildings are canonical simulation geometry. Daily schedules are computed locally without Bedrock calls. **Run warning** freezes the visible daily snapshot and starts the emergency from those exact positions. After a recording, **Return to town** restores the previous town time and play state.

## Run both warnings

1. Choose **Flash flood → Generic advisory**. Edit the message if desired, then click **Run warning**. The app saves that exact message, obtains a matching local Mini artifact, checks Bedrock access and spending limits, and records the simulation with real model decisions.
2. Watch the city, pause, and select a resident after a decision checkpoint. The inspector shows the resident’s recorded action, time and explanation. Living-town residents choose **Continue routine**, **Wait**, **Prepare**, **Share** or **Evacuate** from their available actions. Travel follows the actual road network; waiting holds position and evacuation interrupts the daily trip.
3. Use Restart, step controls, speed or the timeline to inspect the recording. Replay does not call Bedrock or Mini again.
4. Click **Compare warning**, choose **Actionable warning**, and click **Run alternative**. The baseline city, residents, disaster, seed and decision mode remain locked. Both views share one timeline; the inspector shows the alternative’s actual outcomes and deltas against the baseline.
5. Open **Advanced → Model & methods** for the recorded model, request/decision counts, token usage and estimated cost. Each run is capped at $0.30 and this Bedrock phase at $5. The remaining allowance is also visible in Scenario settings.

Fresh LLM decisions can vary even at temperature zero. Compare the measurements produced by the current runs; earlier Rules-baseline counts are not expected Bedrock outcomes. Starting conditions are controlled, while a saved replay preserves the exact recorded result.

Living-town experiments use `nova_resident_json_life_v1`; legacy experiments retain `nova_resident_json_v4`. Both use normal Bedrock Converse text requests, with every returned resident ID and available action validated before applying the round. If an otherwise valid response omits a resident, one follow-up asks the model for that missing decision. Only a complete validated round is applied. The app does not use Bedrock tool calls or silently replace failed model decisions.

## Edit, inspect and restore

- **Warning delivery:** Advanced → Warning & assumptions changes the message, alert channels, delivery reach and broadcast tick, or creates/duplicates a custom warning. In Bedrock mode, the model chooses the response; Rules-baseline notice/action/sharing probabilities and preparation delay do not apply.
- **Neural response:** Advanced → TRIBE Mini & imports contains exact-text curves, immutable revisions, protocol, provenance and downloads. New text requires matching inference; unchanged text can reuse a validated result. Original external stimuli and matching metadata/NPZ artifacts can be registered and imported here.
- **History:** Saved runs reopens a recording or comparison with its warning snapshot, including after edits or deletion. Export the gzip recording if needed. Restoring history does not regenerate model responses.
- **Other disasters:** choose Wildfire or Tornado in the same toolbar. Each has actual hazard mechanics and its own warning pair; tornado residents use nearby storm shelters. Changing disaster clears the previous replay before the next run.

Local Mini presents text at 2.5 words per second and predicts an average subject’s cortical fMRI response. It does not measure fear or evacuation success and does not drive Bedrock actions.

## Optional offline baseline

Select **Advanced → Scenario settings → Resident decisions → Rules baseline** to run without AWS. Configured probabilities and delays determine behavior; message text alone does not alter uncoupled resident decisions. This is an explicit comparison mode and never an automatic replacement for a failed Bedrock request.

Optional neural coupling is available only in Rules mode, under Advanced → TRIBE Mini & imports. Its assumed relationship is a sensitivity experiment, not a validated neuroscience-to-behavior model. Coupling is off by default.

The previous deterministic demo used Rules mode; measured outputs and artifact evidence are in [verification](verification.md). Scripts such as `backend/scripts/verify_disasters_demo.py` explicitly use their own scenarios and decision mode. Confirm a script’s mode before treating its result as a Bedrock-agent demonstration.
