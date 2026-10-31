// render.mjs: drives the film page in headless Chrome and writes stills, contact sheets, frame strips, crops, frames and the mp4.
// Copy it to the project root (new_project.py does) and run it from there: it resolves puppeteer-core from the project's
// node_modules and serves the project folder, so pages load /assets/..., /src/... and /node_modules/... .
// Times are seconds of the song file. The film's range and shots come from assets/timing.json; --timing=PATH reads another
// file with the same fields (a look test's clip). The page contract is in the skill's references/pipeline.md.
//
//   node render.mjs --serve                                          preview: open the printed URL in Chrome, then renderAt(95.6)
//   node render.mjs --list                                           the shots and their frame ranges
//   node render.mjs --still=95.6 [--out=out/check/a.png]             one full frame (PNG); --still=a,b,c writes several
//   node render.mjs --sheet=84.7:97:0.5 --cols=6 --w=320 [--out=..]  contact sheet of a range (start:end:step) ...
//   node render.mjs --sheet=95.5,95.55,95.6 --cols=3 --w=640         ... or of listed times
//   node render.mjs --shot=s09 --sheet [--n=12]                      n frames spread over one shot
//   node render.mjs --strip=95.45:95.7 --cols=8 --w=240              every frame of a moment (accents, cuts)
//   node render.mjs --sheet=95.6 --crop=700,300,500,400 --w=1000     full-resolution crop (x,y,w,h in frame pixels)
//   node render.mjs --film-sheet [--n=48]                            the whole film, n frames evenly spread
//   node render.mjs --frames [--shots=s07,s08] [--workers=3] [--reverse] [--tag=NAME]
//                                                                    frames -> out/frames (out/frames_NAME with --tag)
//   node render.mjs --encode [--shots=s07,s08 | --range=a:b] [--tag=NAME] [--out=..] [--crf=18] [--audio=PATH]
//                                                                    frames + the song -> mp4. The default name is
//                                                                    out/<project>_rebuild.mp4 (out/check/... for a part), so a
//                                                                    delivered cut is never overwritten: pass --out for a version.
//                                                                    Sound: --audio, else assets/audio/film.wav, else the song in
//                                                                    assets/ (both on the song's own time line).
//                                                                    --fadein / --fadeout in seconds (0 = none).
//   node render.mjs --compare=a,b                                    out/frames_a vs out/frames_b byte for byte ('-' = out/frames)
//   node render.mjs --eval="FILM.shots.length" [--at=95.6]           run an expression in the page (after drawing time --at)
//
//   --page=look_tests/x/index.html renders another page; --q="text=0&use=_example" passes page switches; --fw/--fh change the
//   frame size; --root=DIR (default: the current directory); --chrome=PATH; --chrome-args="--flag1 --flag2"; --verbose.
//
// Determinism: render some shots with several workers into one --tag, again with --reverse --workers=1 into another --tag, then
// --compare the two. A frame that differs depends on what was drawn before it.
import puppeteer from 'puppeteer-core';
import http from 'node:http';
import { mkdirSync, writeFileSync, existsSync, readdirSync, readFileSync, createReadStream, statSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, join, extname, normalize, resolve, basename, relative, sep } from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).map(a => { const m = /^--([^=]+)(?:=(.*))?$/s.exec(a); return m ? [m[1], m[2] ?? true] : [a, true]; }));
const str = k => (typeof args[k] === 'string' ? args[k] : null);
const root = resolve(str('root') || process.cwd());
const rel = p => relative(root, p) || '.';
const timingFile = resolve(root, str('timing') || 'assets/timing.json');
if (!existsSync(timingFile)) { console.error(`no ${rel(timingFile)}: write it with tools/make_timing.py, or pass --timing=PATH`); process.exit(1); }
const T = JSON.parse(readFileSync(timingFile, 'utf8'));
const fps = +T.fps, W = +(args.fw || T.w), H = +(args.fh || T.h);
const firstFrame = te => Math.ceil((te - T.t0) * fps - 1e-6);            // a shot owns the frames at or after its start, before its end
const NF = firstFrame(T.t1);
const SHOTS = (Array.isArray(T.shots) && T.shots.length ? T.shots : [{ id: 'all', name: '', t0: T.t0, t1: T.t1 }])
  .map(s => ({ ...s, f0: Math.max(0, firstFrame(s.t0)), f1: Math.min(NF, firstFrame(s.t1)) }));
const project = basename(root);
const FRAMES = join(root, 'out', str('tag') ? `frames_${args.tag}` : 'frames');
const name = F => `f${String(F).padStart(5, '0')}.jpg`, timeOf = F => T.t0 + F / fps;
const outFile = dflt => resolve(root, str('out') || dflt);              // resolve(), not join(): an absolute --out stays absolute
const save = (file, url) => { mkdirSync(dirname(file), { recursive: true }); writeFileSync(file, Buffer.from(url.split(',')[1], 'base64')); };
function wanted() {
  const l = str('shots') ? args.shots.split(',') : str('shot') && !args.sheet ? [args.shot] : null;
  if (l) for (const id of l) if (!SHOTS.find(s => s.id === id)) { console.error(`no shot ${id} in ${rel(timingFile)}`); process.exit(1); }
  return l;
}
const AUDIO_EXT = ['.wav', '.flac', '.m4a', '.mp3', '.aac', '.ogg', '.opus'];
function findAudio() {
  if (str('audio')) return resolve(root, args.audio);
  const film = join(root, 'assets', 'audio', 'film.wav');
  if (existsSync(film)) return film;
  const dir = join(root, 'assets'), found = existsSync(dir) ? readdirSync(dir).filter(f => AUDIO_EXT.includes(extname(f).toLowerCase())).sort() : [];
  if (!found.length) { console.error('no audio file in assets/: put the song there, or pass --audio=PATH'); process.exit(1); }
  if (found.length > 1) console.warn(`several audio files in assets/; using ${found[0]} (pass --audio=PATH to choose)`);
  return join(dir, found[0]);
}

if (args.list) {
  for (const s of SHOTS) console.log(`${String(s.id).padEnd(8)} ${s.t0.toFixed(3)}-${s.t1.toFixed(3)}  ${(s.t1 - s.t0).toFixed(2).padStart(6)} s  frames ${s.f0}-${s.f1 - 1}  ${s.name || ''}`);
  console.log(`${SHOTS.length} shots, ${NF} frames at ${fps} fps, ${W}x${H}, song ${T.t0}-${T.t1} s`); process.exit(0);
}
if (args.compare) {                                  // --compare=A,B: frames_A and frames_B byte for byte ('-' for out/frames)
  const [A, B] = String(args.compare).split(',').map(x => join(root, 'out', x === '-' ? 'frames' : `frames_${x}`)), diff = [];
  const files = readdirSync(A).filter(f => f.endsWith('.jpg')).sort(); let same = 0, missing = 0;
  for (const f of files) { if (!existsSync(join(B, f))) { missing++; continue; } if (readFileSync(join(A, f)).equals(readFileSync(join(B, f)))) same++; else diff.push(f); }
  console.log(`${same} identical, ${diff.length} different${missing ? `, ${missing} only in ${rel(A)}` : ''}${diff.length ? ': ' + diff.slice(0, 20).join(' ') + (diff.length > 20 ? ' ...' : '') : ''}`);
  process.exit(diff.length ? 1 : 0);
}
if (args.encode) {
  const l = wanted(); let F0 = 0, F1 = NF;
  if (l) { F0 = Math.min(...l.map(id => SHOTS.find(s => s.id === id).f0)); F1 = Math.max(...l.map(id => SHOTS.find(s => s.id === id).f1)); }
  if (str('range')) { const [a, b] = args.range.split(':').map(Number); F0 = Math.max(0, firstFrame(a)); F1 = Math.min(NF, firstFrame(b)); }
  const part = l ? l.join('_') : str('range') ? `range_${args.range.replace(':', '-')}` : null;
  const out = outFile(part ? `out/check/${part}.mp4` : `out/${project}${str('tag') ? '_' + args.tag : ''}_rebuild.mp4`), n = F1 - F0, len = n / fps;
  const missing = []; for (let F = F0; F < F1; F++) if (!existsSync(join(FRAMES, name(F)))) missing.push(F);
  if (missing.length) { console.error(`${missing.length} frames missing in ${rel(FRAMES)} (first ${name(missing[0])}): run --frames for them first`); process.exit(1); }
  const AUDIO = findAudio();
  const fadeIn = +(args.fadein ?? (F0 === 0 ? 0.05 : 0.15)), fadeOut = +(args.fadeout ?? (F1 === NF ? 1.2 : 0.4));
  const af = [fadeIn > 0 && `afade=t=in:st=0:d=${fadeIn}`, fadeOut > 0 && `afade=t=out:st=${Math.max(0, len - fadeOut).toFixed(4)}:d=${fadeOut}`].filter(Boolean);
  mkdirSync(dirname(out), { recursive: true });
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-framerate', String(fps), '-start_number', String(F0), '-i', join(FRAMES, 'f%05d.jpg'),
    '-ss', timeOf(F0).toFixed(6), '-t', len.toFixed(6), '-i', AUDIO, '-frames:v', String(n), ...(af.length ? ['-af', af.join(',')] : []), '-c:a', 'aac', '-b:a', '256k',
    // the frames are full-range JPEG (BT.601 matrix); the mp4 is written as standard video: limited range, BT.709, tagged as such
    '-vf', 'scale=in_range=pc:in_color_matrix=bt601:out_range=tv:out_color_matrix=bt709:flags=bicubic+accurate_rnd+full_chroma_int,format=yuv420p,setparams=range=tv:colorspace=bt709:color_primaries=bt709:color_trc=bt709',
    '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', String(args.crf || 18), '-profile:v', 'high', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-shortest', out], { stdio: 'inherit' });
  console.log(`wrote ${rel(out)} (${n} frames, ${len.toFixed(2)} s, from ${timeOf(F0).toFixed(3)} s of the song; sound from ${rel(AUDIO)})`); process.exit(0);
}

// static file server (ES modules do not load from file://), rooted at the project folder
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.css': 'text/css',
  '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.wav': 'audio/wav', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp',
  '.svg': 'image/svg+xml', '.ttf': 'font/ttf', '.otf': 'font/otf', '.woff': 'font/woff', '.woff2': 'font/woff2', '.glb': 'model/gltf-binary',
  '.gltf': 'model/gltf+json', '.bin': 'application/octet-stream', '.hdr': 'application/octet-stream', '.wasm': 'application/wasm', '.txt': 'text/plain; charset=utf-8' };
const server = http.createServer((req, res) => {
  if (req.url.startsWith('/favicon')) { res.writeHead(204); res.end(); return; }
  const p = normalize(join(root, decodeURIComponent(req.url.split('?')[0])));
  if (!(p === root || p.startsWith(root + sep)) || !existsSync(p) || !statSync(p).isFile()) { res.writeHead(404); res.end(); return; }
  const size = statSync(p).size, m = /bytes=(\d+)-(\d*)/.exec(req.headers.range || ''), type = MIME[extname(p).toLowerCase()] || 'application/octet-stream';
  if (m) { const s = +m[1], e = m[2] ? +m[2] : size - 1; res.writeHead(206, { 'content-type': type, 'content-range': `bytes ${s}-${e}/${size}`, 'accept-ranges': 'bytes', 'content-length': e - s + 1 }); createReadStream(p, { start: s, end: e }).pipe(res); }
  else { res.writeHead(200, { 'content-type': type, 'content-length': size, 'accept-ranges': 'bytes', 'cache-control': 'no-store' }); createReadStream(p).pipe(res); }
}).listen(args.serve ? +(args.port || 0) : 0, '127.0.0.1');
await new Promise(r => server.on('listening', r));
const page0 = (str('page') || 'index.html').replace(/^\/+/, '');
const url = `http://127.0.0.1:${server.address().port}/${page0}?w=${W}&h=${H}&fps=${fps}&timing=/${encodeURI(relative(root, timingFile).split(sep).join('/'))}${args.q ? '&' + args.q : ''}`;
if (args.serve) { console.log(`preview: ${url}   (Ctrl+C to stop; in the console: renderAt(${T.t0}))`); await new Promise(() => {}); }

const CHROME = [str('chrome'), process.env.CHROME_PATH, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium',
  '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find(p => p && existsSync(p));
if (!CHROME) { console.error('Chrome not found: pass --chrome=/path/to/chrome or set CHROME_PATH'); process.exit(1); }
const GPU = process.platform === 'darwin' ? ['--use-angle=metal'] : ['--enable-unsafe-swiftshader'];   // macOS: the real GPU; elsewhere WebGL may fall back to SwiftShader
async function open() {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, protocolTimeout: 0,
    args: ['--ignore-gpu-blocklist', ...GPU, '--enable-gpu-rasterization', `--window-size=${W},${H}`, '--disable-renderer-backgrounding',
      '--disable-background-timer-throttling', ...(str('chrome-args') ? args['chrome-args'].split(/\s+/).filter(Boolean) : [])] });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  // page messages go to stderr, so --eval's stdout stays clean; a failed request is reported once, with its path
  page.on('console', m => { if (/^Failed to load resource/.test(m.text())) return; if (m.type() === 'error' || m.type() === 'warn' || args.verbose) console.error(`[page ${m.type()}]`, m.text().slice(0, 1500)); });
  page.on('pageerror', e => console.error('[page error]', e.message.slice(0, 1500)));
  page.on('response', r => { if (r.status() < 400) return; const p = decodeURIComponent(new URL(r.url()).pathname);
    console.error(/^\/src\/shots\/[^/]+\.js$/.test(p) ? `[page] ${p} does not exist yet: that shot draws src/shots/_placeholder.js` : `[page ${r.status()}] ${p}`); });
  await page.goto(`${url}&headless=1`);
  await page.evaluate(() => window.READY);
  return { browser, page };
}
const grab = (page, t, type = 'image/jpeg', qual = 0.95) => page.evaluate(async (t, type, qual) => { await window.renderAt(t); return document.getElementById('stage').toDataURL(type, qual); }, t, type, qual);
const times = s => String(s).includes(':') ? (([a, b, st = 1]) => { const o = []; for (let t = a; t <= b + 1e-6; t += st) o.push(+t.toFixed(4)); return o; })(String(s).split(':').map(Number)) : String(s).split(',').map(Number);

if (args.frames) {
  const first = await open(), film = await first.page.evaluate(() => window.FILM || null);
  const shots = film && Array.isArray(film.shots) && film.shots.length ? film.shots : SHOTS.map(s => ({ ...s, head: s.id }));
  const want = wanted() || shots.map(s => s.id);
  const jobs = [];                                  // one job per head (shots that continue one another stay together), frames in order
  for (const head of [...new Set(shots.map(s => s.head || s.id))]) {
    const fr = []; for (const s of shots) if ((s.head || s.id) === head && want.includes(s.id)) for (let F = s.f0; F < s.f1; F++) fr.push(F);
    if (fr.length) jobs.push({ head, fr });
  }
  jobs.sort((a, b) => b.fr.length - a.fr.length);
  if (args.reverse) for (const j of jobs) j.fr.reverse();            // --reverse: draw every job back to front (the determinism check)
  mkdirSync(FRAMES, { recursive: true });
  for (const j of jobs) for (const F of j.fr) rmSync(join(FRAMES, name(F)), { force: true });
  const workers = Math.max(1, Math.min(+(args.workers || 1), jobs.length)), total = jobs.reduce((a, j) => a + j.fr.length, 0), t0 = Date.now(); let next = 0, done = 0;
  console.log(`${total} frames of ${want.length > 8 ? want.length + ' shots' : want.join(', ')} in ${jobs.length} job(s), ${workers} worker(s) -> ${rel(FRAMES)}`);
  const pool = [first, ...await Promise.all(Array.from({ length: workers - 1 }, () => open()))];
  await Promise.all(pool.map(async ({ page }) => {
    while (next < jobs.length) { const j = jobs[next++];
      for (const F of j.fr) { save(join(FRAMES, name(F)), await grab(page, timeOf(F))); if (++done % 150 === 0 || done === total) console.log(`${done}/${total}  ${((Date.now() - t0) / done).toFixed(0)} ms per frame overall`); } }
  }));
  await Promise.all(pool.map(p => p.browser.close())); server.close(); process.exit(0);
}

const { browser, page } = await open();
if (args.eval) {
  if (args.at !== undefined) await page.evaluate(t => window.renderAt(t), +args.at);
  console.log(await page.evaluate(async src => { let v = (0, eval)(src); if (v && typeof v.then === 'function') v = await v; return typeof v === 'string' ? v : JSON.stringify(v, null, 1); }, String(args.eval)));
} else if (args.sheet || args.strip || args['film-sheet']) {
  let ts;
  if (args.strip) { const [a, b] = String(args.strip).split(':').map(Number); ts = []; for (let F = Math.max(0, firstFrame(a)); F < NF && timeOf(F) <= b + 1e-6; F++) ts.push(timeOf(F)); }
  else if (args['film-sheet']) { const n = +(args.n || 48); ts = Array.from({ length: n }, (_, i) => timeOf(Math.round((NF - 1) * i / (n - 1)))); }
  else if (args.sheet === true) {
    const s = SHOTS.find(x => x.id === args.shot); if (!s) { console.error('--sheet without times needs --shot=ID'); process.exit(1); }
    const n = +(args.n || 12); ts = Array.from({ length: n }, (_, i) => timeOf(Math.round(s.f0 + (s.f1 - 1 - s.f0) * i / Math.max(1, n - 1))));
  } else ts = times(args.sheet);
  const cols = +(args.cols || (args.strip || args['film-sheet'] ? 8 : 6)), cw = +(args.w || 240), crop = args.crop ? String(args.crop).split(',').map(Number) : null;
  const out = outFile(args.strip ? 'out/check/strip.jpg' : args['film-sheet'] ? 'out/check/film_sheet.jpg' : 'out/check/sheet.jpg'), t0 = Date.now();
  const order = ts.map((t, i) => [t, i]).sort((a, b) => a[0] - b[0]);       // draw in time order (cheaper for pages that simulate)
  const data = await page.evaluate(async (order, cols, cw, crop) => {
    const st = document.getElementById('stage'), [sx, sy, sw, sh] = crop || [0, 0, st.width, st.height], ch = Math.round(cw * sh / sw), rows = Math.ceil(order.length / cols);
    const c = document.createElement('canvas'); c.width = cols * cw; c.height = rows * ch; const g = c.getContext('2d'); g.fillStyle = '#222'; g.fillRect(0, 0, c.width, c.height);
    for (const [t, i] of order) {
      await window.renderAt(t);
      const x = (i % cols) * cw, y = Math.floor(i / cols) * ch; g.drawImage(st, sx, sy, sw, sh, x, y, cw, ch);
      const lab = `${(window.INFO && window.INFO.shot) || ''} ${t.toFixed(2)}`; g.font = '14px Menlo, monospace'; g.fillStyle = 'rgba(0,0,0,.6)'; g.fillRect(x, y, 8.6 * lab.length + 8, 18); g.fillStyle = '#fff'; g.fillText(lab, x + 4, y + 14);
    }
    return c.toDataURL('image/jpeg', 0.9);
  }, order, cols, cw, crop);
  save(out, data); console.log(`wrote ${rel(out)} (${ts.length} frames, ${((Date.now() - t0) / ts.length).toFixed(0)} ms per frame)`);
} else if (args.still !== undefined && args.still !== true) {
  const ts = times(args.still);
  for (const t of ts) { const out = ts.length === 1 ? outFile(`out/check/still_${t}.png`) : resolve(root, `out/check/still_${t}.png`); save(out, await grab(page, t, 'image/png')); console.log('wrote', rel(out)); }
} else console.log('nothing to do: pass --serve, --list, --still, --sheet, --strip, --film-sheet, --frames, --encode, --compare or --eval (see the top of render.mjs)');
await browser.close(); server.close();
