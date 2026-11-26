#!/usr/bin/env python3
"""Resolve locally cached, reusable entity images from Wikimedia with attribution.

Requires no runtime network access after this script has run. By default it uses
Wikipedia page thumbnails, then a conservative Wikimedia Commons search fallback.
Only public-domain, CC0, CC BY, and CC BY-SA assets are accepted.
"""
import argparse
import html
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image

UA = 'datavid-skill/2.1 (Wikimedia Commons image resolver; see https://github.com/xwiperx/datavidskill)'
API_WIKI = 'https://en.wikipedia.org/w/api.php'
API_COMMONS = 'https://commons.wikimedia.org/w/api.php'
ALLOW = re.compile(r'^(CC0|CC BY(?:-SA)?(?: |$)|Public domain|PD(?:-|$))', re.I)


def safe_image_directory(project_root, configured='assets/entities'):
    """Resolve a configured image directory without allowing writes outside a project."""
    root = Path(project_root).resolve()
    if not isinstance(configured, str) or not configured.strip():
        raise ValueError('image_directory must be a non-empty project-relative path')
    relative = Path(configured)
    if relative.is_absolute():
        raise ValueError('image_directory must be project-relative')
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError('image_directory must stay inside the project directory') from exc
    return target


def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=35) as resp:
        return json.load(resp)


def api_url(base, params):
    return base + '?' + urllib.parse.urlencode(params)


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', '', value or ''))).strip()


def norm_key(value):
    value = unicodedata.normalize('NFKD', value or '')
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', value.casefold()).strip()


def allowed(ext):
    md = ext or {}
    license_name = clean((md.get('LicenseShortName') or {}).get('value', ''))
    usage = clean((md.get('UsageTerms') or {}).get('value', ''))
    return bool(ALLOW.match(license_name) or ALLOW.match(usage) or 'public domain' in usage.lower())


def commons_info(file_title, width=640):
    data = get_json(api_url(API_COMMONS, {
        'action': 'query', 'format': 'json', 'titles': file_title,
        'prop': 'imageinfo', 'iiprop': 'url|extmetadata|mime', 'iiurlwidth': width,
    }))
    page = next(iter(data.get('query', {}).get('pages', {}).values()), {})
    info = (page.get('imageinfo') or [{}])[0]
    if not info or not info.get('mime', '').startswith('image/') or not allowed(info.get('extmetadata')):
        return None
    md = info.get('extmetadata', {})
    return {
        'title': page.get('title', file_title),
        'url': info.get('thumburl') or info.get('url'),
        'source_url': 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(page.get('title', file_title).replace(' ', '_')),
        'license': clean((md.get('LicenseShortName') or {}).get('value', '')),
        'license_url': clean((md.get('LicenseUrl') or {}).get('value', '')),
        'artist': clean((md.get('Artist') or {}).get('value', '')),
        'credit': clean((md.get('Credit') or {}).get('value', '')),
    }


def wiki_pages(items):
    # MediaWiki supports title batches; URL lengths are kept below practical limits.
    results = {}
    for start in range(0, len(items), 35):
        batch = items[start:start + 35]
        titles = '|'.join((x.get('image_query') or x['name']) for x in batch)
        data = get_json(api_url(API_WIKI, {
            'action': 'query', 'format': 'json', 'redirects': 1,
            'prop': 'pageimages', 'piprop': 'thumbnail|name', 'pithumbsize': 640,
            'titles': titles,
        }))
        for page in data.get('query', {}).get('pages', {}).values():
            key = norm_key(page.get('title', ''))
            results[key] = page
        # Follow redirects so requested name maps to resolved page.
        for redir in data.get('query', {}).get('redirects', []):
            results[norm_key(redir.get('from', ''))] = results.get(norm_key(redir.get('to', '')), {})
    return results


def commons_search(query, required_name, width=640):
    data = get_json(api_url(API_COMMONS, {
        'action': 'query', 'format': 'json', 'generator': 'search',
        'gsrsearch': query, 'gsrnamespace': 6, 'gsrlimit': 8,
        'prop': 'imageinfo', 'iiprop': 'url|extmetadata|mime', 'iiurlwidth': width,
    }))
    pages = data.get('query', {}).get('pages', {})
    stop = {'the', 'and', 'of', 'jr', 'sr', 'ii', 'iii', 'iv', 'portrait', 'photo', 'image'}
    needed = [t for t in norm_key(required_name).split() if len(t) > 1 and t not in stop]
    for page in sorted(pages.values(), key=lambda x: x.get('index', 999)):
        info = (page.get('imageinfo') or [{}])[0]
        md = info.get('extmetadata', {})
        title_key = norm_key(page.get('title', ''))
        if (info and info.get('mime', '').startswith('image/') and allowed(md)
                and needed and all(token in title_key.split() for token in needed)):
            return {
                'title': page.get('title', ''),
                'url': info.get('thumburl') or info.get('url'),
                'source_url': 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(page.get('title', '').replace(' ', '_')),
                'license': clean((md.get('LicenseShortName') or {}).get('value', '')),
                'license_url': clean((md.get('LicenseUrl') or {}).get('value', '')),
                'artist': clean((md.get('Artist') or {}).get('value', '')),
                'credit': clean((md.get('Credit') or {}).get('value', '')),
                'match_method': 'commons-exact-title',
            }
    return None


def resolve(item, page_map, mode):
    name = item['name']
    kind = (item.get('visual_type') or mode or 'auto').lower()
    if kind in ('country', 'nation', 'countries'):
        kind = 'flag'
    if kind in ('human', 'people', 'individual'):
        kind = 'person'
    if kind == 'auto':
        desc = (name + ' ' + item.get('category', '') + ' ' + item.get('meta', '')).lower()
        if re.search(r'\b(country|nation|countries|flag)\b', desc):
            kind = 'flag'
        elif re.search(r'\b(person|people|billionaire|founder|ceo|actor|singer|athlete|politician)\b', desc):
            kind = 'person'
        elif re.search(r'\b(car|vehicle|automotive|motorcycle|aircraft|ship)\b', desc):
            kind = 'vehicle'
        else:
            kind = 'entity'
    query = item.get('image_query') or name
    record = None
    if kind == 'flag':
        country = item.get('country') or name
        record = commons_info('File:Flag of ' + country + '.svg')
        if not record:
            record = commons_search('Flag of ' + country + ' filetype:svg', 'Flag ' + country)
    else:
        page = page_map.get(norm_key(query)) or page_map.get(norm_key(name))
        pageimage = page.get('pageimage') if page else None
        if pageimage:
            record = commons_info('File:' + pageimage)
            if record:
                record['match_method'] = 'wikipedia-pageimage'
        if not record:
            hint = item.get('category', '') if kind == 'entity' else kind
            record = commons_search(f'{query} {hint} -logo', name)
    if not record:
        return {'name': name, 'status': 'not-found-or-license-restricted', 'visual_type': kind}
    return {'name': name, 'visual_type': kind, **record}


def download(record, destination):
    req = urllib.request.Request(record['url'], headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        blob = resp.read(8_000_001)
    if len(blob) > 8_000_000:
        raise ValueError('image exceeds 8 MB')
    image = Image.open(BytesIO(blob)).convert('RGB')
    image.thumbnail((900, 1100), Image.Resampling.LANCZOS)
    image.save(destination, format='JPEG', quality=88, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--workers', type=int, default=5)
    a = ap.parse_args()
    root = Path(a.project).resolve()
    config = json.loads((root / 'config.json').read_text())
    data = json.loads((root / 'data.json').read_text())
    mode = config.get('visual_mode', 'auto')
    images_dir = safe_image_directory(root, config.get('image_directory', 'assets/entities'))
    items = data['items']
    try:
        pages = wiki_pages(items)
    except Exception as exc:
        print('Wikipedia page lookup failed:', exc, file=sys.stderr)
        pages = {}
    # Independent lookups are deterministic for these exact data rows; use bounded concurrency.
    resolved = [None] * len(items)
    with ThreadPoolExecutor(max_workers=max(1, min(8, a.workers))) as pool:
        futures = {pool.submit(resolve, item, pages, mode): i for i, item in enumerate(items)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                resolved[i] = fut.result()
            except Exception as exc:
                resolved[i] = {'name': items[i]['name'], 'status': 'lookup-error: ' + str(exc)[:180]}
            if (i + 1) % 10 == 0:
                print(f'lookups complete: {i + 1}/{len(items)}', flush=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, row in enumerate(resolved):
        if row and row.get('url'):
            local_name = f'{i+1:03d}.jpg'
            try:
                download(row, images_dir / local_name)
                row['local_path'] = os.path.relpath(images_dir / local_name, root)
                row.pop('url', None)
                row['rank'] = i + 1
            except Exception as exc:
                row = {'name': items[i]['name'], 'rank': i + 1, 'status': 'download-error: ' + str(exc)[:180]}
        else:
            row['rank'] = i + 1
        manifest.append(row)
        if i % 10 == 9:
            print(f'images saved: {i + 1}/{len(items)}', flush=True)
    (root / 'image_sources.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    ok = sum(bool(x.get('local_path')) for x in manifest)
    print(f'complete: {ok}/{len(items)} images saved to {images_dir}')
    print('missing: ' + ', '.join(x['name'] for x in manifest if not x.get('local_path')))


if __name__ == '__main__':
    main()
