import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from common import save_json, wp  # noqa: E402  (依赖上面的 sys.path 注入)

# export/notes 共享的最小转写样本
EXPORT_TRANSCRIPT_SEGMENTS = [
    {"id": 0, "t_start": 0.0, "t_end": 4.0, "text": "大家好,欢迎来到本期视频。"},
    {"id": 1, "t_start": 4.0, "t_end": 9.0, "text": "今天我们聊 Token 到底是什么东西"},
]


@pytest.fixture
def export_work():
    """构造一套可导出的最小 .work/ 制品(切片4 票02/03 共享;返回工厂函数)。

    帧文件为纯字节伪 JPEG——export 只做存在性检查与拷贝,不解码,无须真调 ffmpeg
    (tests/AGENTS.md 离线约定)。
    """
    def _make(base, *, platform="youtube", tr_source="manual:zh", quote="Token 到底是什么"):
        out = Path(base) / "out"
        work = out / ".work"
        fdir = work / "frames_proxy"
        fdir.mkdir(parents=True)
        img1 = fdir / "f_001.jpg"; img1.write_bytes(b"\xff\xd8img1")
        img2 = fdir / "f_002.jpg"; img2.write_bytes(b"\xff\xd8img2")
        src = {"youtube": {"platform": "youtube", "vid": "x", "part": None,
                           "canonical_url": "https://www.youtube.com/watch?v=x",
                           "badge_url_template": "https://www.youtube.com/watch?v=x&t={t}s"},
               "local": {"platform": "local", "vid": "v", "part": None, "path": "/abs/v.mp4",
                         "canonical_url": None, "badge_url_template": None}}[platform]
        save_json(wp(work, "meta"), {"title": "测试片", "duration": 600.0, "language": "zh",
                                     "uploader": "up", "source": src})
        save_json(wp(work, "transcript"), {"language": "zh", "source": tr_source,
                                           "segments": EXPORT_TRANSCRIPT_SEGMENTS})
        outline = [{"id": "1", "level": 1, "title": "开场", "summary": "s",
                    "t_start": 0.0, "t_end": 30.0,
                    "evidence": [{"segment_id": 1, "quote": quote}],
                    "media": [{"type": "frame", "proxy_path": str(img1), "final_path": None,
                               "finalized": False, "t": 3.0, "reason": "scene-peak", "score": 0.9,
                               "dedup_group": None, "dedup_primary": True},
                              {"type": "clip", "final_path": None, "finalized": False,
                               "t_start": 2.0, "t_end": 5.0, "poster": str(img1),
                               "reason": "score-peak-window"}],
                    "children": [{"id": "1.1", "level": 2, "title": "细节", "summary": "",
                                  "t_start": 5.0, "t_end": 30.0,
                                  "evidence": [{"segment_id": 0, "quote": "大家好"}],
                                  "media": [{"type": "frame", "proxy_path": str(img2),
                                             "final_path": None, "finalized": False, "t": 8.0,
                                             "reason": "scene-peak", "score": 0.8,
                                             "dedup_group": None, "dedup_primary": True}],
                                  "children": []}]}]
        save_json(wp(work, "storyboard"),
                  {"video": {"title": "测试片", "duration": 600.0, "language": "zh",
                             "genre": "课程/教程",
                             "visual_form": [{"t_start": 0, "t_end": 600.0, "form": "slide-driven"}],
                             "signals": {"scene_scores": "scene_scores.json"},
                             "priors": {"chapters": [], "heatmap": [], "danmaku_density": [],
                                        "page_boundaries": []}},
                   "outline": outline})
        return out, work
    return _make


@pytest.fixture
def fake_rgb_signature(monkeypatch):
    """按文件名前缀造 16×16 RGB 假签名(r*→纯红,其余→纯蓝),免真调 ffmpeg(tests/AGENTS.md 离线约定)。"""
    import storyboard as sb_mod

    def _sig(path):
        return (b"\xff\x00\x00" if Path(path).stem.startswith("r") else b"\x00\x00\xff") * 256

    monkeypatch.setattr(sb_mod, "rgb_signature", _sig)
    return _sig
