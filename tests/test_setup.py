import setup as setup_mod


def test_parse_version_ffmpeg():
    assert setup_mod.parse_version("ffmpeg version 8.0.1 Copyright ...") == (8, 0)


def test_parse_version_ytdlp():
    assert setup_mod.parse_version("2026.07.04") == (2026, 7)


def test_parse_version_unknown():
    assert setup_mod.parse_version("garbage") == (0, 0)


def test_probe_on_dev_machine(monkeypatch):
    """开发机已装全量二进制,probe 应全 found;blurdetect 依赖 ffmpeg>=5.1。"""
    # 防环境耦合:本机默认 funasr 会触发 60s 子进程导入
    monkeypatch.setattr(setup_mod, "check_asr", lambda: (True, "ok"))
    p = setup_mod.probe()
    assert p["ffmpeg"]["found"] and p["yt_dlp"]["found"] and p["ffprobe"]["found"]
    assert p["ffmpeg"]["blurdetect"] is True


def test_json_output_stays_pure_when_missing(monkeypatch, capsys):
    """--json 模式下 stdout 必须整体可被 json.loads(exit code 承载状态)。"""
    import json
    fake = {"ffmpeg": {"found": True, "version": [8, 0], "blurdetect": True},
            "ffprobe": {"found": True, "version": [8, 0]},
            "yt_dlp": {"found": True, "version": [2026, 7]},
            "tesseract": {"found": False}}
    # 防环境耦合:本机默认 funasr 会触发 60s 子进程导入
    monkeypatch.setattr(setup_mod, "check_asr", lambda: (True, "ok"))
    monkeypatch.setattr(setup_mod, "probe", lambda: fake)
    rc = setup_mod.main(["--json"])
    assert rc == 4
    out_json = json.loads(capsys.readouterr().out)
    # 检查基础 probe 字段和 asr 字段都在 JSON 中
    assert out_json["tesseract"]["found"] is False
    assert "asr" in out_json


def test_check_asr_branches(monkeypatch, tmp_path):
    """check_asr 的三家族分支:none 通过,chat 家族 key 检查,funasr venv 检查。"""
    monkeypatch.setattr(setup_mod, "resolve_asr_config", lambda env: {"family": "none"})
    ok, _ = setup_mod.check_asr()
    assert ok

    monkeypatch.setattr(setup_mod, "resolve_asr_config",
                        lambda env: {"family": "chat", "backend": "qwen", "key": ""})
    ok2, msg = setup_mod.check_asr()
    assert not ok2 and "DASHSCOPE_API_KEY" in msg

    monkeypatch.setattr(setup_mod, "resolve_asr_config",
                        lambda env: {"family": "funasr", "backend": "funasr",
                                     "funasr_venv": str(tmp_path / "nope")})
    ok3, msg3 = setup_mod.check_asr()
    assert not ok3 and "FUNASR_VENV" in msg3


def test_main_exit3_when_asr_unavailable(monkeypatch):
    """二进制全齐但 ASR 不可用时,exit 3。"""
    fake = {"ffmpeg": {"found": True, "version": [8, 0], "blurdetect": True},
            "ffprobe": {"found": True, "version": [8, 0]},
            "yt_dlp": {"found": True, "version": [2026, 7]},
            "tesseract": {"found": True}}
    monkeypatch.setattr(setup_mod, "probe", lambda: fake)
    monkeypatch.setattr(setup_mod, "check_asr", lambda: (False, "缺 DASHSCOPE_API_KEY"))
    assert setup_mod.main(["--check"]) == 3
