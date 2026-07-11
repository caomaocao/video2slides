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


def test_resolve_default_funasr():
    cfg = transcribe.resolve_asr_config({"FUNASR_VENV": "~/.venvs/funasr"})
    assert cfg["backend"] == "funasr" and cfg["family"] == "funasr"
    assert cfg["funasr_venv"] == "~/.venvs/funasr"


def test_resolve_presets_and_override():
    cfg = transcribe.resolve_asr_config({"ASR_BACKEND": "qwen", "DASHSCOPE_API_KEY": "sk-x"})
    assert cfg["family"] == "chat" and cfg["model"] == "qwen3-asr-flash"
    assert cfg["base"].startswith("https://dashscope.aliyuncs.com")
    cfg2 = transcribe.resolve_asr_config({"ASR_BACKEND": "qwen", "DASHSCOPE_API_KEY": "sk-x",
                                          "ASR_API_BASE": "https://my.proxy/v1", "ASR_MODEL": "m2"})
    assert cfg2["base"] == "https://my.proxy/v1" and cfg2["model"] == "m2"   # 覆盖任意预设
    cfg3 = transcribe.resolve_asr_config({"ASR_BACKEND": "mimo", "MIMO_API_KEY": "sk-m"})
    assert cfg3["family"] == "chat" and cfg3["asr_options"] is True


def test_resolve_api_requires_triple_and_unknown_backend():
    with pytest.raises(ValueError, match="ASR_API_BASE"):
        transcribe.resolve_asr_config({"ASR_BACKEND": "api", "ASR_API_KEY": "k"})
    with pytest.raises(ValueError, match="未知"):
        transcribe.resolve_asr_config({"ASR_BACKEND": "whisperx"})
    assert transcribe.resolve_asr_config({"ASR_BACKEND": "none"})["family"] == "none"


def test_parse_silences_midpoints():
    txt = (FIX / "silencedetect.txt").read_text()
    mids = transcribe._parse_silences(txt)
    assert mids[0] == pytest.approx((42.8124 + 43.5312) / 2, abs=0.01)
    assert len(mids) == 2


def test_plan_chunks_short_audio_single_chunk():
    assert transcribe.plan_chunks([], 40.0) == [(0.0, 40.0)]


def test_plan_chunks_snaps_to_silence():
    # 43.17s 处有静音点,落在 45±15 窗内 → 在此断
    chunks = transcribe.plan_chunks([43.17, 89.56], 120.0)
    assert chunks[0] == (0.0, 43.17)
    assert chunks[-1][1] == 120.0
    assert all(t1 - t0 <= 45.0 * 1.5 + 0.01 for t0, t1 in chunks)


def test_plan_chunks_hard_cut_without_silence():
    chunks = transcribe.plan_chunks([], 100.0)
    assert chunks == [(0.0, 45.0), (45.0, 100.0)]


def test_cut_chunk_produces_mp3(tmp_path):
    """lavfi 合成 10s 音频,切 [2,5] 应产出 ≈3s 的 mp3。"""
    import subprocess
    import common
    src = tmp_path / "a.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
                    "-c:a", "libmp3lame", "-b:a", "64k", "-ac", "1", "-y", str(src)], check=True)
    out = transcribe.cut_chunk(src, 2.0, 5.0, tmp_path / "c.mp3")
    assert abs(common.ffprobe_duration(out) - 3.0) < 0.3
