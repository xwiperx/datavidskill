#!/usr/bin/env python3
"""Detect black frames, long near-freezes, cadence errors, and visual jumps."""
from __future__ import annotations
import argparse
import json
import math
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np


def contiguous_runs(mask):
    runs, start = [], None
    for i, flag in enumerate(list(mask) + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            runs.append((start, i - 1))
            start = None
    return runs


def analyze_luma_frames(frames, fps, edge_ignore_seconds=0.5, black_mean_max=5.0,
                        black_dark_fraction=0.995, pixel_dark_max=12,
                        freeze_delta=0.00001, freeze_min_seconds=0.8,
                        jump_delta=24.0, freeze_candidate_delta=0.08,
                        allow_black_ranges=()):
    """Pure analysis function for HxWxN grayscale uint8 frames."""
    arr = np.asarray(frames)
    if arr.ndim != 3 or arr.shape[0] < 2:
        raise ValueError('at least two grayscale frames are required')
    if fps <= 0:
        raise ValueError('fps must be positive')
    edge = int(round(edge_ignore_seconds * fps))
    means = arr.astype(np.float32).mean(axis=(1, 2))
    dark_fraction = (arr <= pixel_dark_max).mean(axis=(1, 2))
    black = (means <= black_mean_max) & (dark_fraction >= black_dark_fraction)
    eligible = np.ones(len(arr), dtype=bool)
    if edge:
        eligible[:min(edge, len(arr))] = False
        eligible[max(0, len(arr) - edge):] = False
    black_runs, allowed_black_runs = [], []
    for start, end in contiguous_runs(black & eligible):
        run = {'start_frame': start, 'end_frame': end,
               'start_seconds': start / fps, 'duration_seconds': (end - start + 1) / fps,
               'frame_count': end - start + 1}
        run_end = (end + 1) / fps
        if any(a <= run['start_seconds'] + 0.5 / fps and b >= run_end - 0.5 / fps
               for a, b in allow_black_ranges):
            allowed_black_runs.append(run)
        else:
            black_runs.append(run)

    diffs = np.abs(np.diff(arr.astype(np.int16), axis=0)).mean(axis=(1, 2))
    minimum_pairs = max(1, int(math.ceil(freeze_min_seconds * fps)) - 1)
    def collect_runs(threshold):
        found = []
        for start, end in contiguous_runs(diffs <= threshold):
            if end - start + 1 >= minimum_pairs:
                found.append({'start_frame': start, 'end_frame': end + 1,
                              'start_seconds': start / fps,
                              'duration_seconds': (end - start + 2) / fps,
                              'mean_abs_luma_delta': float(diffs[start:end + 1].mean())})
        return found
    freeze_runs = collect_runs(freeze_delta)
    freeze_candidates = collect_runs(freeze_candidate_delta)
    jumps = [{'frame': i + 1, 'time_seconds': (i + 1) / fps,
              'mean_abs_luma_delta': float(delta)}
             for i, delta in enumerate(diffs) if delta >= jump_delta]
    duplicate_pairs = [{'frame_pair': [i, i + 1], 'time_seconds': (i + 1) / fps}
                       for i, delta in enumerate(diffs) if delta == 0]
    return {'black_runs': black_runs, 'allowed_black_runs': allowed_black_runs,
            'freeze_runs': freeze_runs, 'freeze_candidates': freeze_candidates,
            'duplicate_frame_pairs': duplicate_pairs, 'jumps': jumps,
            'mean_abs_luma_delta': float(diffs.mean()) if len(diffs) else 0.0,
            'max_abs_luma_delta': float(diffs.max()) if len(diffs) else 0.0}


def probe_video(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                        '-show_entries', 'stream=codec_name,width,height,r_frame_rate,avg_frame_rate,duration,nb_read_frames',
                        '-show_entries', 'format=duration', '-of', 'json', str(path)],
                       check=True, capture_output=True, text=True)
    doc = json.loads(p.stdout)
    if not doc.get('streams'):
        raise ValueError('no video stream')
    return doc['streams'][0], float(doc.get('format', {}).get('duration') or
                                  doc['streams'][0].get('duration') or 0.0)


def frame_timestamps(path):
    p = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_frames',
                        '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'json', str(path)],
                       check=True, capture_output=True, text=True)
    return [float(x['best_effort_timestamp_time']) for x in json.loads(p.stdout).get('frames', [])
            if x.get('best_effort_timestamp_time') not in (None, 'N/A')]


def cadence_issues(times, expected_fps=30.0, tolerance_seconds=0.005):
    if len(times) < 2:
        return [{'type': 'insufficient_timestamps'}]
    period = 1.0 / expected_fps
    issues = []
    previous = None
    for i, (a, b) in enumerate(zip(times, times[1:])):
        delta = b - a
        if delta <= 0:
            issues.append({'frame_pair': [i, i + 1], 'type': 'non_monotonic_pts', 'delta': delta})
        elif abs(delta - period) > tolerance_seconds:
            issues.append({'frame_pair': [i, i + 1], 'type': 'irregular_frame_cadence',
                           'delta_seconds': delta, 'expected_seconds': period})
        if previous is not None and b <= previous:
            issues.append({'frame': i + 1, 'type': 'non_monotonic_pts'})
        previous = b
    return issues


def inspect_video(path, expected_fps=30.0, edge_ignore_seconds=0.5,
                  freeze_min_seconds=0.8, freeze_delta=0.00001,
                  jump_delta=24.0, cadence_tolerance=0.005,
                  freeze_candidate_delta=0.08, allow_black_ranges=()):
    stream, duration = probe_video(path)
    try:
        width, height = int(stream['width']), int(stream['height'])
        fps = float(Fraction(stream.get('avg_frame_rate') or stream['r_frame_rate']))
        frames = int(stream.get('nb_read_frames') or 0)
    except (KeyError, TypeError, ValueError, ZeroDivisionError, SyntaxError) as exc:
        raise ValueError(f'invalid video metadata: {exc}') from exc
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError('invalid frame rate')
    p = subprocess.run(['ffmpeg', '-hide_banner', '-nostdin', '-loglevel', 'error', '-i', str(path),
                        '-map', '0:v:0', '-vf', 'scale=160:90:flags=area', '-pix_fmt', 'gray',
                        '-vsync', '0', '-f', 'rawvideo', 'pipe:1'], check=True, capture_output=True)
    frame_bytes = 160 * 90
    if len(p.stdout) % frame_bytes:
        raise ValueError('decoded grayscale output ended on a partial frame')
    luma = np.frombuffer(p.stdout, dtype=np.uint8).reshape((-1, 90, 160))
    if frames and len(luma) != frames:
        raise ValueError(f'decoded frames {len(luma)} disagree with ffprobe count {frames}')
    if len(luma) < 2:
        raise ValueError('video has fewer than two decodable frames')
    report = analyze_luma_frames(luma, fps, edge_ignore_seconds=edge_ignore_seconds,
                                 freeze_delta=freeze_delta, freeze_min_seconds=freeze_min_seconds,
                                 jump_delta=jump_delta, freeze_candidate_delta=freeze_candidate_delta,
                                 allow_black_ranges=allow_black_ranges)
    timestamps = frame_timestamps(path)
    cadence = cadence_issues(timestamps, expected_fps, cadence_tolerance)
    rate_issue = abs(fps - expected_fps) > 0.01
    report.update({'file': str(path), 'width': width, 'height': height, 'fps': fps,
                   'frame_count': len(luma), 'duration_seconds': duration,
                   'cadence_issues': cadence, 'rate_mismatch': rate_issue,
                   'passed': not report['black_runs'] and not report['freeze_runs'] and
                             not cadence and not rate_issue})
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('video')
    ap.add_argument('--fps', type=float, default=30.0)
    ap.add_argument('--edge-ignore-seconds', type=float, default=0.5,
                    help='ignore intentional near-black fades at the first/last edge')
    ap.add_argument('--freeze-min-seconds', type=float, default=0.8)
    ap.add_argument('--freeze-delta', type=float, default=0.00001,
                    help='near-zero maximum average luma change per pixel for a repeated-frame freeze failure')
    ap.add_argument('--freeze-candidate-delta', type=float, default=0.08,
                    help='looser threshold for review-only low-motion/freeze candidates')
    ap.add_argument('--allow-black-range', action='append', default=[], metavar='START:END',
                    help='explicitly allow black frames only within this reviewed fade interval; repeatable')
    ap.add_argument('--fail-on-freeze-candidate', action='store_true',
                    help='treat review-only low-motion candidates as failures')
    ap.add_argument('--jump-delta', type=float, default=24.0,
                    help='report larger adjacent-frame luma changes as jump candidates; not fatal by default')
    ap.add_argument('--cadence-tolerance', type=float, default=0.005)
    ap.add_argument('--fail-on-jump', action='store_true')
    ap.add_argument('--report', default='qa_media_report.json')
    a = ap.parse_args(argv)
    try:
        ranges = []
        for value in a.allow_black_range:
            try:
                start, end = (float(part) for part in value.split(':', 1))
            except (ValueError, TypeError) as exc:
                raise ValueError(f'invalid --allow-black-range {value!r}; expected START:END') from exc
            if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end <= start:
                raise ValueError(f'invalid --allow-black-range {value!r}; require 0 <= START < END')
            ranges.append((start, end))
        report = inspect_video(a.video, a.fps, a.edge_ignore_seconds, a.freeze_min_seconds,
                               a.freeze_delta, a.jump_delta, a.cadence_tolerance,
                               a.freeze_candidate_delta, ranges)
        if a.fail_on_jump and report['jumps']:
            report['passed'] = False
        if a.fail_on_freeze_candidate and report['freeze_candidates']:
            report['passed'] = False
        Path(a.report).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'passed': report['passed'], 'black_runs': report['black_runs'],
                          'allowed_black_runs': report['allowed_black_runs'],
                          'freeze_runs': report['freeze_runs'],
                          'freeze_candidates': report['freeze_candidates'],
                          'cadence_issues': len(report['cadence_issues']),
                          'jump_candidates': len(report['jumps']), 'report': a.report}))
        return 0 if report['passed'] else 1
    except (OSError, ValueError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f'qa_media: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
