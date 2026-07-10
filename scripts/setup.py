"""预检(垂直切片最小版):二进制存在性 + 版本门槛。--json 结构化 / --check 静默。

exit 0 可运行;2 缺 ffmpeg/ffprobe/yt-dlp;4 仅缺 tesseract(自动降级,不阻塞)。
exit 3(所配 ASR 后端不可用)属 ASR 三家族范围,切片不实现——见 spec §10.2。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys

from common import emit

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    p = probe()
    if args.json:
        print(json.dumps(p, ensure_ascii=False, indent=1))
    missing = [k for k in ("ffmpeg", "ffprobe", "yt_dlp") if not p[k]["found"]]
    if missing:
        if not args.check:
            emit(f"缺必装二进制: {', '.join(missing)}", "macOS: brew install ffmpeg yt-dlp")
        return 2
    if not p["tesseract"]["found"]:
        if not args.check:
            emit("tesseract 缺失:文字密度打分降级为边缘密度代理(不阻塞)")
        return 4
    if not args.check and not args.json:
        emit("预检通过", next_hint="python scripts/fetch.py --url <URL> --work <DIR>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
