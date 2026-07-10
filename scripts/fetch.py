"""下载层:URL 归一化、yt-dlp 元数据/先验、代理流与字幕下载(spec §3 下载层)。"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

from common import emit, is_fresh, load_json, run, save_json, wp


def _yt(vid: str) -> dict:
    return {
        "platform": "youtube", "vid": vid, "part": None,
        "canonical_url": f"https://www.youtube.com/watch?v={vid}",
        "badge_url_template": f"https://www.youtube.com/watch?v={vid}&t={{t}}s",
    }


def normalize_url(url: str) -> dict:
    u = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(u.query)
    host = u.netloc.lower()
    if "youtu.be" in host:
        return _yt(u.path.strip("/").split("/")[0])
    if "youtube.com" in host:
        vid = q.get("v", [None])[0]
        if not vid:
            raise ValueError(f"无法解析 YouTube 视频 id: {url}")
        return _yt(vid)
    if "bilibili.com" in host:
        m = re.search(r"/video/(BV[0-9A-Za-z]+)", u.path)
        if not m:
            raise ValueError(f"无法解析 B 站 BV 号: {url}")
        bv, part = m.group(1), int(q.get("p", ["1"])[0])
        # 分 P 合集必须显式带 p,否则 yt-dlp 枚举全部分 P(spec §2 实测)
        return {
            "platform": "bilibili", "vid": bv, "part": part,
            "canonical_url": f"https://www.bilibili.com/video/{bv}?p={part}",
            "badge_url_template": f"https://www.bilibili.com/video/{bv}?p={part}&t={{t}}",
        }
    raise ValueError(f"不支持的输入源: {url}")


def parse_metadata(info: dict) -> tuple[dict, dict]:
    meta = {
        "title": info.get("title") or "",
        "duration": float(info.get("duration") or 0),
        "language": info.get("language"),
        "uploader": info.get("uploader"),
    }
    chapters = [
        {"title": c.get("title", ""), "t_start": float(c["start_time"]), "t_end": float(c["end_time"])}
        for c in (info.get("chapters") or [])
    ]
    heatmap = [
        {"t_start": float(h["start_time"]), "t_end": float(h["end_time"]), "value": float(h["value"])}
        for h in (info.get("heatmap") or [])
    ]
    # priors 全部 fail-open:缺失置空,禁止因信号缺失中断(spec §6)
    return meta, {"chapters": chapters, "heatmap": heatmap, "danmaku_density": [], "page_boundaries": []}


def pick_subtitle_track(subtitles: dict, automatic: dict, video_lang: str | None):
    subs, autos = subtitles or {}, automatic or {}
    lang = (video_lang or "").lower()
    lang2 = lang[:2]

    def by_lang(keys):
        keys = [k for k in keys if k != "danmaku"]   # danmaku 永不入选,任何路径
        if not lang:
            return None
        exact = next((k for k in keys if k.lower() == lang), None)
        if exact:
            return exact                              # 精确匹配优先于前缀匹配
        return next((k for k in keys if k.lower().startswith(lang2)), None)

    manual = [k for k in subs if k != "danmaku" and not k.startswith("ai-")]
    if manual:
        return ("manual", by_lang(manual) or manual[0])
    ai = [k for k in subs if k.startswith("ai-")]
    if ai:
        return ("ai", by_lang(ai) or ai[0])
    k = by_lang(autos)
    return ("auto", k) if k else None


def _ytdlp_base(source: dict, cookies_from_browser: str | None) -> list:
    cmd = ["yt-dlp", "--no-playlist"]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    return cmd + [source["canonical_url"]]


def fetch_meta(source: dict, work: Path, cookies: str | None, force: bool) -> dict:
    meta_p, priors_p, raw_p = wp(work, "meta"), wp(work, "priors"), wp(work, "raw_info")
    if not force and is_fresh(meta_p) and is_fresh(priors_p):
        return load_json(meta_p)
    cmd = _ytdlp_base(source, cookies)
    cmd[-1:-1] = ["-J", "--skip-download"]
    info = json.loads(run(cmd, timeout=180))
    info.pop("formats", None)  # 体积大且无下游消费者,裁掉再落盘
    save_json(raw_p, info)
    meta, priors = parse_metadata(info)
    meta["source"] = source
    save_json(meta_p, meta)
    save_json(priors_p, priors)
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--cookies-from-browser", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    source = normalize_url(args.url)
    meta = fetch_meta(source, work, args.cookies_from_browser, args.force)
    emit(
        f"meta: {wp(work, 'meta')}({meta['title'][:40]},{meta['duration']:.0f}s)",
        f"priors: {wp(work, 'priors')}",
        next_hint="下一步在 Task 4 补代理流与字幕下载",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
