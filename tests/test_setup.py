import setup as setup_mod


def test_parse_version_ffmpeg():
    assert setup_mod.parse_version("ffmpeg version 8.0.1 Copyright ...") == (8, 0)


def test_parse_version_ytdlp():
    assert setup_mod.parse_version("2026.07.04") == (2026, 7)


def test_parse_version_unknown():
    assert setup_mod.parse_version("garbage") == (0, 0)


def test_probe_on_dev_machine():
    """开发机已装全量二进制,probe 应全 found;blurdetect 依赖 ffmpeg>=5.1。"""
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
    monkeypatch.setattr(setup_mod, "probe", lambda: fake)
    rc = setup_mod.main(["--json"])
    assert rc == 4
    assert json.loads(capsys.readouterr().out) == fake
