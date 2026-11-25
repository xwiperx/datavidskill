# richest-2026

Data: Forbes World's Billionaires 2026 API snapshot (stock prices as of March 1, 2026).
Raw response saved as `source/forbes2026.json`:

```
https://www.forbes.com/forbesapi/person/billionaires/2026/position/true.json?limit=200
```

`source/prep_data.py` cleans names, fixes a few company labels and writes `data.json` in the
engine schema (`items[].name/value/category/meta`, ascending by value, plus `total`).

Stats: 100 people, $7,123.7B combined, min $25.6B (Dilip Shanghvi), max $839B (Elon Musk),
Musk is 3.3× the second richest.

Render: `python3 scripts/render.py --project projects/richest-2026 --workers 6`
(5400 frames, ~5 min on 6 cores, CRF 18 ≈ 370 MB).
