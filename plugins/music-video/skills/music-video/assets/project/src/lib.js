// lib.js: small pure helpers for shots. Nothing here keeps state, so every frame stays a function of t alone.
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, k) => a + (b - a) * k;
export const mix = (a, b, k) => (Array.isArray(a) ? a.map((v, i) => lerp(v, b[i], k)) : lerp(a, b, k));
export const seg = (t, a, b) => (b > a ? clamp((t - a) / (b - a)) : t >= a ? 1 : 0);        // 0..1 progress of t through [a, b]
export const ease = k => k * k * (3 - 2 * k);                                                  // smoothstep
export const easeIn = k => k * k * k;
export const easeOut = k => 1 - (1 - k) ** 3;
export const easeInOut = k => (k < 0.5 ? 4 * k * k * k : 1 - (-2 * k + 2) ** 3 / 2);
export const backOut = (k, s = 1.70158) => 1 + (s + 1) * (k - 1) ** 3 + s * (k - 1) ** 2;        // overshoots, then settles

// Keyframes: kf(t, [[t0, v0], [t1, v1], ...], easeFn). Values are numbers or arrays; the first and last values hold outside.
export function kf(t, keys, fn = ease) {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) if (t < keys[i][0]) return mix(keys[i - 1][1], keys[i][1], fn(seg(t, keys[i - 1][0], keys[i][0])));
  return keys[keys.length - 1][1];
}

// Integer hash -> [0, 1): the same (i, seed) always gives the same number. Use it for anything that must stay put between frames.
export function hash(i, seed = 0) {
  let x = (Math.imul(i | 0, 0x9e3779b1) ^ Math.imul((seed | 0) + 0x632be5ab, 0x85ebca77)) >>> 0;
  x ^= x >>> 16; x = Math.imul(x, 0x7feb352d); x ^= x >>> 15; x = Math.imul(x, 0x846ca68b); x ^= x >>> 16;
  return (x >>> 0) / 4294967296;
}

// Seeded generator (mulberry32): const r = rng(7); r() -> [0, 1). Make it inside draw() every frame; never keep one across frames.
export function rng(seed) {
  let a = (seed | 0) >>> 0;
  return () => { a = (a + 0x6d2b79f5) >>> 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// Smooth 1D value noise in [0, 1).
export const noise1 = (x, seed = 0) => { const i = Math.floor(x), f = x - i; return lerp(hash(i, seed), hash(i + 1, seed), f * f * (3 - 2 * f)); };

// 1 at each time in the list (numbers, or [time, strength] pairs as in timing.json), decaying with time constant `decay` seconds.
export function hitEnv(t, times, decay = 0.2) {
  let v = 0;
  for (const h of times || []) { const [th, s] = Array.isArray(h) ? h : [h, 1]; if (th <= t) v = Math.max(v, s * Math.exp(-(t - th) / decay)); }
  return v;
}

// The last time in a sorted list at or before t (-Infinity if none).
export function lastBefore(times, t) {
  let r = -Infinity;
  for (const x of times || []) { const tx = Array.isArray(x) ? x[0] : x; if (tx <= t) r = tx; else break; }
  return r;
}

// Hold drawings for two frames ("on twos"): for poses and expressions, not for cameras.
export const onTwos = (t, fps = 24) => Math.floor(t * fps / 2 + 1e-9) * 2 / fps;

// A damped spring released at t0: 0 before, overshoots and settles to 1.
export function spring(t, t0, freq = 2.5, damp = 5) { if (t < t0) return 0; const x = t - t0; return 1 - Math.exp(-damp * x) * Math.cos(2 * Math.PI * freq * x); }

// '#rrggbb' -> 'rgba(r,g,b,a)'
export const rgba = (hex, a = 1) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; };
