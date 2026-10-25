# Pixel world sound

The soundtrack is original Web Audio synthesis: no downloaded samples, external requests, paid service, or package dependency. The quiet master level is capped at 0.09. Sound is off on first use; the existing Sound button saves the preference locally. A saved On preference still waits for a real pointer or keyboard interaction before creating and unlocking an audio context, following browser autoplay requirements. Hidden tabs are muted, and an inactive soundscape suspends its audio context.

## Cues

| Interaction | Sound |
| --- | --- |
| Panel, resident, disaster or mode selection | Short soft triangle click |
| Completed save/import or enabled sound | Two-note confirmation |
| New error | Quiet descending pair |
| Warning broadcast during playback | Distinct two-note notification |
| Opening travel | Filtered wind with a rising triangle tone, following camera progress |
| Arrival on the Oval | Short three-note arrival |
| Severe thunderstorm | Sparse filtered low rumble |
| Hail | Sparse group of three light ticks |
| Blizzard/tornado | Occasional soft wind swells |
| Wildfire | Sparse quiet crackle |
| Flood | Continuous low water/wind texture |
| Public safety | Neutral ambience; no operational alarm or simulated violence |

Weather accents only occur during short forward playback steps. Seeking or loading a recording does not trigger weather audio. Continuous ambience follows playback state; UI clicks and opening travel can play while the town is paused. All transient cues have cooldowns, at most twelve voices can exist at once, and every voice is stopped and disconnected after its envelope. Mute, hidden-tab and unmount paths stop transients immediately. All persistent nodes are stopped and disconnected on unmount.

## Integration API

`useWorldAudio` keeps its original options and `enabled`, `toggle`, `unavailable` return values, and adds two stable callbacks:

- `cue('select' | 'confirm' | 'error' | 'broadcast' | 'arrival')`
- `flight(progress: number | null)` — zero to one follows opening travel; `null` ends travel on completion, Skip, or cleanup.

The hook handles warning broadcasts and weather cues internally. Call `arrival` only when the opening actually finishes. Playback ticks must never trigger UI selection cues. Sound is optional and never carries information absent from the screen.

## Verification

Run `node scripts/verify-pixel-audio.mjs`. Eight regression checks exercise opt-in silence, paused-world UI cues, master level, cue cooldowns and voice limits, flight cleanup, mute/visibility handling, sparse weather, suspended-context wakeup, and disposal. A wall clock is used for cue cooldowns because the AudioContext clock freezes while suspended.

Browser audition fixture: `output/playwright/pixel-audio-audit.html` (generated local verification artifact; ignored by git). It has explicit Play buttons for every cue and a Render button that renders the actual engine through `OfflineAudioContext`, checking each PCM waveform is nonzero, finite and below a conservative 0.2 peak ceiling. No audio is played by loading the fixture or rendering samples. Chrome rendered all eleven entries successfully on 2026-10-25: every waveform was finite and nonzero; the highest observed peak was 0.018573. An explicit Play flight click put the real AudioContext into `running`; it returned to `suspended` after travel ended. This checks rendering and lifecycle, not a subjective listening review.

A separate actual React hook fixture (`output/playwright/pixel-audio-hook.*`) passed browser checks for first-load silence, gesture unlocking, broadcast deduplication across pause/resume, silent seeks, sparse weather, paused-world flight/UI audio, Skip idle suspension, persisted Off, persisted On without autoplay, and unmount context closure. It uses the real hook and synthesizer with an instrumented native AudioContext, not a fake React implementation.

The served simulator also passed Sound On → replay → Skip, Escape interruption, full opening completion, mute, and reload persistence. Enabling sound created the two persistent oscillators plus two confirmation notes, with no duplicate selection note. Skip and Escape added no arrival notes and suspended the paused-world context. Natural completion added exactly three arrival notes. Muting produced a zero master gain and suspended context; reload retained Off and created no context. The visibility handler produced the same zero/suspended result under a controlled hidden-state event. This automation browser kept native `document.hidden` false even with another tab foreground, so actual native background-tab behavior was not independently verified. No warnings were run or paid calls made during these checks.

Manual integration pass:

1. In a clean browser profile, load the simulator. Confirm Sound is off and there is no audio.
2. Turn Sound on, then pause the world. Open a panel: the selection cue should still play.
3. Replay the opening. Flight audio should rise with the camera; successful arrival should play the chime. Skip must stop flight immediately without an arrival chime.
4. Play a warning and watch the hazard. Broadcast should play once; weather accents should remain sparse. Scrub to a different point: no burst of queued sounds.
5. Turn Sound off during travel or weather. It should stop immediately; reload should retain Off. Save On and reload: no sound until the next real interaction.
6. Hide the tab, return, and unmount/remount the simulator. No orphaned loops or overlapping soundscapes should remain.

Browser policy reference: [MDN autoplay guide](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Autoplay). Offline waveform validation uses [OfflineAudioContext.startRendering](https://developer.mozilla.org/en-US/docs/Web/API/OfflineAudioContext/startRendering).
