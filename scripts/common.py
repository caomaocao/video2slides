"""公共工具:制品路径、时新性检查、JSON 读写、子进程封装、stdout 协议、RGB 签名。"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

# .work/ 内的制品名注册表——所有脚本经 wp() 取路径,禁止散落硬编码
ARTIFACTS = {
    "meta": "meta.json",
    "priors": "priors.json",
    "raw_info": "ytdlp_info.json",
    "proxy": "proxy.mp4",
    "subs_dir": "subs",
    "transcript": "transcript.json",
    "audio": "audio.mp3",
    "scene_scores": "scene_scores.json",
    "page_boundaries": "page_boundaries.json",
    "frames_dir": "frames_proxy",
    "probe_dir": "probe_frames",
    "candidates": "candidates.json",
    "sheets_dir": "sheets",
    "chapter_hints": "chapter_hints.json",
    "chapter_plan": "chapter_plan.json",
    "storyboard": "storyboard.json",
}


def wp(work: Path | str, key: str) -> Path:
    return Path(work) / ARTIFACTS[key]


def is_fresh(artifact: Path, *upstreams: Path) -> bool:
    if not artifact.exists():
        return False
    m = artifact.stat().st_mtime
    return all(u.exists() and u.stat().st_mtime <= m for u in upstreams)


def load_json(p: Path | str):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save_json(p: Path | str, obj) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)   # 原子替换:storyboard.json 等制品写一半被杀不损坏(续跑契约)


def run(cmd: list, timeout: int = 600) -> str:
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        tail = "\n".join((r.stderr or "").splitlines()[-8:])
        raise RuntimeError(f"命令失败({r.returncode}): {' '.join(str(c) for c in cmd)}\n{tail}")
    return r.stdout


def ytdlp_cookie_flags(cookies_from_browser: str | None,
                       cookies_file: str | None = None) -> list[str]:
    """yt-dlp cookie 参数:浏览器读取(有本机 Chrome)或 cookies 文件(headless/无浏览器,跨平台 P2-8)。
    二者可并存(通常二选一),空则返回 []。fetch/frames 两处取流共用一份,避免各自重抄。"""
    flags: list[str] = []
    if cookies_from_browser:
        flags += ["--cookies-from-browser", cookies_from_browser]
    if cookies_file:
        flags += ["--cookies", cookies_file]
    return flags


def emit(*lines: str, next_hint: str | None = None) -> None:
    for line in lines:
        print(line)
    if next_hint:
        print(f"NEXT: {next_hint}")


def rgb_signature(image: Path | str) -> bytes:
    """16×16 RGB 签名(768 字节),ffmpeg rawvideo 管道,零 pip。"""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(image), "-vf", "scale=16:16",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    )
    return r.stdout


def sig_diff_ratio(a: bytes, b: bytes, channel_thr: int = 24) -> float:
    """变化像素占比:单像素任一通道差 > channel_thr 记为变化。

    标定值 24(2026-07-11 于验收视频 #13 标定):深底讲义页间共享大面积背景,
    初始值 48 下不同页的变化占比仅 0.03–0.08(全部误判重);24 下真翻页 0.12–0.43、
    同页递进 build ≤0.04,与判重阈值 DUP_RATIO=0.10 分离良好。"""
    assert len(a) == len(b) == 768, "签名必须是 16×16×3 字节"
    changed = sum(
        1
        for i in range(0, 768, 3)
        if max(abs(a[i] - b[i]), abs(a[i + 1] - b[i + 1]), abs(a[i + 2] - b[i + 2])) > channel_thr
    )
    return changed / 256


def config_dir() -> Path:
    """配置目录:尊重 $XDG_CONFIG_HOME(Linux 惯例),缺省回落 ~/.config。macOS/未设时行为不变。"""
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "video2slides"


def load_env_config(path: Path | str | None = None) -> dict[str, str]:
    """读 <config_dir>/.env(KEY=VALUE)并叠加 os.environ(environ 优先)。零 pip 自写解析。"""
    p = Path(path) if path else config_dir() / ".env"
    cfg: dict[str, str] = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            cfg[k.strip()] = v.strip()
    for k, v in os.environ.items():
        cfg[k] = v
    return cfg


def ffprobe_duration(path: Path | str) -> float:
    """ffprobe 读媒体时长(秒)。"""
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", str(path)])
    return float(out.strip().splitlines()[0])


_SIL_RE = re.compile(r"silence_(start|end): ([\d.]+)")
SIL_ARGS = "silencedetect=noise=-35dB:d=0.4"


def parse_silence_spans(stderr_text: str) -> list[tuple[float, float]]:
    """silencedetect stderr → (start, end) 区间列表(升序);孤立 start(音频在静音中结束)丢弃。"""
    spans, start = [], None
    for kind, val in _SIL_RE.findall(stderr_text or ""):
        if kind == "start":
            start = float(val)
        elif start is not None:
            spans.append((start, float(val)))
            start = None
    return spans


def detect_silence_spans(audio: Path | str) -> list[tuple[float, float]]:
    """ffmpeg silencedetect 一遍音频解码取静音区间(切片3 划章信号;transcribe 切块共用同一参数)。"""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(audio), "-af", SIL_ARGS,
                        "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    return parse_silence_spans(r.stderr or "")
