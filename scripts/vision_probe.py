"""视觉能力探针 checker(跨平台可移植性 spec §视觉能力处理)。

前奏里宿主 `Read` `assets/vision_probe.png`,把看到的文字经本脚本比对:
  $PYBIN "$SKILL_DIR/scripts/vision_probe.py" --claim "<你在图上看到的确切文字>"
exit 0 → 命中,宿主确能读本地图(视觉模式);exit 1 → 未命中(答不出/拒读/幻觉编造),
判无视觉,后续走时间轴路(spec §视觉能力处理·无视觉行为)。

**明文答案永不落地**:只存归一化后的 sha256。否则纯文本宿主读了 SKILL/源码就能直接回显
「标准答案」而不真读图,探针失效——这是防幻觉/防回显作弊的关键(实现期对票 02 的修正)。
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

# sha256(归一化明文);归一化 = 大写后仅保留 A-Z0-9。明文只在生成期与测试里出现,不入本文件。
_EXPECTED_SHA256 = "6961d807e4d6886409a39d464588c2a90f00081a635999e72e60920a0712f211"


def normalize(text: str) -> str:
    """大写、仅留 A-Z0-9——吸收 OCR/大小写/标点/空白抖动,只认真正读到的内容。"""
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def check(claim: str) -> bool:
    """宿主报出的文字归一化后哈希,与预期比对;空/错一律 False。"""
    norm = normalize(claim)
    if not norm:
        return False
    return hashlib.sha256(norm.encode("utf-8")).hexdigest() == _EXPECTED_SHA256


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="视觉探针:比对宿主读图报出的文字")
    ap.add_argument("--claim", default="", help="宿主在 assets/vision_probe.png 上读到的确切文字")
    ap.add_argument("--work", default=None,
                    help="给定则把判决落 <work>/host_caps.json,续跑/新会话可复用,不必重读探针图")
    args = ap.parse_args(argv)
    ok = check(args.claim)
    if args.work:                                    # 落盘判决(续跑友好,spec §视觉能力处理 D1)
        from common import save_json                 # 延迟导入:仅落盘时才依赖 common
        save_json(Path(args.work) / "host_caps.json", {"vision": ok})
    if ok:
        print("视觉模式:确认宿主能读本地图,走完整视觉路径")
        return 0
    print("无视觉模式:未能读出探针图文字——后续选帧走时间轴路(peak_score),"
          "步骤 6 默认笔记,幻灯片需用户显式确认(spec §视觉能力处理)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
