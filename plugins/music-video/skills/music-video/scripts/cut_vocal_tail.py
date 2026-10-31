#!/usr/bin/env python3
"""cut_vocal_tail.py: remove the end of the previous sung line from the opening of an excerpt -> assets/audio/film.wav.

  python3 -I tools/cut_vocal_tail.py --stem=assets/audio/vocals.wav --stem-start=44.0 --cut=50.90 --full=51.86 --fade=51.96
  python3 -I tools/cut_vocal_tail.py --stem=... --scale-file=assets/audio/vocals_scale.txt --cut=... --full=... --fade=...

A film cut out of the middle of a song starts on a bar line, while the last note of the line before it may still be sounding;
a fade-in would only soften that tail and dull the first downbeat. Here the separated vocal is subtracted from the mix instead:
at full strength from --cut to --full, then faded out of the subtraction (raised cosine) by --fade. Every other sample is the
ffmpeg decode of the song, unchanged, so the film's audio stays on the song's own time line (render.mjs --encode prefers
assets/audio/film.wav when it exists).

The stem: a vocal stem separated from the same decode (see references/song.md: audio-separator, BS-RoFormer). --stem-start is
where its first sample sits in the song (seconds), or --scale-file holds "k first_sample" when the stem was separated from an
excerpt scaled by k. Integer stems are read as fractions of full scale. Set --fade where the next line's breath begins.
Prints the changed range and peak levels, no words. Check without listening: the difference old - new correlates with the stem.
"""
import argparse, pathlib, subprocess, tempfile
import numpy as np
import scipy.io.wavfile as wf

AUDIO_EXT = ('.wav', '.flac', '.m4a', '.mp3', '.aac', '.ogg', '.opus')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--song', help='the song file (default: the first audio file in assets/)')
    ap.add_argument('--stem', required=True, help='separated vocal (wav) covering the cut')
    ap.add_argument('--stem-start', type=float, help='song time of the stem\'s first sample, seconds')
    ap.add_argument('--scale', type=float, default=1.0, help='the stem is k times the vocal in the song\'s units')
    ap.add_argument('--scale-file', help='a file holding "k first_sample" (overrides --scale and --stem-start)')
    ap.add_argument('--cut', type=float, required=True, help='start subtracting here (s)')
    ap.add_argument('--full', type=float, required=True, help='full subtraction up to here (s)')
    ap.add_argument('--fade', type=float, required=True, help='subtraction faded out by here (s)')
    ap.add_argument('--out', default='assets/audio/film.wav')
    a = ap.parse_args()
    ROOT = pathlib.Path(a.root).resolve()
    song = ROOT / a.song if a.song else next(iter(sorted(p for p in (ROOT / 'assets').glob('*') if p.suffix.lower() in AUDIO_EXT)), None)
    if song is None: raise SystemExit('no song file in assets/')
    with tempfile.TemporaryDirectory() as d:
        dec = pathlib.Path(d) / 'full.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(song), '-c:a', 'pcm_f32le', str(dec)], check=True)
        sr, full = wf.read(dec)
    sr2, stem = wf.read(ROOT / a.stem)
    if sr2 != sr: raise SystemExit(f'the stem is {sr2} Hz, the song decodes at {sr} Hz: resample the stem first')
    if a.scale_file:
        k, first = open(ROOT / a.scale_file).read().split(); k, first = float(k), int(first)
    else:
        if a.stem_start is None: raise SystemExit('pass --stem-start (or --scale-file)')
        k, first = a.scale, int(round(a.stem_start * sr))
    v = stem.astype(np.float64)
    if np.issubdtype(stem.dtype, np.integer): v /= float(np.iinfo(stem.dtype).max) + 1
    voc = v / k                                                         # the vocal in the song's own units
    if voc.ndim == 1: voc = np.repeat(voc[:, None], full.shape[1], axis=1)
    n = min(len(voc), len(full) - first); voc = voc[:n]
    t = (first + np.arange(n)) / sr
    g = np.where(t < a.full, 1.0, np.where(t > a.fade, 0.0, 0.5 + 0.5 * np.cos(np.pi * (t - a.full) / (a.fade - a.full))))
    g[t < a.cut] = 0.0
    out = full.astype(np.float64)
    out[first:first + n] -= voc * g[:, None]
    out = out.astype(np.float32)
    changed = np.flatnonzero(np.any(out != full, axis=1))
    dest = ROOT / a.out; dest.parent.mkdir(parents=True, exist_ok=True)
    wf.write(dest, sr, out)
    print(f'wrote {dest.relative_to(ROOT)}: {len(out) / sr:.3f} s, {sr} Hz; ' + (f'changed {changed[0] / sr:.3f}-{changed[-1] / sr:.3f} s; ' if len(changed) else 'nothing changed; ')
          + f'peak {np.abs(out).max():.3f} (song decode {np.abs(full).max():.3f})')


if __name__ == '__main__':
    main()
