#!/usr/bin/env python3
"""new_project.py: start a music-video project folder from the skill's skeleton.

  python3 <skill>/scripts/new_project.py <folder> [--w=1920 --h=1080 --fps=30] [--title="歌名 · 歌手"]

Creates <folder> (one folder per song, e.g. its name in pinyin) holding:
  index.html, src/          the film page: main.js (the page contract), lib.js, caption.js, shots/_example.js, shots/_placeholder.js
  render.mjs                stills, sheets, strips, crops, frames, encode, compare (from the skill's scripts/)
  tools/                    analyze_audio.py, fetch_lyrics.py, build_lyrics.py, make_timing.py, cut_vocal_tail.py, fill_post.py,
                            check_frames.py, check_no_lyrics.py
  docs/                     STORYBOARD.md, GUIDE.md, BRIEF.md, POST.tpl (templates to fill in)
  assets/, out/             empty; the song goes in assets/
  package.json, .gitignore
The project keeps its own copies so it can always be rebuilt the way it was made, even after the skill changes.
Existing files are never overwritten. Afterwards: put the song in assets/ and run npm install in the folder.
"""
import argparse, pathlib, re, shutil

SKILL = pathlib.Path(__file__).resolve().parent.parent
TOOLS = ['analyze_audio.py', 'fetch_lyrics.py', 'build_lyrics.py', 'cut_vocal_tail.py', 'fill_post.py', 'check_frames.py', 'check_no_lyrics.py']
DOCS = ['STORYBOARD.md', 'GUIDE.md', 'BRIEF.md', 'POST.tpl']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('--w', type=int, default=1920)
    ap.add_argument('--h', type=int, default=1080)
    ap.add_argument('--fps', type=int, default=30)
    ap.add_argument('--title', default='', help='shown in the browser tab and on the example cover')
    a = ap.parse_args()
    dst = pathlib.Path(a.folder).resolve()
    name = dst.name
    plan = []                                                            # (source, destination)
    for p in sorted((SKILL / 'assets/project').rglob('*')):
        if p.is_file() and p.name != '.DS_Store': plan.append((p, dst / p.relative_to(SKILL / 'assets/project')))
    plan.append((SKILL / 'scripts/render.mjs', dst / 'render.mjs'))
    plan += [(SKILL / 'scripts' / t, dst / 'tools' / t) for t in TOOLS]
    plan += [(SKILL / 'assets/docs' / d, dst / 'docs' / d) for d in DOCS]
    made, kept = [], []
    for src, out in plan:
        if out.exists(): kept.append(out); continue
        out.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in ('.json', '.html', '.py', '.js', '.md', '.tpl') or src.name in ('.gitignore',):
            text = src.read_text(encoding='utf-8')
            if src.name == 'package.json': text = text.replace('"name": "music-video-project"', f'"name": "{name}"')
            if src.name == 'index.html' and a.title: text = re.sub(r'<title>.*?</title>', f'<title>{a.title}</title>', text)
            if src.name == 'make_timing.py': text = re.sub(r'^FPS, W, H = .*$', f'FPS, W, H = {a.fps}, {a.w}, {a.h}', text, count=1, flags=re.M)
            out.write_text(text, encoding='utf-8')
            shutil.copymode(src, out)
        else:
            shutil.copy2(src, out)
        made.append(out)
    for sub in ('assets/lyrics', 'assets/analysis', 'assets/audio', 'out/check', 'docs/img', 'look_tests'):
        (dst / sub).mkdir(parents=True, exist_ok=True)
    print(f'{dst}: {len(made)} files written' + (f', {len(kept)} already there and left alone' if kept else ''))
    print(f'frame {a.w}x{a.h} at {a.fps} fps (tools/make_timing.py holds it; change it there)')
    print('next: put the song in assets/, then:  cd ' + str(dst) + ' && npm install && python3 -I tools/analyze_audio.py --plot=out/check/audio.png')


if __name__ == '__main__':
    main()
