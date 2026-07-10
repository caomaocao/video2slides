import pytest

import frames


B = [{"n": 60, "t": 2.0, "score": 0.41}, {"n": 300, "t": 10.0, "score": 0.52},
     {"n": 600, "t": 20.0, "score": 0.38}]


def test_align_window_expands_to_prev_boundary():
    # 要点 12.0–18.0s,上一页边界 10.0s → 前扩到 10.0
    assert frames.align_window(12.0, 18.0, B, 600.0) == (10.0, 18.0)


def test_align_window_no_expand_when_boundary_too_far():
    # 上一边界距 t_start 超 30s → 不前扩(初始值)
    assert frames.align_window(55.0, 60.0, B, 600.0) == (55.0, 60.0)


def test_align_window_clamps_to_zero():
    assert frames.align_window(1.0, 5.0, [], 600.0) == (1.0, 5.0)


def test_plan_candidates_peaks_with_offset():
    leaf = {"id": "1.1", "win": (8.0, 22.0)}
    cs = frames.plan_candidates(leaf, B, 600.0)
    assert [c["reason"] for c in cs] == ["scene-peak", "scene-peak"]
    assert cs[0]["t"] == pytest.approx(10.7)      # 10.0 + 0.7 避糊偏移
    assert all(c["node_id"] == "1.1" for c in cs)


def test_plan_candidates_midpoint_fallback():
    leaf = {"id": "2.3", "win": (30.0, 40.0)}
    cs = frames.plan_candidates(leaf, B, 600.0)
    assert len(cs) == 1 and cs[0]["reason"] == "window-midpoint"
    assert cs[0]["t"] == pytest.approx(35.0)


def test_t_to_frame_nearest():
    rows = [{"n": i, "t": i * 0.1, "score": 0} for i in range(100)]
    assert frames.t_to_frame(2.04, rows) == 20
    assert frames.t_to_frame(2.06, rows) == 21
