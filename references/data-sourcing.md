# Sourcing a ranked dataset

Goal: one ordered list of N items, each with a number, a category and a short meta line, plus a source name and snapshot date.

## Fastest paths, in order

1. **The site's own JSON API.** Data-driven publishers expose one. Example that works: `https://www.forbes.com/forbesapi/person/billionaires/2026/position/true.json?limit=200` returns every billionaire with `personName`, `finalWorth` (USD millions), `industries`, `country`, `source`, `rank`. Check the network tab of a list page for `api`, `.json` or `graphql` in the URL before scraping HTML.
2. **Wikipedia tables.** `pandas.read_html(url)` on a "List of …" article usually yields a clean table; the first table is often the ranked one. Verify units and the "as of" date in the caption.
3. **Market/industry aggregators** (CompaniesMarketCap, CTBUH Skyscraper Center, Transfermarkt, Box Office Mojo). Their pages are static enough for `fetch`, or expose CSV export.
4. **Search + read** for short lists (N ≤ 25). Only when the above fail.

## Cleaning rules that matter for the render

- Sort ascending by value in the file; the engine also sorts, but keep the file readable.
- Normalise units to one number: USD billions for money (`839`, not `$839B`), metres for heights, millions for users.
- Name: keep it short enough to fit a 470 px plate at 33 px (`MAX 26–30 characters`). Move detail to `meta`.
- `meta` should be 2–3 tokens joined by ` · ` (company · country, city · country). The card clips after ~48 chars.
- `category` is one or two words, uppercase.
- Drop entries with missing values rather than guessing.
- Record `source_line` (short, on screen) and `source_note` (longer, end card) plus the snapshot date. Values change weekly; the date is part of the claim.

## Scale decisions

- `scale_max`: round the largest value up to a multiple of 200 (money) or 100 (metres) so the tick labels stay round.
- `gamma`: 0.7 for heavy-tailed money data, 0.85–1.0 for heights and other bounded metrics.
- If the top item is more than ~10× the second, mention the power scale in the delivery note; users notice the visual compression otherwise.
