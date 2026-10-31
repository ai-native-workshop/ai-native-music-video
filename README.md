# AI-native Music Video

**中文** · [English](README.en.md)

一个 [Claude Code](https://claude.com/claude-code) skill：给一首歌做动画 MV，每一帧都是代码画的。浏览器里的 Canvas、WebGL 或 three.js 能画出歌里任意一秒，无头 Chrome 逐帧渲染，ffmpeg 配上原曲。不用生图、生视频模型。

它整理自 2026 年 9–10 月用 Claude Opus 5.5 在 Claude Code 里做的八支片子。分工是：人定方向、看样片、按时间点挑错；Claude 写全部代码、自己检查画面。每支换了一种画风：

| 片子 | 长度 | 画风 | 引擎 |
|---|---|---|---|
| 林宥嘉《说谎》 | 全曲 4:24，横屏 | 手绘水彩绘本 | p5.js + p5.brush |
| 孙燕姿《我不难过》 | 全曲 5:20，横屏 | 纸雕灯箱 | Canvas 2D 纸层 + WebGL2 透光合成 |
| Billie Eilish《BIRDS OF A FEATHER》 | 末段副歌 39 秒，横屏 | 黄昏湖面上的 4.5 万只鸟 | three.js，子画面平均出运动模糊和景深 |
| FIELD OF VIEW《DAN DAN 心魅かれてく》 | 开头 26 秒，竖屏 | 会动的龙珠漫画 | three.js，游戏模型当底稿画成网点和墨线 |
| 张惠妹《人质》 | 后半首 91 秒，竖屏 | 水下的墨与红，首尾是花窗 | WebGL 二维流体 |
| 汪苏泷《万有引力》 | 54 秒，横屏 | 发光矢量的物理课 | Canvas 2D |
| 周杰伦《枫》 | 后段 102 秒，竖屏 | 叶绿素显影（做完第一版，未发布） | three.js 程序化植物 |
| 郑润泽《于是》 | 全曲 3:52，横屏 | 像素 + Q 版 | Canvas 2D 调色板缓冲 |

## 它做什么

- **流程**：量歌 → 取逐字歌词并对到人声上 → 提两三个方向，并行做试片给你挑 → 人物定妆 → 分镜和节拍表 → 从选中的试片长出整片引擎 → 子代理分镜头并行 → 用联系表、逐帧条、原尺寸局部自查 → 合成 → 按你的时间点修改 → 终检 → 四种比例的封面和投稿文案 → 收尾整理。每一步做完先给你看。
- **规则**：每一帧只由时间决定，所以能多进程乱序渲染、改哪段只重渲哪段，交付前正着倒着各渲一遍逐字节比对；歌词只当数据，不出现在任何模型输出里；第一帧就是封面；横竖屏由内容决定。
- **工具**：建项目、渲染（预览、联系表、逐帧条、局部、全片一览、帧序列、合成、比对）、量歌、取逐字歌词和对时间、去掉片段开头上一句的尾音、帧检查（亮度、黑帧、突变、颗粒是不是网格）、扫描文档里混进的歌词、填投稿文案。脚本在已经发布的片子上验证过：同样的输入，输出和当时逐字节相同。
- **经验**：八支片子的画风目录（怎么做、为什么适合那首歌、踩过的坑、速度）；人物的解剖和图层清单；八支片子里被指出的每个问题，以及以后要查什么。

## 它不做什么

- 不替你找音乐：音频由你提供（专辑原版，和歌词时间轴对得上的版本）。
- 不在回复、文件和代码里写歌词原文：歌词由脚本下载、处理，画面从数据里取字。
- 不替你投稿。

## 安装

在 Claude Code 里：

```
/plugin marketplace add ai-native-workshop/ai-native-music-video
/plugin install music-video@ai-native-music-video
```

或者作为个人 skill：

```bash
git clone https://github.com/ai-native-workshop/ai-native-music-video
cp -r ai-native-music-video/plugins/music-video/skills/music-video ~/.claude/skills/
```

## 使用

需要 Node.js 18+、Python 3（numpy、scipy、Pillow）、ffmpeg 和 Google Chrome。去尾音、找和声、做伴奏版要另装 audio-separator。这些片子都是在 macOS（Apple Silicon）上做的；别的系统没有显卡时 WebGL 会慢很多。

新建一个空文件夹，把歌放进去，在里面打开 Claude Code，说你想要什么，例如：

> 给《我不难过》做一支完整的 MV，专辑原版音频在这个文件夹里。想要安静、克制的感觉，先给我看两三个方向的试片。

建议把推理强度开到最高（`/effort max`）。

## 成本

按 API 价格折合，一支全曲 MV 约 250–360 美元（一个工作日加两三轮修改），一支 30–100 秒的短片约 130–240 美元。大头是并行的子代理和人物设计。可以先只做一段 10–16 秒的试片，看了效果再决定。

## 目录

```
plugins/music-video/skills/music-video/
├── SKILL.md                 规则、流程、工具、八支片子一览
├── references/
│   ├── song.md              音频来源、量歌、歌词只当数据、逐字歌词对时、字幕、截片段、人声分离
│   ├── direction.md         从歌到片、范围和横竖、第一帧、节奏和镜头、热血同人、提方向、试片
│   ├── styles.md            画风目录
│   ├── characters.md        人物：类型和好看、做法、定妆表、剪影、Q 版、3D 模型、解剖和图层清单
│   ├── production.md        分镜、节拍表、给子代理的说明、并行、总装、修改轮
│   ├── pipeline.md          页面约定、render.mjs、确定性、渲染器和速度、合成和色彩
│   ├── review.md            自查、终检、审片清单
│   └── release.md           封面、文案、求提示词、版权、收尾
├── scripts/                 new_project.py  render.mjs  analyze_audio.py  fetch_lyrics.py  build_lyrics.py
│                            cut_vocal_tail.py  check_frames.py  check_no_lyrics.py  fill_post.py
└── assets/
    ├── project/             页面骨架（页面约定、逐字字幕、示例镜头、占位镜头）和 make_timing.py
    └── docs/                分镜、写镜头说明、子代理任务书、投稿文案、项目 README 的模板
```

## 维护

每做完一支片子，把新画风加进 `styles.md`，把被指出的问题加进 `review.md` 的审片清单。清单里的每一条都真的发生过。

## 致谢

- [ClaudeAnimationBase](https://github.com/JohnHeibel/ClaudeAnimationBase)（MIT）和 [PDoomVideo](https://github.com/JohnHeibel/PDoomVideo)：第一支片子的起步包。“页面画任意一秒、无头 Chrome 逐帧渲染、ffmpeg 合成”的做法和“给观众时间看懂”的节奏原则从这里开始。
- 用到的开源工具和模型：p5.brush、three.js、puppeteer、ffmpeg、audio-separator 和 BS-RoFormer、rembg。

## License

MIT
