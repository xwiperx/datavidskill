"""Safe parallel renderer: validated segment cache, atomic mux, no overwrites."""
import fcntl
import glob
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import wave
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
    """Hash every input that can change rendered frames, audio or output timing."""
    code_dir = os.path.dirname(os.path.abspath(__file__))
    paths = glob.glob(os.path.join(code_dir, '*.py'))
    paths += glob.glob(os.path.join(code_dir, 'fonts', '*'))
    paths += [os.path.join(os.path.dirname(code_dir), 'render.py')]
    paths += [os.path.join(ROOT, name) for name in
              ('config.json', 'data.json', 'image_sources.json')]
    try:
        with open(os.path.join(ROOT, 'image_sources.json'), encoding='utf-8') as f:
            manifest = json.load(f)
        paths += [os.path.join(ROOT, row['local_path']) for row in manifest
                  if row.get('local_path')]
    except (OSError, ValueError, TypeError, KeyError):
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


def _atomic_json(path, data):
    fd, tmp = tempfile.mkstemp(prefix='.signature-', suffix='.tmp', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def invalidate_stale_cache(force=False, chunk=CHUNK):
    """Invalidate changed inputs but only publish a signature after safe concat."""
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SEG, exist_ok=True)
    current = source_fingerprint(chunk=chunk)
    try:
        with open(SIGNATURE, encoding='utf-8') as f:
            previous = json.load(f).get('sha256')
    except (OSError, ValueError, AttributeError):
        previous = None
    if force or previous != current:
        stale = glob.glob(os.path.join(SEG, 'seg_*.mp4'))
        for path in stale:
            os.remove(path)
        for path in glob.glob(os.path.join(SEG, 'seg_*.tmp.mp4')):
            os.remove(path)
        for name in ('video_silent.mp4', 'segs.txt', 'score.wav', 'score_raw.wav'):
            path = os.path.join(OUT, name)
            if os.path.exists(path):
                os.remove(path)
        print(f'render inputs changed; invalidated {len(stale)} cached segments', flush=True)
    return current


def chunks_list(chunk=CHUNK):
    if chunk <= 0:
        raise ValueError('chunk must be a positive integer')
    return [(i, start, min(start + chunk, TOTAL))
            for i, start in enumerate(range(0, TOTAL, chunk))]


def _decode_ok(path):
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'null', '-'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return result.returncode == 0 and not result.stderr.strip()


def valid_segment(path, expected_frames):
    """Reject truncated, wrong-size, wrong-fps or undecodable segment cache entries."""
    if not os.path.isfile(path) or os.path.getsize(path) < 1024:
        return False
    try:
        probe = subprocess.run([
            'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate,nb_read_frames,codec_name',
            '-of', 'json', path], check=True, capture_output=True, text=True)
        stream = json.loads(probe.stdout)['streams'][0]
        if (int(stream['width']) != W or int(stream['height']) != H or
                stream['r_frame_rate'] != f'{FPS}/1' or
                int(stream['nb_read_frames']) != expected_frames or
                stream['codec_name'] != 'h264'):
            return False
        return _decode_ok(path)
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, TypeError):
        return False


def _temp_mp4(directory, prefix):
    fd, path = tempfile.mkstemp(prefix=prefix, suffix='.tmp.mp4', dir=directory)
    os.close(fd)
    return path


def work(args):
    idx, f0, f1 = args
    import scene as S
    path = os.path.join(SEG, f'seg_{idx:03d}.mp4')
    expected = f1 - f0
    if valid_segment(path, expected):
        return idx, expected, 0.0, 'cache'
    if os.path.exists(path):
        os.unlink(path)
    tmp = _temp_mp4(SEG, f'.seg_{idx:03d}-')
    crf = str(E.cfg('crf', 18))
    preset = E.cfg('preset', 'veryfast')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-an', '-c:v', 'libx264', '-preset', preset, '-crf', crf,
           '-pix_fmt', 'yuv420p', '-g', '60', '-keyint_min', '60', '-sc_threshold', '0',
           '-threads', '2', tmp]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    started = time.time()
    try:
        for fi in range(f0, f1):
            proc.stdin.write(S.render(fi / FPS, fi).tobytes())
        proc.stdin.close()
        error = proc.stderr.read().decode(errors='replace')[-1200:]
        code = proc.wait()
        if code:
            raise RuntimeError(f'ffmpeg failed on segment {idx}: {error}')
        if not valid_segment(tmp, expected):
            raise RuntimeError(f'segment {idx} failed frame-count/decode validation')
        os.replace(tmp, path)
    except BaseException:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return idx, expected, time.time() - started, 'rendered'


def valid_wav(path, duration):
    try:
        with wave.open(path, 'rb') as wav:
            expected = int(round(44100 * duration))
            return (wav.getnchannels() == 2 and wav.getsampwidth() == 2 and
                    wav.getframerate() == 44100 and abs(wav.getnframes() - expected) <= 1)
    except (OSError, wave.Error):
        return False


def _temp_wav(directory, prefix):
    fd, path = tempfile.mkstemp(prefix=prefix, suffix='.tmp.wav', dir=directory)
    os.close(fd)
    return path


def _ensure_score():
    raw = os.path.join(OUT, 'score_raw.wav')
    score = os.path.join(OUT, 'score.wav')
    if not valid_wav(raw, E.DUR):
        if os.path.exists(raw):
            os.unlink(raw)
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'audio.py')],
                       check=True, env=dict(os.environ, DATAVID_PROJECT=ROOT))
    if not valid_wav(raw, E.DUR):
        raise RuntimeError('generated source WAV failed duration/format validation')
    if valid_wav(score, E.DUR):
        return score
    if os.path.exists(score):
        os.unlink(score)
    tmp = _temp_wav(OUT, '.audio-')
    try:
        subprocess.run([
            'ffmpeg', '-y', '-hide_banner', '-nostdin', '-loglevel', 'error',
            '-i', raw, '-af', 'loudnorm=I=-14:TP=-2:LRA=11',
            '-ar', '44100', '-ac', '2', '-t', f'{E.DUR:.6f}',
            '-c:a', 'pcm_s16le', tmp], check=True)
        if not valid_wav(tmp, E.DUR):
            raise RuntimeError('loudness-normalized WAV failed duration/format validation')
        os.replace(tmp, score)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return score


def _video_ok(path, expected_frames):
    try:
        p = subprocess.run([
            'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate,nb_read_frames',
            '-of', 'json', path], check=True, capture_output=True, text=True)
        s = json.loads(p.stdout)['streams'][0]
        return (int(s['width']) == W and int(s['height']) == H and
                s['r_frame_rate'] == f'{FPS}/1' and
                int(s['nb_read_frames']) == expected_frames and _decode_ok(path))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, TypeError):
        return False


def _next_final_path():
    configured = os.path.basename(str(E.cfg('output_name', 'video.mp4')))
    stem, ext = os.path.splitext(configured)
    if ext.lower() != '.mp4':
        raise ValueError('output_name must be an .mp4 filename')
    candidate = os.path.join(OUT, configured)
    version = 2
    while os.path.lexists(candidate):
        candidate = os.path.join(OUT, f'{stem}_v{version}{ext}')
        version += 1
    return candidate


def run(workers=6, chunk=CHUNK, audio=True, mux=True, force=False):
    if not isinstance(workers, int) or workers <= 0:
        raise ValueError('workers must be a positive integer')
    if not isinstance(chunk, int) or chunk <= 0:
        raise ValueError('chunk must be a positive integer')
    if E.N <= 0 or TOTAL <= 0:
        raise ValueError('project has no frames or ranked items')
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, '.render.lock'), 'a+') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('another render is already active for this project') from exc
        fingerprint = invalidate_stale_cache(force=force, chunk=chunk)
        chunks = chunks_list(chunk)
        started = time.time()
        with Pool(workers) as pool:
            done = 0
            for idx, count, seconds, state in pool.imap_unordered(work, chunks):
                done += count
                print(f'[{time.time() - started:6.1f}s] chunk {idx:3d} '
                      f'({count}f in {seconds:.1f}s; {state}) {done}/{TOTAL}', flush=True)
        list_tmp = os.path.join(OUT, '.segs.txt.tmp')
        with open(list_tmp, 'w', encoding='utf-8') as f:
            for idx, _, _ in chunks:
                f.write(f"file '{os.path.join(SEG, f'seg_{idx:03d}.mp4')}\n")
        lst = os.path.join(OUT, 'segs.txt')
        os.replace(list_tmp, lst)
        silent = os.path.join(OUT, 'video_silent.mp4')
        tmp_silent = _temp_mp4(OUT, '.video-')
        try:
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0',
                            '-i', lst, '-c', 'copy', '-movflags', '+faststart', tmp_silent], check=True)
            if not _video_ok(tmp_silent, TOTAL):
                raise RuntimeError('concatenated silent video failed frame-count/decode validation')
            os.replace(tmp_silent, silent)
        finally:
            if os.path.exists(tmp_silent):
                os.unlink(tmp_silent)
        _atomic_json(SIGNATURE, {'sha256': fingerprint})
        print('concat validated', round(os.path.getsize(silent) / 1e6, 1), 'MB', flush=True)
        if not (audio and mux):
            return silent
        wav_path = _ensure_score()
        final = _next_final_path()
        temp_final = _temp_mp4(OUT, '.final-')
        try:
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', silent, '-i', wav_path,
                            '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
                            '-c:a', 'aac', '-b:a', '192k', '-ar', '44100',
                            '-shortest', '-movflags', '+faststart', temp_final], check=True)
            if not _video_ok(temp_final, TOTAL):
                raise RuntimeError('final mux failed frame-count/decode validation')
            os.link(temp_final, final)
        finally:
            if os.path.exists(temp_final):
                os.unlink(temp_final)
        print('FINAL', final, round(os.path.getsize(final) / 1e6, 1), 'MB', flush=True)
        return final


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--chunk', type=int, default=CHUNK)
    parser.add_argument('--force', action='store_true', help='discard cached segments and render all frames')
    args = parser.parse_args()
    if args.workers <= 0 or args.chunk <= 0:
        parser.error('--workers and --chunk must be positive integers')
    run(workers=args.workers, chunk=args.chunk, force=args.force)
