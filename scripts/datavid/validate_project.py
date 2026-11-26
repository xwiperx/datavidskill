#!/usr/bin/env python3
"""Structural project audit. Identity verification remains a human contact-sheet check."""
import json
import math
import sys
from pathlib import Path

ALLOWED_LICENSES = {'Public domain', 'CC0', 'CC BY', 'CC BY-SA', 'CC BY 3.0',
                    'CC BY-SA 3.0', 'CC BY 4.0', 'CC BY-SA 4.0', 'CC BY 2.0',
                    'CC BY-SA 2.0', 'CC BY-SA 3.0 de'}


def _load_json(path, label, errors):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f'{label} could not be read as JSON: {exc}')
        return None


def _safe_project_file(root, local_path):
    """Resolve a manifest path only when it is relative and remains inside root."""
    if not isinstance(local_path, str) or not local_path.strip():
        return None
    candidate = Path(local_path)
    if candidate.is_absolute():
        return None
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def audit(project):
    root = Path(project).resolve()
    errors, warnings = [], []
    cfg = _load_json(root / 'config.json', 'config.json', errors)
    data = _load_json(root / 'data.json', 'data.json', errors)
    manifest = _load_json(root / 'image_sources.json', 'image_sources.json', errors)
    if errors:
        return errors, warnings
    if not isinstance(cfg, dict):
        errors.append('config.json must contain a JSON object')
        cfg = {}
    if not isinstance(data, dict):
        errors.append('data.json must contain a JSON object')
        data = {}
    if not isinstance(manifest, list):
        errors.append('image_sources.json must contain a JSON list')
        manifest = []

    items = data.get('items')
    if not isinstance(items, list) or not items:
        errors.append('items must be a non-empty list')
        return errors, warnings

    names = []
    values = []
    for index, row in enumerate(items, 1):
        if not isinstance(row, dict):
            errors.append(f'item {index} must be a JSON object')
            names.append('')
            continue
        name = row.get('name')
        name = name.strip() if isinstance(name, str) else ''
        names.append(name)
        if not name:
            errors.append(f'item {index} has an empty or invalid name')
        try:
            raw_value = row['value']
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise ValueError
            value = float(raw_value)
            if not math.isfinite(value) or value < 0:
                raise ValueError
            values.append(value)
        except (KeyError, ValueError, TypeError, OverflowError):
            errors.append(f'item {index} has an invalid value')

    valid_names = [name for name in names if name]
    if len(set(valid_names)) != len(valid_names):
        errors.append('duplicate display names found')
    if len(values) == len(items) and values != sorted(values):
        errors.append('data items are not in ascending value/rank order')
    if 'total' in data:
        try:
            declared_total = float(data['total'])
            if not math.isfinite(declared_total) or not math.isclose(
                    declared_total, sum(values), rel_tol=1e-9, abs_tol=1e-6):
                errors.append('declared total does not equal the sum of item values')
        except (TypeError, ValueError, OverflowError):
            errors.append('declared total is not a finite number')

    if len(manifest) != len(items):
        errors.append(f'manifest has {len(manifest)} rows; expected {len(items)}')
    covered = 0
    for i, row in enumerate(manifest[:len(items)]):
        expected_rank = i + 1
        if not isinstance(row, dict):
            errors.append(f'manifest row {expected_rank} must be a JSON object')
            continue
        if row.get('rank') != expected_rank or row.get('name') != names[i]:
            errors.append(f'manifest rank/name mismatch at rank {expected_rank}')
        local = row.get('local_path')
        if local:
            safe_path = _safe_project_file(root, local)
            if safe_path is None:
                errors.append(f'image path at rank {expected_rank} must be relative and stay inside the project: {local}')
                continue
            covered += 1
            if not safe_path.is_file():
                errors.append(f'missing local image for rank {expected_rank}: {local}')
            if not row.get('source_url') or not row.get('license'):
                errors.append(f'image at rank {expected_rank} lacks source or license metadata')
            elif row.get('license') not in ALLOWED_LICENSES:
                warnings.append(f'license label at rank {expected_rank} needs manual allowlist review')

    maximum = max(values) if values else 0.0
    try:
        scale_max = float(cfg.get('scale_max', 0) or 0)
        if not math.isfinite(scale_max) or scale_max < maximum:
            errors.append(f"scale_max {cfg.get('scale_max')} is below max data value {maximum} or invalid")
    except (TypeError, ValueError, OverflowError):
        errors.append(f"scale_max {cfg.get('scale_max')} is not a finite number")
    if len(items) >= 5 and covered < len(items) * 0.2:
        warnings.append('low portrait coverage; preserve blank cards rather than using substitutes')
    return errors, warnings


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    project = args[0] if args else '.'
    errors, warnings = audit(project)
    for warning in warnings:
        print('WARN:', warning)
    for error in errors:
        print('FAIL:', error)
    if errors:
        return 1
    try:
        manifest = json.loads((Path(project) / 'image_sources.json').read_text(encoding='utf-8'))
        print(f'PASS: project structure valid; {len(manifest)} manifest rows; identity must still be checked visually')
        return 0
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError) as exc:
        print(f'FAIL: image_sources.json could not be read: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
