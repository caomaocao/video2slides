"""FunASR 转写 runner——只在 FUNASR_VENV 独立环境里执行(零 pip 原则:funasr 依赖不进本 skill)。

用法:$FUNASR_VENV/bin/python scripts/funasr_runner.py <audio> [--lang zh]
stdout:segments JSON(秒);模型日志走 stderr。模式对齐 spec §10.1(paraformer-zh + VAD + 标点,句级时间戳)。
"""
import argparse
import contextlib
import json
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--lang", default="zh")
    args = ap.parse_args()

    real_stdout = sys.stdout
    # 依赖库(modelscope 下载进度/torch 等)的 print 噪声全部改道 stderr,守住 stdout 只出 JSON 的契约
    with contextlib.redirect_stdout(sys.stderr):
        from funasr import AutoModel   # 只在 FUNASR_VENV 里可导入
        model = AutoModel(model="paraformer-zh", vad_model="fsmn-vad", punc_model="ct-punc",
                          disable_update=True, log_level="ERROR")
        res = model.generate(input=args.audio, sentence_timestamp=True, batch_size_s=300)
        segs = []
        for item in res:
            for s in item.get("sentence_info") or []:
                txt = (s.get("text") or "").strip()
                if txt:
                    segs.append({"t_start": s["start"] / 1000, "t_end": s["end"] / 1000, "text": txt})
            if not item.get("sentence_info") and (item.get("text") or "").strip():
                segs.append({"t_start": 0.0, "t_end": 0.0, "text": item["text"].strip()})
    json.dump(segs, real_stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
