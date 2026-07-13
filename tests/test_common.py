import time
from pathlib import Path

import common


def test_is_fresh_true_when_newer_than_upstream(tmp_path: Path):
    up = tmp_path / "up.json"; up.write_text("{}")
    time.sleep(0.01)
    art = tmp_path / "art.json"; art.write_text("{}")
    assert common.is_fresh(art, up) is True


def test_is_fresh_false_when_missing_or_stale(tmp_path: Path):
    up = tmp_path / "up.json"; up.write_text("{}")
    art = tmp_path / "art.json"
    assert common.is_fresh(art, up) is False          # 不存在
    art.write_text("{}")
    time.sleep(0.01)
    up.write_text("{} ")                               # 上游更新
    assert common.is_fresh(art, up) is False


def test_json_roundtrip_utf8(tmp_path: Path):
    p = tmp_path / "a" / "b.json"
    common.save_json(p, {"标题": "中文"})
    assert common.load_json(p) == {"标题": "中文"}
    assert "中文" in p.read_text(encoding="utf-8")     # 非 \u 转义


def test_run_raises_with_stderr_tail():
    import pytest
    with pytest.raises(RuntimeError, match="命令失败"):
        common.run(["python3", "-c", "import sys; sys.exit(3)"])


def test_sig_diff_ratio_bounds():
    a = bytes([0, 0, 0] * 256)
    b = bytes([255, 255, 255] * 256)
    assert common.sig_diff_ratio(a, a) == 0.0
    assert common.sig_diff_ratio(a, b) == 1.0


def test_load_env_config_file_and_environ_overlay(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("# 注释\nASR_BACKEND=qwen\nDASHSCOPE_API_KEY=sk-file\n\n", encoding="utf-8")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-env")   # environ 优先
    cfg = common.load_env_config(f)
    assert cfg["ASR_BACKEND"] == "qwen"
    assert cfg["DASHSCOPE_API_KEY"] == "sk-env"


def test_load_env_config_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("ASR_BACKEND", "none")
    cfg = common.load_env_config(tmp_path / "nope.env")
    assert cfg["ASR_BACKEND"] == "none"


def test_parse_silence_spans_pairs():
    text = ("[silencedetect @ 0x0] silence_start: 10.5\n"
            "[silencedetect @ 0x0] silence_end: 13.0 | silence_duration: 2.5\n"
            "[silencedetect @ 0x0] silence_start: 100.0\n"
            "[silencedetect @ 0x0] silence_end: 100.6 | silence_duration: 0.6\n")
    assert common.parse_silence_spans(text) == [(10.5, 13.0), (100.0, 100.6)]


def test_parse_silence_spans_unclosed_start_dropped():
    # 音频在静音中结束:孤立 start 无 end,丢弃不配对
    text = "[silencedetect @ 0x0] silence_start: 50.0\n"
    assert common.parse_silence_spans(text) == []


def test_artifacts_registers_chapter_hints_and_plan(tmp_path):
    assert common.wp(tmp_path, "chapter_hints") == tmp_path / "chapter_hints.json"
    assert common.wp(tmp_path, "chapter_plan") == tmp_path / "chapter_plan.json"


def test_config_dir_respects_xdg(monkeypatch, tmp_path):
    import common
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert common.config_dir() == tmp_path / "xdg" / "video2slides"


def test_config_dir_falls_back_to_home(monkeypatch, tmp_path):
    import common
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(common.Path, "home", classmethod(lambda cls: tmp_path))
    assert common.config_dir() == tmp_path / ".config" / "video2slides"


def test_load_env_config_uses_xdg(monkeypatch, tmp_path):
    import common
    d = tmp_path / "xdg" / "video2slides"; d.mkdir(parents=True)
    (d / ".env").write_text("ASR_BACKEND=none\n", encoding="utf-8")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("ASR_BACKEND", raising=False)
    assert common.load_env_config().get("ASR_BACKEND") == "none"
