# 技术管线

## 目录
- 项目目录
- 页面约定
- timing.json
- render.mjs
- 每一帧只由 t 决定
- 渲染器和速度
- 合成和色彩
- 颗粒、发光、NaN 和其他小坑
- 局部重渲和版本

## 项目目录

```
<歌名拼音>/                一首歌一个目录
  index.html  src/         影片的页面：main.js（页面约定）、lib.js、caption.js、shots/（一镜一个文件）
  render.mjs               渲染（skill 的 scripts/render.mjs 的副本）
  tools/                   Python 工具的副本，加上本片的 make_timing.py
  assets/                  原曲；lyrics/（原始歌词文件和 lyrics.json）；analysis/audio.json；timing.json；audio/film.wav；
                           models/、fonts/（带来源和许可证）
  docs/                    STORYBOARD.md、GUIDE.md、briefs/、POST.tpl、POST.txt、img/（记录用的图）
  look_tests/<名字>/       每个试片一个目录，自己的 index.html 和 src/；clip.json 是试片的片段
  out/                     frames*/、check/（随时可删）；成片和小副本；covers/；look_tests/
```

项目里带着自己的 `render.mjs` 和工具副本，这样以后 skill 改了，这支片子仍能按当时的方式重建。

## 页面约定

`render.mjs` 只认这几样，画风和渲染器随便选：
- `index.html` 里一个 `<canvas id="stage">`。WebGL 上下文要 `preserveDrawingBuffer: true`，`toDataURL` 才拿得到画面。
- `window.READY`：数据、字体、模型、贴图都加载完的 promise。字体要在这里 `document.fonts.load`，否则第一帧用的是替代字体。
- `window.renderAt(t)`：画出原曲第 t 秒的那一帧；可以是 async，返回时画布上就是那一帧。
- `window.FILM`：`{ t0, t1, fps, w, h, frames, shots: [{ id, name, t0, t1, f0, f1, head }] }`。`head` 相同的镜头在同一个渲染任务里按顺序渲（只有共享模拟状态的镜头需要）。
- `window.INFO.shot`：联系表格子上的标签。
- 查询参数：`w`、`h`、`fps`、`timing`（时间表的路径）、`headless=1`，加上本片的开关（`--q` 传进去）。常备的开关：`text=0`（不画字幕，导出封面用）、`use=NAME`（所有镜头画同一个草图）、只画某一层、画质（子画面数）、封面模式。
- ES 模块不能从 `file://` 加载；`render.mjs` 自带一个静态服务器，根目录是项目文件夹，页面可以加载 `/assets/...`、`/node_modules/three/...`。
- 骨架的 `src/main.js` 是一个 Canvas 2D 的实现：每帧重置画布状态，按时间找镜头，调用它的 `draw(K)`，再画字幕；缺文件的镜头画占位卡。three.js、自写 WebGL2、p5.js 的片子把 `drawFrame` 换成自己的渲染，约定不变。
- 预览：`node render.mjs --serve`，在 Chrome 里打开它打印的地址：骨架有时间条，空格播放，方向键逐帧。重的画风实时播放会卡，那只是预览。

## timing.json

`tools/make_timing.py` 写。`render.mjs` 只读 `fps`、`w`、`h`、`t0`、`t1`、`shots`；其余字段给页面用。

```json
{ "fps": 30, "w": 1920, "h": 1080, "t0": 51.2462, "t1": 105.3989,
  "bpm": 97.502, "beat": 0.61537, "bar": 2.46148, "bar0": 2.0166,
  "shots": [{ "id": "s01", "t0": 51.2462, "t1": 56.169, "name": "封面" }],
  "downbeats": [51.246, 53.708], "kicks": [[51.31, 0.62]], "snares": [[52.1, 0.48]],
  "lines": [{ "i": 8, "t": 52.344, "end": 54.304, "n": 12 }] }
```

时间都是原曲的秒数；第 F 帧画的是 `t0 + F / fps`；一个镜头拥有从它开始那一刻起（含）到下一镜开始之前的帧。

## render.mjs

| 命令 | 用途 |
|---|---|
| `--serve` | 预览页 |
| `--list` | 镜头、时长、帧范围 |
| `--still=95.6 [--out=]` | 一帧 PNG；`--still=a,b,c` 写几张 |
| `--sheet=a:b:step` / `--sheet=t1,t2,...` | 联系表；`--cols`、`--w` 是列数和格宽 |
| `--shot=s04 --sheet [--n=12]` | 一个镜头均匀取 n 帧 |
| `--strip=a:b` | 这一刻的每一帧：查卡点（动作要落在重拍之后的第一帧，晚一帧就读成晚了）、查切点 |
| `--sheet=t --crop=x,y,w,h --w=1000` | 原尺寸局部：手、脸、接触、发光、颗粒 |
| `--film-sheet [--n=48]` | 全片一览 |
| `--frames [--shots=] [--workers=] [--reverse] [--tag=]` | 帧序列到 `out/frames`（带 tag 时 `out/frames_<tag>`）；先删掉这些镜头的旧帧 |
| `--encode [--shots= / --range=a:b] [--tag=] [--out=] [--crf=] [--audio=]` | 合成 mp4；缺帧时停下并报第一帧 |
| `--compare=a,b` | 两组帧逐字节比 |
| `--eval="表达式" [--at=t]` | 在页面里求值，例：`CAPTION_TABLE()`、`FILM.shots.length` |
| `--page=` `--timing=` `--q=` `--fw=` `--fh=` | 别的页面（试片、定妆表）、别的时间表、页面开关、换尺寸 |

- 联系表的格子标着镜头号和时间；按时间顺序画（对需要预滚的模拟页面更省）。
- 每张图都要真的打开看。1920 宽的一张联系表约 2.7k token，一支片子审几百张图很正常。
- `--out` 写相对路径（相对项目根）或绝对路径都行。
- 页面的报错和 404 打到 stderr，`--eval` 的 stdout 只有结果。
- macOS 上用 Metal（`--use-angle=metal`）；别的系统没有 GPU 时 WebGL 会退到软件渲染，慢很多。`--chrome=` 指定浏览器。

## 每一帧只由 t 决定

为什么：多进程乱序渲染、中断续渲、改哪个镜头只重渲哪一段、几个月后还能逐字节重建。

规则：
- 不用 `Math.random`、`Date.now`、`performance.now`、`THREE.Clock`；随机用种子哈希（`lib.js` 的 `hash(i, seed)`、`rng(seed)`）。
- 模块变量不在绘制里改；缓存的内容不能取决于之前画过什么。
- 画布状态用 `save`/`restore` 包好：泄漏的 `globalAlpha`、`filter`、阴影、变换会毁掉后面所有的层（骨架每帧先重置）。
- 随机撒的东西（草、雨、纸屑、星星）按固定的格子或固定的编号撒，不按“当前看得见的范围”撒，否则镜头一动就重排。
- 每个镜头设满它依赖的所有共用参数：雾的颜色会从上一个渲过的镜头漏过来，帧就和渲染顺序有关了。
- “什么都不画”的状态也要显式画一张底。three.js 的多重采样渲染目标只在一次 `render` 结束时写进贴图，空帧拿到的是这个进程上一次画的画面；`setRenderTarget` 时读取视口和裁剪框，之后再改不生效；一帧里画好几次时关掉 `renderer.autoClear`。
- 模拟（流体、布料、头发）：每个镜头从开始前 90–150 帧的预滚按固定步长算到要的那一帧；时间往回跳时从头重算；不切镜的镜头共用一段（`head`）。模拟是混沌的：上游改一点，后面全变；验收过的段落冻结。
- 能写成闭式的运动就写成闭式：缓动、开普勒轨道、Hermite 曲线、写成公式的阻尼弹簧、落叶按时间算出的位置。
- 大字加大阴影模糊画在 GPU 画布上，每次加载页面会差一两级：画在软件画布（`getContext('2d', { willReadFrequently: true })`）上再贴。
- 不同 Chrome 进程之间可能有 1–2 级的抗锯齿噪声（《万有引力》的 Canvas 2D、《枫》的 three.js 都有）：要逐字节可复现的成片就用一个进程渲；差多少用 `tools/check_frames.py --compare` 量。《人质》的 WebGL 流体和《于是》的像素缓冲多进程也逐字节相同。
- **检查**：挑一些镜头，多进程正着渲一遍，单进程倒着渲一遍，`--compare`。有一帧不同，就说明它依赖了之前画过的东西。交付前全片做一次；收尾删帧前再做一次。《悟空》两帧冲击帧里是别的画面，九版都没人发现，直到整理时重渲比对。
- 重建依赖本机环境：显卡、Chrome 版本、ffmpeg 版本、系统字体。README 里写清楚。

## 渲染器和速度

M4 Pro 上实测：

| 路线 | 片子 | 每帧 | 全片 |
|---|---|---|---|
| Canvas 2D 调色板缓冲（480×270 放大 4 倍） | 于是 | 约 3 ms | 6976 帧，6 进程约半分钟 |
| Canvas 2D 矢量 + 辉光 | 万有引力 | 约 30 ms | 1625 帧，单进程 50 秒 |
| Canvas 2D 纸层 + WebGL2 透光合成 | 我不难过 | 约 50 ms | 7690 帧，5 进程约 6 分钟 |
| WebGL 流体 + 合成 | 人质 | 20–30 ms（含预滚） | 2730 帧，3 进程约半分钟 |
| three.js 游戏模型 + 漫画着色 | 悟空 | 约 16 ms | 629 帧，3 进程约 10 秒 |
| three.js 子画面平均（16–64 张） | BIRDS、枫 | 60–400 ms | 1179 帧 3–6 分钟；3052 帧约 4.5 分钟 |
| p5.js + p5.brush | 说谎 | 约 200 ms | 6340 帧，4 线程约 20 分钟 |
| Blender EEVEE / Cycles（对比用） | — | 0.6–6 s / 9–75 s | 4.5 分钟的片 EEVEE 1.4–13 小时，Cycles 20–170 小时 |

- three.js 用 `WebGLRenderer`，不用 `WebGPURenderer`（异步渲染，社区的出片管线都避开它）。r186 起没有 `PCFSoftShadowMap`。
- **子画面平均**：一帧是 K 张子画面的平均，每张的时刻（运动模糊）、镜头在光圈上的位置并把投影切变到焦平面（景深）、像素偏移（抗锯齿）都略有不同。近景 56–64 张，远景 16–24 张；虚化大时会出重影，远景用预先虚化的穹顶或后期的圆盘模糊；累加时丢掉非有限数的像素。
- 换 Blender 不会自动更好：同一帧 Cycles 多了接触阴影，但更硬，逆光里着色器特意加强的金光也没了；问题在造型，不在渲染器。
- 预算：每帧 400 毫秒以内，全曲还能接受。全曲 1080p 的 JPEG 帧约 3.6 GB。

## 合成和色彩

`render.mjs --encode` 已经这样做：
- 画布存出的 JPEG 帧是全范围、BT.601 矩阵；ffmpeg 8 会原样保留（`yuvj420p`、`color_range=pc`、`bt470bg`），不理会这个标记的播放器和平台转码会把暗部压得更暗、亮部截掉。所以转成有限范围的 BT.709 并写好标记：`scale=in_range=pc:in_color_matrix=bt601:out_range=tv:out_color_matrix=bt709`，加 `setparams` 和 `-color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709`（没有 `setparams` 时传输特性和原色是 unknown）。
- 检查：`ffprobe` 看 `color_range=tv`、`bt709`；解码几帧回 RGB，和渲染帧比平均颜色（差 1–3 级正常，来自 4:2:0 色度采样）。
- 码率：默认 `crf 18`。细颗粒和密集的小点很费码率：91 秒竖屏 crf 17 是 211 MB，换颗粒之前 crf 21 是 76 MB；平台还会再压一次。
- 声音：有 `assets/audio/film.wav` 用它，否则用原曲；`-ss` 放在 `-i` 前面；片头淡入 0.05 秒、片尾淡出 1.2 秒。查音轨对原曲的偏移：互相关的峰在 0。
- 给用户发文件：超过 30 MiB 的文件发不出去，另压一份 25 MB 以内的（`crf 22–26` 或 720p），原文件留在盘上，说清发的是哪一个。

## 颗粒、发光、NaN 和其他小坑

- **颗粒**：不要用 `fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453)` 或 `fract(p * vec2(123.34, 456.21))` 起头的一行哈希作用在整数像素坐标上：每 3 像素左右重复，“颗粒”成了一张网格，只在 1:1 的平背景上看得见。用 Hoskins 哈希，每轴不同的帧偏移：
  ```glsl
  float grain(vec2 p, float f) {
    vec3 q = fract(vec3(p.xyx + vec2(f * 37.0, f * 59.0).xyx) * vec3(0.1031, 0.1030, 0.0973));
    q += dot(q, q.yzx + 33.33);
    return fract((q.x + q.y) * q.z);
  }
  ```
  检查：`tools/check_frames.py out/frames --grain=x,y,w,h`（选一块平的背景）。
- **发光**：给光源、击中、主要的矢量；不给细线和小字，会变成一团雾。光晕不能大面积超过辉光阈值，否则切出一块硬边的亮斑。长焦对着太阳要压日轮和辉光。
- **NaN**：一个非有限数的像素经过辉光会把整帧染黑；NaN 坐标让路径悄悄消失；`ramp(a, a)` 除以零；负数的小数次幂。每个重拍前后用 `--strip` 看。
- 对象字面量中间插一行 `//` 注释，悄悄吞掉了两个属性，灯光强度成了 NaN，所有受光面变黑。
- 绘制函数里的局部变量和全局重名（身高 `H` 遮住了画面高度），震动的偏移算飞，整帧成了一种颜色。
- 贴图类特效的尺寸各有算法：光球贴图的边长是它尺寸参数的 16 倍。
- 噪声的每一层在接近像素大小时淡出，不然逐帧闪；水面的细波按一个像素覆盖的范围过滤，不然远处是一片噪点。
- three.js 的 `ShaderPass` 会克隆 uniform，渲染目标的贴图要在创建 pass 之后再赋值。

## 局部重渲和版本

- `--frames --shots=s04,s05` 先删掉这几个镜头的帧再渲；`--encode` 发现缺帧就停下并报第一帧（老办法手删帧，删的范围和渲的范围差一帧，ffmpeg 会在那里停住，成片就短一截）。
- 帧目录里的旧帧不会自动更新：改了共用代码就整片重渲。Canvas 2D 的片子整片只要几十秒。
- 渲别的版本（横竖、Q 版和原版、开关）用 `--tag`，帧放在各自的目录；`--frames` 和 `--encode` 带同一个 `--tag`。
- 合成默认写 `out/<项目>_rebuild.mp4`，永远不会覆盖交出去的文件；交付的版本用 `--out=out/<项目>_v2.mp4`。
