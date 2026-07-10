from pathlib import Path

import pytest

import signals

FIX = Path(__file__).parent / "fixtures"


def test_parse_scene_metadata():
    rows = signals.parse_scene_metadata((FIX / "scene_metadata.txt").read_text())
    assert rows[0] == {"n": 0, "t": 0.0, "score": 0.0}
    assert rows[2]["score"] == pytest.approx(0.412)
    assert len(rows) == 5


def test_pick_page_boundaries_threshold_and_gap():
    rows = signals.parse_scene_metadata((FIX / "scene_metadata.txt").read_text())
    bs = signals.pick_page_boundaries(rows, thr=0.30, min_gap=1.5)
    # 2.0s 与 2.033s 在 1.5s 间隔内 → 保留分高者(0.412);4.0s 独立成峰
    assert [round(b["t"], 3) for b in bs] == [2.0, 4.0]
    assert bs[0]["score"] == pytest.approx(0.412)


def test_curve_stats_plateau_ratio():
    rows = [{"n": i, "t": i / 10, "score": 0.01} for i in range(90)] + \
           [{"n": 90, "t": 9.0, "score": 0.9}]
    st = signals.curve_stats(rows)
    assert st["frames"] == 91 and st["spikes"] == 1
    assert st["plateau_ratio"] > 0.95          # 长平台+尖峰 = slide 特征(spec §5.1)


def test_end_to_end_on_synthetic_video(tmp_path):
    """3 段纯色各 2s 的合成视频应产出 2 个页边界(±0.3s)。"""
    import subprocess
    import common
    work = tmp_path / ".work"; work.mkdir()
    proxy = common.wp(work, "proxy")
    subprocess.run(
        ["ffmpeg", "-v", "error",
         "-f", "lavfi", "-i", "color=red:s=320x180:r=10:d=2",
         "-f", "lavfi", "-i", "color=blue:s=320x180:r=10:d=2",
         "-f", "lavfi", "-i", "color=green:s=320x180:r=10:d=2",
         "-filter_complex", "[0][1][2]concat=n=3:v=1:a=0,format=yuv420p",
         "-y", str(proxy)], check=True)
    assert signals.run_cli(["--work", str(work)]) == 0
    bs = common.load_json(common.wp(work, "page_boundaries"))
    assert len(bs) == 2
    assert abs(bs[0]["t"] - 2.0) < 0.3 and abs(bs[1]["t"] - 4.0) < 0.3
