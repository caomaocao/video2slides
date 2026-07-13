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


def test_check_asr_subprocess_failure_fail_closed(monkeypatch, tmp_path):
    """venv python 存在但不可执行(空文件)→ 返回 (False, 指引) 而非 PermissionError 击穿。"""
    venv = tmp_path / "venv" / "bin"; venv.mkdir(parents=True)
    (venv / "python").write_text("")          # 无执行位
    monkeypatch.setattr(setup_mod, "resolve_asr_config",
                        lambda env: {"family": "funasr", "backend": "funasr",
                                     "funasr_venv": str(tmp_path / "venv")})
    ok, msg = setup_mod.check_asr()
    assert not ok and "无法执行" in msg


def test_json_pure_on_exit3(monkeypatch, capsys):
    """--json + exit3 路径:stdout 整体纯 JSON 且含 asr 节。"""
    import json
    fake = {"ffmpeg": {"found": True, "version": [8, 0], "blurdetect": True},
            "ffprobe": {"found": True, "version": [8, 0]},
            "yt_dlp": {"found": True, "version": [2026, 7]},
            "tesseract": {"found": True}}
    monkeypatch.setattr(setup_mod, "probe", lambda: fake)
    monkeypatch.setattr(setup_mod, "check_asr", lambda: (False, "缺 DASHSCOPE_API_KEY"))
    rc = setup_mod.main(["--json"])
    assert rc == 3
    data = json.loads(capsys.readouterr().out)
    assert data["asr"] == {"ok": False, "detail": "缺 DASHSCOPE_API_KEY"}


# 跨平台预检(2026-07-13):Windows 硬拦 / 发行版安装提示 / arch 门 / platform 入 JSON
def test_windows_gate_blocks_with_exit1(monkeypatch, capsys):
    monkeypatch.setattr(setup_mod.platform, "system", lambda: "Windows")
    monkeypatch.setattr(setup_mod.platform, "machine", lambda: "AMD64")
    # 不应触发 probe/check_asr(Windows 在探测前就拦掉)
    monkeypatch.setattr(setup_mod, "probe", lambda: (_ for _ in ()).throw(AssertionError("不应 probe")))
    assert setup_mod.main([]) == 1
    assert "Windows" in capsys.readouterr().out


def test_windows_gate_json_pure(monkeypatch, capsys):
    import json
    monkeypatch.setattr(setup_mod.platform, "system", lambda: "Windows")
    monkeypatch.setattr(setup_mod.platform, "machine", lambda: "AMD64")
    assert setup_mod.main(["--json"]) == 1
    data = json.loads(capsys.readouterr().out)          # stdout 仍整体纯 JSON
    assert data["platform"]["supported"] is False


def test_linux_pkg_hint_debian_family():
    for osr in ('ID=ubuntu\nID_LIKE=debian\n', 'ID=debian\n'):
        assert "apt" in setup_mod.linux_pkg_hint(osr)


def test_linux_pkg_hint_rhel_family():
    for osr in ('ID="centos"\nID_LIKE="rhel fedora"\n', 'ID=rhel\n', 'ID=fedora\n', 'ID=rocky\nID_LIKE="rhel centos fedora"\n'):
        h = setup_mod.linux_pkg_hint(osr)
        assert "dnf" in h and "yum" in h


def test_linux_pkg_hint_unknown_falls_back():
    assert "发行版包管理器" in setup_mod.linux_pkg_hint('ID=arch\n')


def test_install_hint_by_platform(monkeypatch):
    monkeypatch.setattr(setup_mod.platform, "system", lambda: "Darwin")
    assert "brew" in setup_mod.install_hint()
    monkeypatch.setattr(setup_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup_mod, "linux_pkg_hint", lambda: "LINUX-HINT")
    assert setup_mod.install_hint() == "LINUX-HINT"


def test_probe_includes_platform(monkeypatch):
    monkeypatch.setattr(setup_mod, "check_asr", lambda: (True, "ok"))
    p = setup_mod.probe()
    assert set(p["platform"]) == {"system", "machine"}


def test_arch_gate_arm64_only_backend_on_x86(monkeypatch):
    # mlx-whisper 保留槽位:非 arm64 上配置该后端 → 报错建议 funasr(spec §10.2 arch 校验)
    monkeypatch.setattr(setup_mod.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(setup_mod, "resolve_asr_config",
                        lambda env: {"family": "subprocess", "backend": "mlxwhisper", "key": ""})
    ok, msg = setup_mod.check_asr()
    assert not ok and "arm64" in msg and "funasr" in msg


def test_missing_binary_hint_follows_platform(monkeypatch, capsys):
    fake = {"platform": {"system": "Linux", "machine": "x86_64"},
            "ffmpeg": {"found": False, "version": [0, 0], "blurdetect": False},
            "ffprobe": {"found": True, "version": [8, 0]},
            "yt_dlp": {"found": True, "version": [2026, 7]},
            "tesseract": {"found": True}}
    monkeypatch.setattr(setup_mod.platform, "system", lambda: "Linux")
    monkeypatch.setattr(setup_mod, "probe", lambda: fake)
    monkeypatch.setattr(setup_mod, "check_asr", lambda: (True, "ok"))
    monkeypatch.setattr(setup_mod, "linux_pkg_hint", lambda: "APT-HINT")
    assert setup_mod.main([]) == 2
    assert "APT-HINT" in capsys.readouterr().out
