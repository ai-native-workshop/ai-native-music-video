// _example.js: a sketch that shows the conventions; render it in every shot with --q="use=_example". Replace it, don't build on it.
// Everything is a function of K.t: the ground breathes with the measured loudness, stars sit where the hash puts them, a ring hits
// on the low accents measured by make_timing.py, the beat ticks along the bottom, and frame 0 is a finished picture with the
// title, because in a feed the first frame is the thumbnail.
export default {
  draw(K) {
    const { g, W, H, t, S, T, L } = K;
    const level = S ? S.curve('level', t) : 0.5;
    const sky = g.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, `hsl(226, 46%, ${9 + 9 * level}%)`); sky.addColorStop(1, `hsl(262, 38%, ${4 + 6 * level}%)`);
    g.fillStyle = sky; g.fillRect(0, 0, W, H);
    for (let i = 0; i < 180; i++) {                                   // fixed by the hash, twinkling with time: never Math.random
      const x = L.hash(i, 1) * W, y = L.hash(i, 2) * H * 0.8, tw = 0.5 + 0.5 * Math.sin(t * (0.8 + 2 * L.hash(i, 3)) + 6.283 * L.hash(i, 4));
      g.globalAlpha = 0.2 + 0.6 * tw; g.fillStyle = '#fff'; g.fillRect(Math.round(x), Math.round(y), 2, 2);
    }
    g.globalAlpha = 1;
    const hit = K.hit(T.kicks || [], 0.25), R = Math.min(W, H) * (0.17 + 0.04 * hit);
    g.strokeStyle = `rgba(255, 214, 160, ${0.3 + 0.6 * hit})`; g.lineWidth = 3 + 9 * hit;
    g.beginPath(); g.arc(W / 2, H * 0.44, R, 0, Math.PI * 2); g.stroke();
    if (S) {
      const b = S.beatPos(t), ph = b - Math.floor(b), slot = ((Math.floor(b) % 4) + 4) % 4;
      g.fillStyle = `rgba(255,255,255,${0.7 * (1 - ph)})`; g.fillRect(W * (slot + 0.5) / 4 - 24, H - 14, 48, 5);
    }
    const title = document.title, k = 1 - L.seg(t, T.t0 + 1.5, T.t0 + 2.5);   // on the cover from frame 0, gone by 2.5 s
    if (k > 0 && title) {
      g.globalAlpha = k; g.fillStyle = '#fff'; g.textAlign = 'center';
      g.font = `600 ${Math.round(Math.min(W, H) * 0.08)}px "PingFang SC", "Noto Sans CJK SC", sans-serif`; g.fillText(title, W / 2, H * 0.46);
      g.globalAlpha = 1;
    }
  },
};
