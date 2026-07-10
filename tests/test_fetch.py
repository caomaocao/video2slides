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
