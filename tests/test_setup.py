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
