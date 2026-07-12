"""FunASR 转写 runner——只在 FUNASR_VENV 独立环境里执行(零 pip 原则:funasr 依赖不进本 skill)。

用法:$FUNASR_VENV/bin/python scripts/funasr_runner.py <audio> [--lang zh]
stdout:segments JSON(秒);模型日志走 stderr。模式对齐 spec §10.1(paraformer-zh + VAD + 标点,句级时间戳)。

设备选择:优先 GPU(CUDA / Apple Silicon 的 MPS),否则 CPU;GPU 上转写失败时自动回退 CPU 再试一次
(某些 torch 构建下 paraformer 个别算子在 MPS 上未实现,回退保证不因加速器而丢结果)。
"""
import argparse
import contextlib
import json
import os
import sys


def pick_device(env=None, torch_mod=None):
    """选择 funasr 推理设备:FUNASR_DEVICE 覆盖 > CUDA > MPS(Apple Silicon)> CPU。

    torch_mod 仅供测试注入;运行时惰性 import torch(只在 FUNASR_VENV 里可用)。
    对加速器可用性检测做 fail-safe:任一检测抛异常都当作不可用,继续降级。
    """
    env = os.environ if env is None else env
    forced = (env.get("FUNASR_DEVICE") or "").strip()
    if forced:
        return forced
    if torch_mod is None:
        import torch as torch_mod
    try:
        if torch_mod.cuda.is_available():
            return "cuda:0"
    except Exception:
        pass
    try:
        if torch_mod.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def _extract_segments(res):
    """FunASR generate 结果 → segments(句级时间戳,ms→s);无 sentence_info 时兜底整段。"""
    segs = []
    for item in res:
        for s in item.get("sentence_info") or []:
            txt = (s.get("text") or "").strip()
            if txt:
                segs.append({"t_start": s["start"] / 1000, "t_end": s["end"] / 1000, "text": txt})
        if not item.get("sentence_info") and (item.get("text") or "").strip():
            segs.append({"t_start": 0.0, "t_end": 0.0, "text": item["text"].strip()})
    return segs


def transcribe_with_fallback(build_model, audio, device, log=None):
    """在 device 上构建模型并转写;失败且 device 非 cpu 时回退 cpu 再试一次。

    build_model(device) -> 有 .generate(...) 的模型对象(测试可注入)。
    """
    try:
        res = build_model(device).generate(input=audio, sentence_timestamp=True, batch_size_s=300)
        return _extract_segments(res)
    except Exception as e:
        if device == "cpu":
            raise
        if log:
            log(f"[funasr_runner] device={device} 转写失败,回退 cpu:{e!r}")
        res = build_model("cpu").generate(input=audio, sentence_timestamp=True, batch_size_s=300)
        return _extract_segments(res)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--lang", default="zh")
    args = ap.parse_args()

    real_stdout = sys.stdout
    # 依赖库(modelscope 下载进度/torch 等)的 print 噪声全部改道 stderr,守住 stdout 只出 JSON 的契约
    with contextlib.redirect_stdout(sys.stderr):
        from funasr import AutoModel   # 只在 FUNASR_VENV 里可导入
        device = pick_device()
        print(f"[funasr_runner] device={device}", file=sys.stderr)

        def build_model(dev):
            return AutoModel(model="paraformer-zh", vad_model="fsmn-vad", punc_model="ct-punc",
                             disable_update=True, log_level="ERROR", device=dev)

        segs = transcribe_with_fallback(build_model, args.audio, device,
                                        log=lambda m: print(m, file=sys.stderr))
    json.dump(segs, real_stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
