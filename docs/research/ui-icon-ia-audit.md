# UI icon and information architecture audit

Audit scope: the simulator shell, camera/building discovery, warning editing, resident inspection, playback, saved runs, outcomes and TRIBE Mini panel. The source audit reads the actual handlers, rather than assuming an icon's meaning from its existing name.

## Design rules and evidence

An icon is secondary to a clear action label. The interface should use the same glyph for the same operation, and distinguish operations that merely happen to involve the same object. W3C's guidance on [consistent identification](https://www.w3.org/WAI/WCAG22/Understanding/consistent-identification.html) supports that consistency; its formal success criterion applies across pages, while this audit also applies the principle within the simulator.

Icon-only camera controls retain explicit accessible names and hover titles. Decorative SVGs remain hidden from assistive technology because the enclosing button already supplies the name. This follows the [WAI button pattern](https://www.w3.org/WAI/ARIA/apg/patterns/button/) and [accessible-name guidance](https://www.w3.org/WAI/ARIA/apg/practices/names-and-descriptions/). Text should remain beside the less universal icons in the main toolbar and menus: research on [icon usability](https://www.nngroup.com/articles/icon-usability/) warns that most symbols need contextual labels.

The visual language remains a 16×16 integer-coordinate icon family, rendered with `crispEdges` and `currentColor`. No new font, icon dependency or external artwork is needed.

## Action-by-action audit

| Surface / actual action | Existing issue | Correct mapping |
| --- | --- | --- |
| Edit warning | Gear previously implied configuration | Keep the new `edit` pencil and “Edit warning” label |
| World/run configuration | Gear correctly identifies settings | Keep `settings`; use the same label at every entry point |
| Disaster selection | Weather-specific glyphs correspond to selected event | Retain flood, flame, tornado, snow, hail, storm and restricted-zone symbols |
| Warning editor | Alert triangle describes the message being authored | Retain `warning` with visible “Warning” text |
| Compare warnings | Opposed arrows express comparison | Retain `compare`; retain explicit baseline/alternative context |
| Saved runs | Document glyph is reasonable, but drawer says “Saved worlds” | Retain `runs`; rename drawer “Saved runs” |
| Results / charts | House implied shelter only, although drawer contains all outcomes | Use `chart`; use `people` when the drawer is the ordinary town population |
| Sources / methods | Sliders implied adjustable controls, but this is reference material | Use `book` |
| More functions menu | Sliders suggest a settings-only panel, but it includes reference, results and sound | Use `menu`; group destinations rather than calling everything advanced |
| Sound toggle | Emergency beacon implied siren/alert broadcast | Use `volume-on` / `volume-off`; retain explicit sound state |
| Busy Run warning | Pause icon implied a pausable action on a disabled run button | Use `loading`; actual stopping remains the separate “Stop run” action |
| Show recorded route | Crosshair suggested camera tracking | Use `route` |
| Place hazard origin | Same crosshair was reused for tracking and location placement | Use `pin` |
| Follow resident | Tracking crosshair matches the camera action | Retain `follow` with its pressed state and label |
| Previous / next resident | Playback-step glyphs implied changing the timeline | Use `chevron-left` / `chevron-right` |
| Restart replay | Existing bar/triangle was too similar to a frame step | Use `restart`; frame-step buttons retain `step-back` / `step-next` |
| Return to town | Shelter house suggested taking protective action | Use `town` |
| Open a saved recording | Smooth circular arrow was a different visual family and could resemble rerunning | Use `replay`, with a replay/open accessible label, never imply a new inference job |
| Download a recording or predictions | Action is correct but some buttons use smooth line art | Use shared `download` |
| Delete warning | Trash meaning is correct but line style differs | Use shared `trash` |
| Camera search | Magnifier meaning is correct but line style differs | Use `search` |
| Camera zoom | Plain plus/minus can mean adding/removing entities | Use `zoom-in` / `zoom-out` magnifiers with existing zoom labels |
| Camera focus and whole-map fit | Both use smooth corner glyphs | Use `focus` (center mark) and `fit` (frame around extent), retaining distinct labels |
| Close building/search or panel | X is correct but mixed icon families remain | Use shared `close` |
| Local Mini analysis | Brain meaning fits the subject; line style differs | Use `brain`, and `loading` while processing |
| Validate/import Mini artifacts | Upload meaning fits the action; line style differs | Use `upload`; keep “Validate and import” text |
| Replay opening sequence | Needs a separate action from world reset | Use `globe` or `replay` with explicit “Replay opening” text |
| Play/pause, success, errors and notifications | Existing symbols match their operations | Retain play/pause/check/danger/close |

The new glyphs are implemented in `frontend/src/pixel-ui/PixelIcon.tsx`. The application integration must preserve actual handlers and accessible names; the glyph change does not change the action. Contact sheet: `output/playwright/pixel-icon-audit.png`.

## Information architecture corrections

The working surface remains one simulator, not a new collection of pages. Use three levels of detail:

1. **World and immediate actions.** Map, resident/building selection, population counters, event, warning, compare, saved runs and run button. These are the things a player needs while operating the simulation.
2. **Focused drawers.** One task at a time: run setup, warning editing, residents/results, neural analysis and saved recordings. Population should say “Residents” during ordinary town life; completed-run analysis should say “Results.”
3. **Evidence and technical detail.** Sources, modeling assumptions, current model configuration, recorded model use, import artifacts and reproducibility metadata. These belong behind meaningful section names rather than between ordinary controls.

This follows [progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/): keep common operations readily available while exposing specialized details when they become relevant. It does not mean hiding essential controls behind nested accordions.

### Proposed More menu

| Group | Destinations |
| --- | --- |
| World | Run settings; Residents (ordinary town) or Results (recording) |
| Analysis | TRIBE Mini |
| Reference | Sources & methods; Replay opening |
| Preferences | Sound toggle |

Saved runs stays directly on the main toolbar. Its drawer label should match that destination. “TRIBE Mini & imports” gives a maintenance workflow equal weight to the main analysis task; use “TRIBE Mini,” with the existing external-import section inside it.

### Sources & methods structure

Lead with one short explanation of what the current view represents. Then provide separate, named sections for:

- **Campus data:** source, date, real geometry and map limitations.
- **Residents:** fictional population, assigned biographies, routines and assumptions. A generated identity is not an inference about a real person.
- **Weather & safety:** which thresholds/instructions are sourced, which hazard fields are authored and what exposure metrics mean.
- **Models & replay:** ordinary routines, Bedrock emergency decisions and Mini's text-response prediction are different processes. Keep the short explanation that Mini does not control Bedrock actions readily visible.
- **Usage & reproducibility:** the selected recording's model/version/cost separately from the next run's available provider and budget; seed and detailed revisions can be collapsed.

### Additional copy and hierarchy findings

- “Changes apply to the next run” is incomplete for population/seed edits: these rebuild the displayed town preview. Clarify that behavior at the point of editing.
- A warning's world-clock starting time and the recording's elapsed time are different. Keep their labels distinct rather than showing two unlabeled clocks.
- Ticks are useful engineering metadata, but durations and alert timing should also show human-readable simulated minutes/seconds. Detailed tick controls can remain under timing settings.
- Labels such as “Neural response,” “TRIBE Mini” and “Mini analysis” should clearly refer to the same task. Use a consistent destination name and explain the model once inside.
- Avoid adding nationality/ethnicity badges to the resident inspector merely to justify a name or skin color. Name, role, current activity, home/work and relationships are the useful operational information; fictional biography details can be expanded on demand.
- The opening is a brief transition, not an obstacle: always offer Skip, respect reduced motion, avoid autoplay audio, and expose an explicit replay action. Animation should never delay a ready control after Skip.

## Verification responsibilities

The icon library passed TypeScript checking before call-site integration. The contact sheet checks shapes at native16px and2×. Final application QA should verify the updated controls by their actual effects, including sound state, camera functions, previous/next residents, route display, result/reference destinations, local-analysis loading and the busy-run button. Do not start a paid warning just to test an hourglass icon; inspect the existing busy-state branch and test the separate rendering state locally.
