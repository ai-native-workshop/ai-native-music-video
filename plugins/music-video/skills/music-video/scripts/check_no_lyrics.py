#!/usr/bin/env python3
"""check_no_lyrics.py: find lyric text that slipped into docs, code or copy. Prints file names, line numbers and lyric line
indices only, never the words.

  python3 -I tools/check_no_lyrics.py                       the project's docs, src, tools, README and look tests
  python3 -I tools/check_no_lyrics.py path/one.md path/two/  only these files or folders
  python3 -I tools/check_no_lyrics.py --min=4               stricter, for the wrap-up: runs of 4 characters

Lyrics live as data (assets/lyrics/) and are drawn by the page; they should not appear in storyboards, guides, briefs, code,
READMEs or anything shared. A hit is a run of at least 6 consecutive characters of a lyric line (16 for lines written in Latin
letters), ignoring spaces and punctuation. A song title is often a lyric line too: a hit on the title alone is fine.
--min=4 also finds the short overlaps a paraphrase can leave (a shot label, a storyboard cell). It also hits common phrases
and every mention of a title of four or more characters (77 lines in one project against 3 at the default), so read the list.
Exit status 1 when anything hits.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path('.').resolve()
SKIP_DIRS = {'node_modules', 'out', 'assets', '.git', '__pycache__'}
EXT = {'.md', '.txt', '.js', '.mjs', '.py', '.html', '.json', '.sh', '.glsl'}
norm = lambda s: re.sub(r'[\s\W_]+', '', s.lower())


def files(args):
    roots = [ROOT / a for a in args] or [ROOT]
    for r in roots:
        if r.is_file(): yield r; continue
        for p in sorted(r.rglob('*')):
            if p.is_file() and p.suffix in EXT and not (set(p.relative_to(r).parts) & SKIP_DIRS): yield p


def main():
    least = next((int(a[6:]) for a in sys.argv[1:] if a.startswith('--min=')), 6)
    data = json.loads((ROOT / 'assets/lyrics/lyrics.json').read_text(encoding='utf-8'))
    grams = {}
    for l in data['lines']:
        t = norm(l['text']); n = 16 if re.fullmatch(r'[a-z0-9]*', t) else least
        for k in range(len(t) - n + 1): grams.setdefault(t[k:k + n], l['i'])
    sizes = sorted({len(g) for g in grams})
    hits = []
    for p in files([a for a in sys.argv[1:] if not a.startswith('--min=')]):
        try: text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError: continue
        for ln, line in enumerate(text.splitlines(), 1):
            t = norm(line); found = set()
            for n in sizes:
                for k in range(len(t) - n + 1):
                    if t[k:k + n] in grams: found.add(grams[t[k:k + n]])
            if found: hits.append((p.relative_to(ROOT) if p.is_relative_to(ROOT) else p, ln, sorted(found, key=str)))
    for f, ln, idx in hits: print(f'{f}:{ln}: text of lyric line(s) {idx}')
    print(f'{len(hits)} line(s) with lyric text' + (': replace them with line numbers and your own words' if hits else ''))
    sys.exit(1 if hits else 0)


if __name__ == '__main__':
    main()
