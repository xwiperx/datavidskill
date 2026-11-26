# QA checklist and known pitfalls

Use this checklist before storyboard approval and again after every full render. A storyboard approval applies only to the exact current design/data snapshot and never authorizes an older or changed render.

## Data and portrait identity

- Validate non-empty `items`, finite non-negative values, unique display names, stable ascending rank order, and agreement between each row and the corresponding manifest `rank`/`name`.
- Confirm the source/date/unit of the ranking and recompute its stated total. Structural consistency does not establish that every estimate is factually correct; spot-check values against the dated source and flag unresolved discrepancies.
- Build and inspect a labeled contact sheet of every local image. A resolver/API match or a permissive license does not prove identity. Check doubtful source pages manually; if exact identity or license is uncertain, remove the local path and leave the fixed portrait card empty. Never replace a missing portrait with a logo, group scene, similarly named person, or generic image.
- Check every local path exists and its license/artist/credit/source URL remains in the manifest. Do not leave excluded assets available to the renderer.
- Treat every manifest image path and configured image directory as untrusted input: require a relative path, resolve symlinks, and reject any target outside the project root before reading or writing.
- Report actual eligible portrait coverage and list all missing/excluded ranks. Do not say “all images verified” unless each one was separately reviewed.

## Still and layout review

Inspect the intro, early/middle/late rank holds, a missing-image rank, the final ten, finale, and end card. Render all rank holds into labeled contact sheets before asking for approval. Also render exact rank-boundary triplets (`t−1 frame`, boundary frame, `t+1 frame`), growth, chapter gates, both scene transitions, and the last pre-endcard frames.

Check title/brand/logo, source note, name/value/rank, floating plate, large portrait card, on-column image, scale labels, progress rail, finale copy, and end-card text for clipping, overlap, stale-rank carry-over, flashes, seams, and off-frame pixels. On-column imagery must remain inside the flat face, inset from bevels, seams and rank glyphs. Adaptively shrink it to fit; do not silently omit a verified image due to low tower height. Keep vivid opaque columns unless glass is explicitly requested.

Keep the name plate and lower-third in separate deterministic lanes. Shrink names, then ellipsize if necessary; text must remain inside the plate/card. Never suppress required information because it collides—change the layout and regenerate. Keep the progress rail in a dedicated bottom gutter, outside the lower-third. A scale must cover at least the maximum data value; derive a rounded-up safe maximum when configuration is stale.

Map text and image textures to projected faces with a projective homography, not an affine approximation, and test all four corners on a non-rectangular projected quad.

## Timeline and motion

Use one timing source: `start(i) = T_INTRO + (i−1)×PER_BAR`, `end(i)=start(i)+PER_BAR`. At the boundary, activate the column rise, top HUD, name/value/rank, and enlarged portrait together. Clear all previous-rank identity at the next boundary. Check the final frame before, exact boundary, and first frame after every transition class, especially early, middle, and final ranks.

Each reveal receives a readable growth beat and hold. Add restrained chapter accents at 10-rank gates through #90; ranks #91–#100 each get their own independent growth beat. Keep motion off required copy and settle it before the next rank. Derive end-card fades from configured duration, never a fixed absolute timestamp.

Reject empty or malformed datasets with explicit validation messages before rendering; avoid implicit `min()`/`max()` failures.

## Cache, audio and delivery safety

- Fingerprint source code, data, config, image manifest, local source images, fonts, frame rate, frame count, and chunk size. Invalidate cache when any input changes.
- A cached segment is valid only after probing exact dimensions, fps, frame count, codec, and full decode. Render to a unique temporary file, validate it, then atomically publish. Do not treat a size threshold as proof of completion.
- Write the cache signature only after successful segments and validated concatenation. Use a per-project lock. Preserve previously delivered MP4s; choose a unique output name and never use `ffmpeg -y` against a published file. Validate a temporary final output before no-clobber publication.
- Generate WAV to a temporary file, verify channels/sample rate/duration/frame count, and atomically publish. Normalize the delivered mix with EBU R128 (`I≈−14 LUFS`, `TP≤−1.5 dBTP`; use −3.2 dBTP before AAC encoding as codec margin). Measure the final AAC rather than assuming the source target carried through. Inspect audio at all scene/chunk boundaries and check for clipping or isolated discontinuities; do not treat normal musical transients alone as digital clicks.
- When audio-only generation replaces `score_raw.wav`, invalidate the normalized `score.wav` at the same time; otherwise a format-valid but stale normalized cache can be muxed into the next film.
- Full render gate: regenerate the current storyboard, inspect all 100 holds and motion samples, show it to the user, and wait for explicit approval. Ask for one or more resolutions from 144p, 240p, 360p, 480p, 720p and 1080p. Previous approvals/selections do not carry over to a changed storyboard/output.
- After approval, render one 1080p30 master and only the selected delivery sizes. Probe each MP4 for dimensions, frame rate, frame count, duration, video/audio streams, and perform a complete decode. Measure loudness/true peak on the final AAC. Preserve prior versions and use Git LFS for large deliverables.

## Frame/media checks

- The master is 1920×1080, 30fps, with `round(30 × duration)` frames.
- Decode every complete output, not only sampled frames. Compare frames on both sides of every chunk boundary to detect missing/duplicated frames.
- Inspect first and last frames, all chunk boundaries, and a grid of samples spanning the full duration. Verify actual timeline duration, end-card fade and audio tail.
- When publishing, preserve `image_sources.json` and attribution/coverage notes alongside the project.
