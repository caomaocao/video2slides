# AGENTS.md

面向任何 AI 编码代理的入口说明。**权威指令在别处,本文件只做路由 + 红线**,避免与之竞争成为第二个 source of truth。

## 先读这两份

1. **`CLAUDE.md`** —— 本仓库对代理的完整工作指令(项目状态、目标架构、依赖政策、非目标)。开工前必读。
2. **`docs/video2slides-spec-v0.4.md`** —— 设计的 source of truth(中文;v0.3 是历史快照,勿改)。做任何架构判断前读它。

## 项目一句话

**video2slides**:把视频(YouTube / Bilibili / 本地文件)转成 `frontend-slides` 风格的 HTML 讲义,幻灯片内嵌关键帧/片段,点击可跳回源视频对应时间戳。核心不变式:**转写 → 大纲(内容键)→ 关联帧(按节点定向选帧)→ 幻灯片**。

## 红线(任何代理都不得违反)

- **语言**:代码注释、commit message、文档(含新建 `.md`)一律**中文**。
- **零 pip 运行期依赖**:shipped skill 仅用 stdlib + 两个外部二进制(`ffmpeg`/`ffprobe`、`yt-dlp`),`tesseract` 可选。图像处理全走 ffmpeg,**禁用 PIL/opencv/paddleocr**。往运行期依赖里加东西是 spec 变更,不是随手 `uv add`。
- **subprocess 而非 import**:`fetch.py` 必须 shell out 调 `yt-dlp` CLI,**绝不 `import yt_dlp`**;ffmpeg/ffprobe 同理。
- **制品契约**:`storyboard.json`(分析↔渲染层契约,schema 见 spec §6)与 `scene_scores.json`(共享信号基,一次算五处用)是硬边界,改前读 spec。
- **续跑模型**:中间制品落在输出目录的 `.work/` 下并默认保留;每层若自身制品新于上游则跳过,`--force` 重跑。

## 常用命令

- `uv sync` —— 从 lockfile 同步 venv
- `uv run pytest` —— 跑测试(pytest 仅 dev 依赖,运行期保持 stdlib)

## 子目录另有就近说明

`scripts/`、`tests/`、`docs/` 各有自己的 `AGENTS.md`,改动对应目录时以**就近的**那份为准。
