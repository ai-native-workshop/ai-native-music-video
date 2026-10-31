#!/usr/bin/env python3
"""check_frames.py: measurements on rendered frames that a contact sheet cannot show. Prints numbers only.

  python3 -I tools/check_frames.py out/frames                       mean luma, near-black frames, frozen runs, the largest
                                                                     frame-to-frame changes (cuts are marked from assets/timing.json)
  python3 -I tools/check_frames.py out/frames --compare=out/frames_b pixel differences between two renders (when files differ)
  python3 -I tools/check_frames.py out/frames --grain=100,100,300,200 is the grain a pattern? (a patch of flat background, x,y,w,h)
  python3 -I tools/check_frames.py out/frames --grid=4               pixel art: how far each 4x4 block is from flat

Why each one:
  - luma: dark films look darker on phones; a mood piece around 45-55 of 255 still reads (34 was too dark).
  - near-black frames and spikes away from cuts: a NaN pixel through bloom, a forgotten blank draw, a shot that leaks state.
  - frozen runs: identical frames in a row where something should move (a page that stopped drawing).
  - --compare: byte comparison (render.mjs --compare) fails on anti-aliasing noise of a level or two; this says how big it is.
  - --grain: the common fract(sin) / hash21 noise on whole pixel coordinates repeats every few pixels and makes a woven lattice
    that only shows at 1:1. Column and row means of a flat patch, high-passed, should be about as small as white noise predicts
    (tested: white noise 0.9-1.0 of that level; the hash21 one-liner 1.7 in columns and 3.4 in rows).
Needs numpy and Pillow.
"""
import argparse, json, pathlib
import numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter1d

LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def load(f):
    return np.asarray(Image.open(f).convert('RGB'), dtype=np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--root', default='.')
    ap.add_argument('--timing', default='assets/timing.json')
    ap.add_argument('--compare')
    ap.add_argument('--grain')
    ap.add_argument('--grid', type=int)
    ap.add_argument('--top', type=int, default=20)
    a = ap.parse_args()
    ROOT = pathlib.Path(a.root).resolve()
    d = ROOT / a.dir
    files = sorted(d.glob('f*.jpg')) or sorted(d.glob('*.png'))
    if not files: raise SystemExit(f'no frames in {d}')

    if a.compare:
        e = ROOT / a.compare; n = same = 0; worst = (0.0, None); means = []
        for f in files:
            g = e / f.name
            if not g.exists(): continue
            n += 1
            if f.read_bytes() == g.read_bytes(): same += 1; continue
            diff = np.abs(load(f) - load(g)); means.append(float(diff.mean()))
            if diff.max() > worst[0]: worst = (float(diff.max()), f.name, int((diff.max(axis=2) > 8).sum()))
        print(f'{n} frames in both: {same} byte-identical, {n - same} differ' + (f'; mean abs difference {np.mean(means):.3f} levels, worst {worst[0]:.0f} levels in {worst[1]} ({worst[2]} px over 8 levels)' if means else ''))
        return

    if a.grain:
        x, y, w, h = map(int, a.grain.split(','))
        out = []
        for f in files[:: max(1, len(files) // 12)]:
            p = load(f)[y:y + h, x:x + w] @ LUMA
            noise = float(np.std(p - uniform_filter1d(uniform_filter1d(p, 9, axis=0), 9, axis=1)))
            col = p.mean(axis=0); col = col - uniform_filter1d(col, 15); row = p.mean(axis=1); row = row - uniform_filter1d(row, 15)
            out.append((f.name, noise, float(np.std(col)), float(np.std(row)), noise / np.sqrt(h), noise / np.sqrt(w)))
        print('frame          pixel noise   column rms (white-noise level)   row rms (white-noise level)')
        for nm, nz, c, r, ec, er in out: print(f'{nm}   {nz:8.2f}     {c:6.3f} ({ec:.3f})                    {r:6.3f} ({er:.3f})' + ('   <- pattern' if c > 2 * ec or r > 2 * er else ''))
        print('white noise sits near its level (ratio about 1); twice or more means the grain has structure. Use a patch of flat background\n'
              '(no stars, edges or text). Then look at it at 1:1 with the contrast stretched.')
        return

    cuts = set()
    tf = ROOT / a.timing
    if tf.exists():
        T = json.loads(tf.read_text())
        for s in T.get('shots', [])[1:]: cuts.add(int(np.ceil((s['t0'] - T['t0']) * T['fps'] - 1e-6)))
    prev, rows = None, []
    for f in files:
        img = load(f); luma = img @ LUMA; small = luma[::8, ::8]
        diff = float(np.abs(small - prev).mean()) if prev is not None else 0.0
        g = 0.0
        if a.grid:
            k = a.grid; hh, ww = luma.shape; b = luma[:hh // k * k, :ww // k * k].reshape(hh // k, k, ww // k, k)
            g = float((b.max(axis=(1, 3)) - b.min(axis=(1, 3))).mean())
        rows.append((f.name, float(luma.mean()), diff, g, small)); prev = small
    m = np.array([r[1] for r in rows]); df = np.array([r[2] for r in rows])
    num = lambda nm: int(''.join(c for c in nm if c.isdigit()) or -1)
    print(f'{len(rows)} frames  mean luma {m.mean():.1f} (min {m.min():.1f} at {rows[int(m.argmin())][0]}, max {m.max():.1f} at {rows[int(m.argmax())][0]})')
    dark = [r[0] for r in rows if r[1] < 6]
    print(f'near-black frames: {len(dark)}' + (f'  first {dark[0]}, last {dark[-1]}' if dark else ''))
    frozen, run = [], 0
    for i in range(1, len(rows)):
        run = run + 1 if df[i] == 0.0 else 0
        if run == 5: frozen.append(rows[i - 5][0])
    print(f'frozen runs (6+ identical frames): {len(frozen)}' + (f'  starting at {", ".join(frozen[:10])}' if frozen else ''))
    print(f'largest frame-to-frame changes (mean abs luma difference; "cut" = a shot boundary in {a.timing}):')
    for i in sorted(np.argsort(-df)[:a.top]):
        fn = num(rows[i][0]); tag = 'cut' if fn in cuts else ('next to a cut' if (fn - 1) in cuts or (fn + 1) in cuts else '')
        print(f'  {rows[i][0]}  {df[i]:6.1f}  {tag}')
    if a.grid:
        gg = np.array([r[3] for r in rows]); print(f'{a.grid}x{a.grid} block spread: mean {gg.mean():.2f}, worst {gg.max():.2f} at {rows[int(gg.argmax())][0]} (JPEG noise is a few levels; more means drawing off the native grid)')


if __name__ == '__main__':
    main()
