# AGENTS.md

面向任何 AI 编码代理的入口说明。**权威指令在别处,本文件只做路由 + 红线**,避免与之竞争成为第二个 source of truth。

## 先读这两份

1. **`CLAUDE.md`** —— 本仓库对代理的完整工作指令(项目状态、目标架构、依赖政策、非目标)。开工前必读。
2. **`docs/cuepoint-spec-v0.5.md`** —— 设计的 source of truth(中文;v0.4/v0.3 是历史快照,勿改)。做任何架构判断前读它。

## 项目一句话

**Cuepoint**:把视频(YouTube / Bilibili / 本地文件)转成自包含的**视频索引文档**(`video_index.json` + `frames/`,公开契约),再按选择渲染为 `frontend-slides` 风格 HTML 讲义或 markdown 笔记,关键帧/时间戳可跳回源视频对应时刻。核心不变式:**转写 → 大纲(内容键)→ 关联帧(按节点定向选帧)→ 索引文档 → 渲染器族(幻灯片/笔记)**。

## 红线(任何代理都不得违反)

- **语言**:代码注释、commit message、文档(含新建 `.md`)一律**中文**。
- **零 pip 运行期依赖**:shipped skill 仅用 stdlib + 两个外部二进制(`ffmpeg`/`ffprobe`、`yt-dlp`),`tesseract` 可选。图像处理全走 ffmpeg,**禁用 PIL/opencv/paddleocr**。往运行期依赖里加东西是 spec 变更,不是随手 `uv add`。
- **subprocess 而非 import**:`fetch.py` 必须 shell out 调 `yt-dlp` CLI,**绝不 `import yt_dlp`**;ffmpeg/ffprobe 同理。
- **制品契约**:对外公开契约是导出的 `video_index.json`(schema 版本化,spec §6.5,改动有版本号把门);`storyboard.json` 为内部工作格式(spec §6)、`scene_scores.json` 为共享信号基(一次算五处用)——三者都是硬边界,改前读 spec。
- **续跑模型**:中间制品落在输出目录的 `.work/` 下并默认保留;每层若自身制品新于上游则跳过,`--force` 重跑。

## 常用命令

- `uv sync` —— 从 lockfile 同步 venv
- `uv run pytest` —— 跑测试(pytest 仅 dev 依赖,运行期保持 stdlib)

## 子目录另有就近说明

`scripts/`、`tests/`、`docs/` 各有自己的 `AGENTS.md`,改动对应目录时以**就近的**那份为准。
