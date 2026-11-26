#!/usr/bin/env python3
"""Compare two video revisions at matched normalized times and create a contact sheet."""
from __future__ import annotations
import argparse
import io
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def video_duration(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'default=nw=1:nk=1', str(path)], check=True,
                       capture_output=True, text=True)
    value = float(p.stdout.strip())
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f'invalid duration for {path}')
    return value


def sample_rgb(path, timestamp, size=(320, 180)):
    vf = f'scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2'
    p = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-loglevel', 'error', '-ss',
                        f'{timestamp:.6f}', '-i', str(path), '-frames:v', '1', '-an', '-vf', vf,
                        '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1'], check=True,
                       capture_output=True)
    if not p.stdout:
        raise ValueError(f'could not sample {path} at {timestamp:.3f}s')
    with Image.open(io.BytesIO(p.stdout)) as im:
        return np.asarray(im.convert('RGB'), dtype=np.float32)


def compare_arrays(reference, candidate, changed_threshold=12.0):
    a, b = np.asarray(reference, dtype=np.float32), np.asarray(candidate, dtype=np.float32)
    if a.shape != b.shape or a.ndim != 3:
        raise ValueError('comparison arrays must have identical HxWxC shapes')
    diff = np.abs(a - b)
    mae = float(diff.mean())
    mse = float(np.square(a - b).mean())
    psnr = None if mse == 0 else 20.0 * math.log10(255.0 / math.sqrt(mse))
    # 8x8 local-window SSIM, averaged over RGB channels and windows.
    h, w, c = a.shape
    h8, w8 = h // 8, w // 8
    aa = a[:h8 * 8, :w8 * 8].reshape(h8, 8, w8, 8, c).transpose(0, 2, 1, 3, 4)
    bb = b[:h8 * 8, :w8 * 8].reshape(h8, 8, w8, 8, c).transpose(0, 2, 1, 3, 4)
    mux, muy = aa.mean(axis=(2, 3)), bb.mean(axis=(2, 3))
    vx = ((aa - mux[:, :, None, None, :]) ** 2).mean(axis=(2, 3))
    vy = ((bb - muy[:, :, None, None, :]) ** 2).mean(axis=(2, 3))
    cov = ((aa - mux[:, :, None, None, :]) * (bb - muy[:, :, None, None, :])).mean(axis=(2, 3))
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    ssim = ((2 * mux * muy + c1) * (2 * cov + c2) /
            ((mux ** 2 + muy ** 2 + c1) * (vx + vy + c2))).mean()
    return {'mae': mae, 'psnr_db': psnr, 'ssim_8x8': float(ssim),
            'changed_fraction': float((diff.max(axis=2) > changed_threshold).mean())}


def normalize_fractions(fractions):
    """Return a non-empty tuple of finite, unique normalized sample positions."""
    try:
        values = tuple(float(value) for value in fractions)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError('sample fractions must be numeric values in [0,1)') from exc
    if not values:
        raise ValueError('at least one sample fraction is required')
    if any(not math.isfinite(value) or not 0 <= value < 1 for value in values):
        raise ValueError('sample fractions must be finite values in [0,1)')
    if len(set(values)) != len(values):
        raise ValueError('sample fractions must not contain duplicates')
    return values


def compare_videos(reference, candidate, fractions=(0.1, 0.33, 0.5, 0.66, 0.9),
                   size=(320, 180), max_duration_delta=0.5):
    fractions = normalize_fractions(fractions)
    if (not isinstance(size, (tuple, list)) or len(size) != 2 or
            any(not isinstance(dimension, int) or dimension < 16 for dimension in size)):
        raise ValueError('sample size must contain two integer dimensions >=16')
    if not math.isfinite(max_duration_delta) or max_duration_delta < 0:
        raise ValueError('max duration delta must be finite and non-negative')
    d1, d2 = video_duration(reference), video_duration(candidate)
    duration_delta = abs(d1 - d2)
    if duration_delta > max_duration_delta:
        raise ValueError(f'video durations differ by {duration_delta:.3f}s (> {max_duration_delta}s)')
    rows, tiles = [], []
    for fraction in fractions:
        t1, t2 = fraction * d1, fraction * d2
        a, b = sample_rgb(reference, t1, size), sample_rgb(candidate, t2, size)
        metrics = compare_arrays(a, b)
        rows.append({'fraction': fraction, 'reference_time_seconds': t1,
                     'candidate_time_seconds': t2, **metrics})
        ia, ib = Image.fromarray(a.astype(np.uint8)), Image.fromarray(b.astype(np.uint8))
        blend = Image.blend(ia, ib, 0.5)
        diff = Image.fromarray(np.clip(np.abs(a - b) * 3.0, 0, 255).astype(np.uint8))
        tiles.append((fraction, ia, ib, blend, diff))
    width, height = size[0] * 2, (size[1] + 26) * len(tiles) * 2 + 24
    sheet = Image.new('RGB', (width, height), (16, 20, 28))
    draw = ImageDraw.Draw(sheet)
    labels = ['reference', 'candidate', '50% blend', 'difference ×3']
    for i, (fraction, *ims) in enumerate(tiles):
        y0 = i * (size[1] + 26) * 2
        draw.text((4, y0 + 2), f't={fraction:.1%}', fill=(255, 255, 255))
        for j, im in enumerate(ims):
            x, y = (j % 2) * size[0], y0 + 24 + (j // 2) * (size[1] + 26)
            sheet.paste(im, (x, y))
            draw.text((x + 4, y + size[1] + 3), labels[j], fill=(235, 235, 235))
    return {'reference': str(reference), 'candidate': str(candidate),
            'reference_duration_seconds': d1, 'candidate_duration_seconds': d2,
            'duration_delta_seconds': duration_delta, 'samples': rows}, sheet


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('reference')
    ap.add_argument('candidate')
    ap.add_argument('--fractions', default='0.10,0.33,0.50,0.66,0.90')
    ap.add_argument('--size', default='320x180')
    ap.add_argument('--max-duration-delta', type=float, default=0.5)
    ap.add_argument('--max-mae', type=float)
    ap.add_argument('--min-ssim', type=float)
    ap.add_argument('--expect-identical', action='store_true', help='require MAE<=0.01 and SSIM>=0.999')
    ap.add_argument('--report', default='qa_compare_report.json')
    ap.add_argument('--sheet', default='qa_compare_contact_sheet.jpg')
    a = ap.parse_args(argv)
    try:
        size = tuple(int(x) for x in a.size.lower().split('x', 1))
        fractions = normalize_fractions(x for x in a.fractions.split(',') if x.strip())
        if len(size) != 2 or min(size) < 16:
            raise ValueError('--size must be WIDTHxHEIGHT with dimensions >=16')
        report, sheet = compare_videos(a.reference, a.candidate, fractions, size,
                                       a.max_duration_delta)
        thresholds = []
        max_mae = 0.01 if a.expect_identical else a.max_mae
        min_ssim = 0.999 if a.expect_identical else a.min_ssim
        for row in report['samples']:
            if max_mae is not None and row['mae'] > max_mae:
                thresholds.append({'fraction': row['fraction'], 'type': 'mae_exceeded',
                                   'value': row['mae'], 'maximum': max_mae})
            if min_ssim is not None and row['ssim_8x8'] < min_ssim:
                thresholds.append({'fraction': row['fraction'], 'type': 'ssim_below_minimum',
                                   'value': row['ssim_8x8'], 'minimum': min_ssim})
        report['threshold_failures'] = thresholds
        report['passed'] = not thresholds
        Path(a.report).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        sheet.save(a.sheet, quality=88)
        print(json.dumps({'passed': report['passed'], 'samples': len(report['samples']),
                          'threshold_failures': thresholds, 'report': a.report, 'sheet': a.sheet}))
        return 0 if report['passed'] else 1
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f'qa_compare: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
