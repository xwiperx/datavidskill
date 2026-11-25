---
name: datavid
description: Produce ranked data documentaries as procedural 3D tower videos. Use for countdowns about people, countries, buildings, companies, vehicles, products, or other measurable entities, including when the user gives only a topic. The skill researches a dated dataset, finds suitable license-aware entity images, animates towers growing in rank order, and renders one MP4.
---

# datavid — ranked 3D tower documentaries

Render a 3:00 1080p30 film by default. Each ranked entity receives a 3D column with topic-appropriate geometry: a softly chamfered cuboid by default for ranked-person videos, or a selectable cylinder/other shape when the topic or user calls for it. Keep user-selected width; soften corners rather than making them sharp. Default to vivid, opaque solid columns; use glass only when explicitly requested. For countdowns, arrange several columns side-by-side across the frame and track laterally with a straight-on, front-facing camera. Show its name, value, and rank on the front face. Keep any locally cached subject image fully inside the flat face with a clear inset from chamfers, outlines, cap seams, and text; omit it when the bar is too short rather than clipping it. Make the rank numeral large (roughly half the visible face height) in a separate lower zone. When a verified image exists, also show it in a larger, fixed-size square/circular portrait card in reserved negative space; keep identical dimensions and framing for every subject, and show an empty labeled frame rather than an unrelated image when no verified asset exists. Render graphics and audio in code; use downloaded entity images only when they add subject identity. Never depend on remote assets at render time.

## Inputs and ranking

A topic is enough to begin. Research one reliable, dated ranking (Forbes, CTBUH, CompaniesMarketCap, official country or industry lists, etc.). Record the source and snapshot date. Do not invent values or images. Sort project data ascending by ranked value so the first entry is #1 (smallest) and the last is #N (largest). For ties, keep source order or apply a documented stable tie-break.

Each `data.json` item may contain:

| Field | Meaning |
|---|---|
| `name` | Display name. |
| `value` | Numeric ranked value, in one consistent unit. |
| `category` | Industry or type label. |
| `meta` | Short context line, such as company · country. |
| `visual_type` | Optional override: `person`, `flag`, `vehicle`, `building`, `company`, or `entity`. |
| `image_query` | Optional precise search phrase to disambiguate the picture. |
| `country` | Optional country name, used for flag visuals. |

## Workflow

1. Research a dated ranked dataset and save its source URL, units, and snapshot date in the project. For large lists, use the source's JSON API; see `references/data-sourcing.md`.
2. Create the project with `python3 scripts/new_project.py /path/to/project`, then fill `data.json` and `config.json`.
3. Choose visuals deliberately. Set project-level `visual_mode` to `person`, `country`/`flag`, `vehicle`, `building`, `company`, or `auto`; an item-level `visual_type` overrides it. For a known homogeneous topic, set the explicit project mode rather than relying on `auto`. For mixed lists, tag each row. People require a portrait of that exact person; countries require their flag; vehicles/buildings/products require the named subject; companies use a representative subject image, not an unrelated person. Set `image_query` and `country` when needed to disambiguate.
4. Run `python3 scripts/datavid/fetch_images.py --project /path/to/project`. It checks Wikipedia page images and Wikimedia Commons, accepts public-domain, CC0, CC BY, or CC BY-SA images, downloads them locally, and writes `image_sources.json` with artist, license, and source page. Review a contact sheet and inspect doubtful matches; never substitute a similarly named person, generic image, or other unrelated result. If no exact, usable image is found, leave the panel blank and document the gap. The renderer has no network dependency. Respect each license and preserve the attribution manifest when redistributing a project. See `references/image-sourcing.md` for resolver behavior and visual-type guidance.
5. Render stills around the intro, first item, middle, final item, finale, and end card: `python3 scripts/render.py --project /path --stills 2 6 10 14 90 150 168 176` (adjust to duration). Also sample growth, reading-hold, and rank-transition phases for early, middle, and final items. Inspect every title lockup, lower third, scale, portrait, plate, finale, and end card for clipped glyphs, text-to-text collisions, unwanted transparency, and graphic artifacts; correct and regenerate the affected stills.
6. Use ten-rank chapters for the main countdown: retain an individual readable reveal for each item, add a stronger grouped growth/transition cue at ranks 10, 20, …, 90, then give each of the final ten ranks its own distinct growth beat and reading hold. Make this cadence explicit in `storyboard.md`. Before the full video render, prepare the storyboard with a reading-hold frame for each ranked reveal and a compact motion contact sheet showing growth, holds, chapter gates, the final ten, and transitions. Share it for review and wait for explicit user approval before any full-length MP4 render. Do not treat approval of an older preview as approval for a changed storyboard.
7. Verify duration, resolution, frame rate, codecs, audio, stills, image attribution manifest, and playback. Deliver the single MP4 and source project.

## Project appearance controls

| Config key | Default | Effect |
|---|---|---|
| `colors` / `color_positions` | blue–cyan–mint–violet–gold | Choose any RGB ramp; positions map colors across log value. |
| `material` | `solid` | `solid` is vivid and opaque; `metal` adds reflective shading; `glass` is translucent and only used when requested. |
| `bevel_radius` | `0.46` | Soft-edge width in scene units; smaller values are sharper. |
| `camera_front` | `true` | Keep the camera head-on to the front face; false introduces a side offset. |
| `camera_distance` / `camera_target_y` / `camera_fov` | 46 / 9 / 38 | Control framing and lens. Fixed vertical framing keeps portrait panels on early towers and leaves room for the tallest tower. |
| `gamma` | `1.12` | Value curve; larger values widen differences near the top of heavy-tailed lists. |
| `height_rank_mix` | `0.42` | Blends value scaling with rank progression so near-ties still grow visibly. Use 0 for value-only scaling. |
| `height_min` / `height_range` | 2.8 / 19 | Base tower height and added height range. |
| `growth_fraction` | `0.46` | Fraction of each reveal used for the smooth rise. The remainder holds the completed tower for reading. |
| `growth_group_size` / `final_individual_count` | 10 / 10 | Main countdown chapter size and number of closing ranks that each receive an emphasized individual growth beat. |
| `bar_image_size` | 1.28 | Maximum side length in scene units for the inset square image on a column; shrink only to fit the safe flat face. |
| `feature_portrait_box` | `[1480,270,344,410]` | Fixed screen-space x, y, width, height of the enlarged portrait card; reserve this negative-space area in layout. |
| `visual_mode` / `image_directory` | `auto` / `assets/entities` | Select image handling and local asset folder. |
| `seconds_per_item` / `duration` | 1.46 / auto | Exact duration overrides per-item timing. Default 100-item film is 180 seconds. |

Heights use `h = height_min + height_range × ((1 − rank_mix) × (value/max)^gamma + rank_mix × rank_fraction)`. The rank component intentionally helps distinguish near-ties; exact values remain printed on screen. Set `height_rank_mix` to `0` when strict value-only height is required. The active column animates from the floor to its target height over `growth_fraction`, then holds until the next rank; future towers remain hidden until their turn.

## Motion language for the entire film

Do not concentrate motion only in the intro and outro. Give every ranked reveal a small, repeatable event: ease the active column up from the floor, run one brief color-matched light sweep across its visible front face, brighten its top rim, and pulse the existing progress marker as the rank arrives. Keep the sweep below the portrait and away from rank/value plates. Preserve the reading hold; settle all motion before the next item. Use short, clean inter-rank wipes or light ticks, with a slightly stronger but restrained chapter cue every 10 ranks through rank 90. Each of ranks 91–100 gets an independent rise and hold, not a combined final batch. Intro and ending may carry the larger cinematic moves; the countdown should still feel continuously alive through its per-item motion and chapter turns.

Apply one clear focal event at a time. Keep titles, names, values, ranks, portraits, and source lines unobscured; do not animate decorative copy over required information. Prefer edge-safe glints, short sweeps, and geometry-linked pulses over persistent particles, aggressive flashes, camera shake, or full-screen overlays. Motion colors should match the active item while columns remain vivid, opaque, and non-glass unless glass was explicitly requested. Keep the chosen front-facing camera and column spacing; do not let transitions change the established composition.

For motion review, render representative early, middle, and final countdown samples at both growth and hold, plus rank-to-rank transitions, the 10-rank gates, and each of the final ten independent reveals. Verify the large portrait card remains fixed and the on-column image/rank zones do not intersect. Make the motion visible in the storyboard contact sheet, not just described in prose. Review consecutive frames around each effect for clipping, image/plate collisions, flashes, z-fighting, stray marks, and text readability. A storyboard is a proposal: never start a full-length MP4 render until the user explicitly approves the current version.

## Runtime and files

- Python 3.10+, Pillow, NumPy, and FFmpeg with libx264.
- `scripts/render.py`: still and full-video renderer.
- `scripts/datavid/`: 3D engine, scene, HUD, audio, build pipeline, and licensed image resolver.
- `templates/`: starting `config.json` and `data.json`.
- `references/`: data sourcing and QA guidance.

Read `references/qa-and-pitfalls.md` before a first render. A 100-item default film is 5400 frames at 30 fps. Large MP4 files belong in Git LFS or release assets, not ordinary Git blobs.
