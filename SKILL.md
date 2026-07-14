---
name: video2slides
description: Turn a YouTube/Bilibili/local video into a self-contained video index document (video_index.json + frames/, the outline-transcript-frames mapping), then render it as a frontend-slides HTML deck and/or markdown notes with timestamp links back to the source. Requires ffmpeg + yt-dlp; subtitled videos need no API key.
---

# video2slides(垂直切片版)

把视频转为「视频的可导航索引」:transcript → 大纲(带证据引用)→ 定向选帧 → **索引文档(`video_index.json` + `frames/`,一等交付物,公开契约)** → 渲染器族(frontend-slides HTML / markdown 笔记,均为文档的下游视图)。
本版覆盖:带字幕或无字幕(ASR)的在线视频(YouTube / B 站单 P)与本地视频文件。分析全程零打断,唯一交互点在文档导出后、渲染前。

> **运行方式**:以下命令均写作 `python scripts/xxx.py`(面向发布后的最终形态)。在本 repo 内开发/验收时,脚本跑在 `uv` 管理的 venv 里,请一律换成 `uv run python scripts/xxx.py`。
> **路径约定**:`<OUT>`/`<W>` 全程使用绝对路径。脚本把 `--work` 传入值原样拼进 `proxy_path`/`final_path`/`candidates.json` 等制品;`storyboard.py validate` 用 `Path(proxy_path).exists()` 校验存在性——若中途换了相对路径或换了 cwd 调用,校验会因路径不匹配而误报失败。

## 预算(硬约束)

- 图片 Read 预算:短视频(≤30min)总数 ≤ 15 次;分章场景(>30min)按章预算 = 探针 ≤2 + 每章 sheet ≤2 + 细看 ≤1/章(spec §12「长视频分章场景按章预算」——19 章满额约 40 次是预期成本,非超支)
- 引用校验重生成 ≤ 2 轮,仍失败的节点降级纯文字 slide

## 流程

### 0. 预检
`python scripts/setup.py`(不加 `--check`——该 flag 会静默掉所有提示文本,只留 exit code,缺二进制时看不到装什么;不加 flag 才会打印缺失清单与按平台适配的安装提示)。
**支持平台**:macOS(Apple Silicon / Intel)与 Linux/Unix(arm64 / x86_64,含 Ubuntu/Debian、CentOS/RHEL/Fedora);**不支持原生 Windows**(WSL2 上报为 Linux,正常运行)。配置文件路径尊重 `$XDG_CONFIG_HOME`,缺省回落 `~/.config/video2slides/.env`。
exit 0 → 预检通过,继续;**exit 1 → 原生 Windows,不支持**(改用 WSL2 / Linux / macOS,不要继续);exit 2 → 按 stdout 提示装好 `ffmpeg`/`ffprobe`/`yt-dlp`(macOS 印 brew、Linux 按发行版印 apt/dnf——ffmpeg 走发行版包管理器、yt-dlp 走 pipx)后重试;exit 3 → 所配 ASR 后端不可用:按 stdout 提示配置(`<XDG 或 ~/.config>/video2slides/.env` 写 `ASR_BACKEND` 与对应 key,或 `FUNASR_VENV`;若配了 arm64-only 后端而当前非 Apple Silicon,stdout 会提示改用 funasr);仅处理带字幕视频时可 `ASR_BACKEND=none` 继续。exit 4 → 仅缺 `tesseract`,提示信息可读但不阻塞,直接继续(文字密度打分自动降级为边缘密度代理)。

### 1. 取流
`python scripts/fetch.py --url <URL> --work <OUT>/.work`(B 站加 `--cookies-from-browser chrome`)。
exit 3 = 无字幕轨且 ASR 不可用(none/配置无效)——告知用户配置 ASR(设 `ASR_BACKEND` / 部署 funasr venv),停止(转写文件直供 `--transcript` 为未来版本能力,本切片未实现,不要提)。无字幕轨但 ASR 可用时,fetch 会自动抽音频轨(`.work/audio.mp3`)并提示进 transcribe。本地文件:直接把文件路径当 `--url` 传入(sidecar 同名 `.json` 元数据自动读取;`--cookies-from-browser` 忽略)。
输出目录 `<OUT>` 默认 `~/Desktop/video2slides/<title>_<YYYYMMDD>/`。

### 2. 转写与信号
`python scripts/transcribe.py --work <W>` → `python scripts/signals.py --work <W>`。
- transcribe.py:有字幕轨时,exit 1 = 字幕文件解析出 0 段(格式异常/内容为空),停止并告知用户;exit 0 = 成功。无字幕轨时 transcribe 走 ASR(后端由 .env 决定,默认 funasr):exit 3 = ASR 配置无效 / `ASR_BACKEND=none` / `.work/audio.mp3` 缺失 / 后端调用失败(按 stdout 定位具体原因);exit 1 = ASR 产出 0 段(全部块失败或音频异常),不落盘;exit 0 = 成功。funasr 本地转写约 0.1–0.3× 实时(自动选 GPU:Apple Silicon 走 MPS / N 卡走 CUDA,否则 CPU;`FUNASR_DEVICE` 可强制),长视频耐心等待;mimo/qwen 为 45s 切块逐块调用,transcript 的时间戳为块级粒度(45s 级)、`source` 标 `asr:<backend>`。**ASR/机翻文本有噪声**:evidence quote 仍保原文一字不差,专有名词错译可在 slide 正文用小注澄清(参考 meeting5min 成品)。失败块会在 stdout 汇总(transcript 留缺口)。
- signals.py:exit 1 = scene-score 遍历失败(如单帧/静态视频)——spec §11 描述的降级路径(uniform 抽帧兜底)本切片未实现,遇到即直接停止并告知用户。
- **块级时间戳窗口微调**(`transcript.json` 的 `source` 为 `asr:mimo`/`asr:qwen` 时适用):此时时间戳是 45s 块级粒度,叶子节点的选帧时间窗本质是宿主估计,而非精确边界;frames.py 的窗口预扩张可能让选中帧落在字面窗口外,与步骤 9 QA「角标秒数须在节点时间窗内」的规则系统性打架。出现此类落空时,微调相邻叶子节点的边界使角标落回窗内(验收 #21 实例:相邻叶子 3.2/3.3 边界微调至 144.0),而不要因窗外丢弃该帧。
记下 stdout 的 `curve_stats`(含 `plateau_ratio`、`spikes_per_min`,下一步要用)。

### 2.5 划章(仅 meta.duration > 1800s)
`python scripts/signals.py --chapter-hints --work <W>`,读 stdout 候选表(每条含信号依据 + 前后转写摘录):
- 原生 chapters 存在时候选即原生章(信号列 native);无则为多信号共振合成;信号全无时按 10min 均分兜底(fallback=uniform,如实告知用户)
- **语义确认(只并不拆)**:按摘录判断候选是否真是内容转折;过碎相邻章合并(如 19 个 4min 伪章收到 8–10 章);拆分不允许——需要拆分说明候选不足,对该边界拉局部 transcript 上下文再定
- 密度合章:开场铺垫/闲聊占时长大但信息密度低的,合成一章而非按时长均分
- **块级时间戳对齐**(`source` 为 `asr:mimo`/`asr:qwen` 时):章界对齐到最近 45s 块边界,避免章界切开一个块
- 定稿写 `.work/chapter_plan.json`:`{"source": "native|hints|manual|uniform", "chapters": [{"idx", "title", "t_start", "t_end", "hint_refs": [采纳的候选 idx]}]}`——章界必须首尾相接、无缝无重叠、覆盖 [0, duration](validate 会校验)
≤30min 跳过本步(不写 chapter_plan,后续全部走原路径)。

### 3. 轴 A/B 分类
`python scripts/frames.py --probe --work <W>`,Read 探针 sheet(≤2 张):
- 长平台 + 尖峰(plateau_ratio>0.8 且 spikes_per_min 约 0.5–6)且画面为版式文字 → slide-driven
- 其他形态:本版仅支持 slide-driven 的完整能力,如判非 slide-driven,`visual_form` **标签仍如实记录**(talking-head/screen-recording/cinematic,不得改标 slide-driven,否则污染 storyboard 下游语义),告知用户后仅在行为上保守复用 slide-driven 流程,但**不启用页边界 snap**(spec §11)
- 数值判据不可独立成立:曲线数值落在 slide-driven 区间不代表就是 slide-driven(实证:秀场直播 plateau_ratio 0.942 / spikes_per_min 0.57 全部落带,目验实为 talking-head+弹幕 UI),**最终以探针 sheet 目验画面为准**
- **平台分区去锚(轴 A)**:读 `.work/ytdlp_info.json` 的 `categories`/`tags`(若存在,fail-open;**实测 yt-dlp 2026.07:YouTube `categories` 稳定给单一干净值(3/3:Education / Science & Technology / News & Politics),可直接当体裁软提示;B 站 `categories` 恒空、官方分区不透出(4/4),只有 `tags`——UP 主/活动/推广标签混着话题词,有噪声、≠ 官方分区、甚至整串被广告标签污染,可能误导**。故务必只当去锚软提示、绝不建硬表,样本与实例见 spec §5.1)。分区落在**演出/虚构/二创类**(番剧/国创/动画/电影/电视剧/影视/鬼畜/音乐/舞蹈;YouTube `Film & Animation`/`Music`)是强「非 slide-driven」信号——用它把判断**推离** slide-driven,提醒别硬套。**但分区只能去锚、不能定性**:永远不得单凭分区把视频判成 slide-driven,定性仍以探针 sheet 目验为准(与上条「数值判据不可独立成立」同规格——只保留纠错方向,不开锚定口子)。判为演出/虚构非目标时工具会降级(帧退化为氛围/装饰),**如实告知用户但不中途打断分析**,该提醒并入步骤 6 交互点前言 / 交付说明。
轴 B:读 transcript 前 60 段 + `.work/meta.json`(标题)+ `.work/ytdlp_info.json`(简介/description 字段 + `categories`/`tags` 平台分区,若存在——fetch.py 落盘的 `meta.json` 只保留 title/duration/language/uploader,不含简介,原始简介与分区仍在未裁剪的 `ytdlp_info.json` 里)+ `.work/priors.json`(chapters),从 {课程/教程, 演讲/分享, 访谈/播客, 评测/对比, 资讯/解读, 会议记录, vlog/生活, 直播实录/秀场, 纪录片} 选一。**平台分区当软提示,非硬映射**:分区是「主题域」(讲什么)、体裁是「形态」(哪种片),二者正交——一个分区(如 科技数码 / 知识)可对多种形态(课程/演讲/评测/资讯),分区只是与 transcript/标题同权的一个额外输入,最终由语义定。

### 4. 大纲生成(核心语义步骤)
读 `.work/transcript.json` + `.work/priors.json` + `.work/page_boundaries.json`,生成层级大纲并**直接写 `.work/storyboard.json`**(schema 见 spec §6)。规则:
- chapters 作 level-1 骨架(无则自行分层);heatmap 高值时段值得展开为独立要点
- **每个节点的 evidence 必须含 `{segment_id, quote}`,quote 是该字幕段内一字不差的原文短语**——禁止改写
- slide-driven:节点边界优先落在页边界上(±3s 内 snap 到最近页边界,超出保留字幕时间)
- 大纲语言跟随视频语言;`video` 块填 meta 内容(`video.priors.page_boundaries` 取 `.work/page_boundaries.json` 的真实内容——`.work/priors.json` 里同名字段是 fetch.py 阶段写入的占位空数组,永远不会被后续步骤回填,不要从那里取),`visual_form` 填单段,`media` 先留空数组
- 叶子节点数参考:每 10 分钟 6–10 个

**分章生成(存在 `.work/chapter_plan.json` 时)**:
- 逐章生成:每章只读该章 [t_start, t_end] 内的 transcript 段(75–130min 片单章约 150–300 段),外加两样轻量上下文——①已生成各章的 level-1/2 标题树(防跨章重复要点、保术语/编号一致)②前一章最后 3 段转写(防承接语误读)
- 章 = level-1 节点(title/t_start/t_end 与 chapter_plan 对应,容差 ±30s),章内叶子照常规则;每完成一章**立即追加写入** storyboard.json 再开下一章
- **章级续跑**:中断后对比 storyboard 已有 level-1 时间窗与 chapter_plan,缺哪章补哪章,不重生成已有章
- 全部章完成后:宿主只读各章 level-1/2 标题做一次归一(统一层级深度、消除章间标题近重复;不重读正文),然后照常跑 validate(会额外校验章覆盖与 level-1 对应)与 dedup(本就全局,天然覆盖跨章)

写完跑 `python scripts/storyboard.py validate --work <W>`;exit 5 → 按 stdout 失败节点重写其 evidence(≤2 轮,仍失败改纯文字节点:删 media、保留大纲文字)。

### 5. 选帧
`python scripts/frames.py --candidates --work <W>`,然后 Read 各章 sheet(每张有同名 `.map.json` 映射 cell→候选;字段:`chapter`/`truncated`/`dropped_node_ids`/`cells[{cell,node_id,t,file}]`):
- 为每个叶子选 1–2 帧(选版式完整、文字清晰、无转场残影的),需要细看时才 Read 单帧原图
- 候选 `reason` 取值:`scene-peak`/`window-midpoint`(窄窗)、`slot-peak`/`slot-midpoint`(>90s 宽窗槽采样,长视频块级时间戳下常见)——slot 类候选覆盖全窗,后半段内容不再需要跨节点借帧
- **对最高分候选保持怀疑**(2026-07-11 三次实测):tesseract 缺失时边缘密度代理会给"高 UI 杂色低信息量"画面(PPT 编辑器工具栏、水印页、插播网页截图)系统性虚高评分——终选以你目验的内容相关性为准,分数只是排序参考
- 把选中项写回 storyboard 各节点 `media`:`{"type":"frame","proxy_path":<map 的 file>,"final_path":null,"finalized":false,"t":<map 的 t>,"reason":<候选 reason>,"score":<候选 score>}`——`reason`/`score` 不在 map.json 里,需按 `file` 路径去同一份 `.work/candidates.json`(本步开头已生成)里查对应候选取值
- 若某张 sheet 的 `dropped_node_ids` 非空(该章候选量超过 18 帧/2 张 sheet 的预算上限,轮转配额未覆盖到的节点整个被挤出 sheet),这些节点不会出现在任何 sheet 里,需直接读 `.work/candidates.json` 按 `node_id` 过滤出它们的候选(未剪枝的原始候选,含 `score`/`reason`/`file`),挑分数最高的 1 张,不必额外 Read 图——`score` 已经是 ffmpeg 边缘/文字密度 + 峰值合成的排序依据
- 跑 `python scripts/storyboard.py dedup --work <W>`(跨要点去重**标注**:重复组写 `dedup_group`、组内最高分标 `dedup_primary: true`,单帧组为 null;**不删除、不替换任何 media**——唯一性是 slide 视图层策略,见步骤 7)
- **去重仲裁(宿主复核)**:dedup 的 stdout 会列出各标注组及成员。16×16 签名对「同版式、不同内容」的讲义页(如渐进 build 的 BPE 演示页)分辨力不足,可能误组——对每个标注组,回看你在 sheet 上已目验过的成员帧:内容确实不同的,**拆组**(把该 media 的 `dedup_group` 置 null、`dedup_primary` 置 true);首选帧不当的,组内**换 primary**(恰保一个 true)。语义判断归宿主,机器标注只防「同一截图上多页」。改完重跑 validate 确认通过(validate 会校验组内恰一个 primary)

### 5.5 打包导出(无条件,先于交互点)
`python scripts/storyboard.py export --work <W>` —— 从 storyboard + transcript + meta 组装一等交付物 `<OUT>/video_index.json` + `<OUT>/frames/`(单 JSON 内嵌全量转写与 `timestamp_granularity`、媒体全相对路径、dedup 标注如实透传;公开契约 schema 见 `schemas/video_index.schema.json`)。**索引文档是本体,渲染是视图——不因用户只要 slide 而跳过本步**。
- exit 0 = 已产出(或已最新自动跳过,`--force` 重跑);exit 5 = 契约校验不通过:**不产出文档**,按 stdout 定位修复 `.work` 制品(通常回步骤 4 重写对应节点 evidence,或回步骤 5 修 media/标注)后重跑,修不过不得进入步骤 6
- 导出物只读:后续渲染的记账(`on_page`/`final_path`)只写内部 storyboard.json,不回写 video_index.json
- 交付说明须告知用户:`<OUT>` 整目录自包含可迁移,删除 `.work/` 不损失交付物(仅失去换粒度免重跑的缓存)

### 6. 形态与粒度询问(唯一交互点,合并 frontend-slides Phase 1)
用 AskUserQuestion 问一次(此时 video_index.json 已落盘,本问只决定是否继续渲染):
- 「产出形态」slides / markdown 笔记 / 两者 / 仅索引文档(默认 slides)——选「仅索引文档」则按步骤 5.5 的交付说明告知文档落点,到此收束
- 「Length」短 5–10 / 中 10–20 / 长 20+(默认中)——对任何渲染器都是展开深度:slides 页数档位与笔记 `--depth` 同套语义(短→1 / 中→2 / 长→3)
- 分章场景(有 chapter_plan):档位语义不变(短→L1/中→L2/长→L3),但文案报按深度预估的真实页数(如「本片 12 章:短≈12 / 中≈30 / 长≈65 页」)——长视频页数随章数上浮是预期行为,让用户看真数字选档
- 顺带允许覆盖输出语言(默认跟随视频)
Purpose 由轴 B 推断、Content 恒为 ready、Density 默认 high-density/reading-first,不问。

### 6.5 笔记渲染(形态含「笔记」时)
`python scripts/notes.py --index <OUT>/video_index.json --depth <N>`(短→1/中→2/长→3)→ 产出 `<OUT>/notes.md`。确定性脚本,只读导出文档与 frames/,禁碰 `.work/`;本地视频的时间戳自动退化为 mm:ss 纯文本。exit 5 = 契约缺字段/缺资产——不应发生,说明步骤 5.5 的导出校验有漏:回查修复后重跑 export 再渲染。形态只选「笔记」时,到此交付收束(交付说明同步骤 5.5)。

### 7. 渲染前置(形态含 slides 时)
- 深度:短→level 1;中→level 2;长→level 3(不足则全展开)
- 浅于叶子的展开:`python scripts/storyboard.py aggregate --work <W> --depth <N>` 取各页 media(输出到 stdout 的 JSON,不会自动写回 storyboard;下一步的 `on_page` 仍需手动编辑)
- 给本次上页的每条 media 标 `on_page: true`(直接编辑 storyboard.json)
- **视图级唯一性(slide 专属)**:标 `on_page` 时,同一 `dedup_group` 只允许 primary 上页;非 primary 的节点该页改用其候选次名(按步骤 5 的 candidates.json 流程另选未用且目验不同的帧写入该节点 media)或转纯文字——「一帧不上两页」是 slide 的版面策略,不改动 dedup 标注本身
- `python scripts/frames.py --finalize --work <W> [--cookies-from-browser chrome]`
- **语义输入与记账分离**:对外语义真相是导出的 video_index.json(只读);本步及步骤 8 对 media 的视图级调整(唯一性回退、on_page、final_path)只写内部 storyboard.json,不回写导出文档。若发生步骤 4/5 层面的语义修正(改 evidence/大纲/标注),须重跑 `storyboard.py export --force` 保持文档与真相一致

### 8. 渲染(调 frontend-slides skill)
读 frontend-slides 的 SKILL.md 并遵循其全部不变量(1920×1080 fixed stage、零依赖)。跳过其 Phase 1/2 提问:
- 风格 = 轴 B 自动映射(均为 STYLE_PRESETS.md 内已验证存在的预设名):课程/教程→Swiss Modern;演讲/分享→Bold Signal;访谈/播客→Paper & Ink;评测/对比→Electric Studio;资讯/解读→Notebook Tabs;会议记录→Paper & Ink;vlog/生活→Split Pastel;直播实录/秀场→Split Pastel;纪录片→Vintage Editorial
- 版式需求:每页含标题 + storyboard 该节点 media(用 `final_path`)+ **时间戳角标**(mm:ss,`<a href>` 用 video_index.json 的 `video.badge_url_template` 填 t 的整数秒——跳转模板以导出文档为语义真相)+ summary 要点文字;`quality_limited` 的帧右下角标「代理画质」
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
- 索引文档(所有形态必查):`<OUT>/video_index.json` 存在且步骤 5.5 校验通过;抽 1 条 media 确认 `frames/` 相对路径可打开
- slides:每页有标题、无 placeholder 文案;所有 `assets/` 引用文件存在;同一 `dedup_group` 不出现在两页(视图级唯一性生效)
- slides:抽 3 个时间戳角标,核对 URL 格式(YouTube `&t=<n>s` / B 站 `?p=<n>&t=<n>`)且秒数在该节点时间窗内
- slides:抽 2 页核对帧与要点相关性,不符则回 sheet 换帧重渲染该页
- 笔记:notes.md 无死链(引用的 `frames/` 文件存在——渲染器已强校验,此处抽 1 图确认可显示);抽 2 个时间戳——在线核对跳转链接格式,本地确认为 mm:ss 纯文本
