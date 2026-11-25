# richest-2026

Data: Forbes World's Billionaires 2026 API snapshot (stock prices as of March 1, 2026).
Raw response saved as `source/forbes2026.json`:

```
https://www.forbes.com/forbesapi/person/billionaires/2026/position/true.json?limit=200
```

`source/build_data.py` cleans names, fixes a few company labels and writes `data.json` in the
engine schema (`items[].name/value/category/meta`, ascending by value, plus `total`).

Portraits: `image_sources.json` records exact source, credit, and license details for the 69
verified portraits cached locally. The remaining 31 subjects have no image in the cache because
no exact, allowed-license match was verified; do not substitute unrelated search results.
See `IMAGE_COVERAGE.md` for the list and the documented lookup routes.

Stats: 100 people, $7,123.7B combined, min $25.6B (Dilip Shanghvi), max $839B (Elon Musk),
Musk is 3.3× the second richest.

Render: `python3 scripts/render.py --project projects/richest-2026 --workers 6`
(5400 frames, ~5 min on 6 cores, CRF 18 ≈ 370 MB).

Visual direction: DATA ZED branding appears in the intro, persistent watermark and end card. Towers are smooth front-facing cylinders arranged in a horizontal row; exact portraits are shown in a same-sized square window at a fixed position where available.
