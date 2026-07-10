"""帧层:窗口对齐、候选规划、单遍抽取、RGB 去重、打分剪枝、contact sheet、定稿懒抓(spec §8)。"""
from __future__ import annotations

import bisect
import re as _re
import shutil as _shutil
import subprocess as _sp
from pathlib import Path

from common import emit, is_fresh, load_json, rgb_signature, run, save_json, sig_diff_ratio, wp

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
    # 同帧号分组(不同要点命中同一帧):全部保留,共享同一抽帧文件——不可用 setdefault 只留首个,
    # 否则某要点的唯一候选与另一要点撞帧号时会被静默丢弃,导致该要点在 candidates.json 里清零、
    # 下游不可恢复(Task 8 review 发现的问题)。
    by_n: dict[int, list] = {}
    for c in sorted(cands, key=lambda c: c["n"]):
        by_n.setdefault(c["n"], []).append(c)
    ns = sorted(by_n)

    sel = work / "select.txt"
    sel.write_text(build_select_expr(ns), encoding="utf-8")
    run(["ffmpeg", "-y", "-v", "error", "-i", wp(work, "proxy"),
         "-filter_script:v", sel, "-fps_mode", "passthrough",
         "-q:v", "2", frames_dir / "f_%05d.jpg"], timeout=1800)
    ordered = []
    for i, n in enumerate(ns, start=1):        # 输出序 = 帧号升序
        f = str(frames_dir / f"f_{i:05d}.jpg")
        for c in by_n[n]:
            c["file"] = f
            ordered.append(c)
    save_json(wp(work, "candidates"), ordered)
    return ordered


def dedup_candidates(cands: list[dict]) -> list[dict]:
    """时间序遍历,对比最近 4 张保留帧签名,sig_diff_ratio < DUP_RATIO 判重标 dup(不删,剪枝阶段处理)。

    注:extract_candidates 修复同帧号合并后,不同要点撞同一帧号时会产出连续的同文件候选——
    这里签名相同(diff ratio=0 < DUP_RATIO),后一条必判 dup,这是预期行为:谁真正保留该帧由
    Task 10 的跨要点去重仲裁;若某要点的候选全被判 dup,prune_top3 的兜底逻辑会为该要点保留
    分数最高的 1 张,不会导致该要点彻底没有候选。
    """
    kept_sigs: list[bytes] = []
    for c in cands:                             # 已按时间(帧号)序
        sig = rgb_signature(c["file"])
        is_dup = any(sig_diff_ratio(sig, k) < DUP_RATIO for k in kept_sigs[-4:])
        c["dup"] = is_dup
        if not is_dup:
            kept_sigs.append(sig)               # 滑窗只滚动保留帧(spec §8.1:抑制 A-B-A)
    return cands


_YAVG = _re.compile(r"lavfi\.signalstats\.YAVG=([\d.]+)")


def edge_density(image: Path | str) -> float:
    """边缘密度代理(0–1):ffmpeg edgedetect 后取整帧 YAVG 均值 /255(spec §8.1,tesseract 缺失时的降级信号)。"""
    r = _sp.run(["ffmpeg", "-v", "error", "-i", str(image),
                 "-vf", "edgedetect,signalstats,metadata=print:file=-", "-f", "null", "-"],
                capture_output=True, text=True)
    m = _YAVG.search(r.stdout or "")
    return float(m.group(1)) / 255 if m else 0.0


def text_density(image: Path | str) -> float | None:
    """文本密度(0–1):tesseract 存在时按 conf>60 的词数/40 封顶;tesseract 缺失时返回 None,
    由 apply_scores 切到 0.6*edge+0.4*peak 的降级公式(spec §8.1)。"""
    if not _shutil.which("tesseract"):
        return None
    r = _sp.run(["tesseract", str(image), "stdout", "--psm", "6", "-l", "chi_sim+eng", "tsv"],
                capture_output=True, text=True)
    words = sum(1 for line in r.stdout.splitlines()[1:]
                if (c := line.split("\t")) and len(c) >= 12 and c[10].replace(".", "").isdigit()
                and float(c[10]) > 60 and c[11].strip())
    return min(words / 40, 1.0)


def apply_scores(cands: list[dict]) -> list[dict]:
    """由已测量的 _edge/_text/peak_score 合成最终 score(测量与合成拆开便于纯函数单测):
    有文本密度时 0.5*text+0.3*edge+0.2*peak,缺失时降级 0.6*edge+0.4*peak;dup 帧一律 score=0。"""
    for c in cands:
        if c.get("dup"):
            c["score"] = 0.0
            continue
        edge, text, peak = c["_edge"], c["_text"], c["peak_score"]
        c["score"] = (0.5 * text + 0.3 * edge + 0.2 * peak) if text is not None \
            else (0.6 * edge + 0.4 * peak)
    return cands


def measure(cands: list[dict]) -> list[dict]:
    """对每个候选跑 edge_density/text_density(测量副作用),再调用 apply_scores 合成分数。"""
    for c in cands:
        c["_edge"] = edge_density(c["file"])
        c["_text"] = text_density(c["file"])
    return apply_scores(cands)


def prune_top3(cands: list[dict]) -> dict:
    """按 node_id 分组,非 dup 中取分数最高的 TOP_K;若某要点全 dup,兜底保留原始质量最高的 1 张
    (spec §8.3:避免要点彻底没有候选帧)。"""
    by_node: dict[str, list] = {}
    for c in cands:
        by_node.setdefault(c["node_id"], []).append(c)
    sel = {}
    for nid, cs in by_node.items():
        good = sorted((c for c in cs if not c.get("dup")), key=lambda c: -c["score"])[:TOP_K]
        if not good:                             # 全 dup 兜底:保原始质量最高 1 张
            good = [max(cs, key=lambda c: c.get("_raw", c.get("_edge", 0)))]
        sel[nid] = good
    return sel


def _group_by_chapters(flat: list[dict], chapters: list[dict]) -> list[tuple[str, list[dict]]]:
    """全覆盖分组:每个候选按最近的章起点归章(早于首章归首章,晚于末章 t_end 归末章),零丢帧。
    不能用 [t_start, t_end) 区间过滤——章间缝隙/末章之后的候选会被静默丢弃,违背"每要点可见"契约。"""
    if not chapters:
        return [("", flat)] if flat else []
    starts = [ch["t_start"] for ch in chapters]
    buckets: list[list[dict]] = [[] for _ in chapters]
    for c in flat:
        i = max(bisect.bisect_right(starts, c["t"]) - 1, 0)
        buckets[i].append(c)
    return [(chapters[i].get("title", ""), b) for i, b in enumerate(buckets) if b]


def _cap_per_node(g: list[dict], cap: int = 18) -> tuple[list[dict], bool, list[str]]:
    """预算内按节点轮转取帧:先保证每节点第 1 候选,再补第 2/第 3,防止时间序截断饿死后段节点。
    返回 (选中帧按时间序, 是否截断, 被整体截掉的 node_id 列表——轮转下通常为空,记录仅为可审计)。"""
    by_node: dict[str, list[dict]] = {}
    for c in g:                                  # g 已按 t 排序,插入序即时间序
        by_node.setdefault(c["node_id"], []).append(c)
    picked: list[dict] = []
    rank = 0
    while len(picked) < cap:
        added = False
        for cs in by_node.values():
            if rank < len(cs) and len(picked) < cap:
                picked.append(cs[rank])
                added = True
        if not added:
            break
        rank += 1
    truncated = len(picked) < len(g)
    dropped = sorted({c["node_id"] for c in g} - {c["node_id"] for c in picked})
    return sorted(picked, key=lambda c: c["t"]), truncated, dropped


def make_sheets(work: Path, selected: dict, chapters: list[dict]) -> list[dict]:
    """按章全覆盖分组(无 chapters 视为单章),章内按节点轮转配额取帧后按时间序
    scale=640:360 + tile=3x3 拼图,每章预算 ≤2 张(18 帧);截断记 truncated=true,
    被整体截掉的节点记 dropped_node_ids(spec §8.3)。"""
    sheets_dir = wp(work, "sheets_dir")
    sheets_dir.mkdir(parents=True, exist_ok=True)
    flat = sorted((c for cs in selected.values() for c in cs), key=lambda c: c["t"])
    out = []
    for gi, (ch_title, g) in enumerate(_group_by_chapters(flat, chapters)):
        capped, truncated, dropped = _cap_per_node(g)    # 每章 ≤2 张 3x3(预算,spec §8.3)
        for si in range(0, len(capped), 9):
            batch = capped[si:si + 9]
            tmp = sheets_dir / f"tmp_ch{gi}_{si // 9}"
            tmp.mkdir(exist_ok=True)
            for bi, c in enumerate(batch):
                _shutil.copy(c["file"], tmp / f"img_{bi:03d}.jpg")
            sheet = sheets_dir / f"ch{gi}_{si // 9}.jpg"
            run(["ffmpeg", "-y", "-v", "error", "-framerate", "1",
                 "-i", tmp / "img_%03d.jpg",
                 "-vf", "scale=640:360,tile=3x3", "-frames:v", "1", sheet])
            _shutil.rmtree(tmp)
            mp = {"chapter": ch_title, "truncated": truncated,
                  "dropped_node_ids": dropped,
                  "cells": [{"cell": bi, "node_id": c["node_id"], "t": c["t"], "file": c["file"]}
                            for bi, c in enumerate(batch)]}
            save_json(sheet.with_suffix(".map.json"), mp)
            out.append({"sheet": str(sheet), "map": mp})
    return out


def run_cli(argv=None) -> int:
    """CLI:--probe 全片均匀 15 帧供轴 A 视觉形态仲裁;--candidates 走完整对齐/规划/抽取/去重/
    打分/剪枝/拼图链路并回填 candidates.json;--finalize 留给 Task 11 实现(spec §8)。"""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--candidates", action="store_true")
    mode.add_argument("--finalize", action="store_true")   # Task 11 实现
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    work = Path(args.work)
    rows = load_json(wp(work, "scene_scores"))
    duration = rows[-1]["t"] if rows else 0

    if args.probe:
        ts = [duration * (i + 0.5) / 15 for i in range(15)]
        cands = [{"node_id": f"probe_{i}", "t": t, "reason": "probe", "peak_score": 0.0}
                 for i, t in enumerate(ts)]
        ordered = extract_candidates(work, cands, rows)
        sheets = make_sheets(work, {"probe": ordered}, chapters=[])
        emit(*[f"probe sheet: {s['sheet']}" for s in sheets],
             next_hint="Claude Read 探针 sheet 确认 visual_form(spec §5.1)")
        return 0

    if args.candidates:
        sb = load_json(wp(work, "storyboard"))
        bounds = load_json(wp(work, "page_boundaries"))
        chapters = load_json(wp(work, "priors"))["chapters"]
        leaves = []

        def walk(nodes):
            for nd in nodes:
                if nd.get("children"):
                    walk(nd["children"])
                else:
                    leaves.append({"id": nd["id"],
                                   "win": align_window(nd["t_start"], nd["t_end"], bounds, duration)})
        walk(sb["outline"])
        cands = [c for lf in leaves for c in plan_candidates(lf, bounds, duration)]
        ordered = dedup_candidates(extract_candidates(work, cands, rows))
        selected = prune_top3(measure(ordered))
        sheets = make_sheets(work, selected, chapters)
        save_json(wp(work, "candidates"), ordered)
        emit(f"候选 {len(ordered)} 帧,叶子 {len(leaves)} 个",
             *[f"sheet: {s['sheet']}" for s in sheets],
             next_hint="Claude Read sheets 终选各要点用帧并回填 storyboard.media(spec §8.3)")
        return 0
    return 2


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(run_cli())
