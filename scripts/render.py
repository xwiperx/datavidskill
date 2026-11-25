#!/usr/bin/env python3
"""Render a datavid project.

  python3 render.py --project /path/to/project --stills 3 20 60
  python3 render.py --project /path/to/project --workers 6
"""
import argparse, os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, 'datavid')

ap = argparse.ArgumentParser()
ap.add_argument('--project', default='.')
ap.add_argument('--stills', nargs='*', type=float, help='timestamps (s) to render as PNG')
ap.add_argument('--audio-only', action='store_true')
ap.add_argument('--workers', type=int, default=6)
ap.add_argument('--chunk', type=int, default=300)
a = ap.parse_args()

proj = os.path.abspath(a.project)
os.environ['DATAVID_PROJECT'] = proj
sys.path.insert(0, PKG)

if a.stills is not None:
    import scene as S
    from PIL import Image
    outdir = os.path.join(proj, 'stills')
    os.makedirs(outdir, exist_ok=True)
    for t in a.stills:
        arr = S.render(t, int(t * 30))
        p = os.path.join(outdir, f'still_{t:07.2f}.png')
        Image.fromarray(arr).save(p)
        print(p, flush=True)
elif a.audio_only:
    subprocess.run([sys.executable, os.path.join(PKG, 'audio.py')], check=True,
                   env=dict(os.environ, DATAVID_PROJECT=proj))
else:
    import build
    build.run(workers=a.workers, chunk=a.chunk)
