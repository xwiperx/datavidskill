# Portrait coverage — richest-2026

The project contains 100 ranked people. The local image cache currently contains **69 exact-person portraits** that passed the resolver's source/identity checks and the accepted-license test (Public Domain, CC0, CC BY, or CC BY-SA). The remaining 31 panels are intentionally unpictured. No unrelated person, company logo, or generic image is used as a substitute.

The per-image manifest, including source page, license, author/credit, match method, and local file path, is `image_sources.json`. Review it together with the local portraits before redistribution; retain attribution and comply with the terms recorded for each asset.

## Subjects without a verified cached portrait

| Rank | Person |
|---:|---|
| 1 | Dilip Shanghvi |
| 4 | Rick Cohen |
| 6 | Cyrus Poonawalla |
| 7 | Vicky Safra |
| 12 | Emmanuel Besnier |
| 16 | Prajogo Pangestu |
| 24 | Lyndal Stephens Greth |
| 27 | Melinda French Gates |
| 33 | Michal Strnad |
| 34 | Robert Pera |
| 36 | He Xiangjian |
| 38 | Zheng Shuliang |
| 43 | Colin Huang |
| 46 | William Ding |
| 48 | Jean-Louis van der Velde |
| 50 | Savitri Jindal |
| 51 | Alain Wertheimer |
| 52 | Gerard Wertheimer |
| 55 | Andrea Pignataro |
| 57 | Rafaela Aponte-Diamant |
| 58 | Mark Mateschitz |
| 60 | Giovanni Ferrero |
| 61 | Lukas Walton |
| 66 | Iris Fontbona |
| 71 | Germán Larrea Mota Velasco |
| 72 | Dieter Schwarz |
| 73 | Jeff Yass |
| 74 | Zhong Shanshan |
| 78 | Thomas Peterffy |
| 79 | Giancarlo Devasini |
| 81 | Francoise Bettencourt Meyers |

## Lookup routes

The resolver checks Wikipedia page-image metadata, then Wikimedia Commons file records/search results. Commons metadata is tested against the allowlist before any image is downloaded. Wikidata P18 claims were also considered during the image-coverage review; a claim alone is insufficient—the depicted identity and image license still need verification. Relevant API roots:

- Wikipedia page-image API: <https://en.wikipedia.org/w/api.php>
- Wikimedia Commons API: <https://commons.wikimedia.org/w/api.php>
- Wikidata API: <https://www.wikidata.org/w/api.php>

An absent or rejected image is kept as an explicit gap in `image_sources.json`; the renderer does not fetch or substitute images at run time.
