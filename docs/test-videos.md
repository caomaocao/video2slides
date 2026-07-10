# 测试视频集(v2)

> 来源:用户提供,2026-07-10(第一批 10 源 + 第二批 5 源)。在线视频元数据已用 yt-dlp 2026.07.04 逐个核实(字幕轨/时长/chapters/heatmap);本地文件已用 ffprobe 核实。
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
| 7 | [B BV1EM7t6pEcu](https://www.bilibili.com/video/BV1EM7t6pEcu) | 金沙扩建(The B1M 搬运)/ 黑纹白斑马 | 12:17 | ai-zh 待确认 + 弹幕 | 0 | danmaku | cinematic | 纪录片 |
| 8 | [B BV1BZLQ6JENm](https://www.bilibili.com/video/BV1BZLQ6JENm) | 世界杯现场 / 杰克小兔 | 18:13 | ai-zh 待确认 + 弹幕 | **5** | danmaku | cinematic(游记) | 游记 |
| 9 | 本地 ×3:`…/local-channel/videos/` | 杭商故事(视频号短视频) | 8:24 / 9:45 / 8:32 | 无 → ASR 或 `--transcript` | — | — | talking-head/实拍(待探针) | 资讯/人物故事 |
| 10 | 本地 ×1:`…/local-channel/lives/` | 视频号直播回放(标题空) | **41:11** | 无 → ASR | — | — | talking-head(待探针) | 访谈/直播 |
| 11 | [B BV1k44LzPEhU](https://www.bilibili.com/video/BV1k44LzPEhU)(**187P 分 P 合集**,推荐 p02) | 尚硅谷 NLP 零基础教程 | p01 4:37 / p02 11:59 | ai-zh(**需 cookie**)+ 弹幕 | 每 P 无 | danmaku | **slide-driven** | 课程 |
| 12 | [YT TCH_1BHY58I](https://www.youtube.com/watch?v=TCH_1BHY58I) | Building makemore Part 2: MLP / Andrej Karpathy | **75:39** | 自动 en(+机翻 zh) | **19** | heatmap ✅ | screen-recording(coding) | 课程 |
| 13 | [YT QNiaoD5RxPA](https://www.youtube.com/watch?v=QNiaoD5RxPA) | Token 到底是什么 / 马克的技术工作坊 | 10:31 | **手动 zh-Hans/zh-Hant** | **5** | heatmap ✅ | **slide-driven** | 课程/科普 |
| 14 | [YT tamj4B7OALc](https://www.youtube.com/watch?v=tamj4B7OALc) | Lecture 01 Course Overview / Abhinav Maurya | **64:13** | 自动 en | 0 | 无 | **slide-driven** | 课程 |
| 15 | [B BV1VC7g6vE9f](https://www.bilibili.com/video/BV1VC7g6vE9f) | Vibe Coding 是什么 / 隔壁的程序员老王 | 12:26 | **无 ai-zh(实测,含 cookie)** → ASR | 0 | danmaku | slide/talking 混合(待探针) | 科普/评测 |

本地文件补充:横屏,分辨率 1280×720 / 1024×576 / 960×544;**每个视频带同名 `.json` sidecar**(title、作者、时长、宽高、封面等)——`fetch.py` 本地路径应优先读取 sidecar 作 metadata,无需要求用户手填标题。

## 核实中发现的事实(影响 spec,已同步修订 v0.4)

1. **B 站字幕 = AI 字幕轨(`ai-zh`,SRT),必须登录 cookie 才可获取**;无 cookie 时 yt-dlp 只能看到弹幕(XML)轨。「有字幕免配置」对 B 站不成立:B 站 happy path = `--cookies-from-browser chrome`(免 key 但需登录态)或回退 ASR。→ spec §1.1、§10.3、§11 已修订
2. **中文 YouTube 频道普遍没有自动字幕轨**(#1、#2 连 auto captions 都为 0)。ASR 路径不是边缘 fallback,是中文场景的主干之一
3. **B 站无 cookie 实测可列到 1080p**(cookie 后解锁 2160/4K)——spec 原表述「≥720p 需登录」基于旧版 yt-dlp,实际下载可用性待实现期验证
4. **烧录字幕(#1、#2)是信号层考验点**:底部字幕条逐句变化给 scene-score 叠加持续小抖动,可能把 slide-driven/cinematic 误判成 screen-recording。候选对策:探针阶段 crop 掉底部 ~15% 再算 score;或探针 contact sheet 仲裁时目视纠偏
5. **B 站 AI 字幕非全覆盖**:#15 即便带 cookie 也只有弹幕轨——存在无字幕轨的 B 站视频,ASR 需求独立于 cookie 问题存在
6. **分 P 合集必须带 `?p=n` 定 P**:#11 是 187P 合集,不带 p 参数时 yt-dlp 逐 P 枚举 metadata(实测直接超时)。`fetch.py` 实现要点:先归一化 URL(缺省补 `p=1`)再调 yt-dlp

## 覆盖矩阵(管线路径 → 用例)

| 管线路径 | 用例 |
|---|---|
| 字幕直取(YouTube 手动) | #3、#4、**#13** |
| 字幕直取(YouTube 自动 en) | #12、#14 |
| 字幕直取(B 站 ai-zh + cookie) | #5、#6、**#11**(#7、#8 待确认) |
| ASR(api / funasr) | #1、#2、#9、#10、#15 |
| `--transcript` 逃生门 | #9(短,适合人工准备转写) |
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

## 垂直切片验收(定稿)

第二批已补齐「自带字幕 + slide-driven」组合,恢复 spec 原验收口径:

- **YouTube 切片主验收:#13(Token 讲解)**——slide-driven + 手动中文字幕 + 5 chapters + heatmap,10:31 体量适中,先验全齐
- **B 站切片主验收:#11 p02(尚硅谷 NLP 课程概述)**——slide-driven + ai-zh 字幕,11:59,顺带验证分 P 规则与 cookie 流程
- 切片后的首批回归:#6(screen-recording + chapters + clip 主力)、#3(cinematic + 先验最全)、#1(slide-driven 无字幕 + FunASR,验 ASR 路径)

## 待办

- [ ] #7、#8 的 ai-zh 轨逐个确认(推定存在,跑回归时顺带验证)
- [ ] B 站无 cookie 的 1080p 实际下载可用性验证(影响 §10.3 降级表述)
- [x] ~~补充 slide-driven + 自带字幕用例~~ → 第二批已补(#11、#13、#14)
- [ ] 每形态扩充到 5–10 个,作为探针阈值调参的标注集(spec §14 仍开放项 1)
