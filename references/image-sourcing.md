# Sourcing entity visuals

Use the image type that represents the ranked entity, not a decorative substitute. Set project `visual_mode` once when the list has one clear type; use `items[].visual_type` for mixed lists or exceptions. `auto` is a heuristic, not identity recognition: for reliable behavior, explicitly set the mode for homogeneous lists and tag mixed/ambiguous rows. Add `image_query` when a name is ambiguous.

| Entity | Recommended visual |
|---|---|
| Person | Face/portrait of the named individual. Do not substitute a relative, company, photographer, or similarly named person. |
| Country or territory | Official national flag image. Store the country name in `country` when the item name is not itself the country. |
| Vehicle | A photograph of the specific model or make, matching `image_query` to the ranked item. |
| Building | A photograph of the named building, not a generic skyline. |
| Company/product | A representative image of the named company, product, or its clearly identified subject. Avoid logos unless the project specifically calls for logos. |
| Other entity | A photograph directly depicting the named item; if no reliable match exists, leave the image missing rather than inventing a match. |

## Resolver behavior

Run `python3 scripts/datavid/fetch_images.py --project PROJECT`. For non-flag entities the resolver first checks Wikipedia's page-image metadata for the requested entity. If that route has no usable image, it searches Wikimedia Commons and accepts a candidate only when the file title explicitly contains the required subject-name tokens. For flags it looks for the named country's flag file. It rejects non-image files and licenses outside public domain, CC0, CC BY, and CC BY-SA. Thumbnails are converted to local JPEGs so rendering is deterministic and does not contact the network.

The script writes `image_sources.json` with each image's source file title, Commons page URL, license name and URL, credited artist, credit text, matching route, and local path. Review this manifest together with a contact sheet or the intro/countdown stills. Reject false or ambiguous identities and correct them with an item-specific `image_query` or `visual_type`; never silently reuse another entity's photo.

Missing subjects are expected. Do not substitute a random search result. Either leave the panel unpictured, source a trustworthy licensed image manually and add its full attribution to the manifest, or use an entity-specific symbolic visual that the project can reproduce. Keep source attribution with the project when sharing or publishing it, and follow the exact license terms, including attribution and share-alike obligations.

All downloaded images are stored under `image_directory` (default `assets/entities/`) using rank-based filenames. The renderer reads only these local files. It crops portraits into a fixed-size square or circular front-face window near the top of each column and scales flags or other imagery within the same visual area; it does not warp the source asset during download.
