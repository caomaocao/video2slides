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


def proxy_format_selector() -> str:
    # 代理流:≤360p 仅视频轨(分析不需音频;ASR/clip 需要时再拉,spec §8.0)
    return "bv*[height<=360][ext=mp4]/bv*[height<=360]/b[height<=360]"


def fetch_proxy(source: dict, work: Path, cookies: str | None, force: bool) -> Path:
    proxy = wp(work, "proxy")
    if not force and is_fresh(proxy):
        return proxy
    cmd = _ytdlp_base(source, cookies)
    cmd[-1:-1] = ["-f", proxy_format_selector(), "--remux-video", "mp4",
                  "-o", str(work / "proxy.%(ext)s")]
    run(cmd, timeout=1800)
    if not proxy.exists():
        raise RuntimeError(f"代理流未产出: {proxy}")
    return proxy


def subs_download_cmd(source: dict, track: tuple[str, str], work: Path, cookies: str | None) -> list:
    kind, lang = track
    cmd = _ytdlp_base(source, cookies)
    flag = "--write-auto-subs" if kind == "auto" else "--write-subs"
    cmd[-1:-1] = ["--skip-download", flag, "--sub-langs", lang,
                  "-o", str(wp(work, "subs_dir") / "sub")]
    return cmd


def fetch_subs(source: dict, work: Path, cookies: str | None, force: bool):
    meta_p = wp(work, "meta")
    meta = load_json(meta_p)
    subs_dir = wp(work, "subs_dir")
    if not force and meta.get("subtitle") and Path(meta["subtitle"]["path"]).exists():
        return meta["subtitle"]
    info = load_json(wp(work, "raw_info"))
    track = pick_subtitle_track(info.get("subtitles"), info.get("automatic_captions"), meta.get("language"))
    if track is None:
        return None
    subs_dir.mkdir(parents=True, exist_ok=True)
    run(subs_download_cmd(source, track, work, cookies), timeout=300)
    # 精确匹配刚下载的目标轨文件(yt-dlp 命名 sub.<lang>.<ext>),避免残留旧语言文件按字母序被错选
    files = [f for f in sorted(subs_dir.glob(f"sub.{track[1]}.*")) if f.suffix in {".vtt", ".srt"}]
    if not files:
        files = sorted(list(subs_dir.glob("sub*.vtt")) + list(subs_dir.glob("sub*.srt")))
    if not files:
        return None
    sub = {"kind": track[0], "lang": track[1], "path": str(files[0])}
    meta["subtitle"] = sub
    save_json(meta_p, meta)
    return sub


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
    proxy = fetch_proxy(source, work, args.cookies_from_browser, args.force)
    sub = fetch_subs(source, work, args.cookies_from_browser, args.force)
    if sub is None:
        print("无可用字幕轨——切片范围外,需 ASR(spec §10.1 三家族)或 --transcript")
        return 3
    emit(
        f"meta: {wp(work, 'meta')}({meta['title'][:40]},{meta['duration']:.0f}s)",
        f"priors: {wp(work, 'priors')}",
        f"proxy: {proxy}",
        f"subs: {sub['path']}({sub['kind']}/{sub['lang']})",
        next_hint=f"python scripts/transcribe.py --work {work}",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
