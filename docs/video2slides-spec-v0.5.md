# video2slides — 项目规格说明(Spec v0.5)

> 一个 Claude Code skill:输入 YouTube / Bilibili 视频或本地视频文件,产出自包含的**「视频索引文档」**(`video_index.json` + `frames/`,公开契约),并按用户选择渲染为 frontend-slides 风格 HTML 演示文稿、markdown 笔记等下游形态;slide 内嵌视频关键帧与动态片段,可点击跳转回原视频对应时刻。
>
> 主干不变式:**transcript → content keys(大纲)→ related frames(要点窗口内定向选帧)→ video_index(索引文档)→ 渲染器族(slide / 笔记 / …)**。所有技术决策服务于这条链路。
>
> 状态:v0.5,定位升格决议源自 2026-07-13 拷问式 review(九条决议逐条确认),可进入切片实现。
>
> **v0.4 → v0.5 变更摘要**(源自「制品升格」grilling review,全部为已确认决议):
> 1. **定位升格**:一等交付物从 HTML slide 改为**视频索引文档**(`video_index.json`),slide 降为下游渲染器之一;skill 仍为单视频、宿主 Claude 形态,§1.2 非目标不推翻;搜广推/内容创意等业务对文档的消费属可移植性范畴,不为其增设运行形态(§1、§2)
> 2. **双制品契约分层**:内部 `storyboard.json` 保持工作格式(住 `.work/`,可自由演进,宿主反复读写不驮 transcript);对外契约由导出的 `video_index.json` 承担,以 JSON Schema 文件(`schemas/video_index.schema.json`)+ 文档内 `schema_version` 字段版本化,导出时机械校验(§6、§6.5)
> 3. **dedup 标注化**:跨节点去重从「删除式」改「标注式」——节点 media 记录语义真相(允许多节点引同帧),唯一性下沉为 slide 渲染器的视图级策略;宿主仲裁从「恢复被删数据」变「改标注」(§6、§9、§11)
> 4. **物理形态**:单 JSON 内嵌 meta/priors + 大纲树 + **全量 transcript segments**,配 `frames/` 目录,全相对路径,整目录可打包迁移;`.work/` 降为纯缓存,「可手动删除」承诺继续成立且不再损失交付物(§6.5)
> 5. **媒体资产政策**:终选帧 + 代理画质入档;每条 media 记 `t` + 分辨率,高清由消费方按时间戳自取(video 级源信息足够定位);clip 以区间 + poster 引用入档不物化;candidates 不入契约;定稿懒抓架构红利(§8.4)完整保留(§6.5)
> 6. **产出时机与交互扩展**:分析收尾(选帧 + dedup 后)由确定性脚本**无条件自动打包**——文档是本体不是可选输出;唯一交互点扩展为「产出形态(slides / 笔记 / 两者 / 仅索引文档)+ Length + 输出语言」,零打断契约不变(§9)
> 7. **笔记渲染器(第二消费方,兼契约验收器)**:`scripts/notes.py`,stdlib-only 确定性脚本,输入仅限导出文档 + `frames/`,禁碰 `.work/`;「两个消费方只读文档完成渲染」为契约完备性验收标准(§9.5、§12)
> 8. **时间戳精度显式化**:导出契约携带 `timestamp_granularity` 字段——chat 家族 ASR 的 45s 块级粒度必须让下游可见(§6.5)
> 9. **落地次序**:本升格为下一个切片;P2 dedup 判据升级排其后——届时只换签名判据不动契约,不返工(§13)
>
> **v0.3 → v0.4 变更摘要**(源自实现前 review 问答,全部为决议落地,不改变主链路):
> 1. 交互契约定稿:分析全程零打断,唯一交互点在渲染前——粒度询问与 frontend-slides Phase 1 的 Length 问题合并;风格由轴 B 体裁自动映射(跳过其 Phase 2 三选预览),交付时告知所用风格,可换风格重渲染(零重跑分析)(§9)
> 2. 输出语言规则:大纲与 slide 文字默认跟随视频语言,`--lang` 参数覆盖;evidence quote 始终为原文(§2、§7)
> 3. 本地文件输入定稿:时间戳跳转用 HTML 内嵌 `<video>` 弹层 + JS seek 就地跳播;预检明确提示本地输入必需 ASR 或 `--transcript`(§2、§9、§10)
> 4. 长视频分章生成机制定稿:超过阈值(初始 30min)按 chapters/页边界分章,每章独立生成大纲后全局归并;storyboard 分章合并写入(§7)
> 5. 中间制品统一存放输出目录 `.work/`,默认保留;断点续跑显式化:各层开始前检测制品存在且新于上游即跳过,`--force` 强制重跑(§2、§3)
> 6. B 站分 P:处理 URL 指定的单 P(缺省 P1);跳转 URL 格式补 `?p=n&t=`(§2、§9)
> 7. §14 开放项裁剪:页边界 snap 定软提示 + ±3s 容差、adaptive 参数沿用 crv 默认、帧预算定软上限初始值——从「待定」降级为「初始值,标注视频集仅用于回归调参」(§8、§14)
> 8. 项目名定稿:video2slides,slash command `/video2slides`(别名 `/v2s`)(§4)
> 9. 定位与路线定稿:YouTube / Bilibili 双平台对等一等公民,两条 ASR 路径(groq / funasr)均在 MVP 内验证;先自用后发布;实现路径为垂直切片——带字幕的 slide-driven 视频端到端优先(§1、§13)
> 10. 渲染细节:密度默认 high-density / reading-first;`--clips` 关闭时的 base64 内联作为版式需求传给 frontend-slides,不做渲染后处理(§9)
> 11. 【实测修订】B 站字幕实为平台 AI 字幕轨(`ai-zh`),**获取必须登录 cookie**,无 cookie 仅弹幕轨可得——「有字幕免配置」对 B 站改为「需 cookie 或回退 ASR」;测试视频集及核实结论见 `docs/test-videos.md`(§1、§10.3、§11、§13)
> 12. 【review 决议】ASR 配置面重构为三家族:**OpenAI 兼容 API 通用后端**(groq/openai 内置预设 + `api` 自定义 `ASR_API_BASE`/`ASR_API_KEY`/`ASR_MODEL` 三元组,任意兼容端点零代码接入)、**本地子进程后端**(FunASR 即刻支持,arm64/x86_64 Mac 通吃;mlx-whisper 仅 Apple Silicon、whisper.cpp 跨平台,留槽位)、**none**;预检按所配后端校验可用性与平台 arch 匹配(§3、§4、§10、§13)
> 13. 【实测补充】测试集扩至 15 源,补齐「自带字幕 + slide-driven」验收(YouTube #13 / B 站 #11);实测 B 站 AI 字幕非全覆盖(存在无 ai-zh 轨的视频),分 P 合集取流必须带 `?p=n` 定 P(§2、§13、`docs/test-videos.md`)
> 14. 【切片 2 设计修订,2026-07-11】API 家族按实测端点拆两种协议形状:`transcriptions`(whisper 式,原生段级时间戳:groq/openai/api)与 `chat`(chat-completions 携带 base64 音频,无原生时间戳:mimo/qwen 预设,单请求 base64 ≤10MB);新增**音频切块层**(ffmpeg silencedetect,零 pip)为 chat 家族供块级时间戳、为 transcriptions 处理大小上限;`ASR_BACKEND` 取值扩为 `funasr|groq|openai|mimo|qwen|api|none`,默认 funasr。详见 `docs/superpowers/specs/2026-07-11-slice2-asr-local-design.md`(§10.1)
>
> **v0.2 → v0.3 变更摘要**(源自主链路深推演讨论):
> 1. scene 尖峰序列升格为「页边界」结构先验(与 chapters 同级),slide-driven 段大纲节点边界 snap 到页边界(§3、§6、§7)
> 2. 要点窗口对齐规则:slide-driven 窗口前扩至上一页边界、cue 锚点窗口后扩 2–5s,消除「讲的时间≠画面时间」系统性错位(§8.1)
> 3. 引用校验从「summary fuzzy 相似」改为「verbatim quote 原文存在性」(§6、§7)
> 4. 媒体两阶段:分析期对全部叶子要点在代理流上跑满候选→终选;高清定稿与 clip 截取懒抓到渲染粒度确定后,换粒度零重跑分析(§3、§6、§8.0、§8.4、§9)
> 5. ASR 后端配置化:`ASR_BACKEND=groq|funasr|none`,本地 FunASR 成为一等可配置后端(§10)
> 6. 输入逃生门:`--transcript <path>` 直喂外部转写,跳过取字幕与 ASR(§2)
>
> **v0.1 → v0.2 变更摘要**(源自对 claude-real-video 的源码级调研):
> 1. 新增全局 scene-score 时间线 sidecar,作为探针/选帧/clip 定位/末帧规则的共享信号基底(§3、§8.0)
> 2. 新增低清代理流分析、高清定稿抓帧的双分辨率架构(§8.0)
> 3. 窗口候选抽取由逐窗调用改为全局单遍复合 select filter(§8.1)
> 4. 去重升级为滑动窗口 + RGB 算法,零 pip 实现;新增跨要点媒体去重校验(§8.1、§6、§12)
> 5. 新增 adaptive 滚动相对阈值选峰,按 visual_form 自动路由(§8.1)
> 6. 新增 contact sheet(ffmpeg tile)作为 Claude 仲裁/终选环节的 token 优化(§8.3)
> 7. 新增竞品格局章节(§15)

---

## 1. 目标与非目标

### 1.1 目标

- 将视频转化为**视频的可导航索引**,而非静态摘要。**【v0.5 升格】索引的本体是一份自包含的结构化文档**(`video_index.json`):大纲 ↔ transcript ↔ frames 的映射关系 + 全量转写内嵌,每个要点配关键帧/动态片段与时间戳;slide、笔记等渲染形态都是这份文档的下游视图
- **【v0.5 定稿】一等交付物与渲染器族**:索引文档无条件产出;首批两个渲染器——frontend-slides HTML 与 markdown 笔记——均以「只读文档完成渲染」为契约完备性验收;换形态/换粒度重渲染零重跑分析
- 分析质量建立在**双模态证据**上:timestamped transcript(语义)+ 关键帧(画面),弥补纯文本方案"看不到画面"的根本缺陷
- 安装摩擦对齐 claude-video 水平:必装二进制 2 个,pip 零依赖,有字幕的在线视频无需任何 API key 即可跑通——YouTube 字幕直接可得;B 站字幕为 AI 字幕轨,需浏览器 cookie(免 key 但需登录态,§10.3)【v0.4 实测修订】;本地文件输入见 §10.2 措辞限定
- **【v0.4 定稿】双平台对等**:YouTube 与 Bilibili 均为一等目标平台,测试视频集各半,groq 与 funasr 两条 ASR 路径均在 MVP 内验证
- **【v0.4 定稿】路线:先自用后发布**——代码按可发布标准写(出处注明、预检完备、SKILL.md 规范),但不为 marketplace 上架做额外适配;自用跑顺后再上架

### 1.2 非目标(MVP 明确不做)

- 不做独立 CLI / 服务形态(分析层 LLM 即宿主 Claude,不自行调用 LLM API)
- 不做 pptx 输出(HTML 的时间戳跳转与内嵌视频是核心红利,pptx 形态无法承载)
- **【v0.5 确认】不做批量/服务化的「视频理解基础设施」**:搜广推/内容创意等业务对索引文档的消费属可移植性范畴——文档自包含、schema 版本化正是为此服务——但对接由消费方自行完成,本项目不为其增设运行形态
- 不做画中画区域检测(整帧处理)、板书/实拍的独立分类(归并处理,见 §5)
- 不做批处理 / 队列 / 生产化(B 站整稿多 P 亦属批处理,见 §2)
- 不做拉片/创作分析(镜头语言、剪辑节奏等,claude-real-video Pro 的方向,与本项目正交)

---

## 2. 输入与输出

| 项 | 规格 |
|---|---|
| 输入 | YouTube URL(`youtube.com/watch?v=` / `youtu.be/`)、Bilibili URL(`bilibili.com/video/BV…`)、本地视频文件路径;MVP 单源 |
| B 站分 P【v0.4 定稿】 | 处理 URL `p` 参数指定的单 P,缺省 P1;整稿多 P 属批处理(非目标)。实现要点【实测】:分 P 合集的 metadata/取流调用必须带 `?p=n`(fetch.py 先归一化 URL,缺省补 `p=1`),否则 yt-dlp 枚举全部分 P(187P 合集直接超时) |
| 本地文件事项【v0.4 定稿】 | 无字幕/chapters/heatmap 等先验,必需 ASR 后端或 `--transcript`(预检明确提示,§10);时间戳跳转走内嵌播放器(§9) |
| 输入逃生门【v0.3 新增】 | `--transcript <path>`:直喂外部转写(SRT/VTT/带时间戳 JSON),跳过取字幕与 ASR 整层;覆盖「已有现成转写资产」的复用场景 |
| 输出【v0.5 修订】 | **视频索引文档**(`video_index.json` + `frames/`,§6.5)——分析收尾**无条件产出**;渲染产物按交互点选择:frontend-slides 规范的 HTML 演示文稿(固定 1920×1080 stage、零运行时依赖)+ `assets/` 目录(定稿帧 JPEG、片段 MP4),和/或 markdown 笔记(`notes.md`,§9.5) |
| 输出语言【v0.4 定稿】 | 大纲与渲染产物文字默认**跟随视频语言**(中文视频出中文,英文视频出英文),`--lang` 参数覆盖;evidence quote 不受影响,始终为转写原文 |
| 输出形态开关 | `--clips` 默认开:HTML + assets 目录;关闭:纯静态帧 base64 内联的单 HTML 文件(内联作为版式需求传给 frontend-slides,非渲染后处理,§9)——仅影响 slide 渲染,不影响索引文档 |
| 中间制品【v0.5 修订】 | 统一存放输出目录下 **`.work/`**:`storyboard.json`(内部工作格式,§6)、`scene_scores.json`(帧层共享信号基底,§8.0)、`frames_proxy/`(代理流候选与终选帧,§8.4)、代理流视频。**默认保留**——换粒度重渲染与断点续跑均依赖它;交付物已自包含(§6.5),删除 `.work/` 不再损失交付物,SKILL.md 提示可手动删除 |
| 默认输出路径 | `~/Desktop/video2slides/<title>_<date>/` |

---

## 3. 架构总览

**核心分工原则**:确定性脚本负责重计算与可复现逻辑,宿主 Claude 负责语义判断与编排决策;两者通过结构化制品交接,脚本 stdout 即为喂给 Claude 的下一轮指令。

**断点续跑【v0.4 新增】**:制品链(代理流 → transcript → scene_scores → storyboard → 索引文档 → 定稿资产)天然是 checkpoint 序列。SKILL.md 显式约定:每层开始前检测对应制品已存在且新于上游制品,是则跳过该层;各脚本提供 `--force` 强制重跑。中断(context 耗尽 / 用户打断 / 网络故障)后重新发起即从断点继续。

```
下载层(脚本,确定性)
  yt-dlp:低清代理流(≈360p,供全部分析)+ 字幕/chapters/heatmap/弹幕/metadata
  ASR fallback:三家族可配置后端(OpenAI 兼容 API / 本地子进程 / none,§10;--transcript 直喂时整层跳过)
      ↓  timestamped transcript + 免费人工先验信号
信号基底层(脚本,确定性)【v0.2 新增】
  对代理流做一次 ffmpeg 元数据遍历(select='gte(scene,0)' + metadata=print,null 输出)
  → 全视频逐帧 scene-score 时间线,落盘 scene_scores.json
  五个下游消费者共享:轴A探针 / 页边界先验(大纲 snap) / 窗内选峰 / clip定位 / whiteboard末帧规则
      ↓
分析层(宿主 Claude)
  轴 A 画面形态分类(基于 score 曲线形状 + 边缘密度,Claude 看探针 contact sheet 仲裁)
  轴 B 体裁分类(transcript + metadata)
  层级大纲生成:每个节点生成时直接引用 evidence 时间段;
    slide-driven 段以页边界为结构先验,节点边界 snap 到页边界【v0.3 新增】
    >30min 默认分章生成后全局归并【v0.4 定稿,§7】
  引用校验:verbatim quote 原文存在性验证,防幻觉引用【v0.3 修订】
      ↓  outline tree,每节点带 [t_start, t_end]
帧层(脚本,确定性 + Claude 终审)
  全部叶子要点窗口(经 §8.1 对齐规则扩展)合成一个复合 select 表达式,代理流上单遍抽取全部候选
  → 窗口 RGB 去重 → 避糊/文字密度打分 → 剪枝至每要点 top-3
  → 按要点/章节拼 contact sheet,宿主 Claude 一次 Read 终选
  → 跨要点全局去重**标注**(不删除,§6)【v0.5 修订】
      ↓  storyboard.json(内部工作格式,全部叶子挂代理媒体,finalized=false)
打包层(脚本,确定性)【v0.5 新增】
  storyboard + transcript + meta/priors 组装为 video_index.json(内嵌全量转写,schema_version)
  + 终选帧拷入 frames/(相对路径);JSON Schema + quote 存在性 + 路径存在性机械校验
  分析收尾无条件执行——索引文档是分析层的终点制品,不是可选输出
      ↓  video_index.json + frames/(公开契约,§6.5)
渲染层(宿主 Claude + 渲染器族)【v0.5 修订】
  询问「产出形态 + 粒度 + 语言」(单交互点,§9)
  → slides:frontend-slides skill——定展开深度 → 浅层节点从子树聚合 top-k 媒体
    → 仅对真正上页的媒体回高清流抓定稿帧、截取 clip(§8.4 定稿懒抓)
    → 视图级唯一性(按 dedup 标注取 primary)→ 风格由轴 B 自动映射生成 HTML
  → 笔记:scripts/notes.py 确定性渲染,只读导出文档(§9.5)
```

---

## 4. Skill 形态与目录结构

- **形态**:Claude Code skill,可发布至 plugin marketplace
- **命名【v0.4 定稿】**:项目名 **video2slides**,slash command `/video2slides`,别名 `/v2s`(仓库目录随实现统一为复数;【v0.5 确认】定位升格后项目名保留不改,SKILL.md 顶部 description 改为「索引文档 + 渲染器族」表述)
- **前置依赖 skill**:frontend-slides(作为要求安装项,SKILL.md 中声明;slide 渲染阶段读取其 SKILL.md 并按其 fixed-stage 规范生成,不自行内嵌裁剪版)
- **风险预案**:frontend-slides 版本漂移时以其当前 SKILL.md 为准;我方只传递内容与版式需求(帧卡片、时间戳角标、clip 卡片、base64 内联开关),不硬编码其内部实现

```
video2slides/
├── SKILL.md              # 编排契约:预检 → 取流 → 信号基底 → 分析 → 选帧 → 打包导出 → 渲染(含定稿懒抓);含断点续跑约定
├── schemas/
│   └── video_index.schema.json  # 导出契约的 JSON Schema【v0.5 新增】
├── scripts/
│   ├── setup.py          # 预检(--json / --check)+ 幂等安装器 + .env 脚手架
│   ├── fetch.py          # yt-dlp 封装:代理流/高清流/字幕/chapters/heatmap/弹幕/metadata
│   ├── transcribe.py     # VTT/SRT 解析去重 + 三家族可插拔 ASR 后端(§10.1)+ 弹幕密度直方图
│   ├── signals.py        # scene-score 元数据遍历 → scene_scores.json【v0.2 新增】+ 划章 hints
│   ├── frames.py         # 复合单遍候选抽取 + 窗口RGB去重 + 打分剪枝 + contact sheet + --finalize 定稿懒抓(高清帧+clip)
│   ├── storyboard.py     # 内部制品校验(schema、时间戳、quote 存在性、跨要点 dedup 标注)+ export 导出组装与契约校验【v0.5 扩展】
│   └── notes.py          # markdown 笔记渲染器:只读 video_index.json + frames/,stdlib-only【v0.5 新增】
└── (slide 渲染直接调用 frontend-slides skill,不自带渲染代码)
```

LLM 职责(形态/体裁分类、大纲生成、帧终选、HTML 生成)**写为 SKILL.md 中给 Claude 的步骤指令,不落为脚本**——语义判断显式留给宿主。打包导出与笔记渲染是纯确定性变换,归脚本。

---

## 5. 两轴分类体系

体裁与抽帧策略非一一对应,拆为两根正交轴,各自独立判定、独立消费。

### 5.1 轴 A:画面形态(visual_form)— 驱动抽帧策略

**判定方式**:视觉探针。**v0.2 起以 scene_scores.json 的曲线形状为主信号**(取代 v0.1 的缩略图差分),辅以边缘密度;Claude Read 探针 contact sheet 仲裁:

- **score 曲线形状**:长平台+尖峰 = slide;持续小抖动 = 录屏;低幅但滚动均值缓升 = 板书;全程低 = talking-head;高频大幅 = cinematic
- **边缘/文字密度**(ffmpeg `edgedetect,signalstats` 代理,或 tesseract 抽查):高 = slide/录屏,低 = 实拍
- ~~人脸占比~~(已砍:需 opencv 级依赖,边际价值不足)

**MVP 实现 4 类**,余者归并:

| 形态 | 抽帧策略要点 | MVP |
|---|---|---|
| slide-driven | score 尖峰 = 翻页;每"页"取一帧;OCR/边缘密度打分;页内任意时刻等价 | ✅ |
| screen-recording | 固定阈值失效;窗内 adaptive 选峰 + 激进去重;滚动中取停顿帧;**clip 主力场景** | ✅ |
| talking-head | 每要点 0–1 帧,纯装饰;slide 以文字排版为主 | ✅ |
| cinematic | 按画质/构图分选帧而非按变化选;帧是叙事主体 | ✅ |
| whiteboard/手写 | 归并至 slide-driven,但取要点窗末帧(板书写满时信息量最大)+ adaptive 选峰捕获书写节奏 | 归并 |
| 实拍演示 | 归并至 cinematic;转录 cue 词("像这样"/"完成了")辅助定位 | 归并 |
| 画中画/混合 | 整帧处理,后续版本做区域检测 | 归并 |

**Schema 预留**:`visual_form` 为**分段数组**(conference talk 常见"开场 talking-head → 正片 slide → 结尾 demo 录屏")。MVP 输出单段;score 曲线本身可粗分段(平台区 vs 抖动区),升级时契约不变:

```json
"visual_form": [
  {"t_start": 0, "t_end": 312, "form": "talking-head"},
  {"t_start": 312, "t_end": 2140, "form": "slide-driven"}
]
```

### 5.2 轴 B:内容体裁(genre)— 驱动大纲模板与主题

**判定方式**:宿主 Claude 基于 transcript + 标题/简介/chapters。

体裁集合:课程/教程、演讲/分享、访谈/播客、评测/对比、资讯/解读、会议记录、vlog/生活、纪录片。每体裁对应一套大纲骨架与 frontend-slides 风格倾向(v0.4 起风格由此表**直接定**而非仅"倾向",见 §9)。

两轴正交消费:轴 A 查抽帧策略表并门控页边界先验(§7),轴 B 查大纲模板表与风格映射表,无需枚举组合矩阵。

---

## 6. storyboard.json(内部工作格式)【v0.5 重定位】

**自 v0.5 起,storyboard.json 是内部制品**:住 `.work/`,是分析层各步骤(分章追加、media 回写、dedup 标注、渲染側定稿记账)反复读写的工作格式,**可随内部迭代自由演进,不构成对外承诺**。对外契约由导出的 `video_index.json` 承担(§6.5)——「分析层与渲染层解耦、任一侧可独立重实现」的原有价值主张,由导出契约接棒兑现。

不内嵌 transcript 的理由(v0.5 决议):宿主在步骤 4–7 需反复读写本文件(分章逐章追加、media 回写、on_page 标注),内嵌全量转写会让每次读写都驮着数百段文本,纯烧 token;全量转写在导出时才合入文档。

```json
{
  "video": {
    "source_url": "…", "platform": "youtube|bilibili|local",
    "title": "…", "duration": 1834.0, "language": "zh",
    "genre": "lecture",
    "visual_form": [ {"t_start": 0, "t_end": 1834.0, "form": "slide-driven"} ],
    "signals": { "scene_scores": "scene_scores.json" },
    "priors": {
      "chapters": [ {"title": "…", "t_start": 0, "t_end": 312} ],
      "heatmap": [ {"t_start": 0, "t_end": 18.3, "value": 0.42} ],
      "danmaku_density": [ {"t": 60, "count": 34} ],
      "page_boundaries": [ {"t": 312.4, "score": 0.83} ]
    }
  },
  "outline": [
    {
      "id": "2.1", "level": 2,
      "title": "反向传播的链式法则",
      "summary": "…",
      "t_start": 421.5, "t_end": 587.0,
      "evidence": [
        {"segment_id": 88, "quote": "把链式法则拆到计算图的每一条边上"}
      ],
      "media": [
        {"type": "frame", "proxy_path": "frames_proxy/f_0431.jpg",
         "final_path": null, "finalized": false, "t": 431.2,
         "reason": "scene-peak", "ocr_density": 0.81, "score": 0.92,
         "dedup_group": null, "dedup_primary": true},
        {"type": "clip", "final_path": null, "finalized": false,
         "t_start": 429.5, "t_end": 433.0,
         "poster": "frames_proxy/f_0431.jpg", "reason": "score-peak-window"}
      ],
      "children": []
    }
  ]
}
```

要点:

- **多粒度 = 树的 level**。渲染时选深度(5 页 executive 取 level 1;20 页详版展开至 level 2/3),不重跑分析
- **【v0.3 新增】帧层只对叶子节点选帧**(`children` 为空的节点,不必同层)。父节点时间窗是子节点窗口的并集,对父节点独立选帧是重复劳动;浅层渲染时父节点从子树叶子聚合 top-k 媒体(纯读 storyboard 排序,不碰视频)。细粒度媒体可向上兑换成粗粒度的,反之不行——这是「换粒度不重跑分析」成立的前提
- **【v0.3 新增】媒体两阶段生命周期**:分析期产出 `proxy_path`(代理流帧,`finalized: false`);渲染期定稿懒抓(§8.4)回填 `final_path` 并置 `finalized: true`(clip 的 `poster` 同步切到定稿帧)。storyboard 在两期之间是合法中间态,`storyboard.py` 按 `finalized` 分别校验。【v0.5 确认】渲染側记账(`on_page`/`final_path`/`finalized`)继续记在本文件——导出文档只读,不承载渲染状态
- **【v0.4 新增】分章场景的写入**:长视频分章生成(§7)时,storyboard 按章合并写入——章级子树逐章追加,全部章完成后 `storyboard.py` 做一次全局校验(含跨章 dedup 标注)
- **`priors` 全部 fail-open**(含 v0.3 新增的 `page_boundaries`):缺失即置空并静默跳过,SKILL.md 明确"有则用、无则纯 transcript",禁止 Claude 因信号缺失中断
- `media` 支持一要点混搭 frame + clip,渲染层按版面容量取舍
- **【v0.5 修订】跨要点媒体 dedup 标注化**(替代 v0.2 的删除式唯一性校验):`storyboard.py` 对全部选中帧计算去重签名,重复组**打标注不删除**——同组 media 写入相同 `dedup_group`(组标识),组内分数最高者标 `dedup_primary: true`,其余 `false`;无重复的帧 `dedup_group: null`。节点 media 由此记录**语义真相**(一帧可真实关联多个要点);「slide 不重复配图」下沉为 slide 渲染器的视图级策略(取 primary,§9)。宿主仲裁(SKILL 步骤 5)从「恢复被删数据」变「改标注」:目验后确认「同版式不同内容」误判的,拆组(置 `dedup_group: null`)或调换 primary。P2 的去重判据升级(§13)只替换签名算法,不再改动数据形状

---

## 6.5 video_index.json(导出公开契约)【v0.5 新增】

分析层的终点制品、本项目的一等交付物:大纲 ↔ transcript ↔ frames 映射关系的自包含单文档。所有渲染器(slide、笔记及任何第三方消费者)的语义输入**只来自这份文档**;下游视频理解类消费(检索、素材复用、内容创意等)对接的也是它——自包含 + schema 版本化即为可移植性服务。

### 6.5.1 物理形态与自包含承诺

- `<OUT>/video_index.json`:单 JSON,内嵌 video meta/priors、**全量 transcript segments**、大纲树(含 evidence 与 media);全部媒体引用为**相对路径**
- `<OUT>/frames/`:文档引用的终选帧(代理画质拷贝,§6.5.3)
- 整个 `<OUT>` 目录可打包迁移/分享,不依赖 `.work/`(删除 `.work/` 后文档与两个渲染器的语义输入仍完整);quote 校验可离线复验(quote ∈ 内嵌 segments 的原文)

### 6.5.2 结构(示意;规范定义以 `schemas/video_index.schema.json` 为准)

```json
{
  "schema_version": "1.0.0",
  "generator": {"skill": "video2slides", "spec": "v0.5"},
  "video": {
    "source_url": "…", "platform": "youtube|bilibili|local",
    "title": "…", "uploader": "…", "duration": 1834.0, "language": "zh",
    "genre": "lecture",
    "visual_form": [ {"t_start": 0, "t_end": 1834.0, "form": "slide-driven"} ],
    "badge_url_template": "https://www.youtube.com/watch?v=…&t={t}s",
    "priors": { "chapters": [], "heatmap": [], "danmaku_density": [], "page_boundaries": [] }
  },
  "transcript": {
    "source": "subtitle|asr:<backend>",
    "timestamp_granularity": "segment|sentence|chunk-45s",
    "segments": [ {"id": 88, "t_start": 421.5, "t_end": 427.9, "text": "…"} ]
  },
  "outline": [
    {
      "id": "2.1", "level": 2, "title": "…", "summary": "…",
      "t_start": 421.5, "t_end": 587.0,
      "evidence": [ {"segment_id": 88, "quote": "…"} ],
      "media": [
        {"type": "frame", "path": "frames/2.1_431.2.jpg", "t": 431.2,
         "resolution": "proxy-360p", "score": 0.92, "reason": "scene-peak",
         "dedup_group": null, "dedup_primary": true},
        {"type": "clip", "t_start": 429.5, "t_end": 433.0,
         "poster": "frames/2.1_431.2.jpg", "reason": "score-peak-window"}
      ],
      "children": []
    }
  ]
}
```

字段要点:

- **`schema_version`**:语义化版本——加字段升次版本,删字段/改语义为破坏性变更升主版本;消费方按主版本判兼容
- **`transcript.timestamp_granularity`**:时间戳精度显式化——`segment`(字幕轨原生)/ `sentence`(funasr 句级)/ `chunk-45s`(chat 家族 ASR 块级)。下游必须能知道 `t_start`/`t_end` 的可信粒度,不能让 45s 块级精度伪装成秒级
- **`video.badge_url_template`**:时间戳跳转模板(YouTube `&t={t}s` / B 站 `?p=n&t={t}`;本地文件为 `null`)——任何消费方据此生成回源跳转
- **媒体的高清自取**:文档只含代理画质;需要高清的消费方用 `video.source_url/platform` + `media.t` 自行按时间戳取帧(这正是 slide 渲染层 finalize 的机制,§8.4)。clip 只含区间 + poster 引用,不物化视频片段
- **关系形态(v0.5 决议)**:树 + 1:N——节点→segments 走 `evidence`,节点→frames 走 `media`,多粒度走树 level;**不设 frame↔segment 显式边**,时间戳是全文档的天然 join key,任何消费方可自行按时间对齐;dedup 标注(§6)如实导出,消费策略归各渲染器

### 6.5.3 媒体资产政策(v0.5 决议)

- `frames/` **只收节点终选 media**(含 dedup 标注保留的全部帧),360p 代理画质直接拷入;candidates.json(全量候选)是剪枝副产品不是语义真相,留在 `.work/` 当缓存,**不入契约**——由此 P2 的候选策略调整不构成契约变更
- 文档帧不做高清定稿:高清是渲染层按需懒抓的特权(§8.4),定稿资产落 `assets/` 归 slide 交付物,不回写文档——保住「分析成本与出图质量解耦」的架构主线

### 6.5.4 打包与校验

- 默认命名 `storyboard.py export --work <W>`(实现期可调,§14):从 storyboard + transcript + meta/priors 确定性组装,拷帧、重写相对路径、写入 `schema_version`
- 导出时机械校验:JSON Schema 校验 + quote 存在性复核(对内嵌 segments)+ 媒体相对路径存在性;**校验不通过不产出文档**(契约宁缺毋滥),按 stdout 修复内部制品后重跑
- 执行时机:SKILL 步骤 5(选帧 + dedup 标注 + validate)完成后**无条件自动执行**,先于唯一交互点——文档是本体,不因用户选择「仅要 slides」而跳过

---

## 7. 大纲生成与对齐(分析层)

- **文本优先为主路径**:LLM 从 timestamped transcript 生成层级大纲,**生成时即要求引用支撑证据**(structured output,`evidence` 为 `{segment_id, quote}` 列表);"要点→时间段"mapping 生成时免费获得,不做事后 embedding 对齐
- **引用校验【v0.3 修订】**:structured output 中每条 evidence 须附 `quote`(该字幕段内的 verbatim 原文短语);`storyboard.py` 校验 quote 确实存在于所引段文本(substring 优先,ASR 噪声场景退高阈值 fuzzy)。v0.2 的「summary 与段文本 fuzzy 相似」方案已废弃——summary 是综合改写,与原文字面相似度天然低,会大量误杀。校验不通过打回重生成,超 2 次该节点降级纯文字 slide
- **免费人工先验作为骨架**:YouTube chapters(`yt-dlp -J`)与 B 站分P 优先作为 level-1 骨架;YouTube heatmap 与 B 站弹幕密度峰值作为"高能时刻"信号,提示 LLM 该时段值得展开为独立要点
- **页边界先验【v0.3 新增,仅 slide-driven 段启用】**:scene 尖峰序列即翻页时刻——**视频里的 slide 是作者亲手做好的大纲**,页边界是免费的结构边界。升格为与 chapters 同级的骨架先验喂给大纲生成:提示 LLM 尖峰附近的 transcript 是要点候选,并要求节点时间边界 snap 到最近页边界。**snap 规则【v0.4 定稿】:软提示 + ±3s 容差**——容差内 snap 到页边界,超出保留字幕时间;标注视频集仅用于回归调参(§12)。轴 A 判非 slide-driven 或置信度低时不启用,节点边界用字幕时间原样——fail-open 与其他先验一致
- **长视频分章生成【v0.4 定稿】**:视频超过阈值(初始 **30min**)时默认分章:以 chapters 优先、页边界次之、时长均分兜底划章;每章独立走「大纲生成 + 引用校验」产出章级子树,章标题作 level-1 骨架;全部章完成后做**全局归并**——跨章 dedup 标注、层级归一、storyboard 分章合并写入(§6)。脚本契约(transcribe.py 分段输出、storyboard.py 增量校验)按分章设计,短视频退化为单章,同一条代码路径
- **输出语言【v0.4 定稿】**:大纲 `title` / `summary` 默认跟随视频语言,`--lang` 覆盖;`evidence.quote` 始终为转写原文(校验依赖原文存在性,与输出语言解耦)

---

## 8. 媒体选取(帧层)

### 8.0 共享信号基底与双分辨率架构【v0.2 新增】

**scene_scores.json**:开局对代理流做一次 ffmpeg 元数据遍历(`select='gte(scene,0)',metadata=print`,`-f null` 不输出图像),得到全视频逐帧 scene-change 分数时间线并落盘。轴 A 探针、页边界先验、窗内选峰、clip 定位、whiteboard 末帧规则五个消费者全部读这一份数组做纯 Python 计算,不再各自调 ffmpeg。
(方法出处:claude-real-video `_scene_scores`,MIT,重新实现)

**双分辨率**:全部分析(score 遍历、探针、候选抽取、去重签名、打分、Claude 终选)跑在 yt-dlp 单独拉取的**低清代理流(≈360p)**上;终选只确定时间戳,高清定稿抓取**懒到渲染粒度确定后**,仅对真正上页的媒体执行(§8.4)。分析成本与出图质量解耦——2h 视频的全量遍历从高清数分钟降至代理流数十秒;这是在线视频(多码率可选)相对本地文件工具的独有红利。本地文件输入时代理流由 ffmpeg 现场降采样生成。

### 8.1 静态帧候选与剪枝

0. **要点窗口对齐【v0.3 新增】**:选帧窗口不等于字幕时间原样——字幕时间是「讲这个要点的时间」,画面最佳帧常在窗外:
   - slide-driven:窗口起点前扩至上一页边界(讲者先翻页再开讲,slide 出现早于第一句话)
   - cue 词锚点(cinematic/实拍):窗口终点后扩 2–5s(「我们来试试」说完动作才出现)
   纯读 scene_scores.json 的 Python 计算,零额外解码成本。
1. **全局单遍复合抽取【v0.2 修订】**:全部叶子要点窗口(经步骤 0 对齐)及各自策略合成一个 select 表达式,代理流一遍解码抽出所有候选,天然时序保序(去重比较真实邻居):
   ```
   select='between(t,421.5,587)*gt(scene,0.2) + between(t,720,810)*not(mod(n,50)) + eq(n,anchor…)'
   ```
   窗内选峰策略按该窗所处 visual_form 段路由:
   - slide-driven:固定阈值尖峰(翻页)
   - screen-recording / whiteboard:**adaptive 滚动相对阈值**——score ≥ 前 2s 滚动均值 ×3 且 ≥ 绝对下限,渐变内容相对自身安静邻域被捕获(出处:crv `--adaptive`;我们由探针自动路由,无需用户手动开关)。**参数【v0.4 定稿】:直接沿用 crv 默认(窗口 2s / 倍数 3× / 下限 0.04)作为初始值**
   - talking-head:窗中点单帧
   - cinematic:均匀采样,交由打分排序
   字幕 cue 锚点(讲者"看这里"类指示语,由 Claude 读 transcript 判定后回传时间戳)以 `eq(n,…)` 并入同一表达式,并在预算分配时 pin 住
2. **窗口 RGB 去重【v0.2 升级】**:16×16 **RGB** 签名(等亮度色彩切换在灰度下不可见),对比**最近 4 张保留帧的滑动窗口**(抑制 A-B-A 交替——讲者特写↔slide 全屏来回切时,已见镜头不再重复入选;这恰是我们要点窗口的高频场景)。实现:ffmpeg `rawvideo -pix_fmt rgb24` 批量输出字节流 + 纯 Python 逐像素占比计算,**零 pip**(规避 crv 的 PIL 依赖及其"缺失时静默失效"隐患)
3. **打分剪枝至每要点 top-3**:
   - 避糊:优先"score 尖峰后偏移 0.5–1s 取稳定帧";ffmpeg ≥ 5.1 叠加 `blurdetect`
   - 文字密度(slide/录屏段):tesseract subprocess;缺失自动降级 ffmpeg 边缘密度代理

### 8.2 动态片段(clip)

- **判据:运动本身是否为信息**。screen-recording(主力)与实拍类默认生成;slide-driven / talking-head 不生成;whiteboard 延时循环为 P2
- **格式:H.264 MP4(CRF 28、无音轨、2–5 秒硬上限),不用 GIF**
- **区间定位【v0.2 简化】**:直接读 scene_scores.json,取要点窗内分数活动最密集子区间为中心;实拍类叠加转录 cue 词。分析期只落区间与 poster 引用,截取动作在渲染期定稿阶段执行(§8.4)
- **渲染**:`<video autoplay muted loop playsinline poster="…">`;poster 设为该要点已选关键帧(加载占位 / PDF 导出降级 / Claude QA 三用);遵循 `prefers-reduced-motion`

### 8.3 Claude 终选与 contact sheet【v0.2 新增】

候选剪枝后,frames.py 用 ffmpeg `tile` filter(零依赖)把帧拼成带文件名标注的九宫格 contact sheet:

- **探针仲裁**:15 张探针帧 = 2 张 sheet,Claude 一次 Read 完成轴 A 分类确认
- **帧终选**:按章节拼 sheet(每张含该章各要点的 top-3 候选),Claude 读 sheet 选定各要点用帧,仅对需要细看的单帧(如确认 slide 文字)追加高清单帧 Read

相比逐帧 Read,图片读取次数降约一个数量级;sheet 内帧按时间序排列,Claude 可顺带感知运动与进程。

**帧预算【v0.4 定稿,软上限初始值】**:contact sheet 每章 ≤2 张;单视频 Claude 图片 Read 目标 ≤15 次(含探针仲裁与追加细看;长视频分章场景按章预算)。写入 SKILL.md 契约,数值实现期按视频集回归调整。

### 8.4 定稿懒抓(渲染期)【v0.3 新增】

分析期结束时索引文档已完整(全部叶子挂代理媒体),但不产出任何高清资产。slide 渲染期:

1. 用户选定粒度 → 确定展开深度 → 浅层节点从子树叶子聚合 top-k 媒体(纯 storyboard 排序,见 §6)
2. `frames.py --finalize`:仅对真正上页的媒体回高清流按时间戳精准抓定稿帧、按区间截取 clip,回填 `final_path` / `finalized: true`
3. 换粒度重渲染 = 增量补抓新上页媒体的高清资产,分析层零重跑
4. 高清流直链过期(yt-dlp URL 有时效)则重新 fetch;仍失败降级用代理帧上页并标注质量受限(见 §11)

【v0.5 确认】定稿懒抓是 slide 渲染层的机制:语义输入(选哪些媒体、时间戳、源信息)来自导出文档,记账状态(`on_page`/`final_path`/`finalized`)记在内部 storyboard.json(§6),定稿资产落 `assets/`;**导出文档只读,不被渲染过程改写**。第三方消费者需要高清时走同一机制的等价物:`video.source_url` + `media.t` 自取。

---

## 9. 渲染层

- 调用 frontend-slides skill,遵循其全部不变量(1920×1080 fixed stage、零依赖、密度模式、反 AI-slop 美学)
- **【v0.3 新增】渲染前置步骤**:粒度确定后,按深度展开大纲树 → 浅层节点聚合子树 top-k 媒体 → 执行 `frames.py --finalize` 产出高清资产(§8.4),再进入 HTML 生成
- **交互契约【v0.5 修订】**:分析全程零打断,**唯一交互点在打包导出之后、渲染之前**,一次问三件事:
  1. **产出形态**:slides / markdown 笔记 / 两者 / 仅索引文档(到此为止)——索引文档此时已落盘,该选项只决定是否继续渲染
  2. **Length**:短 5–10 / 中 10–20 / 长 20+(默认中)——对任何渲染器都是展开深度选择(slides 的页数档位 = 笔记的 `--depth` 档位);与 frontend-slides Phase 1 的 Length 问题一字不差,直接合并
  3. **输出语言**(默认跟随视频)
  其余 frontend-slides Phase 1 问题不问:Purpose 由轴 B 体裁推断,Content 恒为 ready(索引文档即内容),**Density 默认 high-density / reading-first**(视频索引产物天然面向阅读,询问时可顺带改)
- **视图级唯一性【v0.5 新增】**:slide 渲染消费 dedup 标注(§6)——同 `dedup_group` 只上 primary 帧,其余节点该页回退窗内候选次名或转纯文字;「一帧不上两页」从此是 slide 的视图策略,不再是数据事实
- **风格自动映射【v0.4 定稿】**:跳过 frontend-slides Phase 2 三选预览,由轴 B 体裁 → 风格映射表**直接定**风格(映射表实现期定,§14)。**纠错口子**:交付时告知所用风格,不满意可指定风格重渲染——与换粒度/换形态同机制,零重跑分析
- 本 skill 传递的增量版式需求:帧卡片带时间戳角标、clip 卡片规范(§8.2)、`--clips` 关闭时全部图片以 base64 data URI 内联(与其"单文件全内联"哲学一致,非渲染后处理)
- **时间戳跳转**:
  - YouTube:`youtube.com/watch?v=…&t=431s`
  - Bilibili:`bilibili.com/video/BV…?t=431`,分 P 视频补 `p` 参数:`?p=n&t=431`【v0.4 定稿】
  - **本地文件【v0.4 定稿】**:无可跳 URL,时间戳角标点击改为打开 HTML 内嵌 `<video src=本地文件路径>` 弹层播放器,JS 设 `currentTime` 就地跳播——本地场景体验反而最强,亦为 P2 的平台 iframe 内嵌播放铺路

### 9.5 markdown 笔记渲染器【v0.5 新增】

第二个一等渲染器,同时是导出契约的**完备性验收器**——它的证明力来自「只靠文档活着」:

- `scripts/notes.py`,stdlib-only 确定性脚本;**硬规则:输入仅限 `video_index.json` + `frames/`,禁碰 `.work/`**——契约缺字段立刻失败,禁止静默绕过(宿主渲染做不到这一点:它看得见全部中间制品,缺口会被悄悄补齐,验收就失效了)
- `--depth` 控展开层级,与交互点 Length 档位同语义(短→L1 / 中→L2 / 长→L3)
- 产出 `<OUT>/notes.md`:标题层级映射大纲树、要点 summary、evidence 引用(原文 + 时间戳)、配图(`frames/` 相对路径,代理画质)、时间戳跳转链接(`badge_url_template` 填 `t`;本地文件无 URL,时间戳退化为纯文本标注,形态实现期定,§14)
- dedup 标注的消费策略自定(默认全收、标注可见——笔记不受「一帧不上两页」的 slide 版面约束)
- 确定性、可测、可复现、零 token;符合零 pip 依赖政策(§10)

---

## 10. 依赖与预检

### 10.1 依赖清单

| 类别 | 依赖 | 说明 |
|---|---|---|
| 必装二进制 | `ffmpeg` + `ffprobe` | score 遍历/抽帧/去重 rawvideo/边缘密度/blurdetect/tile/clip/音频;所有图像计算以 ffmpeg 为引擎,Python 只处理字节流与文本 |
| 必装二进制 | `yt-dlp` | 代理流/高清流/字幕/chapters/heatmap/弹幕/metadata;仅 CLI 调用永不 import,brew/pipx 安装隔离依赖树 |
| 可选二进制 | `tesseract`(+ `chi_sim`) | OCR 密度打分;缺失自动降级,不阻塞;双平台对等定位下 `chi_sim` 建议随装 |
| ASR·API 家族【v0.4 重构;切片 2 拆双形状】 | OpenAI 兼容端点(两种协议形状) | **transcriptions 形状**(`groq\|openai\|api`):`audio/transcriptions` multipart,verbose_json 原生段级时间戳;**chat 形状**(`mimo\|qwen` 预设,2026-07-11 实测用户端点):`chat/completions` 携带 base64 音频(≤10MB/请求),无原生时间戳,由音频切块层(ffmpeg silencedetect,零 pip)供块级时间戳。预设仅需 key,`ASR_API_BASE`/`ASR_MODEL` 可覆盖任意预设;手写 multipart/json + urllib,零 pip;仅遇无字幕视频时才实际调用。详见切片 2 设计文档 |
| ASR·本地子进程家族【v0.4 重构】 | FunASR(独立 venv,MVP) | `ASR_BACKEND=funasr`:transcribe.py 以 subprocess 调 `FUNASR_VENV` 指定的独立环境(paraformer-zh + VAD + 标点,句级时间戳),零 pip 原则不破;**设备自动选择 CUDA > MPS(Apple Silicon)> CPU,GPU 上失败自动回退 CPU 再试;`FUNASR_DEVICE` 可强制覆盖**(实测 MPS 上 paraformer forward RTF≈0.05,约 CPU 的 2–3 倍);**arm64 / x86_64 Mac 通吃**,中文最优。统一子进程接口:音频入 → 带时间戳 segments JSON 出 |
| ASR·本地槽位(P2) | `mlxwhisper` / `whispercpp` | 走同一子进程接口的预留后端:mlx-whisper **仅 Apple Silicon**(MLX),whisper.cpp 跨平台二进制;SKILL.md 进阶节先给配置方法,P2 进预检 |
| **pip 依赖** | **零** | 纯 stdlib;显式规避 PIL(去重与 contact sheet 均由 ffmpeg 承担)。【v0.5 确认】打包导出(`storyboard.py export`)与笔记渲染器(`notes.py`)同样零新增依赖 |
| 明确排除 | ~~paddleocr~~ ~~PIL/opencv~~ | 违反零 pip 原则 |
| 前置 skill | frontend-slides | 安装要求项(slide 渲染路径;仅出索引文档/笔记时不触发) |

### 10.2 setup.py 预检

`--json` 结构化预检 / `--check` 静默快查 / 幂等安装器 / `~/.config/video2slides/.env`(0600)存 `ASR_BACKEND`、API 家族三元组(`ASR_API_BASE` / `ASR_API_KEY` / `ASR_MODEL`)、`FUNASR_VENV` 与 `SETUP_COMPLETE` 标记【v0.4 重构】。

| Exit | 含义 | 动作 |
|---|---|---|
| 0 | 可运行(含主动选择 `ASR_BACKEND=none` 的 keyless 状态) | 静默继续 |
| 2 | 缺 ffmpeg / yt-dlp | 跑安装器(macOS brew 自动,其余打印命令) |
| 3 | 真首次运行且所配 ASR 后端不可用(API 家族无 key 或端点不通 / funasr venv 缺失 / 本地后端平台 arch 不匹配) | 鼓励配置(groq key,或 `ASR_BACKEND=funasr`+`FUNASR_VENV`),可 `ASR_BACKEND=none`(CLI 别名 `--no-whisper`)继续 |
| 4 | tesseract 缺失 | 仅提示,不阻塞,自动降级 |

**版本检查(不止存在性)**:ffmpeg < 5.1 → 静默关闭 blurdetect,仅用峰后偏移规则;yt-dlp 过旧 → 软提示 `yt-dlp -U`(heatmap 与 B 站支持依赖新版)。

**平台 arch 校验【v0.4 新增】**:本地子进程后端按平台校验——`mlxwhisper` 仅 Apple Silicon(arm64),Intel Mac 配置时预检直接报错并建议 `funasr`(CPU,双 arch 通吃)或 `whispercpp`;API 家族与 arch 无关。

**本地文件输入措辞【v0.4 定稿】**:本地输入无字幕源,预检明确提示"需配置 ASR 后端或 `--transcript` 直喂转写";「有字幕免 API key」的卖点表述仅适用于 URL 输入。

### 10.3 平台专属事项

- **B 站【v0.4 实测修订】**:字幕为平台 AI 字幕轨(`ai-zh`,SRT),**获取必须登录 cookie**;无 cookie 时仅弹幕(XML)轨可得,字幕层回退 ASR。预检说明 `--cookies-from-browser chrome`,并把 cookie 定位为「字幕 + 高分辨率」双开关。分辨率:无 cookie 实测可列 1080p(原「≥720p 需登录」表述基于旧版 yt-dlp),4K 需登录;实际下载可用性实现期验证。无 cookie 时**分析用代理流不受影响**。另实测 **AI 字幕非全覆盖**:存在无 `ai-zh` 轨的 B 站视频(即便登录),此时按无字幕处理走 ASR——B 站的 ASR 需求独立于 cookie 问题存在
- **中文 ASR**:社区默认 Groq whisper-large-v3;中文主场景推荐一行配置切本地 FunASR paraformer-zh(`ASR_BACKEND=funasr`,中文准确率与速度均优、零 API 费用、零代理依赖)

---

## 11. 失败与降级矩阵

| 故障 | 行为 |
|---|---|
| 无字幕且所配 ASR 后端不可用 / `ASR_BACKEND=none` | 帧-only 模式,大纲仅靠视觉信号 + Claude 看帧,明确告知质量受限 |
| ASR 单分块失败 | 跳过该块、transcript 标注缺口,全部失败才报错 |
| chapters / heatmap / 弹幕 / 页边界缺失 | 静默置空,纯 transcript 路径(fail-open) |
| tesseract 缺失 | 边缘密度代理分 |
| scene-score 遍历失败(如单帧/静态视频) | 降级 uniform 抽帧,探针改用缩略图差分兜底;页边界先验随之禁用 |
| 探针分类置信度低 | Claude Read 探针 sheet 仲裁;仍不定按 slide-driven 保守处理,但**不启用页边界 snap**(snap 只在高置信 slide-driven 下开) |
| 引用校验(quote 存在性)不通过 | 打回重生成,超 2 次降级纯文字节点(删 media、保留大纲文字) |
| 跨要点帧重复【v0.5 修订】 | 标注化后不丢数据:重复组打 `dedup_group` 标注,slide 视图取 primary,其余节点该页回退窗内候选次名或转纯文字;「同版式不同内容」误判由宿主目验仲裁改标注(拆组/换 primary),P2 判据升级只换签名算法不动契约 |
| 导出打包 / 契约校验失败【v0.5 新增】 | JSON Schema / quote 复核 / 路径存在性任一不过则**不产出文档**,按 stdout 修复内部制品后重跑 export;`.work/` 制品不受影响 |
| 高清流直链过期 / 拉取失败(定稿懒抓期)【v0.3 新增】 | 重新 fetch 高清流;仍失败降级用代理帧上页,slide 标注质量受限 |
| B 站 cookie 不可用【v0.4 修订】 | 字幕不可得 → 回退 ASR(或帧-only 并告知);定稿帧取无 cookie 可用最高档(实测可列 1080p,下载可用性待验证);分析不受影响 |
| 流程中断(context 耗尽 / 用户打断)【v0.4 新增】 | 重新发起即断点续跑:各层检测 `.work/` 内制品存在且新于上游则跳过(§3) |
| 长视频【v0.4 修订】 | >30min 默认分章生成大纲(§7);代理流架构下媒体成本可控 |

---

## 12. 质量评估(实现期必备)

- **大纲时间覆盖率**:要点时间窗并集 ÷ 视频时长;过低 = 漏内容,过高 = 未压缩
- **帧-要点相关性抽检**:Claude 按索引文档抽样判断帧是否支撑要点
- **引用校验通过率【v0.3 修订】**:quote 存在性校验的拦截率作为大纲 prompt 迭代回归指标
- **【v0.5 新增】契约完备性验收**:`notes.py` 只读导出文档跑通(在线视频 + 本地文件各至少一例);JSON Schema 机械校验纳入回归;自包含检查——打包后移走 `.work/`,slide 的语义输入与笔记渲染仍完整可用
- **【v0.2 新增】去重可视化报告**:frames.py 可选产出 report.html,展示每帧去留与签名距离,肉眼校准阈值(出处:crv dedup report)
- **【v0.5 修订】dedup 标注质量抽检**:标注组的误判率(同版式不同内容被并组)与宿主仲裁改动率进回归指标(替代原「跨要点唯一性检查」——唯一性已下沉为视图策略)
- **【v0.3 新增】页边界 snap 质量抽检**:slide-driven 视频上抽样核对大纲节点边界与真实翻页时刻的偏差,作为 ±3s 容差的回归调参依据
- QA 兜底:产出后对渲染产物做结构抽取核验(每 slide 标题/媒体齐全、无 placeholder 残留;笔记无死链)

---

## 13. MVP 范围与后续路线

**MVP**:单视频源(YouTube / Bilibili / 本地文件,+`--transcript` 逃生门);轴 A 4 类(单段 visual_form);轴 B 全集但风格映射从简;静帧 + screen-recording 的 clip;chapters + heatmap + 弹幕密度 + 页边界四先验;窗口对齐 + 全叶子终选 + 定稿懒抓;scene-score 基底 + 双分辨率架构;三家族 ASR 后端(OpenAI 兼容 API 通用实现 + FunASR 子进程 + none,mlx-whisper/whisper.cpp 留槽位);长视频分章大纲(>30min);断点续跑;本地文件内嵌播放器跳转;**【v0.5 增补】索引文档导出(公开契约)+ 双渲染器(frontend-slides HTML / markdown 笔记)**+ 时间戳跳转。

**实现顺序【v0.4 定稿,v0.5 增补】:垂直切片**——切片 1(带字幕在线视频端到端)、切片 2(ASR 三家族 + 本地文件)、切片 3(长视频分章大纲)均已合入 main。**下一个切片:索引文档升格(2026-07-13 grilling 决议)**,范围:
1. `storyboard.py export` 导出组装 + `schemas/video_index.schema.json` + 机械校验(§6.5)
2. dedup 标注化改造(`storyboard.py dedup` 从删除改标注;SKILL 步骤 5 宿主仲裁改「改标注」;slide 渲染视图级取 primary)(§6、§9)
3. 交互点扩展产出形态选项(§9)
4. `scripts/notes.py` 笔记渲染器(§9.5)
5. SKILL.md 编排更新(步骤 5 后插入打包导出;description 改「索引文档 + 渲染器族」表述)
验收 = §12 契约完备性条目。**P2 跨要点去重判据升级排本切片之后**——标注化先落地,届时只替换签名算法(更细网格 / 边缘密度差 / OCR 文本哈希),数据形状与契约不动,不返工。验收用例沿用 `docs/test-videos.md`(27 源)。

**P2 候选**:visual_form 分段分类(score 曲线粗分段);whiteboard 延时 clip;whiteboard 擦除检测(擦除大峰前取帧,替代机械末帧);嵌入原平台播放器 iframe(带 `t` 参数就地播放,本地内嵌 `<video>` 弹层已为此铺路);实拍演示独立形态;画中画区域检测;多视频 compare 模式;本地 ASR 槽位后端落地(mlx-whisper、whisper.cpp,§10.1);批量/分P 处理;marketplace 上架适配;**跨要点去重判据升级【2026-07-11 验收发现;v0.5 起排在标注化之后】**——16×16 RGB 签名对「同版式不同内容」页(深底 deck/白底文档/黑板/会议网格)分辨力不足,验收与批量试产的误伤率 5/14、9/10、3/5、1/8,现靠 SKILL.md 宿主目验仲裁兜底;候选判据:更细签名网格、边缘密度差、OCR 文本哈希(实测数据见 `docs/test-videos.md` 批量试产结论)

---

## 14. 开放项(实现期确定)

**【v0.4 裁剪】已定初始值,降级为回归调参项**(标注视频集只用于验证,不阻塞实现):

- 页边界 snap:软提示 + ±3s 容差(§7)
- adaptive 选峰:窗口 2s / 倍数 3× / 下限 0.04,即 crv 默认(§8.1)
- cue 锚点窗口后扩:2–5s(§8.1)
- 帧预算:contact sheet 每章 ≤2 张、单视频图片 Read ≤15 次(§8.3)
- RGB 签名判重通道差:**24**(2026-07-11 于验收视频 #13 标定——深底讲义页下初始值 48 过粗,不同页全部误判重;24 下真翻页 0.12–0.43、同页 build ≤0.04,与占比阈值 0.10 分离良好)
- 长视频分章阈值:30min(§7)
- 项目名:video2slides,`/video2slides`(别名 `/v2s`)——已关闭(§4)

**仍开放**:

1. 探针分类的 score 曲线形状阈值——需真实视频集调参(每形态 5–10 个标注视频,切片跑通后补齐)。**【2026-07-11 批量试产修订】数值判据不可独立成立**:三个非 slide 视频(#3 cinematic、#6 录屏、#18 画板)的 plateau/尖峰指标全部落进 slide-driven 判据区间——曲线数值只做初筛,轴 A 定判必须经 probe contact sheet 目验(现行 SKILL.md 机制),P2 可加构图特征(如固定 PiP 头像区域检测)辅助
2. 大纲生成 prompt 的 structured output schema 约束写法(含 `evidence.quote` 字段)
3. 轴 B 体裁 → frontend-slides 风格映射表——v0.4 起风格由此表直接定(§9),为渲染期核心表;有「换风格重渲染」兜底,可先粗后精
4. 长视频(>1h)的章数上限与分批渲染策略细节
5. **【v0.5 新增】命名默认值**:`video_index.json` / `storyboard.py export` / `scripts/notes.py`——实现期可调,以 `schemas/` 文件与 SKILL.md 落地为准
6. **【v0.5 新增】JSON Schema 字段清单落笔**:§6.5.2 为示意结构,逐字段的类型/必选性/枚举随实现定稿并 review
7. **【v0.5 新增】本地视频场景笔记的时间戳形态**(无跳转 URL 时纯文本标注的具体写法)
8. **【v0.5 新增】dedup 标注的仲裁记录形态**(宿主拆组/换 primary 是否留仲裁痕迹字段,供 §12 改动率统计)

---

## 15. 竞品格局(Related Work)

调研时间:2026-07。四梯队划分,每梯队恰缺本项目方案的某一环。

### 梯队一:transcript-only → PPT(最拥挤)

开源:OpenSourceInnovation/project-video-to-ppt(字幕→LLM 摘要→marp)、Sadonim/video2ppt(全 prompt 无代码,mlx-whisper + pptxgenjs 现场生成)。SaaS:Plus AI、SlidesPilot、MagicSlides、SlideGen、Gamma、NoteGPT、Brisk 等。共同盲区:**丢弃画面**,视觉部分需人工补。

### 梯队二:纯视觉 slide extractor(古老、无 LLM)

vid2slides、slide-extractor 系列、SlideXtract 等(2019–2021):场景检测 + OCR → 截图 PDF。只有画面没有语义,无大纲无重组。工程遗产可参考:多帧 MSE 比较 + 噪声自适应等对抗不同压缩源的调参经验(轴 A 探针实现期参考)。

### 梯队三:双模态证据提取器(技术栈最近,活跃竞争区)

- **claude-video**(bradautomates):三引擎抽帧 + fallback、感知去重、字幕优先 + Whisper API、SKILL.md 编排契约。本项目多处设计直接改造自它(MIT,注明出处)
- **claude-real-video / crv**(HUANGCHIHHUNGLeo):v0.2 多项修订的来源。核心可取:scene-score 元数据遍历、单遍复合 select、adaptive 相对阈值、窗口 RGB 去重、contact sheet、dedup report。核心短板:不从 YouTube 拉字幕(URL 场景被迫本地 whisper base)、无先验信号、无形态路由(策略靠用户手动 flag)、PIL 依赖且缺失时去重静默失效、止步 MANIFEST 无制品。商业化方向为拉片分析(Pro),与本项目赛道正交。注:社区热度含较重运营成分,引用其代码思路但不形成依赖
- **treesoop/video_transcription**:帧 + ±30s 音频上下文交给 AI CLI agent 逐帧描述,产出交错时间线;"audio→context→frame" grounding 模式与本项目"Claude 看 top-3 终选"同构
- **transcribe-critic**:多源转录 LLM 仲裁合并;Make 式 DAG + checkpoint 续跑,长视频工程参考(v0.4 断点续跑的先例)

**梯队三全部止步于"喂证据",无一产出可复用制品。**

### 梯队四:最接近的竞品

**Sharayeh YouTube-to-Slides**(SaaS,闭源):转录 + 关键帧配图 + AI 结构化 + chapters 作章节分隔 + 每页时间戳跳回原视频。基本是本项目的 SaaS 版。差异化据点:本项目为开源 skill(可审计/可定制/数据本地)、支持 B 站(弹幕先验独家)、HTML 输出承载 clip 与内嵌播放(其为静态 pptx)、视觉形态路由(其疑似单一策略)、**【v0.5】自包含索引文档契约(其无可复用中间制品)**。

### 结论

"梯队三的双模态证据 + 梯队一的 slide 制品"的连接点在开源世界为空白,本项目卡位于此。证据提取环节将快速同质化(crv 更新频繁且在收敛,已加 transcript.json),护城河在 **video_index 公开契约(自包含、schema 版本化的双模态索引文档)+ 两轴路由 + 渲染质量** 三环节——【v0.5】契约从内部 storyboard 升格为对外交付物后,「梯队三喂证据、我们出契约制品」的差异化进一步坐实。
