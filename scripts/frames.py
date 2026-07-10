"""帧层:窗口对齐、候选规划、单遍抽取、RGB 去重、打分剪枝、contact sheet、定稿懒抓(spec §8)。"""
from __future__ import annotations

import bisect
from pathlib import Path

# 初始值(spec §14)
PEAK_OFFSET = 0.7        # 避糊:峰后偏移取稳定帧
PER_POINT_CAP = 6        # 每要点候选上限(去重前)
MAX_BACK_EXPAND = 30.0   # 前扩上限:上一页边界太远则不扩
DUP_RATIO = 0.10         # 判重:变化像素占比阈值
TOP_K = 3                # 剪枝每要点 top-3


def align_window(t_start: float, t_end: float, boundaries: list[dict], duration: float):
    """
    对齐窗口:slide-driven 模式下前扩至上一页边界。

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
        t0 = prev[-1]                      # slide-driven:讲者先翻页再开讲(spec §8.1 步骤0)
    return (max(0.0, t0), min(t_end, duration))


def plan_candidates(leaf: dict, boundaries: list[dict], duration: float,
                    offset: float = PEAK_OFFSET, cap: int = PER_POINT_CAP) -> list[dict]:
    """
    规划候选时间戳:窗内每页边界产一个候选(峰后偏移),无边界则用窗中点。

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
    cands = [
        {"node_id": leaf["id"], "t": min(b["t"] + offset, t1 - 0.05, duration - 0.1),
         "reason": "scene-peak", "peak_score": b["score"]}
        for b in boundaries if t0 <= b["t"] < t1
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
