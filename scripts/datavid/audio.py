"""Procedural cinematic score for the film. No samples, no external audio."""
import os
import tempfile
import numpy as np
import wave
import engine as E

SR = 44100
DUR = E.DUR
NS = int(SR * DUR)
rng = np.random.default_rng(42)

L = np.zeros(NS, np.float32)
R = np.zeros(NS, np.float32)


def add(sig, t0, gain=1.0, pan=0.0):
    i0 = int(t0 * SR)
    if i0 >= NS or i0 < 0:
        return
    n = min(len(sig), NS - i0)
    if n <= 0:
        return
    gl = gain * np.sqrt(0.5 * (1 - pan))
    gr = gain * np.sqrt(0.5 * (1 + pan))
    L[i0:i0 + n] += sig[:n] * gl
    R[i0:i0 + n] += sig[:n] * gr


def env_adsr(n, a=0.01, d=0.2, s=0.6, r=0.4):
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    a_n = max(1, min(a_n, n))
    d_n = max(1, min(d_n, n - a_n))
    r_n = max(1, min(r_n, n - a_n - d_n))
    s_n = max(0, n - a_n - d_n - r_n)
    e = np.concatenate([
        np.linspace(0, 1, a_n, endpoint=False),
        np.linspace(1, s, d_n, endpoint=False),
        np.full(s_n, s),
        np.linspace(s, 0, r_n),
    ])
    if len(e) < n:
        e = np.pad(e, (0, n - len(e)))
    return e[:n]


def lowpass_fft(x, cutoff, order=2):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    resp = 1.0 / (1.0 + (f / max(1.0, cutoff)) ** (2 * order))
    return np.fft.irfft(X * resp, n).astype(np.float32)


def highpass_fft(x, cutoff, order=2):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    resp = 1.0 - 1.0 / (1.0 + (f / max(1.0, cutoff)) ** (2 * order))
    return np.fft.irfft(X * resp, n).astype(np.float32)


def bandpass_fft(x, lo, hi, order=2):
    return highpass_fft(lowpass_fft(x, hi, order), lo, order)


def saw(freq, n, phase=0.0):
    t = np.arange(n, dtype=np.float32) / SR
    ph = t * freq + phase
    return (2.0 * (ph - np.floor(ph + 0.5))).astype(np.float32)


def sine(freq, n, phase=0.0):
    t = np.arange(n, dtype=np.float32) / SR
    return np.sin(2 * np.pi * freq * t + phase).astype(np.float32)


def noise(n):
    return rng.normal(0, 1, n).astype(np.float32)


# ------------------------------------------------------------------ material
A2, C3, D3, E3, F3, G3, A3, B3, C4, D4, E4, F4, G4, A4 = (
    110.0, 130.81, 146.83, 164.81, 174.61, 196.0, 220.0, 246.94, 261.63,
    293.66, 329.63, 349.23, 392.0, 440.0)

CHORDS = [
    (A2, [A2, E3, A3, C4, E4]),
    (F3, [F3 * 0.5, C3, F3, A3, C4]),
    (C3, [C3, G3, C4, E4, G4]),
    (G3, [G3 * 0.5, D3, G3, B3, D4]),
]


def pad_chord(freqs, dur, gain=0.16, bright=1400):
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    for f in freqs:
        for det in (-0.12, 0.0, 0.11):
            out += saw(f * (1 + det / 100.0), n, rng.random()) * 0.33
    out = lowpass_fft(out, bright)
    out *= env_adsr(n, a=2.4, d=1.2, s=0.72, r=2.2)
    return out * gain


def pluck(freq, dur=0.9, gain=0.12):
    n = int(dur * SR)
    s = np.zeros(n, np.float32)
    for k, amp in [(1, 1.0), (2, 0.42), (3, 0.20), (4, 0.09)]:
        s += sine(freq * k, n) * amp
    s *= np.exp(-np.arange(n) / (SR * 0.16))
    s *= env_adsr(n, a=0.004, d=0.05, s=1.0, r=0.02)
    return s * gain


def sub_pulse(dur=0.42, gain=0.42):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = 74 * np.exp(-t * 7.0) + 38
    ph = np.cumsum(f) / SR
    s = np.sin(2 * np.pi * ph) * np.exp(-t * 9.0)
    s *= env_adsr(n, a=0.004, d=0.08, s=0.5, r=0.16)
    return s.astype(np.float32) * gain


def tick(gain=0.10, pitch=2100):
    n = int(0.09 * SR)
    s = bandpass_fft(noise(n), 1800, 5200) * np.exp(-np.arange(n) / (SR * 0.012))
    s += sine(pitch, n) * np.exp(-np.arange(n) / (SR * 0.02)) * 0.35
    return s * gain


def boom(gain=0.7):
    n = int(2.6 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = 58 * np.exp(-t * 1.6) + 30
    ph = np.cumsum(f) / SR
    s = np.sin(2 * np.pi * ph) * np.exp(-t * 1.5)
    s += lowpass_fft(noise(n), 220) * np.exp(-t * 5.0) * 0.35
    return s.astype(np.float32) * gain


def whoosh(dur=1.6, gain=0.10, lo=300, hi=2400):
    n = int(dur * SR)
    s = noise(n)
    s = bandpass_fft(s, lo, hi)
    e = np.sin(np.linspace(0, np.pi, n)) ** 2
    return (s * e * gain).astype(np.float32)


def shimmer(dur=4.0, gain=0.09):
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    for f in [A4, C4 * 2, E4 * 2, A4 * 2]:
        out += sine(f, n, rng.random() * 6)
    out *= (0.5 + 0.5 * np.sin(np.linspace(0, 18 * np.pi, n)))
    out *= env_adsr(n, a=1.2, d=0.6, s=0.4, r=2.0)
    return (out * gain).astype(np.float32)


# ------------------------------------------------------------------ arrangement
BPM = 76.0
BEAT = 60.0 / BPM
BAR = BEAT * 4
T_INTRO = E.T_INTRO
T_FINALE = E.T_COUNT_END
T_END = E.T_ENDCARD

# intro drone
n = int(T_INTRO * SR)
drone = lowpass_fft(saw(A2 * 0.5, n, 0.2) + saw(A2 * 0.5 * 1.005, n, 0.7), 260) * 0.5
drone += sine(A2, n) * 0.25
drone *= env_adsr(n, a=3.0, d=1.0, s=0.75, r=3.0)
add(drone, 0.0, 0.30)
add(boom(0.55), 0.15)
add(whoosh(2.2, 0.07, 200, 900), 4.6)

# pad bed from intro to finale
t = 0.0
ci = 0
while t < T_FINALE + 1.0:
    root, freqs = CHORDS[ci % 4]
    dur = BAR * 2
    bright = 900 + 500 * min(1.0, t / 90.0)
    g = 0.135 if t > 4 else 0.10
    add(pad_chord(freqs, dur + 0.5, gain=g, bright=bright), max(0.0, t), 1.0, pan=(-0.2 if ci % 2 else 0.2))
    t += dur
    ci += 1

# rhythmic section
t = T_INTRO
beat_i = 0
while t < T_FINALE - 0.2:
    add(sub_pulse(), t, 1.0)
    if beat_i % 2 == 1:
        add(tick(0.055), t, 1.0, pan=0.25)
    # arpeggio enters at 18s
    if t > 18:
        root, freqs = CHORDS[int((t - T_INTRO) / (BAR * 2)) % 4]
        arp = [freqs[1] * 2, freqs[2] * 2, freqs[3] * 2, freqs[2] * 2]
        for k in range(4):
            tt = t + k * BEAT / 4
            if tt >= T_FINALE - 0.2:
                break
            fade_in = min(1.0, (t - 18) / 14.0)
            add(pluck(arp[k] * (2 if (beat_i // 8) % 2 else 1), 0.75, 0.055 * fade_in), tt, 1.0,
                pan=(-0.45 if k % 2 else 0.45))
    t += BEAT
    beat_i += 1

# bar ticks: one per person (1.46s)
bar_dur = E.PER_BAR
for i in range(E.N):
    tt = 12.0 + i * bar_dur
    acc = 1.6 if (i + 1) % 10 == 0 else 1.0
    add(tick(0.035 * acc, 2400 if (i + 1) % 10 else 1700), tt, 1.0, pan=0.1)
    if (i + 1) % 10 == 0:
        add(whoosh(1.1, 0.055, 500, 2600), tt - 0.55, 1.0, pan=-0.2)

# decade swells
for d in range(1, 10):
    tt = 12.0 + d * 10 * bar_dur
    add(shimmer(3.0, 0.05), tt - 1.2)

# finale
add(boom(0.85), T_FINALE - 0.1)
n = int(10.0 * SR)
final_pad = np.zeros(n, np.float32)
for f in [A2, E3, A3, C4, E4, A4]:
    final_pad += saw(f, n, rng.random()) * 0.16
final_pad = lowpass_fft(final_pad, 2200)
final_pad *= env_adsr(n, a=1.6, d=1.0, s=0.65, r=4.0)
add(final_pad, T_FINALE, 0.34)
add(shimmer(6.0, 0.10), T_FINALE + 0.4)
add(whoosh(2.6, 0.08, 150, 1600), T_FINALE - 1.8)

# end card
n = int(9.0 * SR)
end = np.zeros(n, np.float32)
for f in [A2, E3, A3, C4, E4]:
    end += sine(f, n, rng.random() * 3) * 0.2
end *= env_adsr(n, a=1.4, d=2.0, s=0.5, r=5.0)
add(end, T_END, 0.26)
add(boom(0.4), T_END)

# ------------------------------------------------------------------ reverb + master
def reverb(x, decay=2.0, mix=0.28):
    n_ir = int(decay * SR)
    ir = rng.normal(0, 1, n_ir).astype(np.float32)
    ir *= np.exp(-np.arange(n_ir) / (SR * decay / 4.0))
    ir[:int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
    ir = lowpass_fft(ir, 5000)
    ir /= np.sqrt((ir ** 2).sum())
    m = len(x) + n_ir
    nfft = 1 << (m - 1).bit_length()
    Y = np.fft.rfft(x, nfft) * np.fft.rfft(ir, nfft)
    wet = np.fft.irfft(Y, nfft)[:len(x)].astype(np.float32)
    return x * (1 - mix) + wet * mix


L = reverb(L, 2.4, 0.30)
R = reverb(R, 2.6, 0.30)

# gentle high-shelf lift and low cut
L = highpass_fft(L, 28)
R = highpass_fft(R, 28)

# fade in/out
fade = np.ones(NS, np.float32)
fade[:int(1.2 * SR)] = np.linspace(0, 1, int(1.2 * SR))
tail = np.linspace(1, 0, int(5.0 * SR)) ** 1.4
fade[-len(tail):] = tail
L *= fade
R *= fade

peak = max(np.abs(L).max(), np.abs(R).max())
L = L / peak * 0.88
R = R / peak * 0.88

out = np.stack([L, R], axis=1)
out16 = (np.clip(out, -1, 1) * 32767).astype(np.int16)

outdir = os.path.join(E.ROOT, 'out')
os.makedirs(outdir, exist_ok=True)
fd, tmp = tempfile.mkstemp(prefix='.score-', suffix='.tmp.wav', dir=outdir)
os.close(fd)
try:
    with wave.open(tmp, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(out16.tobytes())
    with wave.open(tmp, 'rb') as w:
        if (w.getnchannels() != 2 or w.getsampwidth() != 2 or
                w.getframerate() != SR or w.getnframes() != NS):
            raise RuntimeError('generated score WAV failed validation')
    os.replace(tmp, os.path.join(outdir, 'score_raw.wav'))
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)

rms = np.sqrt((out ** 2).mean())
print('wrote score_raw.wav', out.shape, 'peak', round(float(np.abs(out).max()), 3), 'rms', round(float(rms), 4))
