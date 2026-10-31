# music-video

一个 Claude Code skill：给一首歌做代码逐帧渲染的动画 MV。量歌、逐字歌词对时、并排试片、人物定妆、分镜、确定性渲染引擎、子代理并行、自查、合成、收尾，附八支成片的画风目录和样图。

在 Claude Code 里安装：

```
/plugin marketplace add ai-native-workshop/ai-native-music-video
/plugin install music-video@ai-native-music-video
```

skill 在 `skills/music-video/`，从它的 `SKILL.md` 开始读。背景见仓库首页的 README。

## English

A Claude Code skill for making a music video, or a short on part of a song, whose every frame is drawn by code. A browser page draws any moment of the song with Canvas, WebGL or three.js; headless Chrome renders it frame by frame and ffmpeg adds the song. The skill walks through measuring the song, timing the lyrics, look tests, characters, storyboard, a deterministic renderer, parallel shot agents, self-review and the wrap-up. It needs Node.js, Python 3 with numpy, scipy and Pillow, ffmpeg and Google Chrome. The documentation is in Chinese.
