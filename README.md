# datavidskill

A small engine that turns a ranked dataset into a **3D tower data film**: every item gets a column whose height grows with its value, the camera tracks the list from rank 1 up to rank N, the scene extends up and to the right, and each tower carries its name, value and rank. Every frame and the whole soundtrack are generated in code — no stock footage, no images, no audio samples.

The reference film in `projects/richest-2026` is a 3:00 documentary on the Forbes 2026 billionaires, from #1 (Dilip Shanghvi, $25.6B) to #100 (Elon Musk, $839B).

[Watch the reference film](https://github.com/xwiperx/datavidskill/releases) · 1920×1080 · 30 fps · H.264 + AAC · 3:00

![preview](docs/preview.jpg)

## Quick start

```bash
python3 scripts/new_project.py my-project          # config.json + data.json
# edit data.json (items: name, value, category, meta) and config.json (titles, units)
python3 scripts/render.py --project my-project --stills 3 8 18 40
python3 scripts/render.py --project my-project --workers 6
```

`--stills` writes PNGs to `my-project/stills/` so you can check typography before spending five minutes on a full render. The full run writes `my-project/out/<output_name>` and also synthesises `out/score.wav` if it is missing.

Requirements: Python 3.10+, Pillow, NumPy, ffmpeg with libx264. Fonts are bundled (Bebas Neue, Inter).

## How the film is built

| Section | Timing | What happens |
|---|---|---|
| Intro | 0–12 s | title card, camera descends onto a rising city of columns |
| Countdown | 12 s → `duration−22 s` | one item per `seconds_per_item`, camera tracks each tower, HUD + lower third + floating name plate |
| Finale | last 22 s − 12 s | camera pulls back on the #1 tower, right-hand title block with the value and two stats |
| End card | last 8.6 s | the whole list as a colour ribbon, the total, credits |

Height: `h = 3.1 + 27 · (value / max)^gamma` with `gamma = 0.72` by default, so a 33× outlier does not flatten the other 99 columns. Heights are strictly monotonic in value.

## Repository layout

```
SKILL.md                  the agent-facing skill (workflow, config reference, quality bar)
scripts/render.py         CLI: stills or full render
scripts/new_project.py    scaffold a project folder
scripts/datavid/          engine.py (3D + post), hud.py, scene.py (timeline), audio.py, build.py
scripts/datavid/fonts/    bundled typefaces
templates/                config.json and data.json templates
references/               data sourcing and QA/pitfall notes
projects/richest-2026/    the reference project (config, data, raw Forbes JSON)
docs/preview.jpg          still from the film
```

## The reference project

`projects/richest-2026/data.json` holds 100 people sorted ascending by net worth, with `category` (industry) and `meta` (company · country). `source/forbes2026.json` is the untouched Forbes API snapshot (March 2026) and `source/prep_data.py` documents how the fields were cleaned. Total: $7.12T.

```bash
python3 scripts/render.py --project projects/richest-2026 --stills 75
```
