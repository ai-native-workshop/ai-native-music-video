#!/usr/bin/env python3
"""analyze_audio.py: measure the song once, so the film page never has to read audio.

  python3 -I tools/analyze_audio.py [--audio=assets/song.mp3] [--bpm-range=60,180] [--fps=30] [--track] [--js] [--plot=out/check/audio.png]

Run from the project root (or pass --root). Reads the song (the first audio file in assets/ unless --audio is given) and
writes assets/analysis/audio.json (and src/gen/song.js with --js, for pages that import it):
  bpm, beat, first      a constant beat grid fitted to the onsets (sequenced pop stays within a few ms of it from start to end)
  bar0                  time of a bar line, found from bass-note changes and kicks; bars are 4 beats
  level, vocal, bass, air, width   per-frame curves at --fps, each 0..1: loudness, centre-channel voice band, low band,
                        high band, stereo width (side against mid)
  onset, kick, snare    attacks, 0..1: whole band, low band (kick drum, bass notes), upper band (snare, claps, hats)
  beats                 (with --track) beat times from a dynamic-programming tracker whose phase may drift: use them instead
                        of the grid when the printed drift is large or the phase shifts between sections (rubato ballads)
It also prints the tempo candidates, the drift from the grid and a table of 2-bar averages for finding the song's sections.
If the chosen tempo is half or double the real one, run again with a narrower --bpm-range.
Needs ffmpeg, numpy and scipy (matplotlib only for --plot). Prints numbers only.
"""
import argparse, json, pathlib, subprocess
import numpy as np
from scipy.ndimage import maximum_filter1d, uniform_filter1d
from scipy.signal import correlate, find_peaks, stft

SR, NFFT, HOP = 22050, 2048, 256
FR = SR / HOP  # analysis frames per second
AUDIO_EXT = ('.wav', '.flac', '.m4a', '.mp3', '.aac', '.ogg', '.opus')


def load(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2)


def spectrum(sig):
    f, t, Z = stft(sig, fs=SR, nperseg=NFFT, noverlap=NFFT - HOP, boundary=None, padded=False)
    return f, t, np.abs(Z).astype(np.float32)


def band_db(S, f, lo, hi, n=40):
    """Power in n log-spaced bands between lo and hi Hz, in dB below the loudest cell (floor -80)."""
    band = np.digitize(f, np.geomspace(lo, hi, n + 1)) - 1
    P = np.stack([(S[band == b] ** 2).sum(axis=0) for b in range(n) if (band == b).any()])
    db = 10 * np.log10(P + 1e-12)
    return np.maximum(db - db.max(), -80)


def onset_env(db):
    """Mean positive rise in dB per frame, with the slow (0.5 s) trend removed."""
    d = np.maximum(np.diff(db, axis=1, prepend=db[:, :1]), 0).mean(axis=0)
    return d - uniform_filter1d(d, int(0.5 * FR))


def tempo_candidates(env, lo=45, hi=190, k=6):
    e = np.maximum(env, 0)
    ac = correlate(e - e.mean(), e - e.mean(), mode='full', method='fft')[len(e) - 1:]
    a, b = int(FR * 60 / hi), int(FR * 60 / lo)
    pk, _ = find_peaks(ac[a:b + 1])
    return [60 * FR / (p + a) for p in pk[np.argsort(ac[a:b + 1][pk])[::-1][:k]]]


def fit_grid(env, t, bpm0):
    """Constant grid (bpm, first beat time) that maximises the mean onset strength on the beats."""
    e = np.maximum(env, 0)
    def search(bpms, ph_step):
        best = (-1.0, 0.0, 0.0)
        for bpm in bpms:
            P = 60 / bpm
            ph = np.arange(0, P, ph_step)
            s = np.interp(t[0] + ph[:, None] + P * np.arange(int((t[-1] - t[0]) / P) - 1)[None, :], t, e).mean(axis=1)
            j = int(s.argmax())
            if s[j] > best[0]: best = (float(s[j]), float(bpm), float(t[0] + ph[j]))
        return best
    _, bpm, _ = search(np.arange(bpm0 - 1.5, bpm0 + 1.5, 0.02), 0.01)
    return search(np.arange(bpm - 0.04, bpm + 0.04, 0.001), 0.002)


def drift(env, t, beats, win=16):
    """Per window of `win` beats: the local shift (s) that best fits the onsets, i.e. how far the song strays from the grid."""
    e, shifts, out = np.maximum(env, 0), np.arange(-0.12, 0.1201, 0.004), []
    for i in range(0, len(beats) - win, win // 2):
        s = np.interp(beats[i:i + win][None, :] + shifts[:, None], t, e).sum(axis=1)
        out.append((float(beats[i]), float(shifts[s.argmax()])))
    return out


def track_beats(env, t, P, tight=120.0):
    """Beat times by dynamic programming (after Ellis 2007): strong onsets, spaced about P apart, phase free to shift."""
    e = np.maximum(env, 0); e = e / (e.std() + 1e-9)
    n, period = len(e), P * FR
    lo, hi = int(round(period * 0.5)), int(round(period * 2))
    score, back = e.copy(), np.full(n, -1)
    pen = -tight * np.log(np.arange(lo, hi + 1) / period) ** 2
    for i in range(hi, n):
        cand = score[i - hi:i - lo + 1][::-1] + pen          # predecessors i-lo .. i-hi
        j = int(cand.argmax()); score[i] = e[i] + cand[j]; back[i] = i - lo - j
    i = int(score[-int(period * 2):].argmax()) + n - int(period * 2); out = []
    while i >= 0: out.append(t[i]); i = back[i]
    return np.array(out[::-1])


def norm01(x, lo=5, hi=99.5):
    a, b = np.percentile(x, [lo, hi])
    return np.clip((x - a) / (b - a), 0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.', help='project folder (default: the current directory)')
    ap.add_argument('--audio', default=None, help='song file, relative to the root (default: the first audio file in assets/)')
    ap.add_argument('--bpm-range', default='60,180', help='plausible tempo range used to pick among candidates')
    ap.add_argument('--fps', type=int, default=30, help='frame rate of the curves (use the film\'s)')
    ap.add_argument('--track', action='store_true', help='also track beats with a drifting phase (writes "beats")')
    ap.add_argument('--js', action='store_true', help='also write src/gen/song.js (export const SONG = ...)')
    ap.add_argument('--plot', default=None)
    a = ap.parse_args()
    ROOT, FPS = pathlib.Path(a.root).resolve(), a.fps
    if a.audio is None:
        found = sorted(p for p in (ROOT / 'assets').glob('*') if p.suffix.lower() in AUDIO_EXT)
        if not found: raise SystemExit('no audio file in assets/: put the song there or pass --audio')
        a.audio = found[0].relative_to(ROOT).as_posix()

    x = load(ROOT / a.audio)
    dur = len(x) / SR
    mid, side = x.mean(axis=1), (x[:, 0] - x[:, 1]) / 2
    f, t, S = spectrum(mid)
    _, _, Sside = spectrum(side)
    V = np.maximum(S - Sside, 0)          # centre minus sides: mostly the lead voice (plus kick, snare and bass)
    full = onset_env(band_db(S, f, 60, 8000))
    low = np.maximum(onset_env(band_db(S, f, 40, 160, 12)), 0)
    high = np.maximum(onset_env(band_db(S, f, 1200, 9000, 24)), 0)
    print(f'{a.audio}: duration {dur:.3f} s')

    lo, hi = map(float, a.bpm_range.split(','))
    fits = [fit_grid(full, t, bpm0) for bpm0 in tempo_candidates(full)]
    for s_, bpm_, b_ in sorted(fits, key=lambda v: -v[0]):
        print(f'  tempo candidate {bpm_:8.3f} BPM  score {s_:.4f}' + ('' if lo <= bpm_ <= hi else '  (outside --bpm-range)'))
    inside = [ft for ft in fits if lo <= ft[1] <= hi]
    if not inside: raise SystemExit(f'no tempo candidate inside --bpm-range {a.bpm_range}: widen it')
    _, bpm, b0 = max(inside, key=lambda v: v[0])
    P = 60 / bpm
    b0 -= P * np.floor(b0 / P)             # first grid point at or after 0
    beats = b0 + P * np.arange(int((dur - b0) / P) + 1)
    sh = np.array([d[1] for d in drift(full, t, beats)])
    print(f'tempo {bpm:.3f} BPM (beat {P:.4f} s, bar {4 * P:.4f} s), first grid point {b0:.3f} s; drift from the grid: median {np.median(np.abs(sh)) * 1000:.0f} ms, max {np.abs(sh).max() * 1000:.0f} ms')
    if np.abs(sh).max() > 0.04:
        print('  the song strays from a constant grid: cut on measured times (the lyrics, the accents), and consider --track')

    # Which beat starts the bar? The bass note changes on the bar line, and the kick is strongest there.
    fb = (f >= 40) & (f <= 260)
    def low_shape(tt): return np.log1p(S[fb][:, np.searchsorted(t, tt):np.searchsorted(t, tt + P * 0.9)].mean(axis=1) + 1e-9)
    change = np.zeros(4); kickc = np.zeros(4); cnt = np.zeros(4)
    for i, b in enumerate(beats[4:-4], start=4):
        va, vb = low_shape(b - P), low_shape(b)
        if not (np.isfinite(va).all() and np.isfinite(vb).all()) or va.size == 0: continue
        c = 1 - float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9))
        k = float(low[(t >= b - 0.04) & (t <= b + 0.04)].max())
        change[i % 4] += c; kickc[i % 4] += k; cnt[i % 4] += 1
    change, kickc = change / cnt, kickc / cnt
    print('per beat class (index mod 4):  bass-note change', np.round(change / change.max(), 2), '  low attack', np.round(kickc / kickc.max(), 2))
    phase = int(np.argmax(change / change.max() + 0.5 * kickc / kickc.max()))
    bar0 = float(beats[phase])
    print(f'bar lines on beat class {phase}: bar0 = {bar0:.3f} s (check it by ear or against the lyrics; a song in 3/4 or 6/8 needs another bar length)')

    n = int(np.ceil(dur * FPS))
    ft = np.arange(n) / FPS
    hold = lambda e: np.interp(ft, t, maximum_filter1d(e, int(FR / FPS) + 1))
    pk = lambda e: np.clip(hold(e) / np.percentile(hold(e), 99.5), 0, 1)
    db = lambda M, lo_, hi_: 10 * np.log10((M[(f >= lo_) & (f <= hi_)] ** 2).sum(axis=0) + 1e-12)
    sm = lambda v, sec: uniform_filter1d(v, max(1, int(sec * FR)))
    mono = mid.astype(np.float64)
    pw = uniform_filter1d(mono ** 2, int(SR / 12))
    curves = {
        'level': norm01(10 * np.log10(np.interp(ft * SR, np.arange(len(pw)), pw) + 1e-12)),
        'vocal': norm01(np.interp(ft, t, sm(db(V, 200, 4000), 1 / 12))),
        'bass': norm01(np.interp(ft, t, sm(db(S, 35, 140), 1 / 12))),
        'air': norm01(np.interp(ft, t, sm(db(S, 5000, 10500), 1 / 6))),
        'width': norm01(np.interp(ft, t, sm(db(Sside, 150, 10000) - db(S, 150, 10000), 0.5))),
        'onset': pk(np.maximum(full, 0)), 'kick': pk(low), 'snare': pk(high),
    }

    # Where the arrangement changes: 2-bar averages, for placing the film's turns.
    bars = bar0 + 4 * P * np.arange(-int(bar0 / (4 * P)), int((dur - bar0) / (4 * P)) + 1)
    print('\n  bar  time    level bass  air   width vocal kick snare   (2-bar averages, 0..1)')
    for j in range(0, len(bars) - 2, 2):
        i0, i1 = int(max(bars[j], 0) * FPS), int(min(bars[j + 2], dur) * FPS)
        if i1 <= i0: continue
        m = {k: float(v[i0:i1].mean()) for k, v in curves.items()}
        print(f"  {j + 1:3d}  {bars[j]:6.2f}  {m['level']:.2f}  {m['bass']:.2f}  {m['air']:.2f}  {m['width']:.2f}  {m['vocal']:.2f}  {m['kick']:.2f}  {m['snare']:.2f}  " + '#' * int(m['level'] * 24))

    r3 = lambda v: [round(float(q), 3) for q in v]
    out = {'audio': a.audio, 'duration': round(dur, 3), 'fps': FPS, 'bpm': round(bpm, 3), 'beat': round(P, 5), 'first': round(float(b0), 4), 'bar0': round(bar0, 4),
           **{k: r3(v) for k, v in curves.items()}}
    if a.track:
        tb = track_beats(full, t, P)
        iv = np.diff(tb)
        print(f'\ntracked {len(tb)} beats from {tb[0]:.2f} to {tb[-1]:.2f} s; interval median {np.median(iv):.4f} s, 5-95% {np.percentile(iv, 5):.3f}-{np.percentile(iv, 95):.3f} '
              '(the tracker can settle half a beat off in quiet passages: check it against the lyrics)')
        out['beats'] = r3(tb)
    body = '{\n' + ',\n'.join(f'  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}' for k, v in out.items()) + '\n}'
    (ROOT / 'assets/analysis').mkdir(parents=True, exist_ok=True)
    (ROOT / 'assets/analysis/audio.json').write_text(body + '\n')
    if a.js:
        (ROOT / 'src/gen').mkdir(parents=True, exist_ok=True)
        (ROOT / 'src/gen/song.js').write_text('// Generated by tools/analyze_audio.py. Do not edit.\nexport const SONG = ' + body + ';\n')
    print(f'\nwrote assets/analysis/audio.json' + (' and src/gen/song.js' if a.js else '') + f' ({n} frames at {FPS} fps)')

    if a.plot:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(3, 1, figsize=(26, 9), sharex=True)
        s1 = lambda v: uniform_filter1d(np.asarray(v), FPS)
        for k in ('level', 'vocal', 'bass', 'air', 'width'): ax[0].plot(ft, s1(curves[k]), lw=1.1, label=k)
        for b in bars: ax[0].axvline(b, color='k', alpha=.1, lw=.6)
        ax[0].legend(loc='upper left', ncol=5)
        ax[1].plot(ft, curves['kick'], lw=.5, label='kick'); ax[1].plot(ft, -curves['snare'], lw=.5, label='snare (down)'); ax[1].legend(loc='upper left')
        dbm = band_db(S, f, 40, 10000, 60); ax[2].imshow(dbm, aspect='auto', origin='lower', extent=[t[0], t[-1], 0, 60], cmap='magma', vmin=-70, vmax=0)
        ax[2].set_xlim(0, dur); ax[2].set_xticks(np.arange(0, dur, 10))
        for q in ax: q.grid(axis='x', alpha=.25)
        (ROOT / a.plot).parent.mkdir(parents=True, exist_ok=True); fig.tight_layout(); fig.savefig(ROOT / a.plot, dpi=60); print('wrote', a.plot)


if __name__ == '__main__':
    main()
