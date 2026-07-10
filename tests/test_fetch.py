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
