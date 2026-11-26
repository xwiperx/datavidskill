#!/usr/bin/env python3
"""Rebuild the cleaned Forbes snapshot using explicit, rank-keyed display overrides.

Usage:
  python3 build_data.py                 # write ../data.json
  python3 build_data.py --check         # compare generated content without writing
  python3 build_data.py --output FILE   # write a separate target
"""
import argparse
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE.parent / 'data.json'
ALLOWED_OVERRIDE_FIELDS = {'name', 'value', 'category', 'meta', 'family'}


def build_data():
    raw_doc = json.loads((HERE / 'forbes2026.json').read_text(encoding='utf-8'))
    people = raw_doc['personList']['personsLists']
    ranked = [person for person in people if int(person.get('rank', 999)) <= 100]
    ranked.sort(key=lambda person: float(person['finalWorthBillions']))
    if len(ranked) != 100:
        raise ValueError(f'expected exactly 100 source rows, found {len(ranked)}')

    override_doc = json.loads((HERE / 'data_overrides.json').read_text(encoding='utf-8'))
    if override_doc.get('schema_version') != 1 or not isinstance(override_doc.get('rank_overrides'), dict):
        raise ValueError('data_overrides.json has an unsupported or invalid schema')
    overrides = override_doc['rank_overrides']
    items = []
    for rank, person in enumerate(ranked, 1):
        source_value = person.get('finalWorthBillions')
        if isinstance(source_value, bool) or not isinstance(source_value, (int, float)):
            raise ValueError(f'source value at generated rank {rank} is not numeric')
        value = round(float(source_value), 1)
        if not math.isfinite(value) or value < 0:
            raise ValueError(f'source value at generated rank {rank} is invalid')
        source = person.get('source', '')
        country = person.get('country', '')
        item = {
            'name': person['personName'],
            'value': value,
            'category': (person.get('industries') or [''])[0].upper(),
            'meta': ' · '.join(str(part).upper() for part in (source, country) if part),
        }
        override = overrides.get(str(rank), {})
        if not isinstance(override, dict):
            raise ValueError(f'override for rank {rank} must be an object')
        unknown = set(override) - ALLOWED_OVERRIDE_FIELDS
        if unknown:
            raise ValueError(f'unsupported override fields at rank {rank}: {sorted(unknown)}')
        item.update(override)
        if not isinstance(item.get('name'), str) or not item['name'].strip():
            raise ValueError(f'generated name at rank {rank} is empty')
        final_value = item.get('value')
        if (isinstance(final_value, bool) or not isinstance(final_value, (int, float)) or
                not math.isfinite(final_value) or final_value < 0):
            raise ValueError(f'generated value at rank {rank} must be finite and non-negative')
        if not isinstance(item.get('category'), str) or not isinstance(item.get('meta'), str):
            raise ValueError(f'generated category/meta at rank {rank} must be strings')
        if 'family' in item and not isinstance(item['family'], bool):
            raise ValueError(f'family override at rank {rank} must be boolean')
        items.append(item)
    unknown_ranks = set(overrides) - {str(rank) for rank in range(1, 101)}
    if unknown_ranks:
        raise ValueError(f'overrides contain unknown ranks: {sorted(unknown_ranks)}')
    values = [item['value'] for item in items]
    if values != sorted(values):
        raise ValueError('generated data is not sorted in ascending value/rank order')
    total = round(sum(values), 1)
    if not math.isfinite(total):
        raise ValueError('generated total is not finite')
    return {'items': items, 'total': total}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true',
                        help='compare generated data with ../data.json without writing')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT,
                        help='output JSON path (default: ../data.json)')
    args = parser.parse_args(argv)
    generated = build_data()
    target = args.output.resolve()
    if args.check:
        try:
            current = json.loads(target.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            print(f'FAIL: cannot read comparison target {target}: {exc}')
            return 1
        if current != generated:
            print(f'FAIL: generated data differs from {target}')
            return 1
        print(f'PASS: generated data matches {target} ({len(generated["items"])} items)')
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(generated, indent=1, ensure_ascii=False, allow_nan=False) + '\n',
                       encoding='utf-8')
    print(f'wrote {target} {len(generated["items"])} items, total {generated["total"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
