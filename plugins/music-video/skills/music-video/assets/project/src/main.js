// main.js: the film page. window.renderAt(t) draws song time t (seconds of the song file) into canvas#stage, and every frame is a
// pure function of t: no Math.random, Date.now or performance.now, no state carried from one frame to the next.
//
// Contract with render.mjs (the skill's references/pipeline.md):
//   window.READY        a promise: data, fonts and shot modules are loaded
//   window.renderAt(t)  draws the frame for song time t (async)
//   window.FILM         { t0, t1, fps, w, h, frames, shots: [{ id, name, t0, t1, f0, f1, head }] }
//   window.INFO         { shot } after each renderAt (it labels the contact sheets)
// Query: w, h, fps, timing (path of the timing file, default /assets/timing.json), headless=1 (set by render.mjs), and switches:
//   text=0     no lyrics             use=NAME    every shot draws src/shots/NAME.js (sketches, the example)
// Opened in a normal tab (render.mjs --serve) the page adds a time bar: drag it, press space to play with the song, arrows step.
//
// A shot is src/shots/<id>.js (ids from timing.json; a shot whose file does not exist yet draws _placeholder.js):
//   export default {
//     draw(K) { ... },                     paint the WHOLE frame for time K.t, background included (K: see makeKit below)
//     caption(K) { return { y: 0.85 } },   optional: where the lyric line sits during this shot, or false to hide it
//     head: 's07',                         optional: render in the same job as s07 (only for shots that share a simulation)
//   };
import * as L from './lib.js';
import { createCaption, FONTS } from './caption.js';

const q = new URLSearchParams(location.search);
const W = +(q.get('w') || 1920), H = +(q.get('h') || 1080);
const stage = document.getElementById('stage'); stage.width = W; stage.height = H;
const g = stage.getContext('2d');
let T = null, S = null, CAP = null, SHOTS = [];
const MODS = {};

async function getJSON(url, optional = false) {
  const r = await fetch(url);
  if (!r.ok) { if (optional) return null; throw new Error(`${url}: HTTP ${r.status}`); }
  return r.json();
}

// The song: beat grid and measured curves from assets/analysis/audio.json (tools/analyze_audio.py); null until it exists.
function makeSong(A) {
  if (!A) return null;
  const beat = A.beat, bar = 4 * beat, bar0 = A.bar0, fps = A.fps;
  const curve = (name, t) => {               // a measured 0..1 curve at time t: level, vocal, bass, air, width, onset, kick, snare
    const v = A[name]; if (!v) return 0;
    const x = Math.max(0, Math.min(v.length - 1.001, t * fps)), i = Math.floor(x), f = x - i; return v[i] * (1 - f) + v[i + 1] * f;
  };
  return { bpm: A.bpm, beat, bar, bar0, curve, beats: A.beats || null,
    beatPos: t => (t - bar0) / beat, barPos: t => (t - bar0) / bar, beatTime: k => bar0 + k * beat, barTime: k => bar0 + k * bar };
}

function shotAt(t) { for (const s of SHOTS) if (t >= s.t0 && t < s.t1) return s; return t < SHOTS[0].t0 ? SHOTS[0] : SHOTS[SHOTS.length - 1]; }

// K: everything a shot needs, built anew for every frame, so nothing leaks from one frame into the next.
function makeKit(t, shot) {
  return {
    g, W, H, t,                                   // the canvas context (reset before every frame), the frame size, song time
    frame: Math.round((t - T.t0) * T.fps),        // frame number from the film's start
    shot, lt: t - shot.t0, dur: shot.t1 - shot.t0, u: L.clamp((t - shot.t0) / (shot.t1 - shot.t0)),   // time and progress in the shot
    T, S, q, L,                                   // timing.json (T.kicks, T.snares, T.downbeats, T.lines), the song, page switches, helpers
    rng: seed => L.rng(seed),                     // seeded random numbers; never Math.random
    hit: (times, decay = 0.2) => L.hitEnv(t, times, decay),   // 1 on each time in the list ([t] or [t, strength]), then decaying
  };
}

function resetContext() {                         // a leaked transform, alpha, filter or shadow would spoil every later layer
  g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = 1; g.globalCompositeOperation = 'source-over'; g.filter = 'none';
  g.shadowBlur = 0; g.shadowColor = 'rgba(0,0,0,0)'; g.shadowOffsetX = 0; g.shadowOffsetY = 0; g.setLineDash([]);
  g.lineCap = 'butt'; g.lineJoin = 'miter'; g.imageSmoothingEnabled = true; g.textAlign = 'start'; g.textBaseline = 'alphabetic';
}

function drawFrame(t) {
  const shot = shotAt(t), mod = MODS[shot.id];
  resetContext(); g.fillStyle = '#000'; g.fillRect(0, 0, W, H);
  const K = makeKit(t, shot);
  g.save(); try { mod.draw(K); } finally { g.restore(); }
  const cap = mod.caption ? mod.caption(K) : {};
  if (CAP && q.get('text') !== '0' && cap !== false) { resetContext(); CAP.draw(g, t, cap || {}); }
  window.INFO.shot = shot.id;
}

async function loadShot(id) {
  try { return (await import(`./shots/${id}.js`)).default; }
  catch (e) { if (!/Failed to fetch|error loading dynamically imported module|Importing a module script failed/i.test(String(e))) throw e; return (await import('./shots/_placeholder.js')).default; }
}

window.INFO = { shot: null };
window.READY = (async () => {
  T = await getJSON(q.get('timing') || '/assets/timing.json');
  S = makeSong(await getJSON('/assets/analysis/audio.json', true));
  const LY = await getJSON('/assets/lyrics/lyrics.json', true);
  await Promise.all(FONTS.map(f => document.fonts.load(f).catch(() => null)));      // fonts must be ready before the first frame
  if (LY) CAP = createCaption(LY.lines);
  const firstFrame = te => Math.ceil((te - T.t0) * T.fps - 1e-6);                     // a shot owns the frames from its start, before its end
  const raw = Array.isArray(T.shots) && T.shots.length ? T.shots : [{ id: 'all', name: '', t0: T.t0, t1: T.t1 }];
  SHOTS = raw.map(s => ({ ...s, f0: Math.max(0, firstFrame(s.t0)), f1: firstFrame(s.t1) }));
  for (const s of SHOTS) { MODS[s.id] = await loadShot(q.get('use') || s.id); s.head = MODS[s.id].head || s.id; }
  window.FILM = { t0: T.t0, t1: T.t1, fps: T.fps, w: W, h: H, frames: firstFrame(T.t1),
    shots: SHOTS.map(({ id, name, t0, t1, f0, f1, head }) => ({ id, name, t0, t1, f0, f1, head })) };
  window.CAPTION_TABLE = () => (CAP ? CAP.table(T.t0, T.t1) : []);   // node render.mjs --eval="CAPTION_TABLE()": each line's in and out
  if (q.get('headless') !== '1') preview();
})();
window.renderAt = async t => { await window.READY; drawFrame(t); };

// Preview controls for a normal browser tab. They only call renderAt-style drawing; the rendered frames never depend on them.
function preview() {
  const bar = document.createElement('div');
  bar.style.cssText = 'position:fixed;left:0;right:0;bottom:0;display:flex;gap:10px;align-items:center;padding:6px 10px;background:rgba(0,0,0,.72);color:#ddd;font:13px Menlo,monospace';
  const btn = document.createElement('button'); btn.textContent = 'play';
  const range = Object.assign(document.createElement('input'), { type: 'range', min: T.t0, max: T.t1, step: 1 / T.fps, value: T.t0 }); range.style.flex = '1';
  const label = document.createElement('span'); bar.append(btn, range, label); document.body.append(bar);
  stage.style.cssText = 'max-width:100vw;max-height:calc(100vh - 40px);margin:auto';
  const audio = q.get('audio') ? new Audio(q.get('audio')) : null;
  const show = t => { drawFrame(t); range.value = t; label.textContent = `${window.INFO.shot}  ${(+t).toFixed(2)} s`; };
  let playing = false;
  const loop = () => {
    if (!playing) return;
    const t = audio ? audio.currentTime : +range.value + 1 / 60;
    if (t >= T.t1) { playing = false; btn.textContent = 'play'; if (audio) audio.pause(); return; }
    show(t); requestAnimationFrame(loop);
  };
  range.oninput = () => { if (audio) audio.currentTime = +range.value; show(+range.value); };
  btn.onclick = () => { playing = !playing; btn.textContent = playing ? 'pause' : 'play'; if (playing) { if (audio) { audio.currentTime = +range.value; audio.play(); } loop(); } else if (audio) audio.pause(); };
  addEventListener('keydown', e => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') show(Math.min(T.t1, Math.max(T.t0, +range.value + (e.key === 'ArrowRight' ? 1 : -1) / T.fps)));
    if (e.key === ' ') { e.preventDefault(); btn.click(); }
  });
  show(T.t0);
}
