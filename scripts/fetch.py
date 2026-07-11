"""下载层:URL 归一化、yt-dlp 元数据/先验、代理流与字幕下载(spec §3 下载层)。"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

from common import emit, ffprobe_duration, is_fresh, load_env_config, load_json, run, save_json, wp
from transcribe import resolve_asr_config


def _yt(vid: str) -> dict:
    return {
        "platform": "youtube", "vid": vid, "part": None,
        "canonical_url": f"https://www.youtube.com/watch?v={vid}",
        "badge_url_template": f"https://www.youtube.com/watch?v={vid}&t={{t}}s",
    }


def normalize_url(url: str) -> dict:
    # 本地文件输入优先(spec §2):无跳转 URL,渲染用内嵌播放器;必走 ASR/--transcript
    p = Path(url).expanduser()
    if p.exists() and p.is_file():
        return {"platform": "local", "vid": p.stem, "part": None, "path": str(p.resolve()),
                "canonical_url": None, "badge_url_template": None}
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


def _local_meta(path: Path) -> tuple[dict, dict]:
    """本地元数据:同名 .json sidecar(视频号格式)优先,缺失 fail-open(ffprobe 时长/文件名标题)。"""
    side = path.with_suffix(".json")
    title, uploader, duration = path.stem, None, None
    if side.exists():
        try:
            d = json.loads(side.read_text(encoding="utf-8"))
            title = d.get("title") or title
            uploader = d.get("nickname")
            duration = float((d.get("media") or {}).get("duration") or 0) or None
        except (json.JSONDecodeError, TypeError, ValueError):
            pass                                       # sidecar 损坏按缺失处理
    if duration is None:
        duration = ffprobe_duration(path)
    meta = {"title": title, "duration": duration, "language": None, "uploader": uploader}
    return meta, {"chapters": [], "heatmap": [], "danmaku_density": [], "page_boundaries": []}


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
        # ai-* 轨按去前缀后的语言参与匹配;danmaku 永不入选,任何路径
        pairs = [(k, k[3:] if k.startswith("ai-") else k) for k in keys if k != "danmaku"]
        if not lang:
            return None
        exact = next((k for k, base in pairs if base.lower() == lang), None)
        if exact:
            return exact                              # 精确匹配优先于前缀匹配
        return next((k for k, base in pairs if base.lower().startswith(lang2)), None)

    manual = [k for k in subs if k != "danmaku" and not k.startswith("ai-")]
    ai = [k for k in subs if k.startswith("ai-")]
    # 语言匹配跨层优先:语言不符的 manual 轨(整条 transcript 都是外语)不如语言匹配的
    # ai/auto 轨——2026-07-11 批量试产 #3 实测:en-US 视频 manual 只有 ar/es/hi/id/zh,
    # 旧逻辑兜底取字典序第一个(阿拉伯语),大纲语言整个跑偏
    for kind, keys in (("manual", manual), ("ai", ai), ("auto", list(autos))):
        k = by_lang(keys)
        if k:
            return (kind, k)
    if manual:
        return ("manual", manual[0])
    if ai:
        # B 站多语 ai 轨中 ai-zh 通常是原声轨、其余为机翻(启发式):无视频语言信息时优先 ai-zh
        return ("ai", "ai-zh" if "ai-zh" in ai else ai[0])
    return None


def _ytdlp_base(source: dict, cookies_from_browser: str | None) -> list:
    cmd = ["yt-dlp", "--no-playlist"]
    if cookies_from_browser:
        cmd += ["--cookies-from-browser", cookies_from_browser]
    return cmd + [source["canonical_url"]]


def fetch_meta(source: dict, work: Path, cookies: str | None, force: bool) -> dict:
    meta_p, priors_p, raw_p = wp(work, "meta"), wp(work, "priors"), wp(work, "raw_info")
    if not force and is_fresh(meta_p) and is_fresh(priors_p):
        return load_json(meta_p)
    # 本地文件分支:不调 yt-dlp,不落 raw_info
    if source["platform"] == "local":
        meta, priors = _local_meta(Path(source["path"]))
        meta["source"] = source
        save_json(meta_p, meta)
        save_json(priors_p, priors)
        return meta
    cmd = _ytdlp_base(source, cookies)
    # --write-subs/--write-auto-subs 触发 yt-dlp 的惰性字幕提取门:B 站等提取器
    # 仅在这些参数存在时才调字幕 API,裸 -J 会得到空 subtitles(2026-07-11 验收 #11 实测);
    # -J 隐含 simulate,不会真正下载字幕文件,对 YouTube 无副作用
    cmd[-1:-1] = ["-J", "--skip-download", "--write-subs", "--write-auto-subs"]
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
    # 本地文件分支:ffmpeg 降采样代理
    if source["platform"] == "local":
        run(["ffmpeg", "-y", "-v", "error", "-i", source["path"],
             "-vf", "scale=-2:360", "-an", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "28", str(proxy)], timeout=3600)
    else:
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
    # 本地无字幕源,必走 ASR/--transcript(spec §2)
    if source["platform"] == "local":
        return None
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


def fetch_audio(source: dict, work: Path, cookies: str | None, force: bool) -> Path:
    """音频轨懒抓(仅无字幕轨且 ASR 可用时调用):在线走 yt-dlp -x,本地走 ffmpeg 抽轨。"""
    audio = wp(work, "audio")
    if not force and is_fresh(audio):
        return audio
    if source["platform"] == "local":
        run(["ffmpeg", "-y", "-v", "error", "-i", source["path"], "-vn",
             "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1", str(audio)], timeout=3600)
    else:
        cmd = _ytdlp_base(source, cookies)
        cmd[-1:-1] = ["-f", "ba", "-x", "--audio-format", "mp3", "--audio-quality", "64K",
                      "-o", str(work / "audio.%(ext)s")]
        run(cmd, timeout=3600)
    if not audio.exists():
        raise RuntimeError(f"音频轨未产出: {audio}")
    return audio


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--cookies-from-browser", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    source = normalize_url(args.url)
    meta = fetch_meta(source, work, args.cookies_from_browser, args.force)
    proxy = fetch_proxy(source, work, args.cookies_from_browser, args.force)
    sub = fetch_subs(source, work, args.cookies_from_browser, args.force)
    if sub is None:
        # 无字幕轨时尝试 ASR 流程
        try:
            cfg = resolve_asr_config(load_env_config())
        except ValueError as e:
            emit(f"无可用字幕轨,且 ASR 配置无效:{e}")
            return 3
        if cfg["family"] == "none":
            emit("无可用字幕轨——ASR_BACKEND=none,需改配后端(funasr/mimo/qwen…)或提供 --transcript(spec §10.1)")
            return 3
        audio = fetch_audio(source, work, args.cookies_from_browser, args.force)
        emit(f"audio: {audio}(无字幕轨 → ASR:{cfg['backend']})",
             next_hint=f"python scripts/transcribe.py --work {work}")
        return 0
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
