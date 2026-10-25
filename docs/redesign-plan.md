# Simulator redesign

Visual thesis: a detailed, sunlit 3D city inside a quiet civic planning workspace, with cool neutral surfaces, dark ink text and one muted blue action color.

Content plan: compact brand and Advanced menu; one disaster/warning composer; a dominant interactive city with replay controls; a narrow outcomes inspector. Comparison stays in the same workspace. Assumptions, real Mini results, saved runs and artifact tools live in an accessible Advanced drawer.

Interaction thesis: smooth interpolation between recorded resident positions, disaster effects tied to actual hazard state, and an interruptible drawer/camera transition. Pause and reduced-motion settings stop ambient effects. Camera controls work with buttons and keyboard as well as pointer gestures.

Palette: shell #f5f7f8, surface #ffffff, ink #20313a, secondary #697b84, border #dce3e7, action #285c77. City materials supply the natural colors: stone, brick, slate, river blue and vegetation.

Type: retain the local sans-serif family, with a small, consistent scale. Data use tabular figures. Remove ornamental labels, numbered panels, research badges, ready states, CLI instructions and footer copy.

The current demo was verified before redesign: real Mini inference for both warnings; 121 frames each; 188 versus 235 sheltered; matching starting conditions; real numerical neural comparison. Final acceptance repeats the full path and exercises all three disasters, history, edited warnings, cache invalidation, mobile layout, keyboard access, camera interaction and playback.

Applied skills: local frontend-skill and Playwright; [Anthropic frontend design](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md), [Vercel web design guidelines](https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/SKILL.md), and the [Three.js graphics skill](https://github.com/majidmanzarpour/threejs-game-skills/blob/main/skills/threejs-aaa-graphics-builder/SKILL.md). The scene uses authored procedural geometry; no paid assets or cloud rendering.
