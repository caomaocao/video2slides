"""转写层(切片版):VTT/SRT 解析去重 → transcript.json。ASR 三家族与弹幕直方图切片外(spec §10.1)。"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from common import emit, is_fresh, load_json, save_json, wp

_TS = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})[.,](\d{3})")
_TAG = re.compile(r"<[^>]+>")

# ASR 预设表(切片2设计 §2):ASR_API_BASE/ASR_MODEL 可覆盖任意预设;asr_options 仅 mimo 需要
PRESETS = {
    "groq":   {"family": "transcriptions", "base": "https://api.groq.com/openai/v1",
               "model": "whisper-large-v3", "key_env": "GROQ_API_KEY", "asr_options": False},
    "openai": {"family": "transcriptions", "base": "https://api.openai.com/v1",
               "model": "whisper-1", "key_env": "OPENAI_API_KEY", "asr_options": False},
    "mimo":   {"family": "chat", "base": "https://api.xiaomimimo.com/v1",
               "model": "mimo-v2.5-asr", "key_env": "MIMO_API_KEY", "asr_options": True},
    "qwen":   {"family": "chat", "base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
               "model": "qwen3-asr-flash", "key_env": "DASHSCOPE_API_KEY", "asr_options": False},
    "api":    {"family": "transcriptions", "base": None, "model": None,
               "key_env": "ASR_API_KEY", "asr_options": False},
}


def resolve_asr_config(env: dict) -> dict:
    """由 env(load_env_config 产物)解析 ASR 配置;配置无效抛 ValueError(带修复指引)。"""
    backend = (env.get("ASR_BACKEND") or "funasr").strip().lower()
    if backend == "none":
        return {"backend": "none", "family": "none", "base": None, "model": None,
                "key": None, "funasr_venv": None, "language": "auto", "asr_options": False}
    if backend == "funasr":
        return {"backend": "funasr", "family": "funasr", "base": None, "model": None, "key": None,
                "funasr_venv": env.get("FUNASR_VENV", "~/.venvs/funasr"),
                "language": env.get("ASR_LANGUAGE", "auto"), "asr_options": False}
    if backend not in PRESETS:
        raise ValueError(f"未知 ASR_BACKEND: {backend}(可选 funasr|groq|openai|mimo|qwen|api|none)")
    p = PRESETS[backend]
    base = env.get("ASR_API_BASE") or p["base"]
    model = env.get("ASR_MODEL") or p["model"]
    if not base or not model:
        raise ValueError("ASR_BACKEND=api 需要 ASR_API_BASE 与 ASR_MODEL(自定义三元组,spec §10.1)")
    return {"backend": backend, "family": p["family"], "base": base.rstrip("/"), "model": model,
            "key": env.get(p["key_env"], ""), "funasr_venv": None,
            "language": env.get("ASR_LANGUAGE", "auto"), "asr_options": p["asr_options"]}


def _sec(ts: str) -> float:
    h, m, s, ms = _TS.match(ts).groups()
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _parse_blocks(text: str) -> list[dict]:
    cues = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        lines = [l for l in block.splitlines() if l.strip()]
        ti = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if ti is None:
            continue
        m = _TS.findall(lines[ti])
        if len(m) < 2:
            continue
        start, end = lines[ti].split("-->")
        body = " ".join(_TAG.sub("", l).strip() for l in lines[ti + 1:]).strip()
        cues.append({"t_start": _sec(start.strip().split()[0]),
                     "t_end": _sec(end.strip().split()[0]), "text": body})
    return cues


def parse_vtt(text: str) -> list[dict]:
    return _parse_blocks(text)


def parse_srt(text: str) -> list[dict]:
    return _parse_blocks(text)


def dedup_cues(cues: list[dict]) -> list[dict]:
    out: list[dict] = []
    for c in cues:
        t = c["text"].strip()
        if not t:
            continue
        if out and t == out[-1]["text"]:
            out[-1]["t_end"] = c["t_end"]      # 滚动重复:合并延长
            continue
        out.append({"t_start": c["t_start"], "t_end": c["t_end"], "text": t})
    return out


def run_cli(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    work = Path(args.work)

    out_p = wp(work, "transcript")
    meta = load_json(wp(work, "meta"))
    sub = meta.get("subtitle")
    if not sub:
        emit("meta.json 无 subtitle——先跑 fetch.py(或走 ASR,切片外)")
        return 3
    sub_p = Path(sub["path"])
    if not args.force and is_fresh(out_p, sub_p):
        emit(f"transcript: {out_p}(已最新,跳过)", next_hint="python scripts/signals.py --work " + str(work))
        return 0
    text = sub_p.read_text(encoding="utf-8")
    cues = parse_srt(text) if sub_p.suffix == ".srt" else parse_vtt(text)
    segs = [{"id": i, **c} for i, c in enumerate(dedup_cues(cues))]
    if not segs:
        emit("解析出 0 段——字幕文件格式异常或内容为空,不落盘")
        return 1
    save_json(out_p, {"language": meta.get("language"), "source": f"{sub['kind']}:{sub['lang']}", "segments": segs})
    emit(f"transcript: {out_p}({len(segs)} 段)", next_hint=f"python scripts/signals.py --work {work}")
    return 0


if __name__ == "__main__":
    sys.exit(run_cli())
