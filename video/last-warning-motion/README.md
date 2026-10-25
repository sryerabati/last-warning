# Last Warning motion assets

Five main full-frame inserts for the final hackathon script. A separate rendering project keeps the application dependencies untouched.

- 1920 × 1080, 30 fps, SDR BT.709
- H.264 MP4, yuv420p, no audio
- Local fonts; no remote assets during rendering
- All movement is driven by the Remotion frame number

## Render or edit

Use Node.js 22+. From this directory:

```sh
npm ci
npm run check
npm run stills
npm run render
npm run extras
npm run verify
```

`npm run studio` opens the editable compositions. Change the baked copy and values in `src/content.json`; scenes live in `src/Scenes.tsx`.

The default output folder is `renders/` in this project. Set `MOTION_OUTPUT` to choose another output folder. `npm run render -- --only Results` renders just one composition. Rendering may download Chrome Headless Shell on first use. The renderer uses software graphics for reliable headless output on this Mac.

`teamName` and `repositoryUrl` are empty because those credits were not supplied. The end card renders cleanly without placeholder text. Fill these fields and re-render `EndCard`, or add them as native CapCut text. Keep long repository links short enough to fit one line.

## Script alignment

| Main clip | Duration | Placement |
|---|---:|---|
| 01-title.mp4 | 6 s | 00:09–00:15, followed by the live app overview |
| 02-results-54-vs-193.mp4 | 17 s | 01:12–01:29 |
| 03-architecture-full.mp4 | 32 s | 01:42–02:14 |
| 04-gpu-pivot.mp4 | 17 s | 02:29–02:46, or trim around presenter footage |
| 05-end-card.mp4 | 3 s | 02:57–03:00 |

The architecture reveals the independent Mini branch at its local 14-second mark, matching the script at 01:56. Optional split versions can be exported for the 14-second core diagram and 18-second neural track; use those instead of the full clip, not in addition to it.

## CapCut

Create a 16:9 project, import the MP4 files and place them above or between your screen footage. They are opaque full-frame inserts, so no keying or transparency setup is required. Add voiceover below them. Do not change playback speed to match your voice; trim static holds or extend a supplied still frame instead.

The lower 150 pixels are kept clear for captions. Keep captions at roughly Y=980, with at most two 42 px lines, and inspect them over the final card. Do not cover the result caveat or model-boundary note above the caption area.

Use the final-state PNG stills to extend a hold. The source text is baked into the MP4; it remains editable in Remotion, not as individual CapCut text layers.

## Evidence boundaries

The result card uses the saved flood comparison: 54 generic / 193 actionable sheltered, +139, 300 residents. Both message and delivery settings changed. It is labeled as simulated.

The architecture has two branches from the warning. TRIBE v2 Mini predicts an average subject's cortical fMRI response independently of the Bedrock residents; no Mini-to-action arrow is drawn.

The pivot describes the failed full-size cloud GPU plan and the working local Mini / cloud Bedrock implementation. It does not claim successful full-size TRIBE CUDA execution.

The title map is a decorative vector motif, not a replay or an additional measured simulation.

Fonts: Inter and Pixelify Sans, distributed under their included SIL Open Font Licenses. Pixel icons reuse the app's original icon paths. Remotion and its dependencies retain their own licenses; see their package documentation for future use outside this project.
