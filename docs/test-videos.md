# 测试视频集(v3)

> 来源:用户提供,2026-07-10 第一批 10 源 + 第二批 5 源;2026-07-11 第三批 8 源(补形态/体裁缺口)+ 第四批 3 源(会议记录)。在线视频元数据已用 yt-dlp 2026.07.04 逐个核实(字幕轨/时长/chapters/heatmap);本地文件已用 ffprobe 核实。
> 用途:垂直切片验收 + 各管线路径的回归用例。spec §13 的"每形态 5–10 个标注视频"回归集以此为起点扩充。

## 清单(已核实)

| # | 源 | 标题 / 作者 | 时长 | 转写来源 | chapters | 热度信号 | 预期轴A(画面形态) | 预期轴B(体裁) |
|---|---|---|---|---|---|---|---|---|
| 1 | [YT eKjMxYA4xak](https://www.youtube.com/watch?v=eKjMxYA4xak) | 高盛研报解读 / 老厉害 | 14:53 | **无任何字幕轨** → ASR | 0 | 无 | slide-driven(讲义) | 资讯/解读 |
| 2 | [YT P-dleHSJYvg](https://www.youtube.com/watch?v=P-dleHSJYvg) | 勇闯美国最穷州府 / 街头小小小霸王 | 12:43 | **无任何字幕轨** → ASR | 0 | heatmap ✅ | cinematic(vlog) | vlog/生活 |
| 3 | [YT TUmEcL3Feo0](https://www.youtube.com/watch?v=TUmEcL3Feo0) | 朝鲜游记 / Harry Jaggard | 27:13 | 手动字幕 5 种(含 zh)+ 自动 en/zh | **11** | heatmap ✅ | cinematic | 游记(英文,`--lang` 用例) |
| 4 | [YT 6Hbd25qDuGs](https://www.youtube.com/watch?v=6Hbd25qDuGs) | 王局拍案 / 王志安 | **36:53** | 手动 en / zh-Hans / zh-Hant | 0 | 无 | talking-head | 演讲/解读 |
| 5 | [B BV1zgVA6gE3x](https://www.bilibili.com/video/BV1zgVA6gE3x) | 法拉利纯电 Luce 评测 / 高转青年-栗子 | 12:46 | ai-zh(**需 cookie**)+ 弹幕;另有 ai-en/es/ar | 0 | danmaku | cinematic + 实拍演示 | 评测/对比 |
| 6 | [B BV12TN56aEk4](https://www.bilibili.com/video/BV12TN56aEk4) | GPT-5.6 Sol 实测 / 程序员阿江-Relakkes | **5:54** | ai-zh(**需 cookie**)+ 弹幕 | **9** | danmaku | screen-recording(+头像画中画) | 评测 |
| 7 | [B BV1EM7t6pEcu](https://www.bilibili.com/video/BV1EM7t6pEcu) | 金沙扩建(The B1M 搬运)/ 黑纹白斑马 | 12:17 | ai-zh(**需 cookie**,已确认)+ 弹幕 | 0 | danmaku | cinematic | 纪录片 |
| 8 | [B BV1BZLQ6JENm](https://www.bilibili.com/video/BV1BZLQ6JENm) | 世界杯现场 / 杰克小兔 | 18:13 | **无 ai 轨(已确认)→ ASR** | **5** | danmaku | cinematic(游记) | 游记 |
| 9 | 本地 ×3:`…/local-channel/videos/` | 杭商故事(视频号短视频) | 8:24 / 9:45 / 8:32 | 无 → ASR 或 `--transcript` | — | — | talking-head/实拍(待探针) | 资讯/人物故事 |
| 10 | 本地 ×1:`…/local-channel/lives/` | 视频号直播回放(标题空) | **41:11** | 无 → ASR | — | — | talking-head(待探针) | 访谈/直播 |
| 11 | [B BV1k44LzPEhU](https://www.bilibili.com/video/BV1k44LzPEhU)(**187P 分 P 合集**,推荐 p02) | 尚硅谷 NLP 零基础教程 | p01 4:37 / p02 11:59 | ai-zh(**需 cookie**)+ 弹幕 | 每 P 无 | danmaku | **screen-recording(讲义文档录屏,验收实测修正)** | 课程 |
| 12 | [YT TCH_1BHY58I](https://www.youtube.com/watch?v=TCH_1BHY58I) | Building makemore Part 2: MLP / Andrej Karpathy | **75:39** | 自动 en(+机翻 zh) | **19** | heatmap ✅ | screen-recording(coding) | 课程 |
| 13 | [YT QNiaoD5RxPA](https://www.youtube.com/watch?v=QNiaoD5RxPA) | Token 到底是什么 / 马克的技术工作坊 | 10:31 | **手动 zh-Hans/zh-Hant** | **5** | heatmap ✅ | **slide-driven** | 课程/科普 |
| 14 | [YT tamj4B7OALc](https://www.youtube.com/watch?v=tamj4B7OALc) | Lecture 01 Course Overview / Abhinav Maurya | **64:13** | 自动 en | 0 | 无 | **slide-driven** | 课程 |
| 15 | [B BV1VC7g6vE9f](https://www.bilibili.com/video/BV1VC7g6vE9f) | Vibe Coding 是什么 / 隔壁的程序员老王 | 12:26 | **无 ai-zh(实测,含 cookie)** → ASR | 0 | danmaku | slide/talking 混合(待探针) | 科普/评测 |
| 16 | [B BV13AmpBiE2o](https://www.bilibili.com/video/BV13AmpBiE2o) | 朱啸虎访谈(第三次)/ 张小珺商业访谈录 | **46:26** | ai-zh(**需 cookie**;另有 ai-en/ja/es/pt/ar 共 6 语)+ 弹幕 | 0 | danmaku | **talking-head(双人 A-B-A 切换)** | 访谈/播客 |
| 17 | [B BV1DK4y1n7J8](https://www.bilibili.com/video/BV1DK4y1n7J8)(**85P 分 P**,推荐 p01) | 可汗学院统计学 | p01 4:02 | ai-en/ai-zh(**需 cookie**)+ 弹幕 | 每 P 无 | danmaku | **whiteboard(手写,640×360 低清源)** | 课程 |
| 18 | [B BV1YG411p7BA](https://www.bilibili.com/video/BV1YG411p7BA) | 哈希表/Leetcode 242 / 代码随想录 | 13:23 | ai-zh(**需 cookie**)+ 弹幕 | 0 | danmaku | **whiteboard/画板讲题** | 课程 |
| 19 | [B BV1a5QRYCE5j](https://www.bilibili.com/video/BV1a5QRYCE5j) | 黄仁勋 GTC 2025 主题演讲 / NVIDIA | **131:47** | ai-zh(**需 cookie**)+ 弹幕 | 0 | danmaku | **分段(开场实拍→keynote slide)**,4K 源 | 演讲/分享 |
| 20 | [B BV1xa411T7f4](https://www.bilibili.com/video/BV1xa411T7f4) | WWDC 2010(iPhone4 发布会) | **112:24** | **无 ai 轨 → ASR(英文)**;画面烧录中英字幕 | 0 | danmaku | **分段(keynote slide + demo)** | 演讲/分享 |
| 21 | [B BV1j3jd6cEtp](https://www.bilibili.com/video/BV1j3jd6cEtp) | 红箭9 反坦克导弹 / 杨叔洞察 | 2:44 | 无 ai 轨 → ASR | 0 | danmaku | **竖屏 1920×3414** 实拍解说 | 资讯/解读 |
| 22 | [B BV1eXqMBzEDD](https://www.bilibili.com/video/BV1eXqMBzEDD) | Dota 辉耀英雄盘点 / Dota情报站 | 2:56 | 无 ai 轨 → ASR | 0 | danmaku | **竖屏 1080×1920** 游戏录屏 | 评测/盘点 |
| 23 | [YT shorts f7bJsbxoLg8](https://www.youtube.com/shorts/f7bJsbxoLg8) | 摇杆开关改造 Short | **0:18** | 无字幕 → ASR | 0 | 无 | **竖屏 1080×1440,极短** | vlog/生活 |
| 24 | [B BV1Wa4y1j7e3](https://www.bilibili.com/video/BV1Wa4y1j7e3) | 腾讯会议录屏(蓝江讲座) | **115:03** | **无 ai 轨 → ASR(中文)** | 0 | danmaku | 会议录屏(1920×948) | **会议记录** |
| 25 | [B BV11S59zUEH2](https://www.bilibili.com/video/BV11S59zUEH2) | 5min 小组会议英文原声 / 听力酵父 | 5:17 | ai-zh(**需 cookie**,英文原声)+ 弹幕 | 0 | danmaku | 会议录屏(短) | **会议记录** |
| 26 | [B BV1hezaY7EKq](https://www.bilibili.com/video/BV1hezaY7EKq) | 1128 会议录屏 | **41:30** | ai-zh(**需 cookie**)+ 弹幕 | 0 | danmaku | slide-driven(共享屏幕 PPT 为主,试产实判) | **演讲/汇报(试产纠偏,原判会议记录)** |
| 27 | 本地 `live_show.mp4`(用户提供,无 sidecar) | 秀场直播实录 | 3:30 | 无字幕 → FunASR | 0 | 无 | talking-head(**竖屏 248×480**,直播 UI 常驻) | **直播实录/秀场(新类目,2026-07-12 建)** |

本地文件补充:横屏,分辨率 1280×720 / 1024×576 / 960×544;**每个视频带同名 `.json` sidecar**(title、作者、时长、宽高、封面等)——`fetch.py` 本地路径应优先读取 sidecar 作 metadata,无需要求用户手填标题。

## 核实中发现的事实(影响 spec,已同步修订 v0.4)

1. **B 站字幕 = AI 字幕轨(`ai-zh`,SRT),必须登录 cookie 才可获取**;无 cookie 时 yt-dlp 只能看到弹幕(XML)轨。「有字幕免配置」对 B 站不成立:B 站 happy path = `--cookies-from-browser chrome`(免 key 但需登录态)或回退 ASR。→ spec §1.1、§10.3、§11 已修订
2. **中文 YouTube 频道普遍没有自动字幕轨**(#1、#2 连 auto captions 都为 0)。ASR 路径不是边缘 fallback,是中文场景的主干之一
3. **B 站无 cookie 实测可列到 1080p**(cookie 后解锁 2160/4K)——spec 原表述「≥720p 需登录」基于旧版 yt-dlp,实际下载可用性待实现期验证
4. **烧录字幕是信号层考验点(实跑细化 2026-07-12)**:底部字幕条逐句变化给 scene-score 叠加持续小抖动。**但抬不抬尖峰取决于形态**——#1 funasr(PDF 慢滚讲义)实测烧录字幕**未**抬尖峰(内容靠慢滚变化、非硬切);#9b(talking-head 访谈烧录字幕)实测**会**抬小尖峰(锁定机位下 caption-text 变化即 scene delta),使 talking-head 数值落入 slide-driven 带。两种形态都靠探针 sheet 目验纠偏。候选对策:探针阶段 crop 掉底部 ~15% 再算 score;或目视仲裁
5. **B 站 AI 字幕非全覆盖**:#15 即便带 cookie 也只有弹幕轨——存在无字幕轨的 B 站视频,ASR 需求独立于 cookie 问题存在
6. **分 P 合集必须带 `?p=n` 定 P**:#11 是 187P 合集,不带 p 参数时 yt-dlp 逐 P 枚举 metadata(实测直接超时)。`fetch.py` 实现要点:先归一化 URL(缺省补 `p=1`)再调 yt-dlp
7. **B 站 AI 字幕多语覆盖不均**:#16 有 6 语种(ai-zh/en/ja/es/pt/ar)、#5 四语、#6/#11 仅 zh、#15/#20-22 为零——疑与 up 主设置或视频体量相关,fetch 的轨选择优先级(视频语言精确匹配)已覆盖此差异
8. **静态封面播客【设计决议 2026-07-11】**:无需专门测试视频——scene-score 全平时直接取首帧作装饰帧 + 纯 transcript 大纲(比 spec §11 的 uniform 抽帧更简单,按 talking-head 文字版式渲染)。实现降级矩阵时并入 §11 该行为

## 覆盖矩阵(管线路径 → 用例)

| 管线路径 | 用例 |
|---|---|
| 字幕直取(YouTube 手动) | #3、#4、**#13** |
| 字幕直取(YouTube 自动 en) | #12、#14 |
| 字幕直取(B 站 ai-zh + cookie) | #5、#6、**#11**(#7、#8 待确认) |
| ASR·funasr(本地) | #1、#9(3支)、#27(实跑✅) |
| ASR·chat 家族(qwen/mimo) | #21、#22(竖屏)、#2、#8、#15(实跑✅,长/横屏扩覆盖) |
| ASR·transcriptions 家族(groq/openai/api) | 预设就位,尚无真跑 |
| ~~`--transcript` 逃生门~~ | **未实现(P2)**——该 flag 不存在,勿在指引中引用 |
| chapters 先验 | #3(11)、#6(9)、#8(5)、#12(19)、#13(5) |
| heatmap 先验 | #2、#3、#12、#13 |
| 弹幕密度先验 | #5–#8、#11、#15 |
| 页边界先验(slide-driven) | #1、#11、#13、#14 |
| >30min 分章·有 chapters | #12(75min、19 章) |
| >30min 分章·无 chapters(页边界/均分兜底) | #4、#10、#14 |
| B 站分 P 规则(`?p=n`) | #11 |
| 本地文件(代理流降采样、内嵌播放器跳转、sidecar 元数据) | #9、#10 |
| `--lang` 覆盖(英文视频→中文 slide) | #3、#12、#14 |
| clip 主力(screen-recording) | #6、#12 |
| 画中画(归并整帧处理) | #6(头像) |
| 访谈/播客(双人 A-B-A 切换,滑窗去重对抗场景) | **#16** |
| whiteboard 手写(末帧规则 + adaptive 选峰) | **#17、#18** |
| 分段 visual_form(演讲:实拍开场→slide 正片) | **#19、#20** |
| >1h 超长(分章 + context 压力) | **#19(132min)、#20(112min)** |
| 竖屏渲染版式(9:16 及更窄) | **#21、#22、#23** |
| 极短视频(<30s,大纲语义退化边界) | **#23** |
| 烧录字幕噪声(探针抗性) | #1、#2、**#20** |
| 低清源(640×360,代理流≈原流) | **#17** |
| 会议记录体裁(短/中/超长无字幕梯度) | **#25(5min)、#26(41min)、#24(115min·ASR)** |

## 批量试产结论(2026-07-11,8 源并行)

字幕就绪且 ≤30min 的 8 源由 subagent 各自照 SKILL.md 全流程试产(粒度统一中档):7 份 deck 出品、1 份按规矩止于取流(#8 无字幕轨)。验证了 SKILL.md 可被非作者 Claude 独立执行。逐片发现:

1. **whiteboard 末帧规则缺失的实锤(#17)**:三页板书全拍在"写到一半"(Mean 公式无结果、排序排一半、mode 刚起笔)——spec §8.1 末帧规则进下切片优先级
2. **探针数值判据不可独立成立(#3/#6/#18)**:三个非 slide 视频的曲线指标全部落进 slide-driven 判据区间(plateau 0.98±、尖峰 1.9–5.7/min),全靠 probe sheet 目验纠正——§14 开放项 1 需加入构图特征,数值只做初筛
3. **字幕轨选择两处真 bug(已修 ade8d0e)**:en-US 视频 manual 层无 en 时兜底取字典序第一(阿拉伯语);多语 ai 轨无视频语言时同样字典序兜底——改为语言匹配跨层优先 + ai-zh 启发式兜底
4. **边缘密度打分的语义盲区(#18)**:插播的网页截图比黑板内容"边缘更忙"得分更高,需宿主目验纠偏——tesseract 装上会缓解
5. **英音 × ai-zh 机翻噪声(#25)**:CloudBees→"云珠子"级别的错译进 transcript;英文内容应优先英文轨(修复 3 已顺带解决)
6. **dedup 误伤延续到新形态**:黑板底(#17,3/5)、会议网格底(#25,1/8)——同底色共享背景的判据缺陷跨形态成立,P2 换判据的优先级再次上调

## 中长视频补跑结论(2026-07-11,#4/#16/#26,手工分章)

三个 37–47min 视频由 subagent 手工分章(spec §7 宿主流程)全流程出品,transcript 分片通读 944/1763/854 段。发现:

1. **工具限位(三次复现,分章机制设计的硬需求)**:`frames.py --candidates` 的 sheet 预算按 `priors.json.chapters` 分桶——无原生 chapters 时全部叶子挤进单桶,三次分别挤出 10/11/若干叶子,靠 dropped_node_ids 兜底路径(candidates.json 按分直选)救回。分章机制落地时必须:手工/自动章界回写 priors.chapters,或改为按 storyboard 的 level-1 节点分桶(后者更优,outline 恒存在)
2. **边缘密度打分盲区第三次复现(#26 三例)**:PPT 编辑器界面/水印页/空白过渡获最高分——已把"对最高分候选保持怀疑"写进 SKILL.md 终选步骤
3. **A-B-A 双人场景 dedup 首验正确(#16)**:替换 2 降级 3 均为真重复(机位构图恒定),纯文字金句页成为合理节奏;字幕轨兜底修复回归通过(六语轨精准选中 ai-zh)
4. **手工分章的真实成本(#4)**:时间戳↔语义边界核对是纯体力活且易偏(实际发生候选帧落 A 窗内容属 B 的编辑插入镜头);944–1763 段需 4–6 次分片通读——分章机制自动化的价值锚点
5. **大纲压缩比参考(#26)**:41.5min/854 段 → 29 叶/16 页 ≈ 29:1;开场铺垫占 42% 时长但信息密度远低于核心章——"每 10 分钟 6–10 叶"对讲座适用,但需按信息密度非时长均分
6. **轴 B 需内容定判非画面定判(#26)**:会议录屏画面 ≠ 会议记录体裁,通篇单人汇报应判演讲/分享——subagent 自主纠偏成功

## 垂直切片验收(定稿)

第二批已补齐「自带字幕 + slide-driven」组合,恢复 spec 原验收口径:

- **YouTube 切片主验收:#13(Token 讲解)**——slide-driven + 手动中文字幕 + 5 chapters + heatmap,10:31 体量适中,先验全齐
- **B 站切片主验收:#11 p02(尚硅谷 NLP 课程概述)**——slide-driven + ai-zh 字幕,11:59,顺带验证分 P 规则与 cookie 流程
- 切片后的首批回归:#6(screen-recording + chapters + clip 主力)、#3(cinematic + 先验最全)、#1(slide-driven 无字幕 + FunASR,验 ASR 路径)

## live show 新类型试产(2026-07-12,#27)

- **deck**:`~/Desktop/video2slides/liveshow_20260712/index.html`,8 页,Split Pastel(新类目「直播实录/秀场」暂与 vlog/生活 同映射,理由:同属镜头前非结构化娱乐向内容;SKILL.md 已建类目)
- **数值判据盲区再实证**:curve_stats(plateau_ratio 0.942 / spikes_per_min 0.57)完全落在 slide-driven 数值带内,目验实为 talking-head+弹幕/礼物 UI——「探针 sheet 目验定谳」规则已写入 SKILL.md 步骤 3
- **FunASR 噪声上限**:清唱/多人声交叠段基本不可读(66 段/85s 转完),quote 保原文照录;秀场类大纲主要靠可读段+画面,属该类型固有约束
- **finalize 语义边界**:源仅 248×480 时定稿与代理同分辨率,6/6 成功 0 降级但无增益——低清源版面策略为小图点缀、不硬放大
- **移交 frontend-slides**:`.slide` 派生类上覆盖 `position` 会击穿固定舞台堆叠(与已知 `display` 坑同源,该 skill 文档仅警示了 display)——待移交其坑位清单
- **QA 缺口**:claude-in-chrome 拒绝 `file://` 导航,本地弹层「真实双击打开可跳播」未能自动化闭环(http.server 代测被跨源策略假阳性拦截),需真人双击复验

## 切片 2 解锁批试产(2026-07-12,6 源并行,全部出品)

切片 2 落地后,ASR 路径解锁的 6 个「无字幕→ASR」源并行试产,全部出 deck(实跑覆盖至 23/27)。ASR 分配:funasr 跑轻量本地/极短(#23/#9b/#9c),chat 家族跑在线长/横屏(qwen #2/#15、mimo #8),兼顾本地 CPU 负载与 API 覆盖扩展。

| # | deck | 页/风格 | ASR | visual_form(目验) |
|---|---|---|---|---|
| #2 勇闯最穷州府 | poorstate_20260712 | 11 / Split Pastel | qwen 17块0失败83s | cinematic |
| #8 世界杯现场 | worldcup_20260711 | 12 / Split Pastel | mimo 24块0失败65s | cinematic |
| #15 Vibe Coding | vibecoding_20260712 | 10 / Notebook Tabs | qwen 17块0失败47s | talking-head(动画讲解) |
| #23 摇杆改造Short | joystick_20260712 | 5 / (竖屏) | funasr 9段28s | cinematic |
| #9b 松研科技 | songyan_20260712 | 10 / Paper&Ink | funasr 281段74s | talking-head |
| #9c 从身价上亿 | fuzhai_20260712 | 9 / Paper&Ink | funasr 271段 | talking-head |

**发现(逐条)**:

1. **【脚本 bug·待修】fetch.py `normalize_url()` 不认 YouTube Shorts `/shorts/<id>` 路径**(#23):支持的输入类型却 ValueError 退出,已就地换 `watch?v=` canonical 绕过。建议增 `/shorts/` 识别分支(小改+可测)
2. **【脚本算法·2 次独立确认】frames.py 候选头部聚簇**(#8、#2):非 slide-driven + 块级时间戳下叶子窗口宽(100–200s),`plan_candidates` 仅 scene-peak 产候选、`cands[:cap]` 按时序头切 6 个 → 候选全聚窗口**前 15s**,后半段无帧覆盖(#8 3.1 窗341–476候选仅338–356;#2 3.1 达135s后半段邦联战旗/议会史无候选)。宿主被迫跨 node 借帧或改配。建议非 slide-driven/宽窗口按**均匀采样**取候选。触 spec §8,切片 3/P2 料
3. **【判据·再实证】RGB dedup 在 talking-head/访谈类高误判**:#15 动画讲解 **4/8=50%(迄今最高)**、#9c 5/8、#9b 1/8,均同背景同机位致 16×16 签名读作近重复,宿主复核全恢复。去重判据升级应**显式点名** talking-head/访谈类为高 FP 场景(不止"同版式讲义")
4. **【visual_form 边界·P2】动画信息图讲解**(#15):卡通旁白+渐进图表+零硬切,数值指纹=talking-head(全程平曲线),实为**承载内容的 slide-driven** 素材。应覆写为信息主体大图版式(代理已正确处理),但"全程低"曲线≠真装饰性 talking-head——现有 whiteboard/录屏/实拍合并规则未覆盖此形态
5. **【规则复现·扩展形态】块级时间戳窗口微调对 cinematic 同样需要**(#8 2.3、#2 两处):qwen/mimo 45s 块级预扩张系统性把最佳帧推到字面窗外,按 SKILL.md 规则微调相邻叶子边界回调即可(非仅访谈类)
6. **【文档·::first-letter 坑扩展】**(#9c):首字放大坑不止阿拉伯数字,**纯数字类汉字(一/二/三/十)**同样糊(细笔画无字身,"一九九八年"→孤立横杠)。SKILL.md 指引应从"不以数字开头"推广到"不以数字或数字类汉字开头"
7. **【鲁棒性·印证终审】mimo 后台转写疑网络挂起**(#8):首次挂后台 20+ 分钟 0%CPU 0 输出(疑单块 urlopen 挂起、300s×重试拖死),前台重跑 65s 净完成——补紧 HTTP 超时的必要性再证(呼应切片 2 终审 Important #1)
8. **【frontend-slides 坑·复现】**:官方 `export-pdf.sh` 与双 class(active+visible)+transition-delay stagger 不兼容(#2、#22),PDF 定格在 opacity=0 假"消失";`.deco-dot` 一类复用两种定位场景 absolute 脱流叠一处(#23)——均待移交 frontend-slides 坑位清单
9. **【ASR 校正技巧】**(#15):用抽出帧的屏幕图文交叉核对转写,逮到 "Mythos→Mistral"(把 Claude 模型层级误听成竞品)等看似合理实为噪声的错译

## 待办

- [x] ~~#7、#8 的 ai-zh 轨确认~~ → 批量试产落定:#7 有(312 段),#8 无(归 ASR 组)
- [ ] B 站无 cookie 的 1080p 实际下载可用性验证(影响 §10.3 降级表述)
- [x] ~~补充 slide-driven + 自带字幕用例~~ → 第二批已补(#11、#13、#14)
- [x] ~~补充 访谈/whiteboard/真演讲/竖屏 用例~~ → 第三批已补(#16–#23)
- [x] ~~静态封面播客样本~~ → 设计决议:无需样本,首帧 + transcript(事实 8)
- [x] ~~会议记录体裁~~ → 第四批已补(#24–#26,短/中/超长梯度)——**覆盖矩阵至此无已知缺口**
- [ ] 每形态扩充到 5–10 个,作为探针阈值调参的标注集(spec §14 仍开放项 1;当前确认数:slide 3-4 / 录屏 3 / talking-head 6 / cinematic 7 / whiteboard 2 / 分段 2)
- [x] ~~切片 2 ASR 路径实跑覆盖~~ → 解锁批已补(#2/#8/#15/#23/#9b/#9c,2026-07-12),**实跑覆盖 23/27**
- [ ] **实跑剩余 6 支长视频组(#10 41min / #12 75min / #14 64min / #19 132min / #20 112min / #24 115min)**——全部 >30min,卡在分章机制,即切片 3 的用例锚点
- [ ] 两个可改脚本项:fetch.py `/shorts/` 识别(小 bug)、frames.py 非 slide-driven 宽窗口候选均匀采样(2 次确认,触 spec §8)

## 切片 4 首例实跑(2026-07-13,#13,feat/slice4-video-index)

#13 全新目录按 v0.5 新编排全流程实跑(dedup 标注 → export → 交互三问 → notes + slides 双渲染),产出 `~/Desktop/video2slides/token_slice4_20260713/`:`video_index.json`(schema 1.0.0,11 帧资产)+ `notes.md`(depth 2)+ `index.html`(Swiss Modern,19 页)。QA 全绿(引用完整/无 .work 泄漏/角标窗内/纯文字页无图)。逐条发现:

1. **标注式 dedup 首验(对照历史删除式)**:12 media 标出 3 组——g1(BPE 渐进 build 三页 3.2/3.3/3.4)与 g2 内 3.1 为已知「同版式不同内容」误组(P2 判据缺陷第 N 次复现),g2 内 5.1/5.2 与 g3(2.3/4.1 同图重现)为真重复。仲裁全程只改元数据(拆组/换 primary),**零数据损失**——旧语义下 5 个节点会被降级纯文字后再靠宿主回忆恢复。
2. **校验器逮住真实仲裁失误**:拆出 g2 原 primary(3.1)后忘补新 primary → validate 报「g2 primary 数 0」、export 拒产文档,宁缺毋滥防线生效;补 5.1 primary 后一次通过。
3. **候选层新发现(候选缺口形态)**:末章同页渐进 build 下,5.2 窗 [597.7,631] 的唯一候选来自窗口前扩(571.3,与 5.1 同帧)——换算数字 build 在同一页上无 scene 尖峰,窗内零候选。视图级唯一性回退纯文字页效果良好(数字换算天然宜大字版式);若要图,可考虑「窗内末帧补位」类候选策略(P2 料)。
4. **finalize 7/10 成功 3 降级**(1.1/2.1/3.4 高清直链两轮未取到):降级帧按 SKILL 拷入 assets/ 并标「代理画质」,交付自包含不受影响。
5. **export/notes 新链路一次跑通**:export 同帧复用(12 media→11 文件)、granularity=segment、badge 模板正确;notes.md 标题层级/跳转链接/引用/配图齐全,与 deck 同源同粒度。
6. 切片 4 剩余实跑:#11 p02(B 站)、>30min 分章一支、本地一支(验笔记时间戳降级)。

## 切片 4 实跑第 2/3 例(2026-07-13,#11 p02 + 本地 #9,feat/slice4-video-index)

两例由 subagent 并行照当前分支 SKILL.md 全流程实跑(交互三问预置:形态=两者/中档/跟随视频),均在 dedup 仲裁后、export 之后撞 Fable 5 额度中止,交付物已完整落盘,由主会话补跑 export --force/notes 保一致并统一 QA——**两例 QA 全绿**(索引文档必查、视图级唯一性无违反、角标格式与窗内、笔记死链、本地时间戳降级)。

**#11 p02(B 站,`nlp_p02_slice4_20260713/`)**:ai-zh 字幕(cookie)403 段/segment 粒度、4 章 12 叶、候选 17。轴 A 探针目验确认 **screen-recording**(讲义文档录屏,如实记录未改标 slide-driven)。dedup 3 组各恰一 primary(仲裁后);export 12 帧资产;finalize 8 定稿 0 降级(cookie 下高清直链稳定);deck 13 页(标题+12 叶,章未单独成页),角标 `?p=2&t=<n>` 格式正确。
- **发现**:录屏形态下标注式 dedup 表现稳健——渐进讲义页(g1/g2/g3)误组由宿主拆解,零 media 丢失;B 站 cookie 流程 + 分 P `?p=2` 取流 + 定稿全部一次通过,新 export/notes 链路无平台特异问题。

**本地 #9(`local_slice4_20260713/`,"一个主动接班的汽配二代"/杭商故事,8:24)**:funasr ASR 260 段/**sentence 粒度**、4 章 10 叶、候选 18。轴 A **talking-head**、轴 B 访谈/播客→Paper & Ink。
- **local 契约字段全对**:`platform=local`、`badge_url_template=null`、`source_url=原始绝对路径`(storyboard.video 里为 None,export 从 meta.source.path 正确回填——设计如此,非 bug);export 9 帧资产、finalize 9 定稿 0 降级(本地文件高清恒可得)。
- **票面重点核验通过**:notes.md 时间戳**降级为 mm:ss 纯文本、零跳转链接**;deck 角标为内嵌 `<video src="file://…">` 弹层 + JS `currentTime` 跳播,弹层显示源路径,deck 不拷视频文件。
- **发现**:talking-head 场景 dedup 误组经宿主**全部拆开**(最终 0 组,同机位同背景致 RGB 签名误判,与解锁批 #15/#9b/#9c 结论一致)——标注化下拆组即置 null,是安全元数据操作,印证 P2 判据升级只需换签名不动数据形状。

**切片 4 实跑进度**:#13(slide-driven)、#11 p02(screen-recording)、本地 #9(talking-head)三例通过,覆盖三种主要 visual_form;仅剩 >30min 分章一支未跑(即票04 最后一项)。三例均验证:索引文档无条件产出且契约校验通过、双渲染器只读文档跑通、slide 视图级唯一性生效、移除 `.work/` 交付物完整。
