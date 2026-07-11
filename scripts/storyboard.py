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
    r["ok"] = not (r["schema_errors"] or r["quote_failures"] or r["time_errors"])
    return r


def dedup_across_nodes(sb: dict, candidates: list[dict]) -> dict:
    """跨要点媒体唯一性(spec §6):分高者优先保位,重复者回退未用候选,耗尽降纯文字。"""
    picked = [(nd, m) for nd in _walk(sb["outline"]) for m in (nd.get("media") or [])
              if m.get("type") == "frame" and m.get("proxy_path")]
    picked.sort(key=lambda nm: -(nm[1].get("score") or 0))
    kept_sigs: list[bytes] = []
    used = {m["proxy_path"] for _, m in picked}
    report = {"replaced": [], "dropped": []}
    for nd, m in picked:
        sig = rgb_signature(m["proxy_path"])
        if all(sig_diff_ratio(sig, k) >= 0.10 for k in kept_sigs):
            kept_sigs.append(sig)
            continue
        alts = sorted((c for c in candidates
                       if c["node_id"] == nd["id"] and not c.get("dup") and c["file"] not in used),
                      key=lambda c: -(c.get("score") or 0))
        for alt in alts:
            alt_sig = rgb_signature(alt["file"])
            if all(sig_diff_ratio(alt_sig, k) >= 0.10 for k in kept_sigs):
                report["replaced"].append({"node": nd["id"], "from": m["proxy_path"], "to": alt["file"]})
                m.update(proxy_path=alt["file"], t=alt["t"], score=alt.get("score", 0), reason=alt["reason"])
                used.add(alt["file"])
                kept_sigs.append(alt_sig)
                break
        else:
            nd["media"].remove(m)       # 候选耗尽:该要点转纯文字(spec §11)
            report["dropped"].append(nd["id"])
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
        r = validate(sb, load_json(wp(work, "transcript")), load_json(wp(work, "meta"))["duration"])
        emit(f"validate: {'通过' if r['ok'] else '不通过'}",
             *(f"  {k}: {v}" for k, v in r.items() if k != "ok" and v))
        return 0 if r["ok"] else 5
    if args.cmd == "dedup":
        rep = dedup_across_nodes(sb, load_json(wp(work, "candidates")))
        save_json(wp(work, "storyboard"), sb)
        emit(f"跨要点去重: 替换 {len(rep['replaced'])},降纯文字 {len(rep['dropped'])}")
        return 0
    import json
    print(json.dumps(aggregate_media(sb["outline"], args.depth), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
