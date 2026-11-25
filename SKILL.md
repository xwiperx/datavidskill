---
name: datavid
description: Produce ranked data documentaries as procedural 3D tower videos. Use for countdowns about people, countries, buildings, companies, vehicles, products, or other measurable entities, including when the user gives only a topic. The skill researches a dated dataset, finds suitable license-aware entity images, animates towers growing in rank order, and renders one MP4.
---

# datavid — ranked 3D tower documentaries

Render a 3:00 1080p30 film by default. Each ranked entity receives a 3D column with topic-appropriate geometry: a softly chamfered cuboid by default for ranked-person videos, or a selectable cylinder/other shape when the topic or user calls for it. Keep user-selected width; soften corners rather than making them sharp. For countdowns, arrange several columns side-by-side across the frame and track laterally with a straight-on, front-facing camera. Show its name, value, rank, and a same-sized square or circular locally cached image/symbol near the top of the front face in a consistent relative position; leave unavailable/uncertain portraits blank. Render graphics and audio in code; use downloaded entity images only when they add subject identity. Never depend on remote assets at render time.

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
5. Render stills around the intro, first item, middle, final item, finale, and end card: `python3 scripts/render.py --project /path --stills 2 6 10 14 90 150 168 176` (adjust to duration). Inspect them and refine config before rendering.
6. Before the full video render, prepare `storyboard.md` with a reading-hold frame for each scene (including every ranked reveal) and share it for plan review. Then render with `python3 scripts/render.py --project /path --workers 6` only after approval.
7. Verify duration, resolution, frame rate, codecs, audio, stills, image attribution manifest, and playback. Deliver the single MP4 and source project.

## Project appearance controls

| Config key | Default | Effect |
|---|---|---|
| `colors` / `color_positions` | blue–cyan–mint–violet–gold | Choose any RGB ramp; positions map colors across log value. |
| `material` | `glass` | `glass`, `metal`, or `solid`; affects transparency, lighting, and highlights. |
| `bevel_radius` | `0.46` | Soft-edge width in scene units; smaller values are sharper. |
| `camera_front` | `true` | Keep the camera head-on to the front face; false introduces a side offset. |
| `camera_distance` / `camera_target_y` / `camera_fov` | 46 / 9 / 38 | Control framing and lens. Fixed vertical framing keeps portrait panels on early towers and leaves room for the tallest tower. |
| `gamma` | `1.12` | Value curve; larger values widen differences near the top of heavy-tailed lists. |
| `height_rank_mix` | `0.42` | Blends value scaling with rank progression so near-ties still grow visibly. Use 0 for value-only scaling. |
| `height_min` / `height_range` | 2.8 / 19 | Base tower height and added height range. |
| `growth_fraction` | `0.46` | Fraction of each reveal used for the smooth rise. The remainder holds the completed tower for reading. |
| `visual_mode` / `image_directory` | `auto` / `assets/entities` | Select image handling and local asset folder. |
| `seconds_per_item` / `duration` | 1.46 / auto | Exact duration overrides per-item timing. Default 100-item film is 180 seconds. |

Heights use `h = height_min + height_range × ((1 − rank_mix) × (value/max)^gamma + rank_mix × rank_fraction)`. The rank component intentionally helps distinguish near-tied values; exact values remain printed on screen. Set `height_rank_mix` to `0` when strict value-only height is required. The active column animates from the floor to its target height over `growth_fraction`, then holds until the next rank; future towers remain hidden until their turn.

## Runtime and files

- Python 3.10+, Pillow, NumPy, and FFmpeg with libx264.
- `scripts/render.py`: still and full-video renderer.
- `scripts/datavid/`: 3D engine, scene, HUD, audio, build pipeline, and licensed image resolver.
- `templates/`: starting `config.json` and `data.json`.
- `references/`: data sourcing and QA guidance.

Read `references/qa-and-pitfalls.md` before a first render. A 100-item default film is 5400 frames at 30 fps. Large MP4 files belong in Git LFS or release assets, not ordinary Git blobs.
