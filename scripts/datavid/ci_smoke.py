#!/usr/bin/env python3
"""Render a short isolated production-path clip and run media/OCR/diff QA."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True)
    ap.add_argument('--report-dir', required=True)
    a = ap.parse_args(argv)
    repo = Path(__file__).resolve().parents[2]
    out = Path(a.output).resolve()
    report_dir = Path(a.report_dir).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(out):
        print(f'ci_smoke: refusing to overwrite existing output: {out}', file=sys.stderr)
        return 2
    fd, temp_name = tempfile.mkstemp(prefix='.' + out.stem + '-', suffix='.tmp.mp4', dir=out.parent)
    os.close(fd)
    temp_video = Path(temp_name)
    try:
        with tempfile.TemporaryDirectory(prefix='datavid-ci-project-') as td:
            project = Path(td)
            config = json.loads((repo / 'templates' / 'config.json').read_text(encoding='utf-8'))
            config.update({'brand': 'DATAVID CI', 'title_top': 'QA SMOKE',
                           'title_big': 'RENDER TEST', 'lower_kicker': 'THREE TEST ITEMS',
                           'duration': 35.0, 'seconds_per_item': 0.34,
                           'output_name': 'ci-smoke.mp4', 'geometry': 'beveled_box',
                           'material': 'solid'})
            (project / 'config.json').write_text(json.dumps(config), encoding='utf-8')
            data = {'items': [
                {'name': 'ALPHA TEST', 'value': 12.0, 'category': 'QA', 'meta': 'Fixture one'},
                {'name': 'BETA TEST', 'value': 25.0, 'category': 'QA', 'meta': 'Fixture two'},
                {'name': 'GAMMA TEST', 'value': 60.0, 'category': 'QA', 'meta': 'Fixture three'},
            ], 'total': 97.0}
            (project / 'data.json').write_text(json.dumps(data), encoding='utf-8')
            (project / 'image_sources.json').write_text('[]\n', encoding='utf-8')
            os.environ['DATAVID_PROJECT'] = str(project)
            sys.path.insert(0, str(repo / 'scripts' / 'datavid'))
            import engine as E
            import scene as S
            import numpy as np
            frame_count = 30
            start_time = E.T_INTRO + 0.03
            cmd = ['ffmpeg', '-y', '-hide_banner', '-nostdin', '-loglevel', 'error',
                   '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-video_size', f'{E.W}x{E.H}',
                   '-framerate', str(E.FPS), '-i', 'pipe:0',
                   '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo',
                   '-map', '0:v:0', '-map', '1:a:0', '-frames:v', str(frame_count),
                   '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32',
                   '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '64k', '-ar', '44100',
                   '-shortest', '-movflags', '+faststart', str(temp_video)]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE)
            try:
                for i in range(frame_count):
                    frame = S.render(start_time + i / E.FPS,
                                     int(round((start_time + i / E.FPS) * E.FPS)))
                    proc.stdin.write(np.ascontiguousarray(frame).tobytes())
                proc.stdin.close()
                stderr = proc.stderr.read().decode(errors='replace')
                code = proc.wait()
                if code:
                    raise RuntimeError(f'FFmpeg smoke encode failed ({code}): {stderr[-1200:]}')
            except BaseException:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                raise
            if not temp_video.is_file() or temp_video.stat().st_size < 4096:
                raise RuntimeError('smoke output is missing or implausibly small')
            from qa_media import inspect_video
            from qa_visual import inspect_media, validate_layout
            from qa_compare import compare_videos
            media = inspect_video(temp_video, expected_fps=30, edge_ignore_seconds=0.0,
                                  freeze_min_seconds=0.8)
            (report_dir / 'media.json').write_text(json.dumps(media, indent=2) + '\n')
            if not media['passed']:
                raise RuntimeError(f'media QA failed: {media}')

            visual = inspect_media(video=str(temp_video), every_seconds=0.32, min_words=1,
                                   expected=())
            (report_dir / 'ocr.json').write_text(json.dumps(visual, indent=2, ensure_ascii=False) + '\n')
            if not visual['passed'] or visual['sample_count'] < 2:
                raise RuntimeError(f'OCR QA failed: {visual}')

            layout_path = repo / 'templates' / 'qa_layout.json'
            layout = validate_layout(layout_path)
            if not layout['passed']:
                raise RuntimeError(f'layout-zone QA failed: {layout}')
            (report_dir / 'layout.json').write_text(json.dumps(layout, indent=2) + '\n')
            layout_box_count = len(json.loads(layout_path.read_text(encoding='utf-8'))['boxes'])

            comparison, sheet = compare_videos(temp_video, temp_video, fractions=(0.2, 0.75))
            (report_dir / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n')
            sheet.save(report_dir / 'comparison.jpg', quality=85)
            for row in comparison['samples']:
                if row['mae'] > 0.01 or row['ssim_8x8'] < 0.999:
                    raise RuntimeError(f'self-comparison QA failed: {row}')
            digest = hashlib.sha256(temp_video.read_bytes()).hexdigest()
            summary = {'passed': True, 'output': str(out), 'bytes': temp_video.stat().st_size,
                       'sha256': digest, 'frame_count': media['frame_count'],
                       'fps': media['fps'], 'ocr_samples': visual['sample_count'],
                       'layout_boxes': layout_box_count,
                       'qa_reports': str(report_dir)}
            (report_dir / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
            # Publish only after media, OCR, declared-layout, and self-comparison QA pass.
            # A hard link is atomic and cannot overwrite a concurrently-created output.
            os.link(temp_video, out)
            print(json.dumps(summary))
            return 0
    except Exception as exc:
        print(f'ci_smoke: {exc}', file=sys.stderr)
        return 1
    finally:
        if temp_video.exists():
            temp_video.unlink()


if __name__ == '__main__':
    raise SystemExit(main())
