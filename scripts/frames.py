"""帧层:窗口对齐、候选规划、单遍抽取、RGB 去重、打分剪枝、contact sheet、定稿懒抓(spec §8)。"""
from __future__ import annotations

import bisect
from pathlib import Path

from common import rgb_signature, run, save_json, sig_diff_ratio, wp

# 初始值(spec §14)
PEAK_OFFSET = 0.7        # 避糊:峰后偏移取稳定帧
PER_POINT_CAP = 6        # 每要点候选上限(去重前)
MAX_BACK_EXPAND = 30.0   # 前扩上限:上一页边界太远则不扩
DUP_RATIO = 0.10         # 判重:变化像素占比阈值
TOP_K = 3                # 剪枝每要点 top-3


def align_window(t_start: float, t_end: float, boundaries: list[dict],
                 duration: float) -> tuple[float, float]:
    """
    对齐窗口:slide-driven 模式下前扩至上一页边界(只前扩、不后缩)。

    args:
        t_start: 窗口起点时间戳
        t_end: 窗口终点时间戳
        boundaries: 页边界列表，每项 {"n": frame_no, "t": timestamp, "score": score}
        duration: 视频总时长

    returns:
        (t0, t1) 对齐后的窗口 tuple
    """
    prev = [b["t"] for b in boundaries if b["t"] <= t_start + 0.5]
    t0 = t_start
    if prev and t_start - prev[-1] <= MAX_BACK_EXPAND:
        # slide-driven:讲者先翻页再开讲(spec §8.1 步骤0)
        t0 = min(prev[-1], t_start)   # 只前扩不后缩:抖动边界落在 t_start 之后时保持原起点
    return (max(0.0, t0), min(t_end, duration))


def plan_candidates(leaf: dict, boundaries: list[dict], duration: float,
                    offset: float = PEAK_OFFSET, cap: int = PER_POINT_CAP) -> list[dict]:
    """
    规划候选时间戳:窗内每页边界产一个候选(峰后偏移),无边界则用窗中点。
    窗尾放不下峰后稳定帧的边界不产候选——clamp 回边界前会拍到旧页,与
    reason="scene-peak" 语义矛盾;该新页属于下一节点,由其窗口前扩覆盖。

    args:
        leaf: 叶节点，包含 {"id": str, "win": (t0, t1)}
        boundaries: 页边界列表，每项 {"n": frame_no, "t": timestamp, "score": score}
        duration: 视频总时长
        offset: 峰后偏移(秒)，默认 0.7s
        cap: 候选上限

    returns:
        候选列表，每项 {"node_id": str, "t": timestamp, "reason": str, "peak_score": float}
    """
    t0, t1 = leaf["win"]
    t_max = min(t1 - 0.05, duration - 0.1)
    cands = [
        {"node_id": leaf["id"], "t": b["t"] + offset,
         "reason": "scene-peak", "peak_score": b["score"]}
        for b in boundaries
        if t0 <= b["t"] < t1 and b["t"] + offset <= t_max
    ]
    if not cands:
        cands = [{"node_id": leaf["id"], "t": (t0 + t1) / 2,
                  "reason": "window-midpoint", "peak_score": 0.0}]
    return cands[:cap]


def t_to_frame(t: float, rows: list[dict]) -> int:
    """
    从时间戳映射到帧号:二分查找最近的帧。

    args:
        t: 查询时间戳
        rows: 帧行，每项 {"n": frame_no, "t": timestamp, "score": score}

    returns:
        最近的帧号
    """
    ts = [r["t"] for r in rows]
    i = bisect.bisect_left(ts, t)
    if i == 0:
        return rows[0]["n"]
    if i >= len(rows):
        return rows[-1]["n"]
    return rows[i]["n"] if abs(ts[i] - t) < abs(t - ts[i - 1]) else rows[i - 1]["n"]


def build_select_expr(frame_ns: list[int]) -> str:
    """构造 ffmpeg select 复合表达式:升序去重后拼接(供 -filter_script:v 写入文件,规避命令行长度上限)。"""
    terms = "+".join(f"eq(n,{n})" for n in sorted(set(frame_ns)))
    return f"select='{terms}'"


def extract_candidates(work: Path, cands: list[dict], rows: list[dict]) -> list[dict]:
    """单遍解码抽出全部候选帧到 frames_proxy/f_%05d.jpg(输出序 = 帧号升序),回填 n/file,落盘 candidates.json。"""
    frames_dir = wp(work, "frames_dir")
    frames_dir.mkdir(parents=True, exist_ok=True)
    for c in cands:
        c["n"] = t_to_frame(c["t"], rows)
    # 同帧号合并(不同要点命中同一帧:保留首个,后续在跨要点去重阶段处理)
    by_n: dict[int, dict] = {}
    for c in sorted(cands, key=lambda c: c["n"]):
        by_n.setdefault(c["n"], c)
    ordered = list(by_n.values())

    sel = work / "select.txt"
    sel.write_text(build_select_expr([c["n"] for c in ordered]), encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", "-i", wp(work, "proxy"),
         "-filter_script:v", sel, "-fps_mode", "passthrough",
         "-q:v", "2", frames_dir / "f_%05d.jpg"], timeout=1800)
    for i, c in enumerate(ordered, start=1):   # 输出序 = 帧号升序
        c["file"] = str(frames_dir / f"f_{i:05d}.jpg")
    save_json(wp(work, "candidates"), ordered)
    return ordered


def dedup_candidates(cands: list[dict]) -> list[dict]:
    """时间序遍历,对比最近 4 张保留帧签名,sig_diff_ratio < DUP_RATIO 判重标 dup(不删,剪枝阶段处理)。"""
    kept_sigs: list[bytes] = []
    for c in cands:                             # 已按时间(帧号)序
        sig = rgb_signature(c["file"])
        is_dup = any(sig_diff_ratio(sig, k) < DUP_RATIO for k in kept_sigs[-4:])
        c["dup"] = is_dup
        if not is_dup:
            kept_sigs.append(sig)               # 滑窗只滚动保留帧(spec §8.1:抑制 A-B-A)
    return cands
