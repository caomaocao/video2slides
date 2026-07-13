# scripts/ · AGENTS.md

确定性脚本层:做重活/可复现的工作,把语义判断留给宿主 Claude,两者通过结构化制品交接(脚本 stdout 直接喂给 Claude 下一步)。先读根 `AGENTS.md` 的红线。

## 本目录不变式

- **零 pip 运行期依赖**:只用 stdlib。图像处理一律走 ffmpeg(rawvideo 管道、`tile`、`edgedetect`/`blurdetect`),不引 PIL/opencv。
- **外部能力走 subprocess**:调 `ffmpeg`/`ffprobe`/`yt-dlp` CLI,绝不 `import yt_dlp`。
- **共享 helper 下沉 `common.py`**,不要在各脚本里重抄。典型:静音 span 解析既服务切片 2 的音频切块,又服务切片 3 的划章信号,只有一份 ffmpeg `silencedetect` 参数。
- **续跑友好**:每层用 `common.is_fresh` 判断制品是否新于上游,新则跳过;落盘用 `common.save_json`(原子写)。
- 改动配 TDD 测试(见 `tests/`),注释中文。

## 各脚本职责

| 脚本 | 职责 | 关键点 |
|---|---|---|
| `setup.py` | 预检(`--json`/`--check`)+ 幂等安装 + `.env` 脚手架 | exit 0 就绪 / 2 缺二进制 / 3 需配 ASR / 4 版本不足 |
| `common.py` | 制品注册表 / `is_fresh` 续跑检查 / RGB 签名 / 静音 span 解析 / `save_json` 原子写 / `emit` / `ffprobe_duration` / `load_env_config` | 全脚本共享座,改签名要顾及所有调用方 |
| `fetch.py` | yt-dlp 代理流(≤360p)+ 字幕/章节/热度/弹幕/元数据;URL 归一化;本地文件分支(sidecar 元数据 fail-open,ffmpeg 降采样代理) | 字幕轨按目标语言精确选、排除 danmaku;`normalize_url` 认 shorts/embed/live/v |
| `transcribe.py` | VTT/SRT 解析去重;音频切块(silence 中点);ASR 三家族(`PRESETS` 表);弹幕密度直方图 | transcriptions 家族(原生时间戳)/ chat 家族(块级 45s 粒度)/ funasr;`_http_post` 是测试 monkeypatch 点;块级失败隔离 |
| `funasr_runner.py` | 仅在 `FUNASR_VENV` 内经 subprocess 执行,句级时间戳 | 真 stdout 只出 JSON,依赖噪声改道 stderr(守 JSON 契约) |
| `signals.py` | 一遍 ffmpeg 产 `scene_scores.json`(五处下游共读);`--chapter-hints` 划章信号 | native 透传 / 信号合成 / uniform 兜底,落 `chapter_hints.json` |
| `frames.py` | 复合单遍抽帧 + RGB 滑窗去重(最近 4 帧)+ 打分剪枝 + contact sheet;`--finalize` 懒抓高清 | 窗口对齐只前扩不后缩;宽窗(>90s)候选槽均匀采样;finalize 只处理真正上页的 media |
| `storyboard.py` | 校验器:schema / 时间戳 / quote 存在性 / 跨节点去重;`aggregate` 变粒度;分章校验 | `chapter_plan` 存在时校验章区间连续覆盖 + 与 level-1 一一对应 |

## 别做

- 不要引 `--transcript` 直供转写(未来能力,本切片未实现,不在用户可见文案里提)。
- 不要在这层调 LLM API —— 流水线里的「LLM」是宿主 Claude,不是自拨的服务。
