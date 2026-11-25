# Production gates: prevent, detect, contain

Use this reference before every substantial render and before publication. It defines a fail-closed process; it cannot prove that every possible defect is absent.

## Non-negotiable contract

- Never promise “bug-free,” “zero errors,” or certainty. Report only checks actually run, their results, and known limits.
- Treat unknown or unverified inputs as unresolved, not as a pass. Stop before full render or release when a blocker remains.
- Keep an evidence trail: record source snapshots, effective configuration, tool versions, test commands/results, render IDs, checksums, and accepted exceptions in the project manifest.
- Do not label a file “final” or publish it as a deliverable until all applicable gates pass. Keep failed/intermediate artifacts out of the release and Git LFS commit.
- After any code, data, timing, design, asset, or audio change, invalidate affected caches and rerun all dependent gates; prior storyboard approval and QA do not transfer to changed content.

## Severity and stop conditions

**Blocker (P0):** wrong or unsourced data; rank/order/timing mismatch; wrong or unlicensed subject image; unreadable or overlapping required content; missing/duplicated frames; corrupt/truncated output; wrong dimensions/duration/codec; audio clipping, failed sync, or failed full decode; output differs from the approved storyboard; overwrite or publication of the wrong file. Any P0 means stop, repair, and rerun affected gates before delivery.

**Major (P1):** visible transient, seam, stray glyph, unstable crop, illegible hold, unexpected blank, unsafe text margin, stale/cache mismatch, or loudness outside the configured target. Treat as a blocker unless the user explicitly accepts the exact documented issue before release. Do not silently waive it.

**Minor (P2):** cosmetic issue that does not obscure required content or change facts. Record it; fix when feasible. Do not describe a known issue as absent.

Never lower a severity just to meet a deadline. A user-approved creative choice is not permission to ignore factual, license, corruption, or safety failures.

## Gate A — contract, data, and provenance

1. Write a compact acceptance contract: topic, audience, duration, frame rate, resolution(s), aspect ratio, language, branding, style, source policy, audio policy, output path, and approval checkpoint. Distinguish hard requirements from creative preferences.
2. Save ranking/source URL, publisher, retrieval/snapshot date, unit, currency, estimate date, transformations, tie-break rule, and any known limitations. Label estimates and time-sensitive figures accurately.
3. Validate schema, required fields, types, finite numbers, allowed ranges, unique identifiers, stable ordering, row count, units, and totals. Compare each row with the dated source; structural validation alone is not factual verification.
4. Generate a machine-readable project fingerprint from renderer/scripts, dependencies, configuration, input data, fonts, audio, image manifest, and local asset bytes. Record random seeds and environment/tool versions when relevant.
5. Use exact local assets for the correct subject and preserve attribution/license/source records. A search hit, filename, permissive license, or model confidence is not identity proof. If identity, rights, or relevance is uncertain, leave the visual empty and document the gap.

## Gate B — layout, timing, and storyboard

1. Use one canonical integer-frame timeline. Derive seconds from frame numbers; define half-open active intervals `[start_frame, end_frame)` and use one boundary policy everywhere. Reject negative, overlapping, missing, or out-of-range intervals.
2. Build explicit layout boxes and safe margins for title, rank, name, value, portrait, attribution, captions, legend, progress indicator, and end card. Test worst-case strings, large/small values, absent images, and narrow aspect ratios.
3. Keep all required content on safe lanes. Detect bounding-box intersections; use OCR or text-metric checks where available, then visually review actual rasterized frames. Automated boxes are a screen, not proof of perception/readability.
4. Create a storyboard/contact sheet for every hold and representative growth/motion frames. Inspect every ranked hold for correctness/readability; inspect `frame−1`, boundary, and `frame+1` around each rank/scene transition, every chunk seam, all chapter gates, and intro/finale/end card. Review both image-present and intentionally empty states.
5. Show the current storyboard and wait for explicit approval before full-length rendering. Approval applies only to the exact fingerprinted design/data version. Ask for output resolution(s) unless explicitly supplied for that exact run.

## Gate C — preflight and render isolation

1. Run project/data validators, unit/regression tests, syntax checks, dependency checks, and lint/type checks when configured. Save actual logs. A validator pass is not a substitute for image/data review.
2. Run a representative low-resolution/short-duration smoke render with the production code path, including at least one ordinary item, a long label, an image-present case, an empty-image case, a boundary, an end card, and audio. Verify that the smoke path uses the same mapping, fonts, effects, and muxing decisions as production.
3. Render into a unique temporary directory under a per-project lock. Do not overwrite prior approved outputs. Use explicit subprocess argument arrays, checked return codes, bounded worker counts, and `-nostdin`; avoid shell interpolation of untrusted names/paths.
4. Cache only by a complete content fingerprint. Validate every cache hit for expected dimensions, frame rate, frame count, codec, timestamps, and complete decode. Reject stale, partial, or mismatched cache entries. Write cache signatures only after successful validation.
5. Assemble to a temporary filename, verify it, then publish with an atomic no-clobber operation. On interruption or failure, clean or quarantine temporary artifacts; never leave a partial file with a final name.

## Gate D — visual, timeline, and audio QA

1. Verify first/middle/last frames, all rank holds and boundary samples, all chunk seams, scene transitions, chapter cues, peak-motion points, and end-card fade. Use both contact sheets and direct full-size inspection; zoom details that cannot be read at sheet scale.
2. Check for clipping, text collisions, stale identity, rank/value mismatch, empty or duplicate frames, unexpected transparency, wrong color/material, image leakage outside its safe face, perspective seams, z-fighting, flashes, flicker, camera jumps, black frames, freeze, and content outside the title-safe area. Compare adjacent frames at transitions and chunk joins.
3. Check every local image against its source and attribution record; report verified, missing, and excluded coverage separately. Do not infer identity from automated labels or claim full coverage if any item was not checked.
4. Probe streams and decode the *entire* candidate. Validate width, height, pixel format, frame rate, exact/expected frame count, duration/tolerance, video and audio codecs, channel count, sample rate, timestamps, and nonzero plausible file size. Run a black/freeze scan. A near-identical long freeze is a blocker; low-motion candidates are review-only unless explicitly promoted with the strict flag. Manually inspect every flagged interval. Exempt black frames only by listing an exact, storyboard-approved fade interval; the JSON report must retain the exempt run as evidence.
5. Measure final encoded audio, not only the source WAV: integrated loudness, true peak, clipping, silence/tail, channel layout, and synchronization. Use the project target (normally about −14 LUFS and no higher than −1.5 dBTP when suitable). Re-encode from validated PCM when an AAC generation has already consumed the headroom; measure again. Listen at transitions and inspect detected discontinuities rather than mistaking normal musical transients for clicks.
6. When subtitles, narration, or on-screen numbers exist, verify their timing against the frame timeline and compare representative/all generated text against the canonical source. Keep source attribution/captions visible and legible.

### Executable checks in this repository

- OCR and detected text-word collisions: `python3 scripts/datavid/qa_visual.py --video <candidate.mp4> --every-seconds 5 --layout-json templates/qa_layout.json --report <qa-dir>/ocr.json`. For a still, use `--image <frame.png>`; add repeatable `--expect "required copy"` checks only for samples where that phrase is expected. `--min-words` applies to every selected sample, so do not require text on a deliberately sparse intro frame. OCR box intersections are review candidates by default because Tesseract can return oversized boxes; use `--strict-ocr-overlap` only after calibration. Declared layout collisions remain hard failures.
- Black frames, strict long freezes, low-motion candidates, irregular timestamps, exact duplicate frames, and jump candidates: `python3 scripts/datavid/qa_media.py <candidate.mp4> --report <qa-dir>/media.json`. Black/freeze/cadence issues gate success; low-motion and jump candidates are reported for human review. For a reviewed designed fade, add repeatable `--allow-black-range START:END` bounds (seconds); exemptions are reported, never silently discarded. Use `--fail-on-freeze-candidate` only when the design expects continuous visible motion.
- Sampled visual revision comparison: `python3 scripts/datavid/qa_compare.py <reference.mp4> <candidate.mp4> --report <qa-dir>/diff.json --sheet <qa-dir>/diff.jpg`. Set MAE/SSIM thresholds only for a known-unchanged target; real revisions are expected to differ.
- Isolated production-path CI smoke: `python3 scripts/datavid/ci_smoke.py --output <tmp>/smoke.mp4 --report-dir <tmp>/qa`. GitHub Actions runs this fixture and uploads its reports; fixture success does not prove full-project or every-frame correctness.

## Gate E — release and publication

1. Create/update the manifest only from measured output. Include the exact selected resolutions, technical probe, QA result, known exceptions, input fingerprint, final SHA-256, and byte size. Recompute the hash after any file change.
2. Only stage approved deliverables. Force-add ignored MP4s only after confirming the LFS filter applies. Confirm `git lfs ls-files` or the staged pointer before committing; never put large MP4 binaries into ordinary Git blobs.
3. Review `git diff --check`, staged path list, manifest, and repository status. Commit and push only when authorized. Verify the remote branch/commit and final clean status; do not claim success before confirmation.
4. Report filenames/links, exact QA performed, measured specs, tests, unresolved limitations, and commit ID. Say “passed the listed checks,” not “has no bugs.”

## Required task-specific test matrix

Adapt the matrix; do not skip a relevant state merely because the happy path passed:

| Dimension | Minimum cases |
|---|---|
| Data | minimum/maximum values, ties, long names, unusual Unicode, invalid/missing rows, ordering |
| Visuals | verified image, intentionally blank card, wrong/ambiguous image rejected, extreme crop/aspect ratio |
| Timeline | first, middle, last rank; every boundary class; chapter gate; first/last frame; chunk join |
| Export | each requested resolution; aspect pad; collisions/no-clobber; missing audio; independent PCM source |
| Failure recovery | truncated input, missing asset, invalid config, interrupted render, stale cache, failed FFmpeg return |
| Audio | quiet/loud passages, peaks, start/end, transition joins, final AAC measurement |

Record skipped cases and why. If a case is not applicable, mark N/A with a reason instead of silently omitting it.
