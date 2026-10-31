#!/usr/bin/env python3
"""check_no_lyrics.py: find lyric text that slipped into docs, code or copy. Prints file names, line numbers and lyric line
indices only, never the words.

  python3 -I tools/check_no_lyrics.py                       the project's docs, src, tools, README and look tests
  python3 -I tools/check_no_lyrics.py path/one.md path/two/  only these files or folders

Lyrics live as data (assets/lyrics/) and are drawn by the page; they should not appear in storyboards, guides, briefs, code,
READMEs or anything published. A hit is a run of at least 6 consecutive characters of a lyric line (16 for lines written in
Latin letters), ignoring spaces and punctuation. docs/POST.txt is reported apart: its title may quote a line on purpose
(filled in by fill_post.py). Exit status 1 when anything else hits.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path('.').resolve()
SKIP_DIRS = {'node_modules', 'out', 'assets', '.git', '__pycache__'}
EXT = {'.md', '.txt', '.js', '.mjs', '.py', '.html', '.json', '.tpl', '.sh', '.glsl'}
norm = lambda s: re.sub(r'[\s\W_]+', '', s.lower())


def files(args):
    roots = [ROOT / a for a in args] or [ROOT]
    for r in roots:
        if r.is_file(): yield r; continue
        for p in sorted(r.rglob('*')):
            if p.is_file() and p.suffix in EXT and not (set(p.relative_to(r).parts) & SKIP_DIRS): yield p


def main():
    data = json.loads((ROOT / 'assets/lyrics/lyrics.json').read_text(encoding='utf-8'))
    grams = {}
    for l in data['lines']:
        t = norm(l['text']); n = 16 if re.fullmatch(r'[a-z0-9]*', t) else 6
        for k in range(len(t) - n + 1): grams.setdefault(t[k:k + n], l['i'])
    sizes = sorted({len(g) for g in grams})
    hits, post = [], []
    for p in files(sys.argv[1:]):
        try: text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError: continue
        for ln, line in enumerate(text.splitlines(), 1):
            t = norm(line); found = set()
            for n in sizes:
                for k in range(len(t) - n + 1):
                    if t[k:k + n] in grams: found.add(grams[t[k:k + n]])
            if found: (post if p.name == 'POST.txt' else hits).append((p.relative_to(ROOT) if p.is_relative_to(ROOT) else p, ln, sorted(found, key=str)))
    for f, ln, idx in post: print(f'{f}:{ln}: lyric line(s) {idx} (posting copy: expected only where a placeholder was filled)')
    for f, ln, idx in hits: print(f'{f}:{ln}: text of lyric line(s) {idx}')
    print(f'{len(hits)} line(s) with lyric text outside the posting copy' + (': replace them with line numbers and your own words' if hits else ''))
    sys.exit(1 if hits else 0)


if __name__ == '__main__':
    main()
