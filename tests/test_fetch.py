import json
from pathlib import Path

import pytest

import fetch

FIX = Path(__file__).parent / "fixtures"


def test_normalize_youtube_watch_and_short():
    for url in ["https://www.youtube.com/watch?v=QNiaoD5RxPA", "https://youtu.be/QNiaoD5RxPA"]:
        s = fetch.normalize_url(url)
        assert s["platform"] == "youtube" and s["vid"] == "QNiaoD5RxPA" and s["part"] is None
        assert s["badge_url_template"] == "https://www.youtube.com/watch?v=QNiaoD5RxPA&t={t}s"


def test_normalize_bilibili_default_p1_and_explicit_p():
    s1 = fetch.normalize_url("https://www.bilibili.com/video/BV1k44LzPEhU")
    assert s1["part"] == 1 and s1["canonical_url"].endswith("?p=1")
    s2 = fetch.normalize_url("https://www.bilibili.com/video/BV1k44LzPEhU?p=2")
    assert s2["part"] == 2
    assert s2["badge_url_template"] == "https://www.bilibili.com/video/BV1k44LzPEhU?p=2&t={t}"


def test_normalize_rejects_unknown():
    with pytest.raises(ValueError):
        fetch.normalize_url("https://example.com/v/123")


def test_parse_metadata_priors_fail_open():
    info = json.loads((FIX / "ytdlp_info_bilibili.json").read_text(encoding="utf-8"))
    meta, priors = fetch.parse_metadata(info)
    assert meta["duration"] == pytest.approx(718.97)
    assert priors["chapters"] == [] and priors["heatmap"] == []          # null → 置空
    assert priors["danmaku_density"] == [] and priors["page_boundaries"] == []


def test_parse_metadata_chapters_heatmap():
    info = json.loads((FIX / "ytdlp_info_youtube.json").read_text(encoding="utf-8"))
    _, priors = fetch.parse_metadata(info)
    assert priors["chapters"][0] == {"title": "视频内容简介", "t_start": 0.0, "t_end": 65.0}
    assert priors["heatmap"][1]["value"] == 0.55


def test_pick_subtitle_track_priority():
    yt = json.loads((FIX / "ytdlp_info_youtube.json").read_text(encoding="utf-8"))
    assert fetch.pick_subtitle_track(yt["subtitles"], {}, "zh-Hans") == ("manual", "zh-Hans")
    bi = json.loads((FIX / "ytdlp_info_bilibili.json").read_text(encoding="utf-8"))
    assert fetch.pick_subtitle_track(bi["subtitles"], {}, None) == ("ai", "ai-zh")
    # 只有 danmaku → None(#15 场景)
    assert fetch.pick_subtitle_track({"danmaku": []}, {}, None) is None
    # 无手动/ai,自动字幕仅取视频语言
    assert fetch.pick_subtitle_track({}, {"en": [], "zh-Hans": []}, "en") == ("auto", "en")
    assert fetch.pick_subtitle_track({}, {"fr": []}, "en") is None


def test_pick_subtitle_exact_match_beats_prefix_order():
    subs = {"zh-Hant": [], "zh-Hans": []}          # 故意把 Hant 放前面
    assert fetch.pick_subtitle_track(subs, {}, "zh-Hans") == ("manual", "zh-Hans")


def test_pick_subtitle_auto_never_selects_danmaku():
    assert fetch.pick_subtitle_track({}, {"danmaku": []}, "da") is None


def test_proxy_format_selector_is_video_only_360p():
    sel = fetch.proxy_format_selector()
    assert "height<=360" in sel and sel.startswith("bv*")


def test_subs_download_cmd_manual_vs_ai():
    src = fetch.normalize_url("https://www.youtube.com/watch?v=QNiaoD5RxPA")
    cmd = fetch.subs_download_cmd(src, ("manual", "zh-Hans"), Path("/tmp/w"), None)
    assert "--write-subs" in cmd and "--write-auto-subs" not in cmd
    assert cmd[cmd.index("--sub-langs") + 1] == "zh-Hans"

    src2 = fetch.normalize_url("https://www.bilibili.com/video/BV1k44LzPEhU?p=2")
    cmd2 = fetch.subs_download_cmd(src2, ("ai", "ai-zh"), Path("/tmp/w"), "chrome")
    assert "--cookies-from-browser" in cmd2 and "chrome" in cmd2

    src3 = fetch.normalize_url("https://youtu.be/TUmEcL3Feo0")
    cmd3 = fetch.subs_download_cmd(src3, ("auto", "en"), Path("/tmp/w"), None)
    assert "--write-auto-subs" in cmd3


def test_fetch_subs_picks_matching_lang_file(tmp_path, monkeypatch):
    """subs_dir 已有旧语言残留时,必须选中目标语言文件而非字母序首个。"""
    import common
    work = tmp_path / ".work"
    subs = work / "subs"; subs.mkdir(parents=True)
    (subs / "sub.en.vtt").write_text("WEBVTT\n", encoding="utf-8")   # 陈旧残留(字母序在前)
    common.save_json(common.wp(work, "meta"), {"language": "zh-Hans"})
    common.save_json(common.wp(work, "raw_info"),
                     {"subtitles": {"zh-Hans": [{"ext": "vtt"}]}, "automatic_captions": {}})
    monkeypatch.setattr(
        fetch, "run",
        lambda cmd, timeout=300: (subs / "sub.zh-Hans.vtt").write_text("WEBVTT\n", encoding="utf-8"))
    src = fetch.normalize_url("https://www.youtube.com/watch?v=QNiaoD5RxPA")
    sub = fetch.fetch_subs(src, work, None, force=True)
    assert sub["lang"] == "zh-Hans" and sub["path"].endswith("sub.zh-Hans.vtt")


def test_fetch_meta_requests_lazy_subtitle_extraction(tmp_path, monkeypatch):
    """B 站字幕在 yt-dlp 里走惰性提取门(仅 --write-subs 等参数触发),
    -J 必须携带,否则 subtitles 恒空(2026-07-11 验收 #11 实测)。"""
    import json as _json
    seen = {}

    def fake_run(cmd, timeout=180):
        seen["cmd"] = [str(c) for c in cmd]
        return _json.dumps({"title": "t", "duration": 1.0,
                            "subtitles": {}, "automatic_captions": {}})

    monkeypatch.setattr(fetch, "run", fake_run)
    src = fetch.normalize_url("https://www.bilibili.com/video/BV1k44LzPEhU?p=2")
    fetch.fetch_meta(src, tmp_path, None, force=True)
    assert "--write-subs" in seen["cmd"] and "--write-auto-subs" in seen["cmd"]


def test_pick_subtitle_lang_match_beats_unmatched_manual():
    """视频语言在 manual 层无匹配时,语言匹配的 auto 轨优先于任意语言 manual 轨
    (2026-07-11 批量试产 #3 实测:en-US 视频被旧逻辑选中字典序第一的 ar 手动轨)。"""
    subs = {"ar": [], "es": [], "hi": [], "id": [], "zh": []}
    autos = {"en": [], "en-orig": []}
    assert fetch.pick_subtitle_track(subs, autos, "en-US") == ("auto", "en")


def test_pick_subtitle_ai_fallback_prefers_ai_zh():
    """B 站多语 ai 轨、无视频语言信息时优先 ai-zh(原声轨),不受字典序影响(#16 场景)。"""
    subs = {"ai-ar": [], "ai-en": [], "ai-zh": [], "danmaku": []}
    assert fetch.pick_subtitle_track(subs, {}, None) == ("ai", "ai-zh")


def test_pick_subtitle_ai_tier_lang_match_strips_prefix():
    """ai-* 轨以去前缀语言参与匹配:video_lang=zh 应命中 ai-zh 而非落入兜底。"""
    assert fetch.pick_subtitle_track({"ai-en": [], "ai-zh": []}, {}, "zh") == ("ai", "ai-zh")


def test_fetch_audio_cmd_online(tmp_path, monkeypatch):
    """fetch_audio 在线源应生成 yt-dlp -x 命令抽音频。"""
    seen = {}
    monkeypatch.setattr(fetch, "run", lambda cmd, timeout=1800: seen.update(cmd=[str(c) for c in cmd]))
    src = fetch.normalize_url("https://www.youtube.com/watch?v=QNiaoD5RxPA")
    work = tmp_path / ".work"; work.mkdir()
    (work / "audio.mp3").write_bytes(b"")     # run 被替换,产物手工放置模拟
    out = fetch.fetch_audio(src, work, None, force=True)
    assert str(out).endswith("audio.mp3")
    assert "-x" in seen["cmd"] and "--audio-format" in seen["cmd"] and "ba" in seen["cmd"]


def test_main_no_subs_with_asr_fetches_audio(tmp_path, monkeypatch):
    """无字幕轨 + ASR 可用 → 不再 exit 3,改抽音频。"""
    import common
    monkeypatch.setenv("ASR_BACKEND", "qwen")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk")
    monkeypatch.setattr(fetch, "fetch_meta", lambda *a, **k: {"title": "t", "duration": 1.0,
                                                              "language": None})
    monkeypatch.setattr(fetch, "fetch_proxy", lambda *a, **k: tmp_path / "p.mp4")
    monkeypatch.setattr(fetch, "fetch_subs", lambda *a, **k: None)
    called = {}
    monkeypatch.setattr(fetch, "fetch_audio", lambda *a, **k: called.setdefault("audio", True))
    rc = fetch.main(["--url", "https://www.youtube.com/watch?v=QNiaoD5RxPA",
                     "--work", str(tmp_path / ".work")])
    assert rc == 0 and called.get("audio")


def test_main_no_subs_no_asr_returns_3(tmp_path, monkeypatch):
    """无字幕轨且无 ASR 可用时返回 3。"""
    monkeypatch.setenv("ASR_BACKEND", "none")
    monkeypatch.setattr(fetch, "fetch_meta", lambda *a, **k: {"title": "t", "duration": 1.0,
                                                              "language": None})
    monkeypatch.setattr(fetch, "fetch_proxy", lambda *a, **k: tmp_path / "p.mp4")
    monkeypatch.setattr(fetch, "fetch_subs", lambda *a, **k: None)
    rc = fetch.main(["--url", "https://www.youtube.com/watch?v=QNiaoD5RxPA",
                     "--work", str(tmp_path / ".work")])
    assert rc == 3


def test_normalize_url_local_path(tmp_path):
    """本地文件输入:normalize_url 识别存在的路径,返回 platform=local 和绝对路径。"""
    f = tmp_path / "v1.mp4"; f.write_bytes(b"x")
    s = fetch.normalize_url(str(f))
    assert s["platform"] == "local" and s["vid"] == "v1"
    assert s["badge_url_template"] is None and s["canonical_url"] is None
    assert s["path"] == str(f)
    # 不存在且非 URL → ValueError
    with pytest.raises(ValueError):
        fetch.normalize_url(str(tmp_path / "nope.mp4"))


def test_local_meta_sidecar(tmp_path):
    """_local_meta 读 .json sidecar(视频号格式):title/nickname/duration 提取。"""
    import shutil
    v = tmp_path / "20260702_x.mp4"; v.write_bytes(b"x")
    shutil.copy(FIX / "sidecar_wechat.json", tmp_path / "20260702_x.json")
    meta, priors = fetch._local_meta(v)
    assert meta["title"].startswith("一个主动接班")
    assert meta["uploader"] == "杭商故事" and meta["duration"] == 504.0
    assert priors == {"chapters": [], "heatmap": [], "danmaku_density": [], "page_boundaries": []}


def test_local_meta_fallback_ffprobe(tmp_path, monkeypatch):
    """_local_meta sidecar 缺失:ffprobe 时长、文件名 stem 作 title(fail-open)。"""
    v = tmp_path / "raw.mp4"; v.write_bytes(b"x")
    monkeypatch.setattr(fetch, "ffprobe_duration", lambda p: 123.4)
    meta, _ = fetch._local_meta(v)
    assert meta["title"] == "raw" and meta["duration"] == 123.4


def test_local_proxy_cmd(tmp_path, monkeypatch):
    """fetch_proxy 本地分支:ffmpeg scale=-2:360 -an 代理。"""
    seen = {}
    monkeypatch.setattr(fetch, "run", lambda cmd, timeout=1800: seen.update(cmd=[str(c) for c in cmd]))
    v = tmp_path / "v.mp4"; v.write_bytes(b"x")
    src = fetch.normalize_url(str(v))
    work = tmp_path / ".work"; work.mkdir()
    (work / "proxy.mp4").write_bytes(b"")
    fetch.fetch_proxy(src, work, None, force=True)
    assert "scale=-2:360" in " ".join(seen["cmd"]) and "-an" in seen["cmd"]
