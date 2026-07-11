---
name: video2slides
description: Turn a YouTube/Bilibili video into a frontend-slides HTML deck. Slides carry keyframes with timestamp badges that deep-link back to the source video. Requires ffmpeg + yt-dlp; subtitled videos need no API key.
---

# video2slides(垂直切片版)

把在线视频转为「视频的可导航索引」:transcript → 大纲(带证据引用)→ 定向选帧 → frontend-slides HTML。
本版覆盖:带字幕或无字幕(ASR)的在线视频(YouTube / B 站单 P)与本地视频文件。分析全程零打断,唯一交互点在渲染前。

> **运行方式**:以下命令均写作 `python scripts/xxx.py`(面向发布后的最终形态)。在本 repo 内开发/验收时,脚本跑在 `uv` 管理的 venv 里,请一律换成 `uv run python scripts/xxx.py`。
> **路径约定**:`<OUT>`/`<W>` 全程使用绝对路径。脚本把 `--work` 传入值原样拼进 `proxy_path`/`final_path`/`candidates.json` 等制品;`storyboard.py validate` 用 `Path(proxy_path).exists()` 校验存在性——若中途换了相对路径或换了 cwd 调用,校验会因路径不匹配而误报失败。

## 预算(硬约束)

- 图片 Read 总数 ≤ 15 次/视频(探针 sheet ≤2 + 各章候选 sheet ≤2/章 + 细看单帧)
- 引用校验重生成 ≤ 2 轮,仍失败的节点降级纯文字 slide

## 流程

### 0. 预检
`python scripts/setup.py`(不加 `--check`——该 flag 会静默掉所有提示文本,只留 exit code,缺二进制时看不到装什么;不加 flag 才会打印缺失清单与 `macOS: brew install ffmpeg yt-dlp` 提示)。
exit 0 → 预检通过,继续;exit 2 → 按 stdout 提示装好 `ffmpeg`/`ffprobe`/`yt-dlp` 后重试;exit 3 → 所配 ASR 后端不可用:按 stdout 提示配置(`~/.config/video2slides/.env` 写 `ASR_BACKEND` 与对应 key,或 `FUNASR_VENV`);仅处理带字幕视频时可 `ASR_BACKEND=none` 继续。exit 4 → 仅缺 `tesseract`,提示信息可读但不阻塞,直接继续(文字密度打分自动降级为边缘密度代理)。

### 1. 取流
`python scripts/fetch.py --url <URL> --work <OUT>/.work`(B 站加 `--cookies-from-browser chrome`)。
exit 3 = 无字幕轨且 ASR 不可用(none/配置无效)——告知用户配置 ASR(设 `ASR_BACKEND` / 部署 funasr venv),停止(转写文件直供 `--transcript` 为未来版本能力,本切片未实现,不要提)。无字幕轨但 ASR 可用时,fetch 会自动抽音频轨(`.work/audio.mp3`)并提示进 transcribe。本地文件:直接把文件路径当 `--url` 传入(sidecar 同名 `.json` 元数据自动读取;`--cookies-from-browser` 忽略)。
输出目录 `<OUT>` 默认 `~/Desktop/video2slides/<title>_<YYYYMMDD>/`。

### 2. 转写与信号
`python scripts/transcribe.py --work <W>` → `python scripts/signals.py --work <W>`。
- transcribe.py:有字幕轨时,exit 1 = 字幕文件解析出 0 段(格式异常/内容为空),停止并告知用户;exit 0 = 成功。无字幕轨时 transcribe 走 ASR(后端由 .env 决定,默认 funasr):exit 3 = ASR 配置无效 / `ASR_BACKEND=none` / `.work/audio.mp3` 缺失 / 后端调用失败(按 stdout 定位具体原因);exit 1 = ASR 产出 0 段(全部块失败或音频异常),不落盘;exit 0 = 成功。funasr 本地转写约 0.1–0.3× 实时,长视频耐心等待;mimo/qwen 为 45s 切块逐块调用,transcript 的时间戳为块级粒度(45s 级)、`source` 标 `asr:<backend>`。**ASR/机翻文本有噪声**:evidence quote 仍保原文一字不差,专有名词错译可在 slide 正文用小注澄清(参考 meeting5min 成品)。失败块会在 stdout 汇总(transcript 留缺口)。
- signals.py:exit 1 = scene-score 遍历失败(如单帧/静态视频)——spec §11 描述的降级路径(uniform 抽帧兜底)本切片未实现,遇到即直接停止并告知用户。
- **块级时间戳窗口微调**(`transcript.json` 的 `source` 为 `asr:mimo`/`asr:qwen` 时适用):此时时间戳是 45s 块级粒度,叶子节点的选帧时间窗本质是宿主估计,而非精确边界;frames.py 的窗口预扩张可能让选中帧落在字面窗口外,与步骤 9 QA「角标秒数须在节点时间窗内」的规则系统性打架。出现此类落空时,微调相邻叶子节点的边界使角标落回窗内(验收 #21 实例:相邻叶子 3.2/3.3 边界微调至 144.0),而不要因窗外丢弃该帧。
记下 stdout 的 `curve_stats`(含 `plateau_ratio`、`spikes_per_min`,下一步要用)。

### 3. 轴 A/B 分类
`python scripts/frames.py --probe --work <W>`,Read 探针 sheet(≤2 张):
- 长平台 + 尖峰(plateau_ratio>0.8 且 spikes_per_min 约 0.5–6)且画面为版式文字 → slide-driven
- 其他形态:本版仅支持 slide-driven,如判非 slide-driven,告知用户后按 slide-driven 保守处理,但**不启用页边界 snap**(spec §11)
轴 B:读 transcript 前 60 段 + `.work/meta.json`(标题)+ `.work/ytdlp_info.json`(简介/description 字段,若存在——fetch.py 落盘的 `meta.json` 只保留 title/duration/language/uploader,不含简介,原始简介仍在未裁剪的 `ytdlp_info.json` 里)+ `.work/priors.json`(chapters),从 {课程/教程, 演讲/分享, 访谈/播客, 评测/对比, 资讯/解读, 会议记录, vlog/生活, 纪录片} 选一。

### 4. 大纲生成(核心语义步骤)
读 `.work/transcript.json` + `.work/priors.json` + `.work/page_boundaries.json`,生成层级大纲并**直接写 `.work/storyboard.json`**(schema 见 spec §6)。规则:
- chapters 作 level-1 骨架(无则自行分层);heatmap 高值时段值得展开为独立要点
- **每个节点的 evidence 必须含 `{segment_id, quote}`,quote 是该字幕段内一字不差的原文短语**——禁止改写
- slide-driven:节点边界优先落在页边界上(±3s 内 snap 到最近页边界,超出保留字幕时间)
- 大纲语言跟随视频语言;`video` 块填 meta 内容(`video.priors.page_boundaries` 取 `.work/page_boundaries.json` 的真实内容——`.work/priors.json` 里同名字段是 fetch.py 阶段写入的占位空数组,永远不会被后续步骤回填,不要从那里取),`visual_form` 填单段,`media` 先留空数组
- 叶子节点数参考:每 10 分钟 6–10 个
写完跑 `python scripts/storyboard.py validate --work <W>`;exit 5 → 按 stdout 失败节点重写其 evidence(≤2 轮,仍失败改纯文字节点:删 media、保留大纲文字)。

### 5. 选帧
`python scripts/frames.py --candidates --work <W>`,然后 Read 各章 sheet(每张有同名 `.map.json` 映射 cell→候选;字段:`chapter`/`truncated`/`dropped_node_ids`/`cells[{cell,node_id,t,file}]`):
- 为每个叶子选 1–2 帧(选版式完整、文字清晰、无转场残影的),需要细看时才 Read 单帧原图
- **对最高分候选保持怀疑**(2026-07-11 三次实测):tesseract 缺失时边缘密度代理会给"高 UI 杂色低信息量"画面(PPT 编辑器工具栏、水印页、插播网页截图)系统性虚高评分——终选以你目验的内容相关性为准,分数只是排序参考
- 把选中项写回 storyboard 各节点 `media`:`{"type":"frame","proxy_path":<map 的 file>,"final_path":null,"finalized":false,"t":<map 的 t>,"reason":<候选 reason>,"score":<候选 score>}`——`reason`/`score` 不在 map.json 里,需按 `file` 路径去同一份 `.work/candidates.json`(本步开头已生成)里查对应候选取值
- 若某张 sheet 的 `dropped_node_ids` 非空(该章候选量超过 18 帧/2 张 sheet 的预算上限,轮转配额未覆盖到的节点整个被挤出 sheet),这些节点不会出现在任何 sheet 里,需直接读 `.work/candidates.json` 按 `node_id` 过滤出它们的候选(未剪枝的原始候选,含 `score`/`reason`/`file`),挑分数最高的 1 张,不必额外 Read 图——`score` 已经是 ffmpeg 边缘/文字密度 + 峰值合成的排序依据
- 跑 `python scripts/storyboard.py dedup --work <W>`(跨要点去重,自动替换/降级)
- **去重仲裁(宿主复核)**:dedup 的 stdout 会列出替换/降级数量。16×16 签名对「同版式、不同内容」的讲义页(如渐进 build 的 BPE 演示页)分辨力不足,可能误伤——对被降级(dropped)的节点,回看你在 sheet 上已目验过的对应帧:内容确实与保留帧不同的,把该节点 media 恢复回去(语义判断归宿主,机器去重只防"同一截图上多页");确属重复的维持纯文字。恢复后重跑 validate 确认通过

### 6. 粒度询问(唯一交互点,合并 frontend-slides Phase 1)
用 AskUserQuestion 问一次:
- 「Length」短 5–10 / 中 10–20 / 长 20+(默认中)
- 顺带允许覆盖输出语言(默认跟随视频)
Purpose 由轴 B 推断、Content 恒为 ready、Density 默认 high-density/reading-first,不问。

### 7. 渲染前置
- 深度:短→level 1;中→level 2;长→level 3(不足则全展开)
- 浅于叶子的展开:`python scripts/storyboard.py aggregate --work <W> --depth <N>` 取各页 media(输出到 stdout 的 JSON,不会自动写回 storyboard;下一步的 `on_page` 仍需手动编辑)
- 给本次上页的每条 media 标 `on_page: true`(直接编辑 storyboard.json)
- `python scripts/frames.py --finalize --work <W> [--cookies-from-browser chrome]`

### 8. 渲染(调 frontend-slides skill)
读 frontend-slides 的 SKILL.md 并遵循其全部不变量(1920×1080 fixed stage、零依赖)。跳过其 Phase 1/2 提问:
- 风格 = 轴 B 自动映射(均为 STYLE_PRESETS.md 内已验证存在的预设名):课程/教程→Swiss Modern;演讲/分享→Bold Signal;访谈/播客→Paper & Ink;评测/对比→Electric Studio;资讯/解读→Notebook Tabs;会议记录→Paper & Ink;vlog/生活→Split Pastel;纪录片→Vintage Editorial
- 版式需求:每页含标题 + storyboard 该节点 media(用 `final_path`)+ **时间戳角标**(mm:ss,`<a href>` 用 `meta.source.badge_url_template` 填 t 的整数秒)+ summary 要点文字;`quality_limited` 的帧右下角标「代理画质」
- **帧的版面权重按 visual_form 定**(2026-07-11 用户 review 反馈落地):
  - screen-recording / 文档录屏 / slide-driven / whiteboard:**帧是信息主体**——截图里的文字必须肉眼可读,帧卡片占页面主导面积(≥60%,全宽大图+紧凑文字条,或图 70% 文 30%),UI 截图用 contain/原比例完整呈现,禁止 cover 裁切
  - cinematic / 游记 / 实拍:帧承载氛围,图文对半或图稍大均可,cover 裁切可接受
  - talking-head / 会议网格:帧纯装饰(画面恒同),小图/拍立得式点缀即可,文字为主体
  - **竖屏帧(高>宽)**:禁止 cover 成横图——原比例居中,两侧留白或毛玻璃衬底;信息主体类(录屏/演示)高度贴满 1080 减留白;可双帧并排利用横向空间
- `final_path` 的两种取值,HTML 里引用方式不同:
  - 正常定稿:`frames.py --finalize` 写到 `<OUT>/assets/final_<node_id>_<t:.1f>.jpg`(如 `final_2.1_431.2.jpg`),HTML 用相对 `index.html` 的 `assets/<文件名>` 引用即可
  - 降级(`quality_limited: true`,高清直链两次都取不到):`final_path` 原样等于代理帧 `proxy_path`,即 `<OUT>/.work/frames_proxy/f_xxxxx.jpg`——**不在** `assets/` 下。渲染前把这些文件也拷贝进 `assets/`(保持自包含,便于之后整目录分享/部署),再按拷贝后的相对路径引用,不要直接从 `.work/` 里引
- **本地文件(platform=local)**:无跳转 URL(badge_url_template 为 null)——时间戳角标改为打开内嵌播放器弹层:`<video src="file://<原始绝对路径>">` + JS 设 `currentTime` 跳播,弹层内显示源文件路径,SKILL 交付说明须注明「移动/删除原视频文件会使跳转失效」。deck 不拷贝视频文件(可达数百 MB)。
- 产出 `<OUT>/index.html`
交付时告知所用风格;用户可要求换风格/换粒度重渲染——只重复 6–8 步,零重跑分析。

### 9. QA(交付前自检)
- 每页有标题、无 placeholder 文案;所有 `assets/` 引用文件存在
- 抽 3 个时间戳角标,核对 URL 格式(YouTube `&t=<n>s` / B 站 `?p=<n>&t=<n>`)且秒数在该节点时间窗内
- 抽 2 页核对帧与要点相关性,不符则回 sheet 换帧重渲染该页
