// _placeholder.js: drawn by every shot whose file does not exist yet, so the whole film renders, with the right timing, from day one.
export default {
  draw(K) {
    const { g, W, H, t, shot, lt, dur, u } = K;
    g.fillStyle = '#1b1d24'; g.fillRect(0, 0, W, H);
    g.fillStyle = '#323848'; g.fillRect(0, H - 10, W * u, 10);
    g.fillStyle = '#a3abbd'; g.textAlign = 'center';
    g.font = `600 ${Math.round(Math.min(W, H) * 0.06)}px Menlo, "PingFang SC", monospace`; g.fillText(`${shot.id}  ${shot.name || ''}`, W / 2, H * 0.46);
    g.font = `${Math.round(Math.min(W, H) * 0.03)}px Menlo, monospace`; g.fillText(`${t.toFixed(2)} s   ${lt.toFixed(2)} / ${dur.toFixed(2)}`, W / 2, H * 0.53);
  },
};
