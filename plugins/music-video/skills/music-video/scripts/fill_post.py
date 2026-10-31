#!/usr/bin/env python3
"""fill_post.py: docs/POST.tpl -> docs/POST.txt, every {{L12}} replaced by the text of lyric line 12 of assets/lyrics/lyrics.json.

  python3 -I tools/fill_post.py [--in=docs/POST.tpl] [--out=docs/POST.txt]

Posting titles often quote a lyric line. The copy is written around placeholders so that no one types lyric text (a model that
writes it into a reply or a file gets the whole response blocked); this script fills them in from the lyric data. Line numbers are
the "i" of lyrics.json, counted from 0. Prints which lines were filled and any placeholder left, never the words.
"""
import argparse, json, pathlib, re


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--in', dest='src', default='docs/POST.tpl')
    ap.add_argument('--out', default='docs/POST.txt')
    a = ap.parse_args()
    ROOT = pathlib.Path(a.root).resolve()
    lines = {l['i']: l['text'] for l in json.loads((ROOT / 'assets/lyrics/lyrics.json').read_text(encoding='utf-8'))['lines']}
    tpl = (ROOT / a.src).read_text(encoding='utf-8')
    used = sorted({int(n) for n in re.findall(r'\{\{L(\d+)\}\}', tpl)})
    bad = [n for n in used if n not in lines]
    if bad: raise SystemExit(f'no lyric line {bad} in lyrics.json (lines are 0..{max(lines)})')
    out = re.sub(r'\{\{L(\d+)\}\}', lambda m: lines[int(m.group(1))].strip(), tpl)
    (ROOT / a.out).write_text(out, encoding='utf-8')
    left = re.findall(r'\{\{[^}]*\}\}', out)
    print(f'wrote {a.out}: lines filled {used or "none"}; {len(out)} characters; placeholders left: {left or "none"}')


if __name__ == '__main__':
    main()
