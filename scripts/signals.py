"""信号基底层:一次 ffmpeg 元数据遍历产出 scene_scores.json,五个下游共享(spec §8.0)。"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from common import detect_silence_spans, emit, is_fresh, load_json, save_json, wp

# 初始值(spec §14):页边界阈值 0.30,峰间最小间隔 1.5s
PAGE_THR = 0.30
MIN_GAP = 1.5

# 切片3 划章辅助初始值(spec 切片3 §3;调参属 spec §14 台账)
HINT_PB_GAP = 60.0    # 页边界簇间长间隙下限:事件记在间隙末端(新内容启动处)
HINT_SEG_GAP = 3.0    # 转写段间隙下限
HINT_SIL_SPAN = 2.0   # 静音区间时长下限
HINT_MERGE = 10.0     # 共振合并窗(±s)
HINT_EDGE = 60.0      # 首尾排除区
HINT_W = {"page-gap": 2.0, "silence": 1.5, "seg-gap": 1.0, "heat-valley": 1.0}

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


def hint_target_n(duration: float) -> int:
    """候选章界目标数:每 10min 约 1 个,clamp [3,24];刻意多于预期章数,宿主只删不增收敛。"""
    return max(3, min(24, round(duration / 600)))


def _merge_events(events: list[dict], win: float = HINT_MERGE) -> list[dict]:
    """±win 内共振合并:score 相加、t 取 score 加权均值、信号并集。

    链式合并:簇内相邻事件各自 ≤win 即持续并入,簇总跨度可超 win——共振窗约束的是相邻间距而非簇宽,这是有意行为。"""
    out: list[dict] = []
    for e in sorted(events, key=lambda e: e["t"]):
        if out and e["t"] - out[-1]["t"] <= win:
            prev = out[-1]
            total = prev["score"] + e["score"]
            prev["t"] = (prev["t"] * prev["score"] + e["t"] * e["score"]) / total
            prev["score"] = total
            prev["signals"] = sorted(set(prev["signals"]) | set(e["signals"]))
        else:
            out.append({"t": e["t"], "score": e["score"], "signals": sorted(e["signals"])})
    return out


def synth_chapter_hints(duration: float, boundaries: list[dict],
                        seg_spans: list[tuple[float, float]],
                        silence_spans: list[tuple[float, float]],
                        heatmap: list[dict]) -> list[dict]:
    """多信号共振合成候选章界(spec 切片3 §3):各信号独立记分 → ±HINT_MERGE 合并 →
    首尾 HINT_EDGE 排除 → top-N(N=hint_target_n)→ 按时间升序返回。"""
    events: list[dict] = []
    for a, b in zip(boundaries, boundaries[1:]):
        if b["t"] - a["t"] >= HINT_PB_GAP:
            events.append({"t": b["t"], "score": HINT_W["page-gap"], "signals": ["page-gap"]})
    for (_, e0), (s1, _) in zip(seg_spans, seg_spans[1:]):
        if s1 - e0 >= HINT_SEG_GAP:
            events.append({"t": s1, "score": HINT_W["seg-gap"], "signals": ["seg-gap"]})
    for s, e in silence_spans:
        if e - s >= HINT_SIL_SPAN:
            events.append({"t": e, "score": HINT_W["silence"], "signals": ["silence"]})
    if heatmap:
        vmax = max(h["value"] for h in heatmap)
        for h in heatmap:
            if h["value"] < 0.25 * vmax:
                events.append({"t": (h["t_start"] + h["t_end"]) / 2,
                               "score": HINT_W["heat-valley"], "signals": ["heat-valley"]})
    merged = [e for e in _merge_events(events) if HINT_EDGE <= e["t"] <= duration - HINT_EDGE]
    top = sorted(merged, key=lambda e: -e["score"])[:hint_target_n(duration)]
    return sorted(top, key=lambda e: e["t"])


def attach_excerpts(hints: list[dict], segments: list[dict], k: int = 2) -> list[dict]:
    """每条候选补前后各 k 段转写文本——宿主语义确认的依据,免通读(spec 切片3 §3)。

    就地往 hints 元素写 before/after 并返回同一引用(有意的原地扩充,调用方勿复用未 attach 的引用)。"""
    for h in hints:
        h["before"] = [s["text"] for s in segments if s["t_end"] <= h["t"]][-k:]
        h["after"] = [s["text"] for s in segments if s["t_start"] >= h["t"]][:k]
    return hints


def run_cli(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--chapter-hints", action="store_true",
                    help="划章辅助:输出候选章界(切片3 spec §3)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    work = Path(args.work)

    if args.chapter_hints:
        meta = load_json(wp(work, "meta"))
        duration = float(meta["duration"])
        segments = load_json(wp(work, "transcript"))["segments"]
        priors = load_json(wp(work, "priors"))
        fallback = None
        if priors.get("chapters"):
            # 原生 chapters 直接透传为候选(信号列 native);宿主仍有收敛权(只并不拆)
            hints = [{"t": float(c["t_start"]), "score": None,
                      "signals": ["native"], "title": c.get("title", "")}
                     for c in priors["chapters"]]
        else:
            audio = wp(work, "audio")
            silence_spans = detect_silence_spans(audio) if audio.exists() else []
            seg_spans = [(s["t_start"], s["t_end"]) for s in segments]
            bounds = load_json(wp(work, "page_boundaries"))
            hints = synth_chapter_hints(duration, bounds, seg_spans,
                                        silence_spans, priors.get("heatmap") or [])
            if not hints:                        # 信号全无:10min 均分兜底,如实标注
                hints = [{"t": float(t), "score": None, "signals": ["uniform"]}
                         for t in range(600, int(duration - HINT_EDGE), 600)]
                fallback = "uniform"
        attach_excerpts(hints, segments)
        for i, h in enumerate(hints, 1):
            h["idx"] = i
        out_p = wp(work, "chapter_hints")
        save_json(out_p, {"n_target": hint_target_n(duration), "fallback": fallback,
                          "hints": hints})
        lines = [f"chapter_hints: {out_p}({len(hints)} 条,fallback={fallback})"]
        for h in hints:
            sig = "+".join(h["signals"])
            title = f" [{h['title']}]" if h.get("title") else ""
            before = (h["before"] or ["(片头)"])[-1]
            after = (h["after"] or ["(片尾)"])[0]
            lines.append(f"  #{h['idx']} t={h['t']:.1f} [{sig}]{title} …{before} ▸ {after}…")
        emit(*lines, next_hint=f"宿主语义确认(可并不可拆)后写 {wp(work, 'chapter_plan')}(SKILL.md 步骤 2.5)")
        return 0

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
