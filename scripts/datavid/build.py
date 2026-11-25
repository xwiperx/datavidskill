"""Parallel render -> x264 segments -> concat -> mux score."""
import os, sys, time, subprocess, argparse, hashlib, json, glob
from multiprocessing import Pool

import engine as E

W, H, FPS = E.W, E.H, E.FPS
TOTAL = int(round(E.FPS * E.DUR))
ROOT = E.ROOT
OUT = os.path.join(ROOT, 'out')
SEG = os.path.join(OUT, 'seg')
CHUNK = 300
SIGNATURE = os.path.join(OUT, '.render_signature.json')


def source_fingerprint(chunk=CHUNK):
    """Hash every input that can change a rendered frame or the score."""
    code_dir = os.path.dirname(os.path.abspath(__file__))
    paths = glob.glob(os.path.join(code_dir, '*.py'))
    paths += glob.glob(os.path.join(code_dir, 'fonts', '*'))
    paths += [os.path.join(os.path.dirname(code_dir), 'render.py')]
    paths += [os.path.join(ROOT, name) for name in
              ('config.json', 'data.json', 'image_sources.json')]
    try:
        manifest = json.load(open(os.path.join(ROOT, 'image_sources.json')))
        paths += [os.path.join(ROOT, row['local_path']) for row in manifest
                  if row.get('local_path')]
    except (OSError, ValueError, TypeError):
        pass
    digest = hashlib.sha256()
    digest.update(f'chunk={chunk};frames={TOTAL};fps={FPS}'.encode())
    for path in sorted(set(paths)):
        if not os.path.isfile(path):
            digest.update(('MISSING:' + os.path.relpath(path, ROOT)).encode())
            continue
        digest.update(os.path.relpath(path, ROOT).encode())
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                digest.update(block)
    return digest.hexdigest()


def invalidate_stale_cache(force=False, chunk=CHUNK):
    """Never concatenate segments rendered from a different code/data version."""
    current = source_fingerprint(chunk=chunk)
    previous = None
    try:
        previous = json.load(open(SIGNATURE)).get('sha256')
    except (OSError, ValueError, AttributeError):
        pass
    if force or previous != current:
        stale = glob.glob(os.path.join(SEG, 'seg_*.mp4'))
        for path in stale:
            os.remove(path)
        for name in ('video_silent.mp4', 'segs.txt', 'score.wav'):
            path = os.path.join(OUT, name)
            if os.path.exists(path):
                os.remove(path)
        print(f'render inputs changed; invalidated {len(stale)} cached segments', flush=True)
    os.makedirs(OUT, exist_ok=True)
    tmp = SIGNATURE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump({'sha256': current}, f)
    os.replace(tmp, SIGNATURE)


def chunks_list(chunk=CHUNK):
    return [(i, s, min(s + chunk, TOTAL)) for i, s in enumerate(range(0, TOTAL, chunk))]


def work(args):
    idx, f0, f1 = args
    import scene as S
    path = os.path.join(SEG, f'seg_{idx:03d}.mp4')
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return idx, f1 - f0, 0.0
    crf = str(E.cfg('crf', 18))
    preset = E.cfg('preset', 'veryfast')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-an', '-c:v', 'libx264', '-preset', preset, '-crf', crf,
           '-pix_fmt', 'yuv420p', '-g', '60', '-keyint_min', '60', '-sc_threshold', '0',
           '-threads', '2', path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    t0 = time.time()
    try:
        for fi in range(f0, f1):
            arr = S.render(fi / FPS, fi)
            p.stdin.write(arr.tobytes())
    finally:
        p.stdin.close()
        err = p.stderr.read().decode()[-800:]
        p.wait()
    if p.returncode != 0:
        raise RuntimeError(f'ffmpeg failed on {idx}: {err}')
    return idx, f1 - f0, time.time() - t0


def run(workers=6, chunk=CHUNK, audio=True, mux=True, force=False):
    invalidate_stale_cache(force=force, chunk=chunk)
    os.makedirs(SEG, exist_ok=True)
    chunks = chunks_list(chunk)
    t0 = time.time()
    with Pool(workers) as pool:
        done = 0
        for idx, n, dt in pool.imap_unordered(work, chunks):
            done += n
            print(f'[{time.time() - t0:6.1f}s] chunk {idx:3d} ({n}f in {dt:.1f}s) {done}/{TOTAL}',
                  flush=True)

    lst = os.path.join(OUT, 'segs.txt')
    with open(lst, 'w') as f:
        for idx, _, _ in chunks:
            f.write(f"file '{os.path.join(SEG, f'seg_{idx:03d}.mp4')}'\n")
    silent = os.path.join(OUT, 'video_silent.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
                    '-i', lst, '-c', 'copy', '-movflags', '+faststart', silent], check=True)
    print('concat done', round(os.path.getsize(silent) / 1e6, 1), 'MB', flush=True)
    if not (audio and mux):
        return silent

    wav = os.path.join(OUT, 'score.wav')
    if not os.path.exists(wav):
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'audio.py')],
                       check=True, env=dict(os.environ, DATAVID_PROJECT=ROOT))
    final = os.path.join(OUT, E.cfg('output_name', 'video.mp4'))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', silent, '-i', wav,
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '44100',
                    '-shortest', '-movflags', '+faststart', final], check=True)
    print('FINAL', final, round(os.path.getsize(final) / 1e6, 1), 'MB', flush=True)
    return final


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--chunk', type=int, default=CHUNK)
    ap.add_argument('--force', action='store_true', help='discard cached segments and render all frames')
    a = ap.parse_args()
    run(workers=a.workers, chunk=a.chunk, force=a.force)
