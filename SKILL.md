---
name: datavid
description: Guide users from diverse topic discovery through a 10-idea shortlist into ranked data documentaries with procedural 3D towers, image-aware animation, and explicit prevention/QA gates. Use when a user wants a ranked documentary, topic ideas, or production from a selected subject.
---

# datavid — ranked 3D tower documentaries

Render a 3:00 1080p30 master by default. Before each full render, always ask which delivery resolution(s) the user wants; offer 144p, 240p, 360p, 480p, 720p, and 1080p, allowing one or multiple choices. Do not assume they want all sizes or silently select a quality. Render the master once at 1080p, then encode the requested deliverables from it. Each ranked entity receives a 3D column with topic-appropriate geometry: a softly chamfered cuboid by default for ranked-person videos, or a selectable cylinder/other shape when the topic or user calls for it. Keep user-selected width; soften corners rather than making them sharp. Default to vivid, opaque solid columns; use glass only when explicitly requested. For countdowns, arrange several columns side-by-side across the frame and track laterally with a straight-on, front-facing camera. Every ranked item must receive its own visible name, value, and rank for its full active interval. Keep each locally cached exact-subject image inside the flat face with a clear inset from chamfers, outlines, cap seams, and text; adaptively shrink it to the safe face area instead of dropping it because a tower is short. If a verified image still cannot fit, fail QA and fix the layout. Make the rank numeral large (roughly half the visible face height) in a separate lower zone. When a verified image exists, also show it in a larger, fixed-size square/circular portrait card in reserved negative space; keep identical dimensions and framing for every subject, and show an empty labeled frame rather than an unrelated image when no verified asset exists. Never claim complete image coverage when verified assets are missing. Render graphics and audio in code; use downloaded entity images only when they add subject identity. Never depend on remote assets at render time.

## Inputs and ranking

After the user selects a final-episode idea, research one reliable, dated ranking (Forbes, CTBUH, CompaniesMarketCap, official country or industry lists, etc.). Record the source and snapshot date. Do not invent values or images. Sort project data ascending by ranked value so the first entry is #1 (smallest) and the last is #N (largest). For ties, keep source order or apply a documented stable tie-break.

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

## Guided topic discovery and selection

For a fresh request without a final topic selection, use two explicit choice gates before researching or creating the project:

1. **Offer diverse starting topics.** Present 8 concise, numbered, compelling topic seeds across at least six distinct domains (for example: wealth/business, countries/cities, science/space, wildlife/nature, sports, technology, history/culture, and transport/engineering). Make each seed suitable for an evidence-based ranking and describe its angle in one short phrase. Ask the user to choose one by number/name or supply another domain/topic. Do not start project research, image searches, asset downloads, project setup, storyboard rendering, or video generation yet.
2. **Offer exactly 10 final-episode ideas.** After the user picks a seed/domain, present exactly ten distinct, numbered ideas within that choice. Each idea must have a strong concise title and one short explanation, including the ranked entities/metric where useful. Prefer measurable, sourceable rankings; do not invent current values, claim that a ranking is verified, or begin researching the list at this ideation stage. Ask the user to select one idea or request a refinement, then wait.
3. **Enter production only after selection.** Treat the selected idea as the project topic, briefly confirm it, then begin the normal workflow below: research a dated source, validate the metric/data feasibility, create the project, plan visuals, and build the storyboard. If the chosen idea cannot be supported by a credible comparable dataset, explain that and offer a nearby measurable alternative before project creation. Keep the existing explicit storyboard approval, requested-resolution, and QA gates; topic selection is not approval to render.

Use the language of the user for both menus and explanations. If the user already provides a broad seed/topic, use it as the Stage 1 selection and offer its ten final-episode angles; do not discard their input. Skip the menus only when the user explicitly asks to use an exact final topic without brainstorming or selects an idea already offered in the current conversation. Never silently choose on the user's behalf.

## Workflow

1. After the user selects a final idea, research a dated ranked dataset and save its source URL, units, and snapshot date in the project. For large lists, use the source's JSON API; see `references/data-sourcing.md`.
2. Create the project with `python3 scripts/new_project.py /path/to/project`, then fill `data.json` and `config.json`.
3. Choose visuals deliberately. Set project-level `visual_mode` to `person`, `country`/`flag`, `vehicle`, `building`, `company`, or `auto`; an item-level `visual_type` overrides it. For a known homogeneous topic, set the explicit project mode rather than relying on `auto`. For mixed lists, tag each row. People require a portrait of that exact person; countries require their flag; vehicles/buildings/products require the named subject; companies use a representative subject image, not an unrelated person. Set `image_query` and `country` when needed to disambiguate.
4. Run `python3 scripts/datavid/fetch_images.py --project /path/to/project`. It checks Wikipedia page images and Wikimedia Commons, accepts public-domain, CC0, CC BY, or CC BY-SA images, downloads them locally, and writes `image_sources.json` with artist, license, and source page. Review a contact sheet and inspect doubtful matches; never substitute a similarly named person, generic image, or other unrelated result. If no exact, usable image is found, leave the panel blank and document the gap. The renderer has no network dependency. Respect each license and preserve the attribution manifest when redistributing a project. See `references/image-sourcing.md` for resolver behavior and visual-type guidance.
5. Render stills around the intro, first item, middle, final item, finale, and end card: `python3 scripts/render.py --project /path --stills 2 6 10 14 90 150 168 176` (adjust to duration). Also sample exact rank boundaries, growth, reading-hold, last pre-boundary frame, and first post-boundary frame for early, middle, and final items. Inspect every title lockup, lower third, scale, portrait, plate, finale, and end card for clipped glyphs, text-to-text collisions, unwanted transparency, and graphic artifacts; correct and regenerate the affected stills.
6. Use ten-rank chapters for the main countdown: retain an individual readable reveal for each item, add a stronger grouped growth/transition cue at ranks 10, 20, …, 90, then give each of the final ten ranks its own distinct growth beat and reading hold. Generate 100 reading holds and motion/boundary contact sheets with `python3 scripts/datavid/regenerate_storyboard.py --project /path/to/project`. Make the cadence explicit in `storyboard.md`; include representative growth frames and before/at/after boundary triplets. Share the current storyboard and wait for explicit user approval before any full-length MP4 render. Do not treat approval of an older preview as approval for a changed storyboard.
7. Before starting the full render, ask which output resolutions are wanted: 144p (256×144), 240p (426×240), 360p (640×360), 480p (854×480), 720p (1280×720), and 1080p (1920×1080). Permit multiple selections. If the current request explicitly names the desired sizes, treat that as the answer; otherwise wait for the user's choice.
8. Render one 1080p30 master, then create a separate MP4 for each selected resolution using `scripts/datavid/export_qualities.sh <master.mp4> <output-dir> <resolution...>`. When available, set `DATAVID_AUDIO_SOURCE` to the validated normalized PCM WAV so AAC is encoded once from PCM, not transcoded from the master's AAC. Keep the source aspect ratio (letterbox/pad rather than crop when necessary), frame rate, duration, and audio. Use names `<master-stem>_<resolution>.mp4`; the exporter uses `_v2`, `_v3`, … on collisions, validates dimensions/fps, fully decodes to a null sink, and atomically publishes without clobbering prior files. Preserve the master even when 1080p is selected.
9. Read `references/production-gates.md` before a substantial render and release. Verify each output's dimensions, duration, frame rate, frame count, codecs, audio stream, and full decode. Add only QA-passed requested MP4s to Git LFS and push them with the project when authorized. Deliver links to each requested quality and the source project.

## Non-negotiable quality contract

- Do not promise “zero bugs,” “error-free,” or certainty. No finite checklist proves that every possible visual, factual, compatibility, or perceptual defect is absent. Report the checks actually run, evidence, and remaining limitations.
- Fail closed: treat unknown data, identity, licensing, layout, timing, cache state, audio, or export properties as unresolved. Do not start the full render or call an output final while a blocker remains.
- Use the production gates and severity levels in `references/production-gates.md`. A known blocker stops release; exceptions must be specific, documented, and explicitly accepted where permissible. Never waive factual, rights, corruption, or wrong-output failures.
- Bind storyboard approval to an input fingerprint covering current code, data, images, fonts, configuration, timing, and format. Any material change invalidates approval and dependent QA; regenerate the preview and obtain approval again.
- Use a production-path smoke test before the full render, then full technical decode and final AAC loudness/true-peak measurement. Do not infer success from file existence, size, or a successful encode command alone.
- Keep intermediates out of the release. Write to unique temporary paths, validate before atomic no-clobber publication, preserve previous approved files, and stage only the manifest-verified final deliverables.
- Before promising a visual format, check whether the renderer implements it. The currently established format is the ranked 3D tower/countdown; other formats are design directions until implemented and tested.

## Automated QA tools

- Run `python3 scripts/datavid/qa_visual.py --video <candidate.mp4> --every-seconds 5 --report <qa-dir>/ocr.json` to OCR sampled frames and report intersecting OCR word-box candidates. `--min-words` applies to every selected sample: sample only time ranges expected to contain text, or leave it at zero for a sparse intro. Use repeatable `--expect` checks only when the copy is expected in the selected samples, and `--layout-json` for declared named rectangles. OCR intersections are review warnings by default because Tesseract can return oversized boxes; enable `--strict-ocr-overlap` only after calibrating the detector. Visually inspect flagged frames and do not use OCR to prove factual or image identity.
- Run `python3 scripts/datavid/qa_media.py <candidate.mp4> --report <qa-dir>/media.json` to decode reduced luma for black frames, strict long freezes, low-motion candidates, exact duplicate frames, timestamp cadence and abrupt changes. Long near-identical freezes, unexpected black runs, cadence defects and rate mismatch fail; low-motion and jump candidates remain review items unless promoted with `--fail-on-freeze-candidate` or `--fail-on-jump`. Add repeatable `--allow-black-range START:END` only for an exact storyboard-approved fade interval; the JSON still lists the exempt run. Never disable black/freeze detection globally to accommodate a designed fade or hold.
- Run `python3 scripts/datavid/qa_compare.py <old.mp4> <new.mp4> --report <qa-dir>/comparison.json --sheet <qa-dir>/comparison.jpg` to sample aligned normalized times and record MAE, local-window SSIM, changed-pixel fraction, and side-by-side/blend/difference sheets. Use thresholds only when the comparison is expected to be identical or when a reviewed tolerance is defined.
- Run `python3 scripts/datavid/ci_smoke.py --output <tmp>/smoke.mp4 --report-dir <tmp>/qa` before release when available. It renders a short isolated fixture through the renderer, muxes a test audio stream, and exercises media, OCR/layout, and self-comparison checks.
- The GitHub Actions workflow `.github/workflows/qa.yml` runs project validation, regression/syntax tests, and this smoke path on pushes to `main`, pull requests, and manual dispatch. Review its uploaded artifacts; a green CI result is evidence for that fixture and toolchain only, not a guarantee for every project, frame, input, or playback device.

## Format registry and honest capability claims

Offer the established tower countdown as the implemented default. Other useful formats to propose or develop as separate tested presets include: horizontal bar-race timeline; map/choropleth with ranked callouts; historical or forecast timeline; slopegraph/rank-change race; small-multiple comparison grid; podium/medal reveal; treemap or bubble-field overview; and editorial profile cards with data-driven transitions. Select a format for the data type and audience, not just visual novelty. Do not imply these alternatives are already supported by the current renderer; prototype, validate, document their controls, and show a storyboard before presenting one as available.

## Exact active-rank timing and graphics QA

- Use `start(i) = T_INTRO + (i−1) × PER_BAR` and `end(i) = start(i) + PER_BAR` as the single timing source. At the exact start, activate the column rise, top HUD, name/value/rank, on-column image, and large portrait together; clear every previous-rank identity at the next boundary. Inspect `t−1 frame`, boundary, and `t+1 frame` for early, middle, late, and final-ten ranks.
- Reject missing, empty, duplicate-name, non-finite, or misordered data with explicit diagnostics before rendering. Verify the dated ranking source, units, individual values and stated total; a structural check alone does not prove factual accuracy.
- Generate a labeled contact sheet for every local image. Check the depicted person/entity and license against its source page; a resolver hit or filename is not identity proof. If identity is uncertain or the image is a poor/group substitute, fail closed by removing its manifest path and leaving the fixed empty card. Report exact eligible coverage and missing/excluded ranks.
- Keep the name plate and lower-third in deterministic non-overlapping lanes. Shrink long names, then ellipsize; never let text escape its reserved box. Keep the progress rail in a separate bottom gutter. Set the scale maximum to at least the maximum value (round upward, e.g. to the next hundred), so the marker does not saturate early.
- Map images and text onto projectively projected faces using a homography, not an affine approximation; include a non-rectangular-quad regression test. Derive the end-card fade from `DUR`, not a hard-coded timestamp.
- Run `python3 scripts/datavid/validate_project.py /path/to/project`, `python3 -m unittest discover -s tests -v`, and `python3 -m py_compile scripts/datavid/*.py` before approval; fix errors and rerun.
- Regenerate and inspect all 100 current reading holds, image-present and image-missing examples, growth samples, chapter gates, final ten, and scene transitions before requesting approval. A previously approved storyboard or quality selection never applies to changed timing, layout, data, or output.
- Fingerprint renderer code, configuration, ranking, image manifest, local image bytes, fonts, frame rate, frame count, and chunk size. Validate every cached segment with exact dimensions/fps/frame count and a full decode; render to a temporary file and atomically publish only after validation. Publish the fingerprint only after successful segment assembly, use a per-project lock, and reject partial WAVs by channels/rate/frame count.
- Normalize and recheck the final encoded audio at about −14 LUFS and ≤−1.5 dBTP (use −3.2 dBTP before AAC as codec headroom, then measure the final AAC rather than assuming the target carried through). Inspect joins and transients for clipping/clicks; normal musical transients alone are not clicks. Validate all MP4s by full decode and preserve prior deliverables using unique names and no-clobber atomic publication.
- Still/contact-sheet QA is allowed before approval. Never start the full MP4 render until the user explicitly approves the current storyboard. Before that render, ask for one or more output sizes from 144p, 240p, 360p, 480p, 720p and 1080p unless the current request already specifies them.

## Delivery resolutions

| Label | Frame size |
|---|---:|
| 144p | 256×144 |
| 240p | 426×240 |
| 360p | 640×360 |
| 480p | 854×480 |
| 720p | 1280×720 |
| 1080p | 1920×1080 |

Always ask the user to choose one or more labels from this exact menu before the full render; do not infer a default selection from the master resolution. Encode each requested size as a distinct H.264/AAC MP4, retain 30 fps for a 30 fps master, and use a quality-based encode (CRF 23, yuv420p, AAC 128 kb/s) unless the user specifies a different delivery constraint. Put files in the project's `output/` directory, use Git LFS, and preserve prior versions. If the user explicitly requests every listed resolution, create all six without asking again.

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
- `scripts/datavid/`: 3D engine, scene, HUD, audio, build pipeline, licensed image resolver, and `export_qualities.sh` for requested MP4 sizes.
- `templates/`: starting `config.json` and `data.json`.
- `references/`: data sourcing and QA guidance.

Read `references/qa-and-pitfalls.md` before a first render. A 100-item default film is 5400 frames at 30 fps. Large MP4 files belong in Git LFS or release assets, not ordinary Git blobs.
