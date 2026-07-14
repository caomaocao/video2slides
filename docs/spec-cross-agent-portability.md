# Spec:跨 Agent 平台可移植性(SKILL 宿主无关化)

> 状态:**设计经 grill 定案(2026-07-14),实现未开始**。缺口盘点 → 平台调研 → 拷问式 review 逐层收敛;P0-3(宿主多模态)这根主枝已定案,详见「视觉能力处理」节。规范正文(what)尚未落进 spec 正文,本文件即当前唯一载体。
> **演进轨迹**:①盘点 9 缺口(前瞻 PRD)→ ②三平台(Codex/OpenClaw/Hermes)装载格式实调研(见「平台兼容性矩阵」)→ ③grill 定案视觉能力处理(本轮)。两处关键更正记录在案(诚实标注):**(a)** 原「Codex 无 skill 触发系统」过时——三平台已收敛到同一 `SKILL.md` 标准;**(b)** 原「P0-3 是核心交付物的硬门 / notes 是零视觉可移植默认」不准——**核心 `transcript↔frame` 映射是时间轴构造,零读图;视觉只是幻灯片视图的精修层**。
> 性质:与 spec §10「跨平台预检」**正交**——§10 解 OS/架构维度(macOS·Linux·arm64/x86_64,已实现);本文件解 **agent 宿主平台维度**。

## Problem Statement

现 `SKILL.md` 是 Claude Code 原生格式,把宿主能力(`Read` 图、`AskUserQuestion`)、工作目录(`python scripts/xxx.py` 假设 cwd=skill 根)、跨 skill 依赖(`frontend-slides`)全默认成 Claude Code 的形态。目标是同一 skill 目录在下述矩阵内跑通:

- **宿主平台**:Claude Code / Claude Desktop、Codex、OpenClaw、Hermes(Nous Research;用户口中「Hermar」经调研即此)。
- **OS/架构**:Mac ARM + Linux/Unix x86/ARM(§10 已解)。

**grill 后的核心认知**:
1. **装载/触发已收敛**——三平台共读 agentskills.io `SKILL.md`+frontmatter,按 description 触发。P1-5 基本消解为文档。
2. **核心交付物零视觉**——`transcript↔frame` 索引 = 字幕/ASR 时间戳 + `scene_scores.json`(ffmpeg 一遍算)对齐,**不需要读图**。视觉是幻灯片视图的**精修层**(误并拆组仲裁 / 一页多帧挑关键 / 轴 A 版面权重),增益非硬门。
3. 剩余工作 = 一批到处要的小散文修 + **一处 `storyboard.py` 脚本改** + `setup.py` 探测 + 一张探针资产。**不是纯文档改**(见「范围诚实重述」)。

### 缺口盘点(Gap Inventory,grill 后状态)

| # | 缺口 | grill 后结论 | 状态 |
|---|---|---|---|
| **P0-1** | 裸 `python` vs `python3` | OpenClaw 最小 PATH 实测 `python` 无、`python3` 有;三平台都不替你解决 → 前奏解析 `python3` | **定案** |
| **P0-2** | `scripts/` 相对路径假设 cwd=skill 根 | OpenClaw exec cwd=workspace 非 skill 根;有 `{baseDir}` 令牌 → 前奏解析绝对 `SKILL_DIR` | **定案** |
| **P0-3** | 宿主多模态硬依赖、未声明无降级 | **核心映射时间轴构造、零视觉**;视觉降级由**探针**分流,无视觉走 `peak_score` 时间轴选帧 + 交互点重塑 + 5b/6a/on-deck 标记(详见专节) | **定案(grill)** |
| **P0-4** | 预检漏查 `node`/`deno` | `setup.py:probe()` 增 node/deno 探测,YouTube 缺则提示、本地/B 站 fail-open | **定案** |
| **P1-5** | 非 Claude 无可调用清单 | 前提作废:三平台原生读 SKILL.md、按 description 隐式触发,无需 AGENTS.md 路由 | **降级为文档** |
| **P1-6** | `AskUserQuestion` 专属 | OpenClaw/Hermes 无等价物 → 交互点补 free-text fallback + 无视觉时重塑菜单 | **定案** |
| **P1-7** | `frontend-slides` 跨 skill 依赖 | slides 需 frontend-slides 在场 **且** 宿主有视觉;缺任一 → 走笔记/索引,或 5b 降级渲染 | **收敛** |
| **P2-8** | `--cookies-from-browser` 假设本机 Chrome | 补 `--cookies <file>` fallback | **定案** |
| **P2-9** | 零真机 / 零真平台验证 | 首选 OpenClaw 本机 DeepSeek(天然无视觉)端到端;仍待执行 | **待执行** |

## 平台兼容性矩阵(2026-07-14 调研结论)

> 置信度记号:**◆ on-disk 实证**(最强)· **● 官方文档/源码** · **○ 推断/未证实** · **⚠ 过我知识截止(2026-01),仅 web 佐证,须真机复核**。

| 维度 | Claude Code/Desktop | **Codex** ⚠ | **OpenClaw** ◆(本机 2026.5.12) | **Hermes Agent**(Nous)⚠ |
|---|---|---|---|---|
| skill 格式 | `SKILL.md`+YAML | ● 同标准 agentskills.io | ◆ 同标准(AgentSkills-compatible) | ● 同标准 agentskills.io |
| 装载路径 | skill 目录 | ● `~/.agents/skills/`、repo `.agents/skills`、`/etc/codex/skills` | ◆ `~/.agents/skills/`(个人)、`<ws>/skills`(ClawHub 装) | ● `~/.hermes/skills/<类>/<名>/` |
| 触发 | 按 description | ● 隐式 description + `$skill`/`/skills` | ◆ 按 name/description 注入 + slash | ● slash 命令 + description |
| **读本地图** | ✅ 原生 | ⚠ **不可靠**:agent 自造本地图被 consent 拒/沙箱不稳(#12439);稳路=用户 `--image` 附(破零打断) | ◆ **本机不能**(DeepSeek V4 纯文本、无 vision model);*另装可配视觉* | ⚠ **不能**:仅粘贴/URL,`/attach` 未发布(#9077) |
| 结构化提问 | ✅ AskUserQuestion | ○ `request_user_input`(门控未证实) | ◆ 无(走 `message` 自由文本) | ○ 无(TUI 自由文本) |
| cwd | skill 相关 | ● 项目目录(非 skill 根) | ◆ **workspace 非 skill 根**;有 `{baseDir}` 令牌 | ○ skill 目录相对(未文档化) |
| `python3` | — | ○ 走系统 PATH(裸 python 会挂) | ◆ 最小 PATH 下 `python` 无、`python3` 有 | ○ 未文档化 |
| MCP | ✅ | ● 全支持 | ◆ 有 | ● 有 |
| 安装 | skill 目录 | ● 拖入目录 / plugin 市场 | ◆ 拖入 `~/.agents/skills` / ClawHub | ● `curl … install.sh` + 拖入 |

## 视觉能力处理(2026-07-14 grill 定案)

本节是本轮拷问的产物,是 P0-3 的定案设计。

### 根认知:核心映射不吃视觉,视觉是精修层

`transcript↔frame` 的核心映射是**时间轴 + 信号**构造,**零读图**:字幕(原生或 ASR)每段带 `t_start/t_end` → 大纲节点引某段、带时间窗 → `scene_scores.json`(ffmpeg 一遍算)标出画面稳定点(换页)→ 节点窗内取落定帧。`frames.py:plan_candidates` 的候选 `t` 已是 `峰值 + PEAK_OFFSET(0.7s)` 的**峰后落定帧**(`避糊` 就为此设),候选早已生成;宿主 `Read` 干的只是「在既有候选里挑一张」。

因此视觉的真实作用域收窄到**幻灯片视图的精修**:①同版式误并的拆组仲裁 ②一节点跨多页时挑「关键那张」 ③轴 A 定版面权重。**这三样缺席只降幻灯片质量,不动核心索引与笔记。** —— 这更正了 PRD 原先「P0-3 是核心硬门」「notes 零视觉」两处不准表述。

### 探针:怎么知道自己无视觉(防静默幻觉)

读图能力是「谁在读 SKILL.md」这个 LLM 宿主的属性,`setup.py` 测不出。最恶失败非崩溃,而是**静默幻觉**——纯文本宿主读到「Read 探针 sheet 并分类」会煞有介事编造对图的描述,给出没看图的判定。

**机制(定案)**:前奏里随包一张**已知答案小图**(印一串猜不出的随机词),指令宿主 `Read` 并报出确切文字;**对不上/报不出 → 判无视觉 → 走时间轴路**。一测同时罩住「没能力」(DeepSeek-V4)与「有能力但拒自主读」(Codex consent-gate)。留**用户覆盖**当保险。

**校准**:主流模型基本都多模态(DeepSeek-V4 是例外),故**默认假设有视觉**,探针只是少数配置的安全网 + 静默幻觉的结构性防线;时间轴兜底路保持最简,不镀金。

### 无视觉时的行为(定案)

| 环节 | 行为 |
|---|---|
| **选帧** | 取现成候选,按 `peak_score`(换页强度)排,**不**按含密度的 composite `score`(躲工具栏/水印虚高);无 peak 的 midpoint 候选退窗口位置。产物标「自动按时间轴选取、未经视觉精修」。**无 `frames.py` 改动** |
| **交互点(步骤 6)** | 默认形态从 slides 翻成**笔记**;slides/两者列为「需视觉、默认不可用」+ 原因 |
| **幻灯片(5b)** | 用户**坚持要**就带风险警告照渲(一站式,不赶用户去别处——「迁移文档到别处渲」纸面干净、现实没人做)。准入两条硬约束 ↓ |
| ├ **(6a) 去重** | `storyboard.py dedup --no-vision` 抬合并阈值 → **宁欠勿并**:宁可多张**可见重复页**(用户翻过即可),绝不**静默吞掉**一张不同讲义页 |
| └ **on-deck 标记** | deck 上盖「自动选帧,未经视觉校对」——让下游转发看 deck 的人也知情,把「静默的错」变「看得见的错」 |
| **轴 A** | 保守不 snap;版面权重在 slide 降级下 moot。**笔记/索引完全不 care 轴 A 判得准不准** |

设计原则:视觉不在场时,让错误偏向**可见且无害**的一侧(重复页 > 丢页;显式标记 > 冒充精修)。

## Solution(提议方向,grill 后)

- **A. 调用可移植(P0-1/P0-2)**:`SKILL.md` 顶部运行前奏,一次性解析解释器与 skill 目录:
  ```
  PYBIN="$(command -v python3 || command -v python)"        # Linux/OpenClaw 最小 PATH 只有 python3
  SKILL_DIR="<本 SKILL.md 所在目录绝对路径>"                  # OpenClaw 用 {baseDir} 令牌;其余平台按 skill 已知位置解析
  # 之后一律:$PYBIN "$SKILL_DIR/scripts/xxx.py" --work <绝对路径>
  ```
- **B. 宿主能力契约(P0-3/P0-4)**:探针自测段(前奏)+ `description`/前奏声明多模态需求 + 无视觉行为(见专节)+ `setup.py` 增 node/deno 探测。
- **C. 交互 fallback(P1-6)**:交互点补 free-text 措辞 + 无视觉时重塑菜单(默认笔记、slides 带注/覆盖)。
- **D. 依赖 + 形态(P1-5/P1-7/P2-8/P2-9)**:笔记/索引为零外部 skill 的可移植形态;slides 需 frontend-slides 在场且宿主有视觉(否则 5b 降级);各平台装载路径速查;frontmatter 守 agentskills.io 公共子集(`name`/`description` 单行键)、平台门控进 `metadata.<平台>`;B 站 `--cookies <file>` fallback;OpenClaw 本机 DeepSeek 端到端冒烟。

## User Stories

1. Linux/OpenClaw 宿主想让第一条命令就用 `python3`,以便不因裸 `python` 缺失崩。
2. Codex/OpenClaw 宿主想从 `{baseDir}`/已知位置解析绝对 `SKILL_DIR`,以便 cwd≠skill 根时 validate 不误报。
3. 无视觉宿主(DeepSeek 纯文本 / Codex 拒自主读)想被探针如实分流走时间轴路,以便**不静默幻觉**出没看图的判定。
4. 用户想在预检期就知道缺 node/deno 会让 YouTube 取流失败,以便先装好。
5. 三平台宿主(已原生读 SKILL.md)想靠 description 隐式触发,以便丢个视频 URL 即命中,无需铺 AGENTS.md。
6. 无 AskUserQuestion 的宿主想有 free-text 提问 fallback,以便唯一交互点在任何平台完成。
7. 无视觉宿主上的用户想要**一站式**产出(哪怕 slide 粗糙),而非被赶去别的宿主渲染。
8. 转发 deck 的下游读者想从 deck 上的标记知道「这些帧未经视觉校对」,以便不把粗糙帧当权威。
9. 用户想在无视觉渲 slide 时,宁可见到重复页也别被静默吞掉不同讲义页(6a),以便信息不丢。
10. headless 宿主想用 `--cookies <file>` 取 B 站字幕,以便无本机 Chrome 也工作。
11. 跨平台用户想让同一 skill 目录在 Mac ARM 与 Linux x86/ARM、四家宿主间迁移即用。
12. 维护者想让 frontmatter 守 agentskills.io 公共子集、平台门控进 `metadata.<平台>`,以便一份 SKILL.md 四家都被正确解析。

## Implementation Decisions

- **无脑决(纯散文 + 一处 setup.py)**:P0-1(`python3` 前奏)、P0-2(`SKILL_DIR`/`{baseDir}` 前奏)、P0-4(node/deno 探测)、P1-6(free-text fallback)。
- **P1-5:文档化而非新机制**——三平台共读 SKILL.md,补装载路径速查 + frontmatter 公共子集约束即可。
- **P0-3(grill 定案)**:核心映射时间轴、零视觉;探针分流;无视觉走 `peak_score` 时间轴选帧 + 交互点重塑 + 5b 睁眼覆盖 + 6a 宁欠勿并 + on-deck 标记。**详见「视觉能力处理」节。**
- **已否决**:①OCR 文本为中心的语义恢复(投入产出不划算,tesseract 保持可选、不升准硬依赖);②「产出文档迁移到别处渲」作为无视觉 slide 的兜底(现实没人做,用户要一站式)。
- **范围诚实重述(改写 PRD「改-散文优先、不动脚本逻辑」)**:本改造**不是纯文档改**。真实范围 = **散文**(SKILL.md 运行前奏 / 探针自测段 / 交互 fallback / 无视觉选帧与幻灯片话术 / 各平台装载速查)+ **`storyboard.py` 加 `--no-vision` 旗**(dedup 抬阈值→宁欠勿并)+ **`setup.py` 加 node/deno 探测** + **一张 bundled 探针图资产** + **渲染侧 on-deck 标记指令**。守住的红线不变:不改 `video_index.json` 契约、不动 schema、不加运行期 pip 依赖。

## Testing Decisions

- **多为编排契约 + 宿主能力假设的改动,验证在外部行为层而非 mock**:
  - **P0-1/P0-2/P0-4**:真 Linux(Ubuntu/Fedora)+ OpenClaw 网关最小 PATH 下跑通前奏;`setup.py` node/deno 分支 monkeypatch 单测(与现有 Linux 分支同法),真机冒烟不可省。
  - **`storyboard.py --no-vision`**:纯确定性,可单测——判据取一对 diff 落在 `[DUP_RATIO_NO_VISION, DUP_RATIO)`(0.05–0.10)之间的帧:正常模式合并成一组、`--no-vision` **不合并**(落 `dedup_group` 的多成员重复组更少、单帧簇更多——「宁欠勿并」)。
  - **探针**:构造纯文本宿主路径(OpenClaw 本机 DeepSeek 即天然此环境),核对探针如实判无视觉、不产幻觉分类。
- **首要端到端验收(P2-9)**:**OpenClaw 本机 DeepSeek(天然无视觉)跑「带字幕视频 → 探针失败 → 笔记 + 无视觉 slide」**——一把验完探针分流、`peak_score` 时间轴选帧、6a 宁欠勿并、on-deck 标记四件事。
- **回归判据**:改动**不得放松**已有硬规则——尤其「数值判据不可独立成立 / 以目验为准」(`SKILL.md:51`);无视觉产物必须**如实标注降级**,不得冒充精修。
- **Prior art**:测试源登记 `docs/test-videos.md`;本维度新增「平台矩阵冒烟」结论(OS×宿主 实跑组合与结果)同源沉淀。

## Out of Scope

- 重写 `video_index.json` 契约或 schema 以适配某平台(YAGNI + 守版本化边界)。
- 运行期 pip 依赖 / 跨平台抽象层(违反零 pip 红线)。
- OCR 文本语义恢复;tesseract 升为准硬依赖(**本轮明确否决**,保持可选)。
- 原生 Windows(§10 已硬拦;WSL2 走 Linux 路径)。
- 为 Codex 终端读图 / Hermes `/attach` 缺陷做上游修复(非本仓库范围;只「声明需求 + 探针分流 + 降级」)。
- 把 skill 改造成自拨 API 独立服务(违反 §1.2 非目标)。
- 「产出文档迁移到别处渲染」作为无视觉 slide 的正式兜底(**本轮否决**,用户要一站式;文档可迁移仍是天然属性,只是不当作产品路径卖)。

## Further Notes

- **grill 决策链(why,供后人挡回重议)**:核心映射零视觉 ← 时间戳+scene score 构造、候选已含峰后落定帧;探针选已知答案图 ← 唯一结构性掐死静默幻觉;`peak_score` 而非 composite score ← composite 含密度、正是工具栏虚高源;5b 睁眼覆盖 ← 「迁移别处渲」现实没人做、用户要一站式;6a 宁欠勿并 ← 可见重复页无害、静默丢页有害;D1 脚本加旗 ← 抬阈值是确定性决策、该待确定性层,不该塞进(还无视觉的)宿主散文。
- **调研可信度分层(诚实标注)**:OpenClaw = ◆ on-disk 实证(本机 2026.5.12,读图缺失是此 DeepSeek 配置的事实,另装可配视觉,故 skill 必须**声明**需求而非假设);Codex = ⚠ 过知识截止(skills 系统 ~2026-03、读图行为 Feb–May 2026 快速变动,须对运行版本复核);Hermes = ⚠ 过知识截止 + web-only(即 Nous Research 的 Hermes Agent,中高置信为真,须真机 smoke test)。
- **与 §10 的关系**:§10 解 OS 维度且已合入;本文件是并列第二维度。建议将来在 spec §13(后续路线)或 §10.3(平台专属事项)加前瞻指针指向本文件,但**未实现前不写进主 spec 决策日志**(日志只承载已决变更)。
- **落地次序建议**:①无脑散文批(P0-1/2/4 + P1-6 + 平台装载速查)先清,立即消除 Linux/OpenClaw 硬崩;②探针资产 + 自测段;③`storyboard.py --no-vision`(带单测)+ 无视觉选帧/5b/6a/标记;④OpenClaw DeepSeek 端到端验收。
- **协同**:`notes.py` 脚手架 i18n(既有 backlog P2)与「笔记是可移植默认」正向协同——非 Claude 平台优先走笔记路径时,硬编码中文缺陷更常暴露,可并档处理。
