"""storyboard.json 校验与渲染前置聚合(spec §6、§7 引用校验、§8.4 前置)。"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

from common import emit, load_json, rgb_signature, save_json, sig_diff_ratio, wp

_PUNCT = re.compile(r"[\s,，。、.!！?？:：;；\"'“”‘’()（）\[\]【】《》<>—\-…·]+")
REQUIRED_NODE_KEYS = ("id", "title", "t_start", "t_end", "evidence")
# 切片3 分章校验容差:CH_L1_TOL 容纳 chat 家族 45s 块级时间戳的边界微调(最坏 22.5s)
CH_EDGE_TOL, CH_SEAM_TOL, CH_L1_TOL = 1.0, 0.5, 30.0


def norm_text(s: str) -> str:
    """去空白与中英标点、转小写。"""
    return _PUNCT.sub("", s or "").lower()


def quote_ok(quote: str, seg_text: str, ratio: float = 0.85) -> bool:
    """quote 存在性:归一化 substring 优先;否则滑窗局部 fuzzy(ASR 噪声容忍,spec §7)。"""
    nq, nt = norm_text(quote), norm_text(seg_text)
    if not nq:
        return False
    if nq in nt:
        return True
    if len(nt) <= len(nq):
        return difflib.SequenceMatcher(None, nq, nt).ratio() >= ratio
    w = len(nq)
    best = max(difflib.SequenceMatcher(None, nq, nt[i:i + w]).ratio()
               for i in range(0, len(nt) - w + 1))
    return best >= ratio


def _walk(nodes):
    """递归遍历节点树。"""
    for nd in nodes:
        yield nd
        yield from _walk(nd.get("children") or [])


def validate(sb: dict, transcript: dict, duration: float) -> dict:
    """检查项:每节点必有 id/title/t_start/t_end/evidence(≥1 条)、0 <= t_start < t_end <= duration+1、
    每条 evidence 的 segment_id 存在且 quote_ok 通过、media(若有)proxy_path 文件存在且 finalized 为 bool。"""
    segs = {s["id"]: s["text"] for s in transcript["segments"]}
    r = {"ok": True, "schema_errors": [], "quote_failures": [], "time_errors": []}
    dedup_groups: dict[str, int] = {}   # 组 id → primary 计数(标注一致性,v0.5 §6;无标注的旧制品跳过)
    for nd in _walk(sb.get("outline") or []):
        nid = nd.get("id", "?")
        missing = [k for k in REQUIRED_NODE_KEYS if k not in nd]
        if missing or not nd.get("evidence"):
            r["schema_errors"].append(f"节点 {nid} 缺字段: {missing or ['evidence 为空']}")
            continue
        if not (0 <= nd["t_start"] < nd["t_end"] <= duration + 1):
            r["time_errors"].append(f"节点 {nid} 时间窗非法: [{nd['t_start']}, {nd['t_end']}]")
        for ev in nd["evidence"]:
            seg = segs.get(ev.get("segment_id"))
            if seg is None or not quote_ok(ev.get("quote", ""), seg):
                r["quote_failures"].append(nid)
                break
        for m in nd.get("media") or []:
            if not isinstance(m.get("finalized"), bool):
                r["schema_errors"].append(f"节点 {nid} media 缺 finalized 布尔")
            if m.get("proxy_path") and not Path(m["proxy_path"]).exists():
                r["schema_errors"].append(f"节点 {nid} proxy_path 不存在: {m['proxy_path']}")
            if m.get("dedup_group"):
                dedup_groups[m["dedup_group"]] = (dedup_groups.get(m["dedup_group"], 0)
                                                  + bool(m.get("dedup_primary")))
    for gid, n_primary in dedup_groups.items():
        if n_primary != 1:
            r["schema_errors"].append(f"dedup 组 {gid} 的 primary 数为 {n_primary},应恰为 1")
    r["ok"] = not (r["schema_errors"] or r["quote_failures"] or r["time_errors"])
    return r


def validate_chapter_plan(plan: dict, outline: list, duration: float) -> list[str]:
    """分章校验(spec 切片3 §4,仅 chapter_plan 存在时启用):章区间首尾相接覆盖全片;
    storyboard level-1 与章一一对应(按时间窗,容差 CH_L1_TOL)。"""
    errs: list[str] = []
    chs = plan.get("chapters") or []
    if not chs:
        return ["chapter_plan.chapters 为空"]
    if abs(chs[0]["t_start"]) > CH_EDGE_TOL:
        errs.append(f"首章 t_start={chs[0]['t_start']} 未从 0 开始")
    if abs(chs[-1]["t_end"] - duration) > CH_EDGE_TOL:
        errs.append(f"末章 t_end={chs[-1]['t_end']} 未覆盖时长 {duration}")
    for a, b in zip(chs, chs[1:]):
        if abs(a["t_end"] - b["t_start"]) > CH_SEAM_TOL:
            errs.append(f"章 {a.get('idx')}→{b.get('idx')} 有缝/重叠: {a['t_end']} vs {b['t_start']}")
    l1 = outline or []
    if len(l1) != len(chs):
        errs.append(f"storyboard level-1 数({len(l1)})与 chapter_plan 章数({len(chs)})不一致")
        return errs
    for ch, nd in zip(chs, l1):
        if abs(nd["t_start"] - ch["t_start"]) > CH_L1_TOL or abs(nd["t_end"] - ch["t_end"]) > CH_L1_TOL:
            errs.append(f"章 {ch.get('idx')} 与 level-1 节点 {nd.get('id')} 时间窗偏差超 {CH_L1_TOL}s")
    return errs


def dedup_across_nodes(sb: dict) -> dict:
    """跨要点媒体去重标注(spec v0.5 §6):重复组打 dedup_group/dedup_primary,不删除、不替换。

    分组:按 score 降序遍历,与各组代表(即组内 primary,遍历序首个成员)签名比对,
    变化占比 < 0.10 归入该组;组按发现序命名 g1、g2…。仅 ≥2 成员的组落 group id,
    单帧 dedup_group=None;所有 frame media 均写 dedup_primary(唯一性归 slide 视图层,
    宿主仲裁只改标注:拆组/换 primary)。"""
    picked = [(nd, m) for nd in _walk(sb["outline"]) for m in (nd.get("media") or [])
              if m.get("type") == "frame" and m.get("proxy_path")]
    picked.sort(key=lambda nm: -(nm[1].get("score") or 0))
    groups: list[dict] = []
    for nd, m in picked:
        sig = rgb_signature(m["proxy_path"])
        for g in groups:
            if sig_diff_ratio(sig, g["sig"]) < 0.10:
                g["members"].append((nd, m))
                break
        else:
            groups.append({"sig": sig, "members": [(nd, m)]})
    report = {"groups": []}
    for g in groups:
        if len(g["members"]) == 1:
            g["members"][0][1].update(dedup_group=None, dedup_primary=True)
            continue
        gid = f"g{len(report['groups']) + 1}"
        for rank, (nd, m) in enumerate(g["members"]):
            m.update(dedup_group=gid, dedup_primary=rank == 0)   # 首位即组内最高分
        report["groups"].append({"group": gid,
                                 "members": [{"node": nd["id"], "t": m.get("t")}
                                             for nd, m in g["members"]]})
    return report


def aggregate_media(outline: list, depth: int, k: int = 2) -> dict:
    """深度 ≤depth 的节点若有更深子树,聚合子树叶子 media 按 score 降序取 k(spec §6:纯排序,不碰视频)。"""
    agg = {}

    def leaves_below(nd):
        """递归收集节点下所有叶子节点的 media。"""
        if not nd.get("children"):
            return list(nd.get("media") or [])
        return [m for c in nd["children"] for m in leaves_below(c)]

    def walk(nodes):
        """遍历节点,在目标深度或叶子处收集聚合 media。"""
        for nd in nodes:
            if nd.get("level", 1) == depth or not nd.get("children"):
                ms = sorted(leaves_below(nd), key=lambda m: -(m.get("score") or 0))[:k]
                agg[nd["id"]] = ms
            elif nd.get("level", 1) < depth:
                walk(nd["children"])
    walk(outline)
    return agg


def main() -> int:
    """CLI: validate/dedup/aggregate."""
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["validate", "dedup", "aggregate"])
    ap.add_argument("--work", required=True)
    ap.add_argument("--depth", type=int, default=2)
    args = ap.parse_args()
    work = Path(args.work)
    sb = load_json(wp(work, "storyboard"))

    if args.cmd == "validate":
        duration = load_json(wp(work, "meta"))["duration"]
        r = validate(sb, load_json(wp(work, "transcript")), duration)
        plan_p = wp(work, "chapter_plan")
        if plan_p.exists():                        # 可选制品:缺失时行为与现状一致(切片3)
            ch_errs = validate_chapter_plan(load_json(plan_p), sb.get("outline") or [], duration)
            if ch_errs:
                r["chapter_errors"] = ch_errs
                r["ok"] = False
        emit(f"validate: {'通过' if r['ok'] else '不通过'}",
             *(f"  {k}: {v}" for k, v in r.items() if k != "ok" and v))
        return 0 if r["ok"] else 5
    if args.cmd == "dedup":
        rep = dedup_across_nodes(sb)
        save_json(wp(work, "storyboard"), sb)
        emit(f"跨要点去重标注: 重复组 {len(rep['groups'])}(不删除,唯一性由 slide 视图层执行)",
             *(f"  {g['group']}: " + ", ".join(f"{x['node']}@{x['t']}" for x in g["members"])
               for g in rep["groups"]))
        return 0
    import json
    print(json.dumps(aggregate_media(sb["outline"], args.depth), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
