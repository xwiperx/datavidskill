# QA checklist and known traps

## Inspect these stills before any full render

`3` (intro title), `8` (city rise), `14` (first item), `middle of the countdown`, `T_COUNT_END − 2` (last item), `T_COUNT_END + 5` (finale), `T_ENDCARD + 3` (end card).

Check that title, channel branding, HUD, lower thirds, value scale, portrait labels, finale text, and end-card text have visible spacing and do not collide or clip. Confirm column faces are opaque and saturated when `material: solid`; only accept translucent columns when `glass` was explicitly selected. Inspect transitions between representative stills for broken geometry, seams, or stray marks before approval.

## Traps that are invisible in code review

- **PIL ignores alpha in text fills.** `draw.text(..., fill=(r,g,b,0))` still paints opaque glyphs on an RGB image. `engine.text_alpha` / `draw_ls` composite through an RGBA layer instead; always use them for fading text, never raw `ImageDraw.text` with an alpha value.
- **Floating plate clipping.** `hud.draw_plate` must be tall enough for the name (`ph = 98·scale`). If the name sits at `y0+55` with a 33 px font, a shorter plate cuts the letter bottoms.
- **Plate vs lower-third collision.** Near the end of the countdown tall towers push the plate down into the card. `draw_plate` returns early when the plate would overlap `x < 930, y > 706`; keep that guard.
- **Numerals on distant towers.** `draw_one_bar` only draws the rank numeral when `vz < 52` and the projected face is at least 44×26 px. Without this, far towers overlap into unreadable glyph soup.
- **Long names.** Plate auto-shrinks to 470 px; the card shrinks to 700 px. Anything longer is truncated visually — shorten the name in the data instead.
- **Scale unit label.** The unit (`$B`, `m`) is drawn above the right end of the scale, not next to the last tick, or it collides with the final tick label.
- **End card fade.** `render_end` fades out over the last 1.6 s; without it the video cuts hard to black.

## New portrait and countdown checks

- Confirm the enlarged portrait card has identical screen-space bounds for every item and does not collide with the top-right rank, lower-third, scale, or floating nameplate. Suppress the nameplate when it intersects the reserved portrait rectangle.
- On-column portraits must remain entirely within the flat front-face safe area, inset from chamfers, seams, and rank numerals. Omit the small portrait on bars that are too short; never stretch it outside the face.
- Rank numerals should occupy roughly half the visible front-face height in their own lower zone. Check short early bars and the #100 tower.
- Review ten-rank transition cues at #10, #20, …, #90, then inspect each independent reveal/hold from #91 through #100.
- Use opaque/near-opaque info cards so distant rank numerals cannot ghost through the lower third and appear to overlap copy.

## Frame-level checks

- `ffprobe` frame count equals `round(30 × duration)`.
- First frame near black, last frame black.
- No duplicated or missing chunk at 10 s boundaries (chunks are 300 frames): compare frames at `t−0.03` and `t+0.03` around 10 s, 20 s, 30 s.
- Audio: `ebur128` integrated ≈ −14 LUFS, true peak ≤ −1.5 dBTP, no clicks (`max |diff|` of the waveform < 0.05).

## Performance

- 1080p30, 6 workers, ~0.31 s/frame/worker → 5400 frames ≈ 5 min; a 1500-frame short ≈ 1.5 min.
- Segments are cached: re-running skips existing `out/seg/seg_*.mp4`. Delete a segment to re-render only that range.
- CRF 18 with film grain lands around 16 Mbps (≈370 MB for 3 min). Raise `crf` to 21–22 for a ~50% smaller file with little visible loss.
