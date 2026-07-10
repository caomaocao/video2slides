"""信号基底层:一次 ffmpeg 元数据遍历产出 scene_scores.json,五个下游共享(spec §8.0)。"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from common import emit, is_fresh, load_json, save_json, wp

# 初始值(spec §14):页边界阈值 0.30,峰间最小间隔 1.5s
PAGE_THR = 0.30
MIN_GAP = 1.5

_FRAME = re.compile(r"frame:(\d+)\s+pts:\S+\s+pts_time:([\d.]+)")
_SCORE = re.compile(r"lavfi\.scene_score=([\d.]+)")


def parse_scene_metadata(text: str) -> list[dict]:
    rows, cur = [], None
    for line in text.splitlines():
        m = _FRAME.search(line)
        if m:
            cur = (int(m.group(1)), float(m.group(2)))
            continue
        m = _SCORE.search(line)
        if m and cur is not None:
            rows.append({"n": cur[0], "t": cur[1], "score": float(m.group(1))})
            cur = None
    return rows


def pick_page_boundaries(rows: list[dict], thr: float = PAGE_THR, min_gap: float = MIN_GAP) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        if r["score"] < thr:
            continue
        if out and r["t"] - out[-1]["t"] < min_gap:
            if r["score"] > out[-1]["score"]:
                out[-1] = dict(r)              # 间隔内保留分高者
            continue
        out.append(dict(r))
    return out


def curve_stats(rows: list[dict]) -> dict:
    scores = sorted(r["score"] for r in rows)
    n = len(scores)
    dur_min = max(rows[-1]["t"], 1e-6) / 60 if rows else 1e-6
    spikes = len(pick_page_boundaries(rows))
    return {
        "frames": n,
        "mean": round(sum(scores) / n, 4) if n else 0.0,
        "p95": round(scores[int(n * 0.95)] if n else 0.0, 4),
        "spikes": spikes,
        "spikes_per_min": round(spikes / dur_min, 2),
        "plateau_ratio": round(sum(1 for s in scores if s < 0.05) / n, 3) if n else 0.0,
    }


def run_cli(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    work = Path(args.work)
    proxy, scores_p, bounds_p = wp(work, "proxy"), wp(work, "scene_scores"), wp(work, "page_boundaries")

    if not args.force and is_fresh(scores_p, proxy) and is_fresh(bounds_p, proxy):
        rows = load_json(scores_p)
    else:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(proxy),
             "-vf", "select='gte(scene,0)',metadata=print:file=-", "-f", "null", "-"],
            capture_output=True, text=True, timeout=1800)
        if r.returncode != 0:
            emit("scene-score 遍历失败:降级 uniform 抽帧、禁用页边界先验(spec §11)——切片内直接报错")
            return 1
        rows = parse_scene_metadata(r.stdout)
        save_json(scores_p, rows)
        save_json(bounds_p, pick_page_boundaries(rows))
    st = curve_stats(rows)
    emit(
        f"scene_scores: {scores_p}({st['frames']} 帧)",
        f"page_boundaries: {bounds_p}({st['spikes']} 个,{st['spikes_per_min']}/min)",
        f"curve_stats: {st}",
        next_hint=f"python scripts/frames.py --probe --work {work}(轴 A 探针仲裁)",
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
