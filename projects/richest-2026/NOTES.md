# richest-2026

Data: Forbes World's Billionaires 2026 API snapshot (stock prices as of March 1, 2026).
Raw response saved as `source/forbes2026.json`:

```
https://www.forbes.com/forbesapi/person/billionaires/2026/position/true.json?limit=200
```

`source/build_data.py` plus the explicit, rank-keyed `source/data_overrides.json` reproducibly write
`data.json` in the engine schema (`items[].name/value/category/meta`, ascending by value, plus
`total`). Verify without overwriting with `python3 source/build_data.py --check`.

Portraits: `image_sources.json` records source, credit, and license details for 61
locally cached portraits. The remaining 39 subjects have no image in the cache because
no exact, allowed-license match was verified; do not substitute unrelated search results.
See `IMAGE_COVERAGE.md` for the list and the documented lookup routes.

Stats: 100 people, $7,123.7B combined, min $25.6B (Dilip Shanghvi), max $839B (Elon Musk),
Musk is 3.3× the second richest.

Render only after reviewing and explicitly approving the current storyboard, choosing delivery
resolution(s), and passing `references/production-gates.md`: `python3 scripts/render.py --project
projects/richest-2026 --workers 6` (5400 frames; runtime and size depend on the host/toolchain).

Visual direction: DATA ZED branding appears in the intro, persistent watermark and end card. Towers
are softly beveled opaque cuboids in a front-facing horizontal row; exact portraits are shown in a
same-sized square window at a fixed position where available. The empty portrait panels are
intentional when an exact locally cached subject image is unavailable.
