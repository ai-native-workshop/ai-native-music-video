// caption.js: the sung line, each character appearing as it is sung. The words come from assets/lyrics/lyrics.json (written by
// tools/build_lyrics.py); nobody types them. Rules that came out of earlier films:
//   - a character starts to appear `lead` (0.12 s) before it is sung and is fully there `fade` later;
//   - a line stays after its last character until `hold` has passed or the next line is about to start, whichever comes first,
//     and is gone `gap` before the next line's first character appears: two lines never overlap;
//   - a line that has to leave early rises a little as it fades;
//   - check the schedule as a table, not by eye: node render.mjs --eval="CAPTION_TABLE()";
//   - keep faces and key action out of the caption band while a line is up, and check that every character exists in the font.
// Text is drawn on a small software canvas and copied onto the stage: large text with a blurred shadow drawn straight onto a GPU
// canvas came out a level or two different between page loads, which breaks the byte-for-byte determinism check.
export const FACE = '"PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif';
export const FONTS = [`600 64px ${FACE}`];

export function createCaption(lines, opts = {}) {
  const P = { lead: 0.12, fade: 0.12, hold: 1.5, gap: 0.06, out: 0.35, rise: 0.012, size: 0.052, x: 0.5, y: 0.9, align: 'center',
    color: '#ffffff', weight: 600, shadow: 'rgba(0,0,0,0.6)', maxWidth: 0.9, ...opts };
  const sched = lines.map((l, k) => {
    const next = lines[k + 1], appear = l.chars[0][0] - P.lead, full = Math.max(...l.chars.map(c => c[0])) - P.lead + P.fade;   // last character fully shown
    let leave = l.end + P.hold, early = false;
    if (next) { const limit = next.chars[0][0] - P.lead - P.gap; if (limit < leave) { leave = limit; early = true; } }
    const fadeOut = Math.max(0.08, Math.min(P.out, leave - full));      // start fading only once the last character is fully there
    return { l, appear, leave, early, fadeOut, full };
  });
  let band = null;                                  // the software canvas; redrawn from scratch every frame
  return {
    draw(g, t, o = {}) {
      const Q = { ...P, ...o }, W = g.canvas.width, H = g.canvas.height;
      for (const s of sched) {
        if (t < s.appear || t >= s.leave) continue;
        const alpha = Math.max(0, Math.min(1, (s.leave - t) / (o.out ?? s.fadeOut)));
        let size = Math.round(Q.size * Math.min(W, H));
        const bh = Math.ceil(size * 2.2);
        if (!band || band.width !== W || band.height !== bh) { band = document.createElement('canvas'); band.width = W; band.height = bh; }
        const c = band.getContext('2d', { willReadFrequently: true });
        c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, W, bh);
        const chars = [...s.l.text];
        c.font = `${Q.weight} ${size}px ${FACE}`;
        let ws = chars.map(ch => c.measureText(ch).width), tw = ws.reduce((a, b) => a + b, 0);
        if (tw > Q.maxWidth * W) { size = Math.floor(size * Q.maxWidth * W / tw); c.font = `${Q.weight} ${size}px ${FACE}`; ws = chars.map(ch => c.measureText(ch).width); tw = ws.reduce((a, b) => a + b, 0); }
        let x = Q.align === 'left' ? Q.x * W : Q.align === 'right' ? Q.x * W - tw : Q.x * W - tw / 2;
        const base = Math.round(bh * 0.62);
        c.fillStyle = Q.color; c.shadowColor = Q.shadow; c.shadowBlur = Math.round(size * 0.22); c.textBaseline = 'alphabetic';
        chars.forEach((ch, j) => {
          const a = Math.max(0, Math.min(1, (t - (s.l.chars[j][0] - Q.lead)) / Q.fade));
          if (a > 0 && ch !== ' ') { c.globalAlpha = a; c.fillText(ch, x, base); }
          x += ws[j];
        });
        const y = Q.y * H - base - (s.early ? (1 - alpha) * Q.rise * H : 0);
        g.save(); g.globalAlpha = alpha; g.drawImage(band, 0, Math.round(y)); g.restore();
      }
    },
    // [{ i, in, sung, end, out, early, short }]: early = it leaves because the next line comes; short = it leaves before its last
    // character is fully shown (a defect: put the two lines in one row, or let the old one move away instead of vanishing)
    table(t0 = -Infinity, t1 = Infinity) {
      return sched.filter(s => s.leave > t0 && s.appear < t1).map(s => ({ i: s.l.i, in: +s.appear.toFixed(3), sung: s.l.chars[0][0], end: s.l.end,
        out: +s.leave.toFixed(3), early: s.early, short: s.leave < s.full + 0.04 }));
    },
  };
}
