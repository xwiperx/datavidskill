#!/usr/bin/env python3
"""OCR and declared-layout collision checks for datavid stills or videos.

OCR is a screening tool, not proof of semantic correctness or readability.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from PIL import Image


def box_intersection_ratio(a, b):
    """Intersection area divided by the smaller box area; 0 means no overlap."""
    ax0, ay0, aw, ah = (float(a[k]) for k in ('x', 'y', 'width', 'height'))
    bx0, by0, bw, bh = (float(b[k]) for k in ('x', 'y', 'width', 'height'))
    area_a, area_b = max(0.0, aw) * max(0.0, ah), max(0.0, bw) * max(0.0, bh)
    if min(area_a, area_b) <= 0:
        return 0.0
    intersection = max(0.0, min(ax0 + aw, bx0 + bw) - max(ax0, bx0)) * max(
        0.0, min(ay0 + ah, by0 + bh) - max(ay0, by0))
    return intersection / min(area_a, area_b)


def find_box_collisions(boxes, threshold=0.02):
    """Return invalid/out-of-bounds and forbidden pair overlaps from layout data."""
    errors, overlaps = [], []
    ids = set()
    by_scene = defaultdict(list)
    for row in boxes:
        name = str(row.get('name', '')).strip()
        scene = str(row.get('scene', 'default'))
        if not name or name in ids:
            errors.append({'type': 'invalid_box_name', 'name': name})
            continue
        ids.add(name)
        try:
            x, y, w, h = (float(row[k]) for k in ('x', 'y', 'width', 'height'))
        except (KeyError, TypeError, ValueError):
            errors.append({'type': 'invalid_box_geometry', 'name': name})
            continue
        if w <= 0 or h <= 0:
            errors.append({'type': 'invalid_box_geometry', 'name': name})
            continue
        by_scene[scene].append({**row, 'x': x, 'y': y, 'width': w, 'height': h})
    for scene, scene_boxes in by_scene.items():
        for i, a in enumerate(scene_boxes):
            for b in scene_boxes[i + 1:]:
                allowed = set(a.get('allow_overlap_with', [])) | set(b.get('allow_overlap_with', []))
                if b['name'] in allowed or a['name'] in allowed:
                    continue
                ratio = box_intersection_ratio(a, b)
                if ratio > threshold:
                    overlaps.append({'scene': scene, 'first': a['name'], 'second': b['name'],
                                     'intersection_ratio': round(ratio, 4)})
    return errors, overlaps


def validate_layout(path, threshold=0.02):
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    width, height = int(doc['width']), int(doc['height'])
    errors, overlaps = find_box_collisions(doc.get('boxes', []), threshold)
    for row in doc.get('boxes', []):
        try:
            x, y, w, h = (float(row[k]) for k in ('x', 'y', 'width', 'height'))
            if x < 0 or y < 0 or x + w > width or y + h > height:
                errors.append({'type': 'out_of_bounds', 'name': row.get('name'),
                               'canvas': [width, height]})
        except (KeyError, TypeError, ValueError):
            pass
    return {'canvas': [width, height], 'errors': errors, 'overlaps': overlaps,
            'passed': not errors and not overlaps}


def _ocr_image(path, lang='eng', psm=11, min_conf=35.0):
    exe = shutil.which('tesseract')
    if not exe:
        raise RuntimeError('tesseract executable not found; install tesseract-ocr')
    proc = subprocess.run([exe, str(path), 'stdout', '-l', lang, '--psm', str(psm), 'tsv'],
                          capture_output=True, text=True, check=True)
    rows = []
    reader = csv.DictReader(io.StringIO(proc.stdout), delimiter='\t')
    for row in reader:
        if row.get('level') != '5':
            continue
        text = (row.get('text') or '').strip()
        try:
            conf = float(row.get('conf', -1))
            box = {'x': int(row['left']), 'y': int(row['top']),
                   'width': int(row['width']), 'height': int(row['height'])}
        except (TypeError, ValueError, KeyError):
            continue
        if text and conf >= min_conf and box['width'] > 0 and box['height'] > 0:
            rows.append({**box, 'text': text, 'confidence': conf})
    collisions = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            ratio = box_intersection_ratio(a, b)
            if ratio >= 0.15:
                collisions.append({'first': a['text'], 'second': b['text'],
                                   'intersection_ratio': round(ratio, 4),
                                   'boxes': [a, b]})
    return rows, collisions


def _duration(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'default=nw=1:nk=1', str(path)], check=True,
                       capture_output=True, text=True)
    return float(p.stdout.strip())


def inspect_media(image=None, video=None, every_seconds=5.0, lang='eng', psm=11,
                  min_conf=35.0, min_words=0, expected=(), strict_ocr_overlap=False):
    if bool(image) == bool(video):
        raise ValueError('provide exactly one of image or video')
    if video and every_seconds <= 0:
        raise ValueError('every_seconds must be positive')
    samples = []
    with tempfile.TemporaryDirectory(prefix='datavid-ocr-') as tmp:
        if image:
            samples = [(None, Path(image))]
        else:
            duration = _duration(video)
            stamps = []
            t = min(0.25, max(0.0, duration / 4))
            while t < duration - 0.02:
                stamps.append(t)
                t += every_seconds
            if not stamps and duration > 0:
                stamps = [duration / 2]
            for i, stamp in enumerate(stamps):
                p = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-loglevel', 'error',
                                    '-ss', f'{stamp:.6f}', '-i', str(video), '-frames:v', '1',
                                    '-an', '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1'],
                                   capture_output=True, check=True)
                if not p.stdout:
                    continue
                out = Path(tmp) / f'frame-{i:05d}.png'
                out.write_bytes(p.stdout)
                samples.append((stamp, out))
        results, failures, texts, overlap_candidates = [], [], [], []
        for stamp, path in samples:
            words, collisions = _ocr_image(path, lang, psm, min_conf)
            full_text = ' '.join(r['text'] for r in words)
            texts.append(full_text.casefold())
            row = {'time_seconds': stamp, 'word_count': len(words), 'text': full_text,
                   'words': words, 'overlaps': collisions}
            results.append(row)
            if len(words) < min_words:
                failures.append({'time_seconds': stamp, 'type': 'insufficient_ocr_words',
                                 'found': len(words), 'minimum': min_words})
            for collision in collisions:
                candidate = {'time_seconds': stamp, 'type': 'ocr_boxes_overlap', **collision}
                overlap_candidates.append(candidate)
                if strict_ocr_overlap:
                    failures.append(candidate)
        all_text = ' '.join(texts)
        for phrase in expected:
            if phrase.casefold() not in all_text:
                failures.append({'type': 'expected_text_missing', 'expected': phrase})
        return {'samples': results, 'failures': failures,
                'overlap_candidates': overlap_candidates,
                'passed': not failures, 'sample_count': len(results)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--image')
    group.add_argument('--video')
    ap.add_argument('--every-seconds', type=float, default=5.0)
    ap.add_argument('--lang', default='eng')
    ap.add_argument('--psm', type=int, default=11)
    ap.add_argument('--min-confidence', type=float, default=35.0)
    ap.add_argument('--min-words', type=int, default=0, help='minimum OCR words per sampled frame')
    ap.add_argument('--strict-ocr-overlap', action='store_true',
                    help='fail on any intersecting OCR word boxes; use only after detector calibration')
    ap.add_argument('--expect', action='append', default=[], help='required text substring; repeatable')
    ap.add_argument('--layout-json', help='declared layout boxes to collision-check')
    ap.add_argument('--layout-overlap-threshold', type=float, default=0.02)
    ap.add_argument('--report', default='qa_visual_report.json')
    a = ap.parse_args(argv)
    try:
        report = inspect_media(a.image, a.video, a.every_seconds, a.lang, a.psm,
                               a.min_confidence, a.min_words, a.expect, a.strict_ocr_overlap)
        if a.layout_json:
            report['layout'] = validate_layout(a.layout_json, a.layout_overlap_threshold)
            if not report['layout']['passed']:
                report['failures'].append({'type': 'layout_collision_or_invalid_box'})
                report['passed'] = False
        Path(a.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n',
                                  encoding='utf-8')
        print(json.dumps({'passed': report['passed'], 'samples': report['sample_count'],
                          'failures': report['failures'],
                          'overlap_candidates': len(report['overlap_candidates']),
                          'report': a.report}, ensure_ascii=False))
        return 0 if report['passed'] else 1
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f'qa_visual: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
