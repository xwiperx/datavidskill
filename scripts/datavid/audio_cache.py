"""Atomic helpers for keeping normalized audio caches synchronized with their source."""
import os
import tempfile
import wave
from pathlib import Path


def invalidate_normalized_score(outdir):
    """Remove score.wav before replacing score_raw.wav with a new audio-only render."""
    score = Path(outdir) / 'score.wav'
    try:
        score.unlink()
    except FileNotFoundError:
        pass
    return score


def publish_raw_score(outdir, payload, sample_rate=44100, channels=2, sample_width=2,
                      expected_frames=None):
    """Validate and atomically publish interleaved PCM, invalidating its derived cache.

    `payload` is raw interleaved PCM bytes. The normalized score is invalidated before
    replacing the source so an interruption cannot leave a usable stale normalization.
    """
    directory = Path(outdir)
    directory.mkdir(parents=True, exist_ok=True)
    if (not isinstance(sample_rate, int) or sample_rate <= 0 or
            not isinstance(channels, int) or channels <= 0 or
            not isinstance(sample_width, int) or sample_width not in (1, 2, 3, 4)):
        raise ValueError('invalid WAV sample rate, channel count, or sample width')
    raw = bytes(payload)
    frame_bytes = channels * sample_width
    if not raw or len(raw) % frame_bytes:
        raise ValueError('PCM payload must contain complete, non-empty audio frames')
    frame_count = len(raw) // frame_bytes
    if expected_frames is not None and frame_count != expected_frames:
        raise ValueError(f'PCM frame count mismatch: expected {expected_frames}, got {frame_count}')

    fd, temp_path = tempfile.mkstemp(prefix='.score-', suffix='.tmp.wav', dir=directory)
    os.close(fd)
    final_path = directory / 'score_raw.wav'
    try:
        with wave.open(temp_path, 'wb') as output:
            output.setnchannels(channels)
            output.setsampwidth(sample_width)
            output.setframerate(sample_rate)
            output.writeframes(raw)
        with wave.open(temp_path, 'rb') as check:
            if (check.getnchannels() != channels or check.getsampwidth() != sample_width or
                    check.getframerate() != sample_rate or check.getnframes() != frame_count):
                raise RuntimeError('generated source WAV failed format/frame-count validation')
        invalidate_normalized_score(directory)
        os.replace(temp_path, final_path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return final_path
