# Last Warning - competitive research for the judging video

Research date: October 24, 2026. Scope: public first-party documentation and research descriptions, compared with Last Warning's locally verified implementation. No competitor software was installed or benchmarked during this review.

## Recommended positioning

**Last Warning is a purpose-built workspace for comparing emergency-warning strategies. It combines a simulated city of AI resident agents, hazard-constrained movement and inspectable evacuation outcomes with an independent TRIBE v2 Mini brain-response analysis of the exact warning text.**

The immediate workflow is choose a disaster, inspect/edit a warning, compare strategies under matching starting conditions, inspect resident choices and replay the evidence. The advantage demonstrated is integration and task fit. Comparative human-response accuracy, operational safety and superiority over validated evacuation tools have not been measured.

## What the user confirmed

- Last Warning did not exist before HackOHI/O; the app was built during the event.
- MiroFish was an existing general-purpose reference the user researched.
- The user wants the comparison to explain why specialization matters, using Google Slides versus Google Drawings as an analogy.
- The user wants both the AI agent swarm and Meta TRIBE v2 emphasized.
- The actual checkpoint executed by this app is **facebook/tribev2-mini**. Calling it “Meta's TRIBE v2 Mini brain-response model” is accurate.
- No emergency-manager interview or target-user feedback was confirmed.

The source-reuse audit in [open-source reuse](open-source-reuse.md) records MiroFish as evaluated but not incorporated. Treat it as prior art/reference, not an embedded runtime.

## Comparison matrix

“Gap” below means a limitation of the documented workflow for this particular demonstration. It does not mean a product is defective or incapable of extension. Statements about what is undocumented are explicitly separated from proved absence.

| Tool / approach | Documented strength | Gap for the proposed workflow - assessment | Demonstrated Last Warning advantage |
|---|---|---|---|
| MiroFish, using OASIS | General multi-agent scenario exploration with personas, memory, simulation, reports and agent interaction; the documented engine is grounded in social simulation | A general social-simulation workflow does not supply the disaster-specific road/hazard/exposure comparison layer shown here without additional implementation | A ready-made warning editor, flood/fire/tornado scenarios, engine-enforced routes and closures, outcome deltas, saved replay and exact-warning Mini artifacts |
| FEMA Message Design Dashboard | Produces 90- and 360-character alert drafts, backed by research and public testing, for more than 50 hazards | The described output is a drafted alert. That does not answer the app's simulated question of how particular residents receive, decide and reach shelter as roads close | A sandbox to explore a warning's simulated consequences after composition, with resident actions and paired outcomes |
| FEMA IPAWS Message Viewer | Confirms test-alert status in the non-public IPAWS demonstration environment, using visual confirmation and status codes | A successful transmission/status check does not establish the behavior of the receiving public | Simulated decision and movement evidence beyond message-status confirmation; this is complementary to the real test system |
| Pathfinder | Pedestrian movement and evacuation, changing door availability, threat awareness, alerts, fire exposure, scenario/sensitivity analysis and published validation tests | Its reviewed documentation centers on movement/egress modeling. An exact-text TRIBE analysis track was not documented in the reviewed pages; this is a documentation finding, not an exhaustive feature exclusion | The current app is explicitly organized around warning editing, paired outcomes and independent Mini predictions. No claim of superior movement physics or validation is supported |
| AgentEvac, DENOS Lab | LLM household agents follow PADM and generate vehicle trips in SUMO; research targets wildfire warning timing, staged departures and routes | This is close prior art, already combining warning-aware agents and physical traffic. Its public overview focuses on wildfire/household vehicles and does not document a TRIBE track | Last Warning has verified flood, wildfire and tornado runs plus exact-warning Mini predictions in the same UI. A more accurate evacuation model has not been demonstrated |

## Primary sources and what each supports

### MiroFish and OASIS

- [MiroFish official repository](https://github.com/666ghj/MiroFish): describes a general swarm/simulation engine, GraphRAG/persona preparation, simulation, reporting and agent interaction; credits OASIS as its engine.
- [OASIS official repository](https://github.com/camel-ai/oasis): describes an LLM-agent social-media simulator, including Twitter/Reddit-style interaction and actions such as comments and reposts.
- Basis for our assessment: the documented social environment is not equivalent to an implemented evacuation road graph and hazard engine. Last Warning's physical constraints come from its own simulator and NetworkX, independently of the LLM's text.
- Do not say “MiroFish cannot simulate an emergency” or “MiroFish agents are fake.” Those are unsupported and miss the task-specialization argument.

### FEMA Message Design Dashboard

- [FEMA announcement of the Assistive Tool Platform](https://content.govdelivery.com/accounts/USDHSFEMA/bulletins/3ae94f5): distinguishes the Dashboard's message drafting from the Message Viewer's demonstration-environment status confirmation.
- [University at Albany developer report](https://www.albany.edu/news-center/news/2025-ualbany-researchers-develop-fema-dashboard-support-emergency-alert-messaging): confirms 90-/360-character drafts for more than 50 hazards, scientific/public testing, emergency-manager involvement and a second version released in July 2025.
- The relevant gap is moving from a well-formed warning draft to an inspectable simulated downstream scenario.
- Do not say “FEMA doesn't test messages with people,” “FEMA uses no behavioral science,” or “our three-hazard prototype has broader coverage.” Those conflict with the developer's account.
- Practical integration idea for future work: use a research-backed message draft as an input to Last Warning's scenario experiments. This is a proposal, not an implemented FEMA integration.

### Pathfinder

- [Official product capabilities](https://www.thunderheadeng.com/pathfinder/): occupants respond to changing conditions, signage and alerts; scenario analysis and validation are explicitly supported.
- [Emergency preparedness application](https://www.thunderheadeng.com/pathfinder/emergency-preparedness/): evacuation, assisted evacuation, awareness and exposure are within scope.
- [Current assisted-evacuation technical reference](https://www.thunderheadeng.com/docs/latest/pathfinder/advanced/assisted-evacuation/tech-ref/): describes agent goals and assisted movement.
- The relevant distinction is the warning-text-centered UI and added independent neural research output, not the presence of agents, behavior, alerts or scenario comparisons in isolation.
- Do not call Pathfinder “just dots following fixed routes”; its public documentation contradicts that characterization.

### AgentEvac and other related research

- [DENOS Lab AgentEvac project](https://denoslab.com/projects/agent-evac/): explicitly couples LLM/PADM household decisions with SUMO vehicle traffic and real road networks; a news item is dated October 7, 2026.
- [FLARE authors' paper](https://arxiv.org/abs/2502.17701): behavioral-theory-informed LLM wildfire evacuation decision prediction, first submitted February 2025.
- [LLM-enhanced crowd evacuation research](https://www.sciencedirect.com/science/article/pii/S0951832025012554): describes individual LLM decision agents with personality, observations and history, along with batching and pedestrian/vehicle simulation.
- These establish that AI-agent evacuation research predates this hackathon. Keep the contribution claim specific to Last Warning's implemented combination and workflow.
- We did not find a documented TRIBE integration in these reviewed descriptions. That is not proof of global priority or of every implementation detail.

### Meta TRIBE v2 and Mini

- [Official TRIBE v2 README](https://github.com/facebookresearch/tribev2/blob/main/README.md): the model predicts fMRI responses; the quick start describes average-subject cortical predictions, naturalistic inputs and vertex/time output.
- [Meta's Mini checkpoint](https://huggingface.co/facebook/tribev2-mini): establishes the published Mini checkpoint. Its public model-card prose is empty, so use the app's pinned implementation and genuine artifacts for claims about the local executed variant.
- [Local implementation notes](tribe-local.md) and [verification](verification.md): exact-text artifacts, controlled 2.5-word/second presentation, real local Mini execution and zero coupling to Bedrock actions.
- “Agent swarm + predicted brain response” is an honest description of the two analysis tracks. Neither predicted cortical activation nor an LLM explanation is a validated measure of a person's comprehension.
- Mini's usefulness here is enabling side-by-side exploratory neural comparisons of the warnings. Whether those patterns predict desirable real-world warning behavior remains a research question.

## Advantages to demonstrate on screen

1. **A constrained world:** the model can choose an eligible action, while the engine enforces reachable roads, travel, exposure and shelter arrival.
2. **A paired warning workflow:** starting city, population and hazard are controlled; warning content and delivery settings are explicit.
3. **Inspectability:** recorded actions, short model reasons, timestamps and immutable replays accompany outcomes.
4. **An additional analysis track:** exact warning text also has genuine local Mini predictions with model/protocol provenance.
5. **Working breadth:** three simplified hazards and six completed verified Bedrock runs, not a menu of unimplemented scenarios.
6. **Hackathon execution:** the application and integrations were built during this event, using existing libraries and pretrained models.

These are demonstrated capabilities. Quantitative superiority to the compared tools, scientific validation of neural effects, validated human behavioral accuracy and a deployed institutional workflow are not established.

## Language for the video and interview

### Main positioning line

“Last Warning pairs an AI agent swarm with Meta's TRIBE v2 Mini brain-response model to compare emergency-warning strategies in one inspectable city simulation.”

### Existing-tools line

“FEMA's Message Design Dashboard helps write alerts. MiroFish explores general social scenarios. Last Warning focuses on the next step: comparing simulated evacuation outcomes under changing hazards, with blocked roads and inspectable resident decisions.”

### Why specialization matters

“MiroFish gave us a useful general reference. For this task, we wanted the warning editor, disaster mechanics, route constraints, outcome comparisons and neural analysis already connected. That is the focused workflow we built.”

### Close-prior-art answer

“LLM-based evacuation simulation already exists, including AgentEvac. Our hackathon contribution is a warning-comparison workspace with three implemented hazards, saved resident decisions and an independent TRIBE Mini analysis of the same text.”

### Model relationship answer

“The swarm produces simulated actions. TRIBE Mini predicts average-subject cortical responses to the warning. We display those together, but Mini does not drive the Bedrock residents or prove which message humans understand better.”

### Research question for curiosity

“How do changes in a warning strategy affect simulated receipt, action and access to shelter, and what differences appear in the model's predicted cortical response to those same texts?”

The saved 54-versus-193 flood pair changes both wording and delivery reach/channels. A wording-only claim would need delivery settings held constant. This research did not run a new experiment.

## Motion design changes - specification only

- Replace the earlier NWS-only opener graphic with a brief three-row focus card: “FEMA MDD: Draft alerts”; “MiroFish: Explore social scenarios”; “Last Warning: Compare warning strategies + neural analysis.” Keep a small source label and avoid checkmark grids implying unverified feature absence.
- Introduce two labeled tracks early: “AI residents / actions + outcomes” and “TRIBE Mini / predicted cortical response.”
- Converge both tracks on the same saved warning identity. Do not draw an arrow from TRIBE to the resident's decision.
- Keep the actual outcome card and pivot card.
- Credit “Built at HackOHI/O 2026” on title and end card.
- No motion graphics or app components were built in this research phase.

## Review limits

This is a focused primary-source comparison, not an exhaustive market audit. Product claims describe their published workflows. “Better suited” judgments refer to the currently demonstrated warning-comparison task. No cost, latency, human-fidelity or evacuation-accuracy benchmark against other products was run. Genasys material appeared in search but its site was blocked from inspection; it was excluded from the comparison.

