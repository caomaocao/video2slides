"""storyboard.json 校验、渲染前置聚合与 video_index 导出(spec §6、§6.5、§7 引用校验、§8.4 前置)。"""
from __future__ import annotations

import argparse
import difflib
import re
import shutil
import sys
from pathlib import Path

from common import emit, is_fresh, load_json, rgb_signature, save_json, sig_diff_ratio, wp

_PUNCT = re.compile(r"[\s,，。、.!！?？:：;；\"'“”‘’()（）\[\]【】《》<>—\-…·]+")
REQUIRED_NODE_KEYS = ("id", "title", "t_start", "t_end", "evidence")
# 切片3 分章校验容差:CH_L1_TOL 容纳 chat 家族 45s 块级时间戳的边界微调(最坏 22.5s)
CH_EDGE_TOL, CH_SEAM_TOL, CH_L1_TOL = 1.0, 0.5, 30.0

# 导出契约(spec v0.5 §6.5):规范本体在 schemas/video_index.schema.json,此处为运行期 stdlib 校验子集
SCHEMA_VERSION = "1.0.0"
PROXY_RESOLUTION = "proxy-360p"
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_PLATFORMS = {"youtube", "bilibili", "local"}
_GRANULARITIES = {"segment", "sentence", "chunk-45s"}
_ASR_GRANULARITY = {"mimo": "chunk-45s", "qwen": "chunk-45s", "funasr": "sentence"}


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


DUP_RATIO = 0.10            # 判重阈值(2026-07-11 于 #13 标定,见 common.sig_diff_ratio 注释)
DUP_RATIO_NO_VISION = 0.05  # 无视觉宿主:抬合并门(实为降阈)→ 宁欠勿并,只并近乎同帧(build ≤0.04),
                            # 以「可见重复页」换「绝不静默吞掉不同讲义页」(跨平台 spec §视觉能力处理 6a)


def dedup_across_nodes(sb: dict, no_vision: bool = False) -> dict:
    """跨要点媒体去重标注(spec v0.5 §6):重复组打 dedup_group/dedup_primary,不删除、不替换。

    分组:按 score 降序遍历,与各组代表(即组内 primary,遍历序首个成员)签名比对,
    变化占比 < 阈值归入该组;组按发现序命名 g1、g2…。仅 ≥2 成员的组落 group id,
    单帧 dedup_group=None;所有 frame media 均写 dedup_primary(唯一性归 slide 视图层,
    宿主仲裁只改标注:拆组/换 primary)。

    no_vision=True(宿主无视觉、无目验仲裁):用更严阈值 DUP_RATIO_NO_VISION 宁欠勿并——
    偏可见重复页、不静默吞掉不同讲义页(跨平台 spec §视觉能力处理 6a)。"""
    thr = DUP_RATIO_NO_VISION if no_vision else DUP_RATIO
    picked = [(nd, m) for nd in _walk(sb["outline"]) for m in (nd.get("media") or [])
              if m.get("type") == "frame" and m.get("proxy_path")]
    picked.sort(key=lambda nm: -(nm[1].get("score") or 0))
    groups: list[dict] = []
    for nd, m in picked:
        sig = rgb_signature(m["proxy_path"])
        for g in groups:
            if sig_diff_ratio(sig, g["sig"]) < thr:
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


def _granularity(source: str) -> str:
    """时间戳精度推导(spec v0.5 §6.5):chat 家族块级、funasr 句级,其余(字幕/transcriptions)段级。"""
    if (source or "").startswith("asr:"):
        return _ASR_GRANULARITY.get(source.split(":", 1)[1], "segment")
    return "segment"


def _claim_copy(src, name: str, copies: dict, errors: list, nid: str):
    """登记一份待拷贝媒体,返回导出相对路径;同一源文件复用同一目标(poster 与帧共享)。"""
    if not src:
        errors.append(f"节点 {nid} media 缺源文件路径")
        return None
    if src in copies:
        return copies[src]
    if not Path(src).exists():
        errors.append(f"节点 {nid} 媒体源文件不存在: {src}")
        return None
    rel, n = f"frames/{name}", 2
    while rel in copies.values():           # 撞名(同节点同秒双帧)加序号
        stem, _, ext = name.rpartition(".")
        rel = f"frames/{stem}_{n}.{ext}"
        n += 1
    copies[src] = rel
    return rel


def _export_nodes(nodes, copies: dict, errors: list, stats: dict) -> list:
    """递归把内部大纲节点归一化为导出形态:内部字段(proxy_path/finalized/on_page)不外泄。"""
    out_nodes = []
    for nd in nodes or []:
        nid = str(nd.get("id", "?"))
        media_out = []
        for m in nd.get("media") or []:
            if m.get("type") == "frame":
                rel = _claim_copy(m.get("proxy_path"), f"{nid}_{(m.get('t') or 0):.1f}.jpg",
                                  copies, errors, nid)
                if "dedup_primary" not in m:
                    stats["dedup_defaulted"] = stats.get("dedup_defaulted", 0) + 1
                media_out.append({"type": "frame", "path": rel, "t": m.get("t"),
                                  "resolution": PROXY_RESOLUTION,
                                  "score": m.get("score"), "reason": m.get("reason"),
                                  "dedup_group": m.get("dedup_group"),
                                  "dedup_primary": m.get("dedup_primary", True)})
            elif m.get("type") == "clip":
                poster = (_claim_copy(m.get("poster"), f"{nid}_poster_{(m.get('t_start') or 0):.1f}.jpg",
                                      copies, errors, nid) if m.get("poster") else None)
                media_out.append({"type": "clip", "t_start": m.get("t_start"),
                                  "t_end": m.get("t_end"), "poster": poster,
                                  "reason": m.get("reason")})
        out_nodes.append({"id": nid, "level": nd.get("level"), "title": nd.get("title"),
                          "summary": nd.get("summary") or "",
                          "t_start": nd.get("t_start"), "t_end": nd.get("t_end"),
                          "evidence": nd.get("evidence") or [],
                          "media": media_out,
                          "children": _export_nodes(nd.get("children"), copies, errors, stats)})
    return out_nodes


def _export_video_block(sb_video: dict | None, meta: dict) -> dict:
    """video 块:storyboard.video(宿主写入的语义字段)为底,meta/source 补机械字段;signals 指向 .work 不外泄。"""
    src = meta.get("source") or {}
    v = {k: val for k, val in (sb_video or {}).items() if k != "signals"}
    v.update(title=meta.get("title") or v.get("title") or "",
             duration=float(meta.get("duration") or v.get("duration") or 0),
             uploader=meta.get("uploader"),
             language=meta.get("language") or v.get("language"),
             platform=src.get("platform"),
             source_url=src.get("canonical_url") or src.get("path"),
             badge_url_template=src.get("badge_url_template"))
    v.setdefault("genre", None)
    v.setdefault("visual_form", [])
    v.setdefault("priors", {})
    return v


def validate_index(doc: dict) -> list[str]:
    """导出契约的运行期校验(stdlib 手写子集;测试以 jsonschema 对拍 schemas/ 规范防漂移)。"""
    errs: list[str] = []
    if not _SEMVER.match(doc.get("schema_version") or ""):
        errs.append("schema_version 非语义化版本")
    v = doc.get("video") or {}
    if v.get("platform") not in _PLATFORMS:
        errs.append(f"platform 非法: {v.get('platform')}")
    duration = v.get("duration")
    if not isinstance(duration, (int, float)) or duration <= 0:
        errs.append("video.duration 必须为正数")
        duration = float("inf")
    badge = v.get("badge_url_template")
    if v.get("platform") == "local":
        if badge is not None:
            errs.append("platform=local 的 badge_url_template 应为 null")
    elif not (isinstance(badge, str) and "{t}" in badge):
        errs.append("badge_url_template 缺 {t} 占位")
    tr = doc.get("transcript") or {}
    if tr.get("timestamp_granularity") not in _GRANULARITIES:
        errs.append(f"timestamp_granularity 非法: {tr.get('timestamp_granularity')}")
    seg_text: dict = {}
    for s in tr.get("segments") or []:
        sid = s.get("id")
        if not isinstance(sid, int) or sid in seg_text:
            errs.append(f"segment id 非法或重复: {sid}")
            continue
        seg_text[sid] = s.get("text") or ""
    if not seg_text:
        errs.append("transcript.segments 为空")
    groups: dict[str, int] = {}

    def walk(nodes):
        for nd in nodes or []:
            nid = nd.get("id", "?")
            missing = [k for k in ("id", "level", "title", "summary", "t_start", "t_end",
                                   "evidence", "media", "children") if k not in nd]
            if missing:
                errs.append(f"节点 {nid} 缺字段: {missing}")
            if not nd.get("evidence"):
                errs.append(f"节点 {nid} evidence 为空")
            ts, te = nd.get("t_start"), nd.get("t_end")
            if not (isinstance(ts, (int, float)) and isinstance(te, (int, float))
                    and 0 <= ts < te <= duration + 1):
                errs.append(f"节点 {nid} 时间窗非法: [{ts}, {te}]")
            for ev in nd.get("evidence") or []:
                seg = seg_text.get(ev.get("segment_id"))
                if seg is None:
                    errs.append(f"节点 {nid} evidence 指向不存在的 segment: {ev.get('segment_id')}")
                elif not quote_ok(ev.get("quote", ""), seg):
                    errs.append(f"节点 {nid} quote 不在所引段原文中: {ev.get('quote', '')!r}")
            for m in nd.get("media") or []:
                if m.get("type") == "frame":
                    if not (isinstance(m.get("path"), str) and m["path"].startswith("frames/")):
                        errs.append(f"节点 {nid} frame path 非 frames/ 相对路径: {m.get('path')}")
                    if not isinstance(m.get("t"), (int, float)):
                        errs.append(f"节点 {nid} frame 缺数值 t")
                    if not (isinstance(m.get("resolution"), str) and m["resolution"]):
                        errs.append(f"节点 {nid} frame 缺 resolution")
                    if not isinstance(m.get("dedup_primary"), bool):
                        errs.append(f"节点 {nid} frame 缺 dedup_primary 布尔")
                    if m.get("dedup_group"):
                        groups[m["dedup_group"]] = (groups.get(m["dedup_group"], 0)
                                                    + bool(m.get("dedup_primary")))
                elif m.get("type") == "clip":
                    if not (isinstance(m.get("t_start"), (int, float))
                            and isinstance(m.get("t_end"), (int, float))):
                        errs.append(f"节点 {nid} clip 缺数值 t_start/t_end")
                    if m.get("poster") is not None and not str(m["poster"]).startswith("frames/"):
                        errs.append(f"节点 {nid} clip poster 非 frames/ 相对路径")
                else:
                    errs.append(f"节点 {nid} media type 非法: {m.get('type')}")
            walk(nd.get("children"))

    if not doc.get("outline"):
        errs.append("outline 为空")
    walk(doc.get("outline"))
    for gid, n_primary in groups.items():
        if n_primary != 1:
            errs.append(f"dedup 组 {gid} 的 primary 数为 {n_primary},应恰为 1")
    return errs


def export_index(work: Path | str, force: bool = False) -> int:
    """打包导出(spec v0.5 §6.5):组装 video_index.json + frames/,机械校验不过则不产出(exit 5)。
    导出物只读、自包含(整 <OUT> 可迁移,删 .work/ 不断链);制品新于上游时跳过(续跑契约)。"""
    work = Path(work)
    out_dir = work.parent
    doc_p = out_dir / "video_index.json"
    ups = [wp(work, "storyboard"), wp(work, "transcript"), wp(work, "meta")]
    if not force and is_fresh(doc_p, *ups):
        emit(f"video_index: {doc_p}(已最新,跳过)")
        return 0
    sb, transcript, meta = (load_json(p) for p in ups)
    copies: dict[str, str] = {}
    errors: list[str] = []
    stats: dict[str, int] = {}
    doc = {"schema_version": SCHEMA_VERSION,
           "generator": {"skill": "video2slides", "spec": "v0.5"},
           "video": _export_video_block(sb.get("video"), meta),
           "transcript": {"source": transcript.get("source") or "",
                          "timestamp_granularity": _granularity(transcript.get("source") or ""),
                          "segments": transcript.get("segments") or []},
           "outline": _export_nodes(sb.get("outline"), copies, errors, stats)}
    errors += validate_index(doc)
    if errors:
        emit("export: 契约校验不通过,不产出文档(宁缺毋滥)", *(f"  {e}" for e in errors))
        return 5
    (out_dir / "frames").mkdir(parents=True, exist_ok=True)
    for src, rel in copies.items():
        shutil.copy2(src, out_dir / rel)
    save_json(doc_p, doc)
    if stats.get("dedup_defaulted"):
        emit(f"提示: {stats['dedup_defaulted']} 条 media 无 dedup 标注,按默认值导出"
             "(group=null/primary=true)——建议先跑 storyboard.py dedup 再导出")
    emit(f"video_index: {doc_p}({len(copies)} 帧资产,schema {SCHEMA_VERSION})")
    return 0


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
    """CLI: validate/dedup/aggregate/export."""
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["validate", "dedup", "aggregate", "export"])
    ap.add_argument("--work", required=True)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-vision", action="store_true",
                    help="无视觉宿主:dedup 抬合并门(宁欠勿并),避免静默吞掉不同讲义页")
    args = ap.parse_args()
    work = Path(args.work)
    if args.cmd == "export":
        return export_index(work, force=args.force)
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
        rep = dedup_across_nodes(sb, no_vision=args.no_vision)
        save_json(wp(work, "storyboard"), sb)
        mode = "(无视觉:宁欠勿并)" if args.no_vision else ""
        emit(f"跨要点去重标注{mode}: 重复组 {len(rep['groups'])}(不删除,唯一性由 slide 视图层执行)",
             *(f"  {g['group']}: " + ", ".join(f"{x['node']}@{x['t']}" for x in g["members"])
               for g in rep["groups"]))
        return 0
    import json
    print(json.dumps(aggregate_media(sb["outline"], args.depth), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
