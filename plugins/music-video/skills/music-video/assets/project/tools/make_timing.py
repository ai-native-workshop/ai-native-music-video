#!/usr/bin/env python3
"""make_timing.py: write assets/timing.json: the film's range and shots, plus the bar grid, the accents and the sung lines in it.
Edit RANGE and SHOTS below to follow docs/STORYBOARD.md, then run from the project root:

  python3 -I tools/make_timing.py                                              -> assets/timing.json (render.mjs and the page read it)
  python3 -I tools/make_timing.py --clip=83.245:97.399 --out=look_tests/clip.json   a look test's passage, as one shot

Times are seconds of the song file. Helpers: bar(k) is bar line k counted from bar0 (fractions allowed: bar(35.5)); beat(k) is beat
k from bar0; line(i) is the first sung character of lyric line i (the "i" of lyrics.json, from 0) and end(i) the end of its last
one; F is one frame, so line(8) - 2 * F cuts two frames before line 8 starts. Cut on the start of a sung phrase or on a bar line.
Accents are the peaks of the measured kick (low) and snare (high) curves, [time, strength 0..1]; the page gets them as T.kicks and
T.snares. Prints times and counts only, never the words, and warns when a sung line straddles the film's start or end.
"""
import argparse, json, math, pathlib
import numpy as np
from scipy.signal import find_peaks

FPS, W, H = 30, 1920, 1080                 # the film's frame rate and size

ROOT = pathlib.Path('.').resolve()
A = json.loads((ROOT / 'assets/analysis/audio.json').read_text())
LP = ROOT / 'assets/lyrics/lyrics.json'
LINES = json.loads(LP.read_text(encoding='utf-8'))['lines'] if LP.exists() else []
BAR, F = 4 * A['beat'], 1 / FPS
bar = lambda k: A['bar0'] + k * BAR
beat = lambda k: A['bar0'] + k * A['beat']
line = lambda i: LINES[i]['t']
end = lambda i: LINES[i]['end']

# ---- edit from here -------------------------------------------------------------------------------------------------------------
RANGE = (0.0, A['duration'])                # the film: the whole song, or a passage such as (bar(20), bar(42))
SHOTS = [                                   # (id, start, name); each shot runs until the next one starts, the last to RANGE[1]
    ('s01', RANGE[0], 'opening'),
]
# ---- to here ----------------------------------------------------------------------------------------------------------------------


def peaks(name, t0, t1, h=0.35):
    v, fps = np.array(A[name]), A['fps']
    i0, i1 = max(0, int((t0 - 0.2) * fps)), min(len(v), int((t1 + 0.2) * fps))
    pk, pr = find_peaks(v[i0:i1], height=h, distance=max(1, int(0.12 * fps)))
    return [[round((i0 + p) / fps, 3), round(float(pr['peak_heights'][k]), 2)] for k, p in enumerate(pk) if t0 <= (i0 + p) / fps < t1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clip', help='a:b in song seconds: one shot over that passage (for look tests)')
    ap.add_argument('--out', default='assets/timing.json')
    a = ap.parse_args()
    if a.clip: (t0, t1), shots = map(float, a.clip.split(':')), [('clip', float(a.clip.split(':')[0]), 'look test')]
    else: (t0, t1), shots = RANGE, SHOTS
    rows = [{'id': s, 't0': round(t, 4), 't1': round(shots[k + 1][1] if k + 1 < len(shots) else t1, 4), 'name': n} for k, (s, t, n) in enumerate(shots)]
    bad = [r['id'] for r in rows if r['t1'] <= r['t0']]
    if bad: raise SystemExit(f'shots with no length (check their order): {bad}')
    if abs(rows[0]['t0'] - t0) > 1e-6: raise SystemExit('the first shot must start where the film starts')
    k0, k1 = math.ceil((t0 - A['bar0']) / BAR - 1e-9), math.floor((t1 - A['bar0']) / BAR + 1e-9)
    inside = [l for l in LINES if l['end'] > t0 and l['t'] < t1]
    out = {
        'note': 'Film range, shots, bar grid, accents and sung lines, in seconds of the song file. Bar k starts at bar0 + k * bar.',
        'fps': FPS, 'w': W, 'h': H, 't0': round(t0, 4), 't1': round(t1, 4),
        'bpm': A['bpm'], 'beat': A['beat'], 'bar': round(BAR, 5), 'bar0': A['bar0'],
        'shots': rows,
        'downbeats': [round(bar(k), 3) for k in range(k0, k1 + 1)],
        'kicks': peaks('kick', t0, t1), 'snares': peaks('snare', t0, t1),
        'lines': [{'i': l['i'], 't': l['t'], 'end': l['end'], 'n': len(l['chars'])} for l in inside],
    }
    if 'beats' in A: out['beats'] = [b for b in A['beats'] if t0 <= b < t1]
    dest = ROOT / a.out; dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    n = math.ceil((t1 - t0) * FPS - 1e-6)
    print(f'wrote {a.out}: film {t0:.3f}-{t1:.3f} s ({t1 - t0:.2f} s, {n} frames at {FPS} fps, {W}x{H}), {len(rows)} shots, '
          f'bars {k0}-{k1}, {len(out["kicks"])} low and {len(out["snares"])} high accents' + (f', lines {inside[0]["i"]}-{inside[-1]["i"]}' if inside else ''))
    for r in rows: print(f"  {r['id']:6s} {r['t0']:9.3f}-{r['t1']:9.3f}  {r['t1'] - r['t0']:6.2f} s  {r['name']}")
    for l in LINES:                          # a line still sounding at a cut point: its tail (or head) would be heard alone
        if l['t'] < t0 < l['end'] + 0.25: print(f"  note: line {l['i']} is still sung at the film's start (ends {l['end']:.2f}): listen for a tail, see tools/cut_vocal_tail.py")
        if l['t'] < t1 < l['end']: print(f"  note: line {l['i']} is cut off at the film's end ({l['t']:.2f}-{l['end']:.2f})")


if __name__ == '__main__':
    main()
