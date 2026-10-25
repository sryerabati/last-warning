# Fictional resident identity audit

## Findings

The former generator combined 24 given names with 16 family names, providing only 384 full-name combinations for a scene that permits up to 1,000 residents. There was no collision handling. The default 300-person cast contained only **207 distinct names**; 93 residents repeated an already-used full name. In the second family, both the caregiver and preschool child were named Noah Park.

The former appearance sampler assigned all eight hair colors equally. In the default cast this produced **29 dyed-plum appearances and 41 gray-haired appearances**, including one of the two preschool children. Family members were independently randomized without any visual continuity. Missing biographies made these disconnected name/appearance combinations feel like attribute lists rather than individual fictional characters.

Resident display names were also included in the Bedrock decision context. That field is unnecessary to choose a route or protective action and could let the language model use a name as an unintended cue. The context now uses a neutral `Resident N` identifier. Role, physical state, responsibilities, warnings and available actions remain operational inputs; visual design, naming style and biography are not.

## Changes

- A versioned fictional identity allocator uses authored naming-style pools and ensures unique complete display names across the scene. Families share a family-name choice while their given names remain distinct. Roommates retain separate identities. Cross-cultural/preferred given names remain possible; a person named Zoe Patel is not inherently inconsistent.
- Names are stored with their complete display form and explicit given/family components. This English-language presentation uses an authored given/family display order rather than trying to infer how a real person's name must be split or ordered.
- Natural hair dominates the art recipe. Gray is common in the older age group and occasional among adults; preschool children use natural shades. Dyed plum remains an occasional style choice. These visual frequencies are authored, not measured OSU statistics.
- A separate household design seed gives relatives a nearby range of skin-palette shades and usually a shared natural-hair base, with variation. It reads the household ID, never a name, naming style, presumed ethnicity or citizenship. Skin tone is not inferred from a surname.
- Each resident receives a short fictional role/interest biography. It provides useful character context without inventing a real person's identity, assigning a nationality, or claiming membership in an actual department.
- Appearance recipes, identity metadata and biographies are saved with profiles. Historical recordings are preserved. New days identify `osu-campus-life/2.2`, and new emergency simulations identify `last-warning-campus/2.2.0`; the geographic world remains `osu-campus-district/2.1`.

## Research and interpretation

[W3C's personal-name guidance](https://www.w3.org/International/questions/qa-personal-names) describes differing name orders, multiple family names and preferred additional names. It supports preserving full display names and avoiding a universal name-splitting assumption. The authored vocabulary here is deliberately a limited fictional cast resource, not a comprehensive representation of every naming tradition.

[SSA's data qualifications](https://www.ssa.gov/OACT/babynames/background.html) describe the U.S.-birth scope and normalization applied to its given-name statistics, including the removal of spaces and hyphens. Such a dataset is not evidence of an individual's ethnicity, appearance or international-campus naming preference. No SSA frequencies are presented as OSU population weights in this generator.

[Ohio State's Autumn 2025 enrollment report](https://sem.osu.edu/media/uz1gjp0k/enrollment-report.pdf) documents a geographically diverse university community, including students from 121 countries across all campuses and levels. It is historical institutional context, not a sample of people on the Oval at a particular time. The naming-style weights, skin palette, hairstyle frequencies, biographies and household designs remain explicitly authored. They are not fitted to enrollment citizenship/race categories.

## Verification and measured result

The default 300-person cast now has **300 unique names**, **eight dyed-hair recipes** and **19 gray-hair recipes**. Both preschool children use natural hair. The two existing families retain their original houses and roles, with distinct given names and visual continuity. These counts are observations of seed 42, not target demographics.

A before/after hash over all operational profile fields, excluding display name/identity/biography/art but retaining mobility, is unchanged: `cdca062f88589e5d3c337d8da462c494da0d2fb6fbd3a71ee3998e7d28359fb2`. Homes, workplaces, routines, social contacts, movement speeds, goals, trust and mobility sampling are unchanged by this identity pass. The new initial-condition hash intentionally differs because saved display profiles are part of provenance.

Regression checks cover unique deterministic allocation up to 1,000 residents across multiple seeds; valid mixed naming choices; independent appearance; family coherence; child/adult/older hair behavior; unchanged mobility sampling; and exclusion of identity/appearance/biography from the operational decision context. Evidence lives in `output/campus-identity-before.json`, `output/campus-identity-after.json`, and `output/campus-identity-operational-before.json`.

The focused identity, campus-life and campus-emergency suite passed **56 tests in 138.27 seconds**. Ruff also passes for the changed Python modules and tests. This verification did not invoke a paid model or change AWS credentials.
