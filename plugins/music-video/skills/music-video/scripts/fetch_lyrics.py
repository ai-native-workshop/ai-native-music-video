#!/usr/bin/env python3
"""fetch_lyrics.py: download timed lyrics for the song into assets/lyrics/, printing counts and times only, never the words.

  python3 -I tools/fetch_lyrics.py --keyword "歌手 - 歌名" [--duration=245.65] [--tolerance=1.5] [--max=6]
  python3 -I tools/fetch_lyrics.py --netease=287398                       NetEase line (lrc) and word (yrc) lyrics by song id
  python3 -I tools/fetch_lyrics.py --lrclib --artist="..." --title="..." [--album="..."]   LRCLIB line-timed lyrics

Sources (none needs a login):
  Kugou KRC   character-timed, often several independently tagged files per song: kugou_<id>.krc.txt (decoded text).
              Candidates whose duration differs from the song by more than --tolerance seconds are skipped (other versions).
  NetEase     netease_<id>.json (the raw reply), netease_<id>.lrc (line times) and netease_<id>.yrc (word times, when it has them).
              Its search API is encrypted; find the song id on the web (music.163.com/song?id=...).
  LRCLIB      lrclib.json and lrclib.lrc (line times; often filed under the traditional-character title).
The duration defaults to the song file's (ffprobe on the first audio file in assets/). Lyrics are copyrighted text: keep them as
data on disk and never type them into replies, code or documents (see references/song.md).
"""
import argparse, base64, json, pathlib, re, subprocess, urllib.parse, urllib.request, zlib

KRC_KEY = bytes([64, 71, 97, 119, 94, 50, 116, 71, 81, 54, 49, 45, 206, 210, 110, 105])
AUDIO_EXT = ('.wav', '.flac', '.m4a', '.mp3', '.aac', '.ogg', '.opus')
UA = {'User-Agent': 'Mozilla/5.0'}


def get(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def song_duration(root):
    found = sorted(p for p in (root / 'assets').glob('*') if p.suffix.lower() in AUDIO_EXT)
    if not found: return None
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(found[0])], capture_output=True, text=True)
    return float(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None


def krc_stats(txt):
    lines = re.findall(r'^\[(\d+),(\d+)\](.*)$', txt, re.M)
    chars = sum(len(re.sub(r'\s', '', ''.join(w for w in re.findall(r'<\d+,\d+,\d+>([^<]*)', body)))) for _, _, body in lines)
    words = sum(len(re.findall(r'<\d+,\d+,\d+>', body)) for _, _, body in lines)
    first = int(lines[0][0]) / 1000 if lines else -1
    last = (int(lines[-1][0]) + int(lines[-1][1])) / 1000 if lines else -1
    return len(lines), words, chars, first, last


def kugou(out, keyword, dur, tol, cap):
    q = urllib.parse.urlencode({'ver': 1, 'man': 'yes', 'client': 'mobi', 'keyword': keyword, 'duration': int(round(dur * 1000)) if dur else '', 'hash': ''})
    cands = json.loads(get('http://krcs.kugou.com/search?' + q)).get('candidates') or []
    print(f'Kugou: {len(cands)} candidates for the keyword')
    saved = 0
    for c in cands:
        cd = int(c.get('duration') or 0) / 1000
        tag = f"id {c['id']}  duration {cd:.2f} s  score {c.get('score')}"
        if dur and abs(cd - dur) > tol:
            print('  skip', tag, f'(song is {dur:.2f} s)'); continue
        try:
            d = json.loads(get('http://lyrics.kugou.com/download?' + urllib.parse.urlencode({'ver': 1, 'client': 'pc', 'id': c['id'], 'accesskey': c['accesskey'], 'fmt': 'krc', 'charset': 'utf8'})))
            raw = base64.b64decode(d['content'])[4:]                         # drop the 'krc1' header
            txt = zlib.decompress(bytes(b ^ KRC_KEY[i % 16] for i, b in enumerate(raw))).decode('utf-8', 'replace')
        except Exception as e:
            print('  failed', tag, str(e)[:80]); continue
        n, words, chars, first, last = krc_stats(txt)
        if not n: print('  empty', tag); continue
        (out / f"kugou_{c['id']}.krc.txt").write_text(txt, encoding='utf-8')
        print(f'  saved kugou_{c["id"]}.krc.txt  {tag}  {n} timed lines, {words} timed words, {chars} characters, first line {first:.2f} s, last ends {last:.2f} s')
        saved += 1
        if saved >= cap: break
    if not saved: print('  nothing saved: try another keyword (歌手 - 歌名, or the traditional-character title), or --tolerance')


def netease(out, sid):
    d = json.loads(get(f'https://music.163.com/api/song/lyric/v1?id={sid}&cp=false&tv=0&lv=0&rv=0&kv=0&yv=0&ytv=0&yrv=0'))
    (out / f'netease_{sid}.json').write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    for key, ext in (('lrc', 'lrc'), ('yrc', 'yrc')):
        txt = ((d.get(key) or {}).get('lyric') or '').strip()
        if not txt: print(f'NetEase {sid}: no {key}'); continue
        (out / f'netease_{sid}.{ext}').write_text(txt + '\n', encoding='utf-8')
        if key == 'lrc':
            ts = [int(m.group(1)) * 60 + float(m.group(2)) for m in re.finditer(r'^\[(\d+):(\d+(?:\.\d+)?)\]\S', txt, re.M)]
            print(f'NetEase {sid}: lrc with {len(ts)} timed lines' + (f', first {ts[0]:.2f} s, last {ts[-1]:.2f} s' if ts else ''))
        else:
            rows = re.findall(r'^\[(\d+),(\d+)\]', txt, re.M)
            print(f'NetEase {sid}: yrc (word times) with {len(rows)} lines')


def lrclib(out, artist, title, album, dur):
    q = {'artist_name': artist, 'track_name': title}
    if album: q['album_name'] = album
    if dur: q['duration'] = round(dur)
    try:
        d = json.loads(get('https://lrclib.net/api/get?' + urllib.parse.urlencode(q), timeout=30))
    except Exception as e:
        print('LRCLIB get failed:', str(e)[:80], '-> search')
        hits = json.loads(get('https://lrclib.net/api/search?' + urllib.parse.urlencode({'track_name': title, 'artist_name': artist}), timeout=30))
        hits = [h for h in hits if h.get('syncedLyrics') and (not dur or abs((h.get('duration') or 0) - dur) < 3)]
        if not hits: print('LRCLIB: nothing usable'); return
        d = hits[0]
    (out / 'lrclib.json').write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    lrc = d.get('syncedLyrics') or ''
    (out / 'lrclib.lrc').write_text(lrc, encoding='utf-8')
    ts = [int(m.group(1)) * 60 + float(m.group(2)) for m in re.finditer(r'^\[(\d+):(\d+(?:\.\d+)?)\]', lrc, re.M)]
    print(f"LRCLIB: duration {d.get('duration')} s, {len(ts)} timed lines" + (f', first {ts[0]:.2f} s, last {ts[-1]:.2f} s' if ts else ''))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--keyword', help='Kugou search: "歌手 - 歌名"')
    ap.add_argument('--duration', type=float, help='song length in seconds (default: the song file in assets/)')
    ap.add_argument('--tolerance', type=float, default=1.5)
    ap.add_argument('--max', type=int, default=6, help='at most this many Kugou files')
    ap.add_argument('--netease', help='NetEase song id')
    ap.add_argument('--lrclib', action='store_true')
    ap.add_argument('--artist'); ap.add_argument('--title'); ap.add_argument('--album')
    a = ap.parse_args()
    root = pathlib.Path(a.root).resolve()
    out = root / 'assets/lyrics'; out.mkdir(parents=True, exist_ok=True)
    dur = a.duration or song_duration(root)
    if dur: print(f'song duration {dur:.2f} s')
    if not (a.keyword or a.netease or a.lrclib): ap.error('pass --keyword, --netease or --lrclib')
    if a.keyword: kugou(out, a.keyword, dur, a.tolerance, a.max)
    if a.netease: netease(out, a.netease)
    if a.lrclib:
        if not (a.artist and a.title): ap.error('--lrclib needs --artist and --title')
        lrclib(out, a.artist, a.title, a.album, dur)


if __name__ == '__main__':
    main()
