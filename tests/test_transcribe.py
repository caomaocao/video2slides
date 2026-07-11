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


def _cfg_transcriptions():
    return {"backend": "groq", "family": "transcriptions", "base": "https://api.groq.com/openai/v1",
            "model": "whisper-large-v3", "key": "sk-t", "language": "auto", "asr_options": False}


def test_multipart_structure():
    body, boundary = transcribe._multipart({"model": "m", "response_format": "verbose_json"},
                                           "file", "c.mp3", b"AUDIO")
    s = body.decode("latin-1")
    assert f"--{boundary}" in s and 'name="model"' in s and 'filename="c.mp3"' in s
    assert s.rstrip().endswith(f"--{boundary}--")
    assert b"AUDIO" in body


def test_asr_transcriptions_offset_and_request(tmp_path, monkeypatch):
    import json as _json
    resp = _json.loads((FIX / "asr_verbose_json.json").read_text(encoding="utf-8"))
    seen = []
    monkeypatch.setattr(transcribe, "_http_post",
                        lambda url, headers, body, timeout=300: (seen.append((url, headers)), resp)[1])
    c1 = tmp_path / "c1.mp3"; c1.write_bytes(b"x")
    c2 = tmp_path / "c2.mp3"; c2.write_bytes(b"y")
    segs, failed = transcribe._asr_transcriptions([(c1, 0.0, 45.0), (c2, 45.0, 90.0)], _cfg_transcriptions())
    assert failed == 0 and len(segs) == 4
    assert segs[2]["t_start"] == pytest.approx(45.0)          # 第二块偏移校正
    assert segs[3]["t_end"] == pytest.approx(50.0)
    url, headers = seen[0]
    assert url == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert headers["Authorization"] == "Bearer sk-t"


def test_asr_transcriptions_retry_then_skip(tmp_path, monkeypatch):
    calls = {"n": 0}

    def flaky(url, headers, body, timeout=300):
        calls["n"] += 1
        raise RuntimeError("ASR HTTP 500")

    monkeypatch.setattr(transcribe, "_http_post", flaky)
    c1 = tmp_path / "c1.mp3"; c1.write_bytes(b"x")
    segs, failed = transcribe._asr_transcriptions([(c1, 0.0, 45.0)], _cfg_transcriptions())
    assert failed == 1 and segs == [] and calls["n"] == 2      # 重试 1 次后跳过


def test_http_post_invalid_json_becomes_runtime_error(monkeypatch):
    """2xx + 非法 JSON(端点配错)必须归一为 RuntimeError,走块失败隔离而非整批崩溃。"""
    import io, urllib.request

    class FakeResp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=300: FakeResp(b"<html>gateway</html>"))
    with pytest.raises(RuntimeError, match="非 JSON"):
        transcribe._http_post("https://x/v1/audio/transcriptions", {}, b"")


def test_asr_transcriptions_malformed_segment_counts_failed(tmp_path, monkeypatch):
    """segment 缺 start/end 只作废该块(failed+1),不崩整批、不留半截段。"""
    bad = {"segments": [{"start": 0.0, "end": 1.0, "text": "好段"},
                        {"start": None, "end": 2.0, "text": "坏段"}]}
    monkeypatch.setattr(transcribe, "_http_post", lambda *a, **k: bad)
    c1 = tmp_path / "c1.mp3"; c1.write_bytes(b"x")
    segs, failed = transcribe._asr_transcriptions([(c1, 0.0, 45.0)], {
        "backend": "groq", "family": "transcriptions", "base": "https://b/v1",
        "model": "m", "key": "k", "language": "auto", "asr_options": False})
    assert failed == 1 and segs == []


def _cfg_chat(asr_options=False):
    return {"backend": "qwen", "family": "chat", "base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model": "qwen3-asr-flash", "key": "sk-c", "language": "auto", "asr_options": asr_options}


def test_chat_payload_shapes():
    p = transcribe._chat_payload(_cfg_chat(False), "QUJD")
    assert p["model"] == "qwen3-asr-flash"
    au = p["messages"][0]["content"][0]["input_audio"]["data"]
    assert au == "data:audio/mpeg;base64,QUJD"
    assert "asr_options" not in p
    p2 = transcribe._chat_payload(_cfg_chat(True), "QUJD")
    assert p2["asr_options"] == {"language": "auto"}          # mimo 需要


def test_asr_chat_chunk_level_segments(tmp_path, monkeypatch):
    import json as _json
    resp = _json.loads((FIX / "asr_chat_resp.json").read_text(encoding="utf-8"))
    seen = []
    monkeypatch.setattr(transcribe, "_http_post",
                        lambda url, headers, body, timeout=300: (seen.append((url, _json.loads(body))), resp)[1])
    c1 = tmp_path / "c1.mp3"; c1.write_bytes(b"abc")
    c2 = tmp_path / "c2.mp3"; c2.write_bytes(b"def")
    segs, failed = transcribe._asr_chat([(c1, 0.0, 45.0), (c2, 45.0, 83.0)], _cfg_chat())
    assert failed == 0
    assert segs == [
        {"t_start": 0.0, "t_end": 45.0, "text": "这里是切块转写出来的整段文本"},
        {"t_start": 45.0, "t_end": 83.0, "text": "这里是切块转写出来的整段文本"},
    ]
    url, payload = seen[0]
    assert url.endswith("/chat/completions")
    assert payload["messages"][0]["content"][0]["type"] == "input_audio"


def test_asr_chat_empty_content_and_oversize(tmp_path, monkeypatch):
    empty = {"choices": [{"message": {"content": "  "}}]}
    monkeypatch.setattr(transcribe, "_http_post", lambda *a, **k: empty)
    c1 = tmp_path / "c1.mp3"; c1.write_bytes(b"x")
    segs, failed = transcribe._asr_chat([(c1, 0.0, 45.0)], _cfg_chat())
    assert failed == 1 and segs == []                          # 空 content 记失败
    big = tmp_path / "big.mp3"; big.write_bytes(b"z" * (8 * 1024 * 1024))   # b64 后 >10MB
    segs2, failed2 = transcribe._asr_chat([(big, 0.0, 45.0)], _cfg_chat())
    assert failed2 == 1                                        # 超限护栏


def test_asr_chat_malformed_resp_shapes_count_failed(tmp_path, monkeypatch):
    """合法 JSON 但形状非常规(None/数组/message 非 dict)按块失败,不穿透、不丢已收块。"""
    good = {"choices": [{"message": {"content": "好块"}}]}
    responses = [good, None, [], {"choices": [{"message": "oops"}]}, {"choices": {"weird": 1}}]
    calls = {"i": -1}

    def fake_post(url, headers, body, timeout=300):
        # 畸形形状是"成功返回",不抛 RuntimeError → _with_retry 首次即返回,每块恰一次调用
        calls["i"] += 1
        return responses[calls["i"]]

    monkeypatch.setattr(transcribe, "_http_post", fake_post)
    files = []
    for i in range(5):
        f = tmp_path / f"c{i}.mp3"; f.write_bytes(b"x"); files.append(f)
    chunks = [(files[i], i * 10.0, (i + 1) * 10.0) for i in range(5)]
    segs, failed = transcribe._asr_chat(chunks, {
        "backend": "qwen", "family": "chat", "base": "https://b/v1",
        "model": "m", "key": "k", "language": "auto", "asr_options": False})
    assert failed == 4
    assert segs == [{"t_start": 0.0, "t_end": 10.0, "text": "好块"}]   # 首块保留
