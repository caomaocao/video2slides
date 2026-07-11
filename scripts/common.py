"""公共工具:制品路径、时新性检查、JSON 读写、子进程封装、stdout 协议、RGB 签名。"""
from __future__ import annotations

import json
import os
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
    "scene_scores": "scene_scores.json",
    "page_boundaries": "page_boundaries.json",
    "frames_dir": "frames_proxy",
    "probe_dir": "probe_frames",
    "candidates": "candidates.json",
    "sheets_dir": "sheets",
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
