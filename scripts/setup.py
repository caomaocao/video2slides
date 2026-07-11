"""预检(垂直切片最小版):二进制存在性 + 版本门槛。--json 结构化 / --check 静默。

exit 0 可运行;2 缺 ffmpeg/ffprobe/yt-dlp;3 所配 ASR 后端不可用(按 ASR_BACKEND 校验
key/venv,可 ASR_BACKEND=none 继续);4 仅缺 tesseract(自动降级,不阻塞)。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from common import emit, load_env_config
from transcribe import PRESETS, resolve_asr_config

_VER_RE = re.compile(r"(\d+)\.(\d+)")


def parse_version(text: str) -> tuple[int, int]:
    m = _VER_RE.search(text or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _version_of(cmd: list) -> tuple[int, int]:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
        return parse_version(out.splitlines()[0] if out else "")
    except Exception:
        return (0, 0)


def probe() -> dict:
    res = {}
    for name, ver_cmd in [("ffmpeg", ["ffmpeg", "-version"]),
                          ("ffprobe", ["ffprobe", "-version"]),
                          ("yt_dlp", ["yt-dlp", "--version"])]:
        found = shutil.which(name.replace("_", "-")) is not None
        ver = _version_of(ver_cmd) if found else (0, 0)
        res[name] = {"found": found, "version": list(ver)}
    res["ffmpeg"]["blurdetect"] = res["ffmpeg"]["found"] and tuple(res["ffmpeg"]["version"]) >= (5, 1)
    res["tesseract"] = {"found": shutil.which("tesseract") is not None}
    return res


def check_asr() -> tuple[bool, str]:
    """按所配 ASR 后端校验可用性(spec §10.2 exit 3)。不联网探活,key 有效性由首次调用报错诊断。"""
    try:
        cfg = resolve_asr_config(load_env_config())
    except ValueError as e:
        return False, str(e)
    if cfg["family"] == "none":
        return True, "ASR_BACKEND=none(keyless 帧-only 允许)"
    if cfg["family"] == "funasr":
        py = Path(cfg["funasr_venv"]).expanduser() / "bin" / "python"
        if not py.exists():
            return False, f"FUNASR_VENV 无效(缺 {py})——配置 FUNASR_VENV 或改用 mimo/qwen 等 API 后端"
        try:
            r = subprocess.run([str(py), "-c", "import funasr"], capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            # 兜底:python 无执行位(PermissionError)/import 挂起(TimeoutExpired)等
            # 均 fail-closed 返回,不击穿 --json 模式的纯 JSON 输出契约
            return False, f"funasr venv 无法执行({py})——检查 FUNASR_VENV 或改用 mimo/qwen 等 API 后端"
        return (r.returncode == 0,
                "funasr 可用" if r.returncode == 0 else "funasr 导入失败(venv 内未安装?)")
    if not cfg["key"]:
        return False, f"缺 {PRESETS[cfg['backend']]['key_env']}(写入 ~/.config/video2slides/.env)"
    return True, f"{cfg['backend']} key 就绪"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    p = probe()
    # 先校验 ASR 可用性(提前判定,便于 JSON 中一并呈现)
    asr_ok, asr_msg = check_asr()
    if args.json:
        # --json 模式:stdout 只输出纯 JSON,状态由 JSON 内容 + exit code 承载
        p["asr"] = {"ok": asr_ok, "detail": asr_msg}
        print(json.dumps(p, ensure_ascii=False, indent=1))
    missing = [k for k in ("ffmpeg", "ffprobe", "yt_dlp") if not p[k]["found"]]
    if missing:
        if not args.check and not args.json:
            names = ", ".join(m.replace("_", "-") for m in missing)
            emit(f"缺必装二进制: {names}", "macOS: brew install ffmpeg yt-dlp")
        return 2
    if not asr_ok:
        if not args.check and not args.json:
            emit(f"ASR 后端不可用:{asr_msg}", "可 ASR_BACKEND=none 继续(帧-only,质量受限)")
        return 3
    if not p["tesseract"]["found"]:
        if not args.check and not args.json:
            emit("tesseract 缺失:文字密度打分降级为边缘密度代理(不阻塞)")
        return 4
    if not args.check and not args.json:
        emit("预检通过", next_hint="python scripts/fetch.py --url <URL> --work <DIR>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
