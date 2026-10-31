#!/usr/bin/env python3
"""build_lyrics.py: per-character lyric times for the page -> assets/lyrics/lyrics.json. Prints times and counts, never the words.

  python3 -I tools/build_lyrics.py                                   all assets/lyrics/kugou_*.krc.txt, merged, shift found on the voice
  python3 -I tools/build_lyrics.py --krc=assets/lyrics/kugou_123.krc.txt --shift=0
  python3 -I tools/build_lyrics.py --lrc=assets/song.lrc [--credits=10] [--spaces=strip]   on-screen text from an .lrc, times from KRC

Text: from the first KRC file (default) or from --lrc. Credit rows (title, 词/曲/编曲 ...) are left out of the sung lines: rows
holding a colon (label：name) or " - " (歌手 - 歌名); with --lrc and --credits=N, the first N rows instead. They are kept apart
in "credits".
Times: one KRC file as tagged; two files averaged per character, except where they are more than 0.3 s apart, where the one
closer to a vocal onset wins; three or more: the median. Then everything is shifted: --shift=auto (default) picks the offset in
-0.4..0.4 s that puts the most character starts within 60 ms of a vocal onset of the song (centre channel, voice band); a number
is used as given; 0 keeps the tags. When the words sit on an even eighth-note grid, several offsets fit about equally well: read
the printed candidates and keep 0 when in doubt. --line-starts=FILE.json ({"<line index>": seconds}) then moves single lines onto
measured starts (for example from a separated vocal), keeping each line's inner spacing.
Output: {source, offset, credits: [{t, text}], lines: [{i, t, end, text, chars: [[start, duration], ...]}]}, in seconds of the
song file, i counted from 0, one chars entry per character of text (a space takes the end of the character before it and lasts 0).
"""
import argparse, difflib, json, pathlib, re, subprocess
import numpy as np
from scipy.ndimage import gaussian_filter1d, uniform_filter1d
from scipy.signal import find_peaks, stft

SR = 22050
AUDIO_EXT = ('.wav', '.flac', '.m4a', '.mp3', '.aac', '.ogg', '.opus')
is_credit = lambda text: any(c in text for c in '：:') or ' - ' in text


def krc_rows(path):
    """[{t: row start s, text, chars: [(start s, dur s, ch)] for the non-space characters}] for every timed row."""
    rows = []
    for raw in path.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^\[(\d+),(\d+)\](.*)$', raw)
        if not m: continue
        t0, toks, chars = int(m.group(1)), re.findall(r'<(\d+),(\d+),\d+>([^<]*)', m.group(3)), []
        for a, d, w in toks:
            vis = [c for c in w if not c.isspace()]
            for k, ch in enumerate(vis): chars.append(((t0 + int(a) + int(d) * k / len(vis)) / 1000, int(d) / len(vis) / 1000, ch))
        rows.append({'t': t0 / 1000, 'text': ''.join(w for _, _, w in toks), 'chars': chars})
    return rows


def lrc_rows(path):
    out = []
    for l in path.read_text(encoding='utf-8').splitlines():
        m = re.match(r'^((?:\[\d+:\d+(?:\.\d+)?\])+)(.*)$', l)
        if not m or not m.group(2).strip(): continue
        for s in re.findall(r'\[(\d+):(\d+(?:\.\d+)?)\]', m.group(1)):      # a row may carry several time tags
            out.append({'t': int(s[0]) * 60 + float(s[1]), 'text': m.group(2).strip()})
    return sorted(out, key=lambda r: r['t'])


def vocal_onsets(audio):
    """Onset times of the centre channel in the voice band (the lead voice sits in the middle of the mix)."""
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(audio), '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
    hop = 256
    f, t, Zm = stft(x.mean(axis=1), SR, nperseg=1024, noverlap=1024 - hop, boundary=None, padded=False)
    _, _, Zs = stft((x[:, 0] - x[:, 1]) / 2, SR, nperseg=1024, noverlap=1024 - hop, boundary=None, padded=False)
    fr = SR / hop
    L = np.log1p(40 * np.maximum(np.abs(Zm) - np.abs(Zs), 0)[(f >= 300) & (f <= 3400)])
    flux = gaussian_filter1d(np.maximum(np.diff(L, axis=1, prepend=L[:, :1]), 0).sum(axis=0), 1.2)
    flux = np.maximum(flux - uniform_filter1d(flux, int(0.6 * fr)), 0); flux /= flux.std()
    pk, _ = find_peaks(flux, height=0.9, distance=6)
    return t[pk]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--krc', nargs='*', help='KRC files (default: every assets/lyrics/kugou_*.krc.txt)')
    ap.add_argument('--lrc', help='take the on-screen text from this .lrc')
    ap.add_argument('--credits', type=int, help='with --lrc: the first N rows are title and credits')
    ap.add_argument('--spaces', choices=('keep', 'strip'), default='keep', help='keep single spaces between words (default) or drop all')
    ap.add_argument('--shift', default='auto', help="'auto', or seconds to add to every time (0 = as tagged)")
    ap.add_argument('--line-starts', help='JSON {"<line index>": seconds}: move those lines onto measured starts')
    ap.add_argument('--audio', help='song file for the vocal onsets (default: the first audio file in assets/)')
    a = ap.parse_args()
    ROOT = pathlib.Path(a.root).resolve()
    krcs = [ROOT / p for p in a.krc] if a.krc else sorted((ROOT / 'assets/lyrics').glob('kugou_*.krc.txt'))
    if not krcs: raise SystemExit('no KRC files: run tools/fetch_lyrics.py first, or pass --krc')
    files = [krc_rows(p) for p in krcs]

    # 1. the on-screen rows and their text
    if a.lrc:
        rows = lrc_rows(ROOT / a.lrc)
        if a.credits is not None: credits, sung = rows[:a.credits], rows[a.credits:]
        else: credits, sung = [r for r in rows if is_credit(r['text'])], [r for r in rows if not is_credit(r['text'])]
        src_text = f'text from {pathlib.Path(a.lrc).name}'
    else:
        credits, sung = [r for r in files[0] if is_credit(r['text'])], [r for r in files[0] if not is_credit(r['text'])]
        src_text = f'text from {krcs[0].stem}'
    norm = (lambda s: re.sub(r'\s', '', s)) if a.spaces == 'strip' else (lambda s: re.sub(r'\s+', ' ', s).strip())
    texts = [norm(r['text']) for r in sung]
    ref = ''.join(re.sub(r'\s', '', s) for s in texts)                # the visible characters, in order
    print(f'{len(sung)} sung lines, {len(ref)} characters; {len(credits)} title/credit rows'
          + (f' ({credits[0]["t"]:.2f}-{credits[-1]["t"]:.2f} s)' if credits else ''))

    # 2. every KRC file mapped onto those characters
    starts, durs = [[] for _ in ref], [[] for _ in ref]
    for p, rows in zip(krcs, files):
        w = [c for r in rows if not is_credit(r['text']) for c in r['chars']]
        sm = difflib.SequenceMatcher(None, ''.join(c[2] for c in w), ref, autojunk=False)
        hit = 0
        for i0, j0, n in sm.get_matching_blocks():
            for k in range(n): starts[j0 + k].append(w[i0 + k][0]); durs[j0 + k].append(w[i0 + k][1]); hit += 1
        print(f'  {p.name}: {len(w)} characters, {hit} matched to the text')
    audio = pathlib.Path(a.audio) if a.audio else next(iter(sorted(p for p in (ROOT / 'assets').glob('*') if p.suffix.lower() in AUDIO_EXT)), None)
    need_onsets = a.shift == 'auto' or any(len(s) == 2 and abs(s[0] - s[1]) > 0.3 for s in starts)
    if need_onsets and not audio: raise SystemExit('no song file in assets/ for the vocal onsets: add it, or pass --shift=0')
    pt = vocal_onsets(ROOT / audio if not audio.is_absolute() else audio) if need_onsets else None
    def near(ts):
        i = np.clip(np.searchsorted(pt, ts), 1, len(pt) - 1)
        return np.where(np.abs(pt[i] - ts) < np.abs(pt[i - 1] - ts), pt[i] - ts, pt[i - 1] - ts)
    start, dur, split = np.full(len(ref), np.nan), np.full(len(ref), np.nan), 0
    for j, (s, d) in enumerate(zip(starts, durs)):
        if not s: continue
        if len(s) == 1: start[j], dur[j] = s[0], d[0]
        elif len(s) == 2:
            if abs(s[0] - s[1]) <= 0.3: start[j], dur[j] = (s[0] + s[1]) / 2, (d[0] + d[1]) / 2
            else: k = int(np.argmin(np.abs(near(np.array(s))))); start[j], dur[j] = s[k], d[k]; split += 1
        else: start[j], dur[j] = float(np.median(s)), float(np.median(d))
    if len(krcs) > 1:
        sp = [np.ptp(s) for s in starts if len(s) > 1]
        print(f'  files agree within {np.median(sp):.3f} s (median), {np.percentile(sp, 90):.3f} s (90%); {split} characters more than 0.3 s apart, settled by the voice')
    miss = int(np.isnan(start).sum())
    if miss:                                                           # characters no file has: interpolate between neighbours
        idx = np.arange(len(ref)); ok = ~np.isnan(start)
        start = np.interp(idx, idx[ok], start[ok]); dur = np.where(np.isnan(dur), 0.25, dur)
        print(f'  {miss} characters had no time and were interpolated')

    # 3. the whole-song offset
    if a.shift == 'auto':
        offs = np.arange(-0.4, 0.4001, 0.01)
        score = np.array([np.mean(np.abs(near(start + o)) < 0.06) for o in offs])
        best = float(offs[int(score.argmax())])
        pk, _ = find_peaks(np.concatenate([[0], score, [0]]))
        top = sorted(((score[p - 1], offs[p - 1]) for p in pk), reverse=True)[:3]
        print(f'within 60 ms of a vocal onset: {score[np.argmin(np.abs(offs))]:.0%} as tagged, {score.max():.0%} after shifting by {best:+.2f} s; '
              'candidates ' + ', '.join(f'{o:+.2f} s ({s:.1%})' for s, o in top))
    else:
        best = float(a.shift)
    start = start + best
    for i in range(1, len(start)): start[i] = max(start[i], start[i - 1] + 0.05)
    dur[:-1] = np.minimum(dur[:-1], np.diff(start)); dur = np.maximum(dur, 0.05)

    # 4. lines (spaces take the end of the character before them)
    lines, k = [], 0
    for i, txt in enumerate(texts):
        chars = []
        for c in txt:
            if c == ' ':
                prev = chars[-1] if chars else [round(float(start[k]), 3), 0.0]
                chars.append([round(prev[0] + prev[1], 3), 0.0])
            else:
                chars.append([round(float(start[k]), 3), round(float(dur[k]), 3)]); k += 1
        lines.append({'i': i, 't': chars[0][0], 'end': round(max(s + d for s, d in chars), 3), 'text': txt, 'chars': chars})
    if a.line_starts:
        moves = json.loads((ROOT / a.line_starts).read_text())
        for key, target in moves.items():
            l = lines[int(key)]; d = target - l['chars'][0][0]
            l['chars'] = [[round(c[0] + d, 3), c[1]] for c in l['chars']]
            l['t'] = l['chars'][0][0]; l['end'] = round(max(s + q for s, q in l['chars']), 3)
            print(f'  line {l["i"]:2d} moved {d:+.3f} s to {l["t"]:.3f}')
        for p, q in zip(lines, lines[1:]):
            if p['end'] > q['t'] - 0.05:
                last = max(range(len(p['chars'])), key=lambda j: p['chars'][j][0])
                p['chars'][last][1] = round(max(0.0, q['t'] - 0.05 - p['chars'][last][0]), 3); p['end'] = round(max(s + d for s, d in p['chars']), 3)
    assert all(len(l['text']) == len(l['chars']) for l in lines)
    out = ROOT / 'assets/lyrics/lyrics.json'
    src = f'{src_text}; character times from {", ".join(p.stem for p in krcs)}' + (f', shifted {best:+.2f} s' if best else '') + \
          (f'; lines moved to {pathlib.Path(a.line_starts).name}' if a.line_starts else '')
    out.write_text(json.dumps({'source': src, 'offset': round(best, 3), 'credits': [{'t': round(r['t'], 3), 'text': r['text']} for r in credits], 'lines': lines},
                              ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'wrote {out.relative_to(ROOT)}: {len(lines)} lines, first {lines[0]["t"]:.2f} s, last ends {lines[-1]["end"]:.2f} s')
    print('  i  ' + ('  row   ' if a.lrc else '') + ' first     end    n   gaps between characters (s)')
    for r, l in zip(sung, lines):
        st = [c[0] for c, ch in zip(l['chars'], l['text']) if ch != ' ']
        print(f"{l['i']:3d} " + (f"{r['t']:7.2f} " if a.lrc else '') + f"{l['t']:7.2f} {l['end']:7.2f} {len(st):4d}  " + ' '.join(f'{b - a_:.2f}' for a_, b in zip(st, st[1:])))


if __name__ == '__main__':
    main()
