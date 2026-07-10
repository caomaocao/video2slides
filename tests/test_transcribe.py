from pathlib import Path

import pytest

import transcribe

FIX = Path(__file__).parent / "fixtures"


def test_parse_vtt_strips_tags_and_settings():
    cues = transcribe.parse_vtt((FIX / "sample.vtt").read_text(encoding="utf-8"))
    assert cues[0]["t_start"] == pytest.approx(1.0)
    assert cues[2]["text"] == "今天我们聊 Token 到底是什么"


def test_parse_srt_comma_timestamps():
    cues = transcribe.parse_srt((FIX / "sample.srt").read_text(encoding="utf-8"))
    assert cues[0]["t_end"] == pytest.approx(2.9)
    assert cues[1]["text"] == "简称 NLP"


def test_dedup_merges_adjacent_identical():
    cues = transcribe.parse_vtt((FIX / "sample.vtt").read_text(encoding="utf-8"))
    out = transcribe.dedup_cues(cues)
    assert len(out) == 2                       # 前两条合并
    assert out[0]["t_end"] == pytest.approx(5.0)


def test_parse_vtt_short_form_timestamps():
    """在 WebVTT 中 MM:SS.mmm(无小时段)合法,不得静默丢弃。"""
    cues = transcribe.parse_vtt("WEBVTT\n\n00:01.000 --> 00:03.500\nhello world\n")
    assert cues == [{"t_start": 1.0, "t_end": 3.5, "text": "hello world"}]


def test_cli_errors_on_zero_segments(tmp_path):
    import common
    work = tmp_path / ".work"; (work / "subs").mkdir(parents=True)
    sub = work / "subs" / "sub.zh.vtt"
    sub.write_text("WEBVTT\n\n没有时间行的垃圾内容\n", encoding="utf-8")
    common.save_json(common.wp(work, "meta"),
                     {"language": "zh", "subtitle": {"kind": "manual", "lang": "zh", "path": str(sub)}})
    assert transcribe.run_cli(["--work", str(work)]) == 1
    assert not common.wp(work, "transcript").exists()


def test_cli_writes_transcript(tmp_path):
    import common
    work = tmp_path / ".work"
    (work / "subs").mkdir(parents=True)
    sub = work / "subs" / "sub.zh-Hans.vtt"
    sub.write_text((FIX / "sample.vtt").read_text(encoding="utf-8"), encoding="utf-8")
    common.save_json(common.wp(work, "meta"),
                     {"language": "zh-Hans", "subtitle": {"kind": "manual", "lang": "zh-Hans", "path": str(sub)}})
    assert transcribe.run_cli(["--work", str(work)]) == 0
    t = common.load_json(common.wp(work, "transcript"))
    assert t["source"] == "manual:zh-Hans"
    assert [s["id"] for s in t["segments"]] == list(range(len(t["segments"])))
