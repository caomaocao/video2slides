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


def test_hint_target_n_clamps():
    assert signals.hint_target_n(600) == 3        # 10min → round=1 → clamp 3
    assert signals.hint_target_n(4500) == 8       # 75min(#12 体量)
    assert signals.hint_target_n(20000) == 24     # 超长封顶


def test_synth_hints_resonance_merge_and_topn():
    # 页边界长间隙(60s+)末端 + 静音末端落在 ±10s 内 → 合并为一条,score 相加、信号并集
    boundaries = [{"t": 100.0, "score": 0.5}, {"t": 300.0, "score": 0.5},
                  {"t": 305.0, "score": 0.4}]
    silence = [(296.0, 298.5)]                     # 2.5s 静音,end=298.5,与 300 共振
    hints = signals.synth_chapter_hints(
        duration=1200.0, boundaries=boundaries, seg_spans=[],
        silence_spans=silence, heatmap=[])
    assert len(hints) == 1                         # 305 与 300 合并(间隔 5 < 10);100 在… 见下
    h = hints[0]
    assert set(h["signals"]) == {"page-gap", "silence"}
    assert h["score"] == pytest.approx(2.0 + 1.5)
    assert 298.0 < h["t"] < 301.0                  # 加权均值落在共振点附近
    # 注:100→300 间隙 200s≥60 触发 page-gap 事件于 t=300;300→305 间隙 5s 不触发。
    # t=100 处无事件(它是间隙的"起点",事件记在间隙末端——新内容启动处)。


def test_synth_hints_edge_exclusion_and_seg_gap():
    # 段间隙 ≥3s 触发;首尾 60s 内的事件被排除
    seg_spans = [(0.0, 30.0), (34.0, 50.0),        # 间隙 4s@34 → 但 34 < 60 被首部排除
                 (50.0, 200.0), (205.0, 590.0),    # 间隙 5s@205 → 保留
                 (590.0, 599.0)]
    hints = signals.synth_chapter_hints(
        duration=600.0, boundaries=[], seg_spans=seg_spans,
        silence_spans=[], heatmap=[])
    assert [round(h["t"]) for h in hints] == [205]
    assert hints[0]["signals"] == ["seg-gap"]


def test_synth_hints_heat_valley():
    heatmap = [{"t_start": 0.0, "t_end": 100.0, "value": 1.0},
               {"t_start": 100.0, "t_end": 200.0, "value": 0.1},   # < 0.25*max → 谷
               {"t_start": 200.0, "t_end": 300.0, "value": 0.9}]
    hints = signals.synth_chapter_hints(
        duration=1200.0, boundaries=[], seg_spans=[], silence_spans=[], heatmap=heatmap)
    assert [h["signals"] for h in hints] == [["heat-valley"]]
    assert hints[0]["t"] == pytest.approx(150.0)   # 谷桶中点


def test_synth_hints_topn_keeps_strongest():
    # 事件数超过 top-N 时按 score 保强、输出仍按时间升序
    boundaries = [{"t": float(t), "score": 0.5} for t in range(100, 1000, 70)]  # 每 70s 一个 page-gap
    hints = signals.synth_chapter_hints(
        duration=1500.0, boundaries=boundaries, seg_spans=[], silence_spans=[], heatmap=[])
    assert len(hints) <= signals.hint_target_n(1500.0)
    assert hints == sorted(hints, key=lambda h: h["t"])


def test_attach_excerpts_two_before_two_after():
    segments = [{"id": f"s{i}", "t_start": i * 10.0, "t_end": i * 10.0 + 8, "text": f"段{i}"}
                for i in range(10)]
    hints = [{"t": 45.0, "score": 1.0, "signals": ["seg-gap"]}]
    out = signals.attach_excerpts(hints, segments, k=2)
    assert out[0]["before"] == ["段2", "段3"]      # t_end<=45 的最后两段(s3 t_end=38)
    assert out[0]["after"] == ["段5", "段6"]       # t_start>=45 的前两段(s5 t_start=50)
