"""markdown 笔记渲染器(spec v0.5 §9.5):video_index 导出契约的第二消费方,兼契约完备性验收器。

硬规则:输入仅限 video_index.json + frames/,禁碰 .work/ ——契约缺字段/缺资产立刻失败(exit 5),
禁止静默绕过。确定性、零 token、stdlib-only。输出语言跟随文档内大纲语言,本渲染器不做翻译。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import emit


class AssetMissing(Exception):
    """文档引用的帧资产不存在(自包含承诺被破坏)。"""


def fmt_ts(t: float) -> str:
    """秒 → mm:ss(超 1h 用 h:mm:ss)。"""
    s = int(t or 0)
    if s >= 3600:
        return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"
    return f"{s // 60:02d}:{s % 60:02d}"


def ts_link(t: float, badge: str | None) -> str:
    """时间戳呈现:有 badge 模板出跳转链接;platform=local(badge 为 null)退化纯文本(spec v0.5 §9.5)。"""
    if badge:
        return f"[{fmt_ts(t)}]({badge.replace('{t}', str(int(t or 0)))})"
    return fmt_ts(t)


def _render(doc: dict, base: Path, depth: int) -> list[str]:
    """契约字段一律用 [] 取值:缺字段抛 KeyError,由上层转 exit 5——这就是验收器的失败姿态。"""
    v, tr = doc["video"], doc["transcript"]
    badge = v["badge_url_template"]
    seg_t = {s["id"]: s["t_start"] for s in tr["segments"]}
    lines = [f"# {v['title']}", "",
             f"> 来源:{v['source_url']} · {v.get('uploader') or '未知'} · 时长 {fmt_ts(v['duration'])}",
             f"> 由 video2slides 索引文档渲染(schema {doc['schema_version']};时间戳精度 {tr['timestamp_granularity']})"]
    if tr["timestamp_granularity"] == "chunk-45s":
        lines.append("> 注:时间戳为 45s 块级精度,跳转为近似定位")
    lines.append("")

    def walk(nodes):
        for nd in nodes:
            if nd["level"] > depth:
                continue
            lines.append(f"{'#' * (nd['level'] + 1)} {nd['title']} · {ts_link(nd['t_start'], badge)}")
            lines.append("")
            if nd["summary"]:
                lines.extend([nd["summary"], ""])
            for m in nd["media"]:
                if m["type"] == "frame":
                    if not (base / m["path"]).exists():
                        raise AssetMissing(m["path"])
                    cap = ts_link(m["t"], badge)
                    if m["dedup_group"]:        # 契约必选字段,缺失即 KeyError(验收器牙齿)
                        cap += f"(画面与同组要点共用:{m['dedup_group']})"
                    lines.extend([f"![{fmt_ts(m['t'])}]({m['path']})", f"*{cap}*", ""])
                elif m["type"] == "clip":
                    span = f"{fmt_ts(m['t_start'])}–{fmt_ts(m['t_end'])}"
                    tail = f"(回源播放:{ts_link(m['t_start'], badge)})" if badge else ""
                    lines.extend([f"*动态片段 {span}{tail}*", ""])
            for ev in nd["evidence"]:
                lines.append(f"> 「{ev['quote']}」 —— {ts_link(seg_t[ev['segment_id']], badge)}")
            lines.append("")
            if nd["level"] < depth:
                walk(nd["children"])

    walk(doc["outline"])
    return lines


def render_notes(index_path: Path | str, depth: int = 2) -> int:
    """读 video_index.json 渲染 <同目录>/notes.md;契约缺字段/缺资产 exit 5,不产出残缺笔记。"""
    index_path = Path(index_path)
    base = index_path.parent
    if not index_path.exists():
        emit(f"索引文档不存在: {index_path}")
        return 5
    try:
        doc = json.loads(index_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        emit(f"索引文档非法 JSON,拒绝渲染: {e}")
        return 5
    try:
        lines = _render(doc, base, depth)
    except KeyError as e:
        emit(f"契约缺字段,拒绝渲染: {e}")
        return 5
    except AssetMissing as e:
        emit(f"帧资产缺失,拒绝渲染: {e}")
        return 5
    out_p = base / "notes.md"
    out_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    emit(f"notes: {out_p}(depth={depth})")
    return 0


def main() -> int:
    """CLI:python scripts/notes.py --index <OUT>/video_index.json [--depth N]。"""
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True, help="video_index.json 路径(输出 notes.md 到同目录)")
    ap.add_argument("--depth", type=int, default=2, help="展开层级:短→1 中→2 长→3,不足全展开")
    args = ap.parse_args()
    return render_notes(args.index, depth=args.depth)


if __name__ == "__main__":
    sys.exit(main())
