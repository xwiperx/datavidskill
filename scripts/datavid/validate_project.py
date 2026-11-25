#!/usr/bin/env python3
"""Structural project audit. Identity verification remains a human contact-sheet check."""
import json
import math
import sys
from pathlib import Path

ALLOWED_LICENSES = {'Public domain', 'CC0', 'CC BY', 'CC BY-SA', 'CC BY 3.0',
                    'CC BY-SA 3.0', 'CC BY 4.0', 'CC BY-SA 4.0', 'CC BY 2.0',
                    'CC BY-SA 2.0', 'CC BY-SA 3.0 de'}


def audit(project):
    root = Path(project).resolve()
    cfg = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    data = json.loads((root / 'data.json').read_text(encoding='utf-8'))
    manifest = json.loads((root / 'image_sources.json').read_text(encoding='utf-8'))
    items = data.get('items')
    errors, warnings = [], []
    if not isinstance(items, list) or not items:
        errors.append('items must be a non-empty list')
        return errors, warnings
    names = [str(row.get('name', '')).strip() for row in items]
    if any(not n for n in names):
        errors.append('one or more items have an empty name')
    if len(set(names)) != len(names):
        errors.append('duplicate display names found')
    values = []
    for index, row in enumerate(items, 1):
        try:
            v = float(row['value'])
            if not math.isfinite(v) or v < 0:
                raise ValueError
            values.append(v)
        except (KeyError, ValueError, TypeError):
            errors.append(f'item {index} has an invalid value')
    if len(values) == len(items) and values != sorted(values):
        errors.append('data items are not in ascending value/rank order')
    if len(manifest) != len(items):
        errors.append(f'manifest has {len(manifest)} rows; expected {len(items)}')
    covered = 0
    for i, row in enumerate(manifest[:len(items)]):
        expected_rank = i + 1
        if row.get('rank') != expected_rank or row.get('name') != names[i]:
            errors.append(f'manifest rank/name mismatch at rank {expected_rank}')
        local = row.get('local_path')
        if local:
            covered += 1
            if not (root / local).is_file():
                errors.append(f'missing local image for rank {expected_rank}: {local}')
            if not row.get('source_url') or not row.get('license'):
                errors.append(f'image at rank {expected_rank} lacks source or license metadata')
            elif row.get('license') not in ALLOWED_LICENSES:
                warnings.append(f'license label at rank {expected_rank} needs manual allowlist review')
    maximum = max(values) if values else 0
    if float(cfg.get('scale_max', 0) or 0) < maximum:
        errors.append(f"scale_max {cfg.get('scale_max')} is below max data value {maximum}")
    if len(items) >= 5 and covered < len(items) * 0.2:
        warnings.append('low portrait coverage; preserve blank cards rather than using substitutes')
    return errors, warnings


def main():
    project = sys.argv[1] if len(sys.argv) > 1 else '.'
    errors, warnings = audit(project)
    for warning in warnings:
        print('WARN:', warning)
    for error in errors:
        print('FAIL:', error)
    if errors:
        return 1
    print(f'PASS: project structure valid; {len(json.loads((Path(project)/"image_sources.json").read_text()))} manifest rows; identity must still be checked visually')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
