from pathlib import Path

import pytest

import common
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
    """事件数超过 top-N 时按 score 保强、淘汰低权重、输出仍按时间升序。"""
    duration = 2400.0
    target_n = signals.hint_target_n(duration)  # 4

    # 5 个 page-gap 事件（高权重 2.0），间隔 100s，都在排除区外（>=60 && <=2340）
    boundaries = [
        {"t": 100.0, "score": 0.5},
        {"t": 200.0, "score": 0.5},  # (100, 200): 100 >= 60 → page-gap@200
        {"t": 300.0, "score": 0.5},  # (200, 300): 100 >= 60 → page-gap@300
        {"t": 400.0, "score": 0.5},  # (300, 400): 100 >= 60 → page-gap@400
        {"t": 500.0, "score": 0.5},  # (400, 500): 100 >= 60 → page-gap@500
        {"t": 600.0, "score": 0.5},  # (500, 600): 100 >= 60 → page-gap@600
    ]

    # 4 个 seg-gap 事件（低权重 1.0），与任何相邻事件间隔 > 10s 不合并
    seg_spans = [
        (60.0, 200.0),
        (215.0, 250.0),  # (200, 215): 15 >= 3 → seg-gap@215
        (265.0, 400.0),  # (250, 265): 15 >= 3 → seg-gap@265
        (415.0, 450.0),  # (400, 415): 15 >= 3 → seg-gap@415
        (465.0, 2300.0), # (450, 465): 15 >= 3 → seg-gap@465
    ]

    hints = signals.synth_chapter_hints(
        duration=duration, boundaries=boundaries, seg_spans=seg_spans,
        silence_spans=[], heatmap=[])

    # 总共生成 5 个 page-gap + 4 个 seg-gap = 9 个事件，top-4 保留最强的 4 个（都是 page-gap）
    assert len(hints) == target_n, f"Expected {target_n} hints, got {len(hints)}"
    for h in hints:
        assert h["signals"] == ["page-gap"], f"Expected page-gap, got {h['signals']}"
        assert h["score"] == 2.0, f"Expected score 2.0, got {h['score']}"
    # 输出按 t 升序
    assert hints == sorted(hints, key=lambda h: h["t"])


def test_synth_hints_boundary_equals():
    """五个阈值'恰好等于'边界用例验证。"""
    duration = 2000.0

    # 1. 页边界间隙恰好 60.0 → 触发 page-gap
    boundaries = [
        {"t": 100.0, "score": 0.5},
        {"t": 160.0, "score": 0.5},  # 间隙=60.0，恰好等于阈值 → page-gap@160
    ]
    hints = signals.synth_chapter_hints(duration, boundaries, [], [], [])
    assert any(h["signals"] == ["page-gap"] and h["t"] == 160.0 for h in hints), \
        "间隙恰好 60.0 应触发 page-gap"

    # 2. 段间隙恰好 3.0 → 触发 seg-gap
    seg_spans = [(100.0, 200.0), (203.0, 300.0)]  # 间隙=203-200=3.0
    hints = signals.synth_chapter_hints(duration, [], seg_spans, [], [])
    assert any(h["signals"] == ["seg-gap"] and h["t"] == 203.0 for h in hints), \
        "段间隙恰好 3.0 应触发 seg-gap"

    # 3. 静音时长恰好 2.0 → 触发 silence
    silence_spans = [(100.0, 102.0)]  # 时长=2.0，恰好等于阈值
    hints = signals.synth_chapter_hints(duration, [], [], silence_spans, [])
    assert any(h["signals"] == ["silence"] and h["t"] == 102.0 for h in hints), \
        "静音时长恰好 2.0 应触发 silence"

    # 4. 两事件相距恰好 10.0 → 合并为一条（断言对整个返回值，不做过滤窗——避免伪通过）
    silence_spans = [(100.0, 102.0), (110.0, 112.0)]  # 事件记在 span 末端:@102 与 @112,恰好相距 10.0
    hints = signals.synth_chapter_hints(duration, [], [], silence_spans, [])
    assert len(hints) == 1, \
        f"两个事件相距恰好 10.0 应合并为 1 条，得到 {len(hints)}"
    assert hints[0]["score"] == pytest.approx(3.0)   # 1.5 + 1.5 合并
    assert "silence" in hints[0]["signals"]

    # 5. 事件 t 恰好等于 HINT_EDGE 和 duration-HINT_EDGE → 都保留（闭区间）
    # HINT_EDGE=60, duration-HINT_EDGE=2000-60=1940
    boundaries = [
        {"t": 0.0, "score": 0.5},
        {"t": 60.0, "score": 0.5},    # 页边界间隙 60 → page-gap@60
        {"t": 1880.0, "score": 0.5},
        {"t": 1940.0, "score": 0.5},  # 页边界间隙 60 → page-gap@1940
    ]
    hints = signals.synth_chapter_hints(duration, boundaries, [], [], [])
    hints_t = [h["t"] for h in hints]
    assert 60.0 in hints_t, f"t=HINT_EDGE 应保留，hints_t={hints_t}"
    assert 1940.0 in hints_t, f"t=duration-HINT_EDGE 应保留，hints_t={hints_t}"


def test_synth_hints_chained_merge():
    """链式合并:三个同权重事件末端间隔 5.5/5s(都<10) → 链式并入一条簇。

    验证链式合并的行为(spec _merge_events 注释):
    簇内相邻事件各自 ≤win 即持续并入,簇总跨度可超 win——共振窗约束的是相邻间距而非簇宽,这是有意行为。
    事件 A(102) 与 B(107.5) 距 5.5≤10 → 合并得 AB(104.75)；
    AB(104.75) 与 C(112.5) 距 7.75≤10 → 继续合并得 ABC。
    """
    duration = 500.0

    # 构造三个 silence 事件，末端相距都 < 10s，应链式合并成 1 条
    silence_spans = [
        (100.0, 102.0),    # silence@102.0, weight=1.5
        (105.0, 107.5),    # silence@107.5, 距 102 的 5.5 < 10 → 合并
        (110.0, 112.5),    # silence@112.5, 距合并后中点的 ~7.75 < 10 → 继续并入
    ]

    hints = signals.synth_chapter_hints(duration, [], [], silence_spans, [])

    # 应该只有 1 条合并后的事件（三个相邻间距都 ≤10 的事件链式并入一条簇）
    assert len(hints) == 1, f"三个事件应链式合并为 1 条，得到 {len(hints)} 条"

    h = hints[0]
    assert "silence" in h["signals"]
    # 中点应该接近加权均值 (102*1.5 + 107.5*1.5 + 112.5*1.5) / (1.5*3) = (102+107.5+112.5)/3 ≈ 107.33
    assert h["t"] == pytest.approx((102.0 + 107.5 + 112.5) / 3)


def test_synth_hints_zero_heatmap_no_valleys():
    """全零 heatmap 应不产生 heat-valley 事件。"""
    duration = 500.0

    # 全零 heatmap
    heatmap = [
        {"t_start": 0.0, "t_end": 100.0, "value": 0.0},
        {"t_start": 100.0, "t_end": 200.0, "value": 0.0},
        {"t_start": 200.0, "t_end": 300.0, "value": 0.0},
    ]

    hints = signals.synth_chapter_hints(duration, [], [], [], heatmap)

    # 不应该产生 heat-valley 事件
    assert not any("heat-valley" in h["signals"] for h in hints), \
        "全零 heatmap 不应产生 heat-valley 事件"


def test_attach_excerpts_two_before_two_after():
    segments = [{"id": f"s{i}", "t_start": i * 10.0, "t_end": i * 10.0 + 8, "text": f"段{i}"}
                for i in range(10)]
    hints = [{"t": 45.0, "score": 1.0, "signals": ["seg-gap"]}]
    out = signals.attach_excerpts(hints, segments, k=2)
    assert out[0]["before"] == ["段2", "段3"]      # t_end<=45 的最后两段(s3 t_end=38)
    assert out[0]["after"] == ["段5", "段6"]       # t_start>=45 的前两段(s5 t_start=50)


def _hints_work(tmp_path, chapters=(), heatmap=(), duration=2400.0):
    """构造 --chapter-hints 所需最小 .work:meta/transcript/page_boundaries/priors。"""
    common.save_json(common.wp(tmp_path, "meta"), {"duration": duration, "title": "t"})
    segs = [{"id": f"s{i}", "t_start": i * 20.0, "t_end": i * 20.0 + 15, "text": f"第{i}段"}
            for i in range(int(duration // 20))]
    common.save_json(common.wp(tmp_path, "transcript"), {"segments": segs})
    common.save_json(common.wp(tmp_path, "page_boundaries"),
                     [{"n": i, "t": t, "score": 0.5} for i, t in enumerate([100.0, 400.0, 900.0])])
    common.save_json(common.wp(tmp_path, "priors"),
                     {"chapters": list(chapters), "heatmap": list(heatmap),
                      "danmaku_density": [], "page_boundaries": []})
    return tmp_path


def test_chapter_hints_cli_native_passthrough(tmp_path, capsys):
    w = _hints_work(tmp_path, chapters=[
        {"title": "开场", "t_start": 0.0, "t_end": 1200.0},
        {"title": "正片", "t_start": 1200.0, "t_end": 2400.0}])
    rc = signals.run_cli(["--chapter-hints", "--work", str(w)])
    assert rc == 0
    out = common.load_json(common.wp(w, "chapter_hints"))
    assert out["fallback"] is None
    assert [h["signals"] for h in out["hints"]] == [["native"], ["native"]]
    assert out["hints"][0]["title"] == "开场"
    assert out["hints"][1]["t"] == 1200.0
    assert "before" in out["hints"][1] and "after" in out["hints"][1]


def test_chapter_hints_cli_synth_without_audio(tmp_path):
    # 无 audio.mp3(字幕路径)→ 静音信号列跳过,其余信号照常;不报错
    w = _hints_work(tmp_path)
    rc = signals.run_cli(["--chapter-hints", "--work", str(w)])
    assert rc == 0
    out = common.load_json(common.wp(w, "chapter_hints"))
    assert out["fallback"] is None
    assert all("silence" not in h["signals"] for h in out["hints"])
    assert all(h["idx"] == i + 1 for i, h in enumerate(out["hints"]))


def test_chapter_hints_cli_uniform_fallback(tmp_path):
    # 信号全无(无边界/无间隙/无静音/无热度)→ 每 600s 均分,fallback 标注
    common.save_json(common.wp(tmp_path, "meta"), {"duration": 2400.0, "title": "t"})
    common.save_json(common.wp(tmp_path, "transcript"),
                     {"segments": [{"id": "s0", "t_start": 0.0, "t_end": 2400.0, "text": "整段"}]})
    common.save_json(common.wp(tmp_path, "page_boundaries"), [])
    common.save_json(common.wp(tmp_path, "priors"),
                     {"chapters": [], "heatmap": [], "danmaku_density": [], "page_boundaries": []})
    rc = signals.run_cli(["--chapter-hints", "--work", str(tmp_path)])
    assert rc == 0
    out = common.load_json(common.wp(tmp_path, "chapter_hints"))
    assert out["fallback"] == "uniform"
    assert [h["t"] for h in out["hints"]] == [600.0, 1200.0, 1800.0]
    assert all(h["signals"] == ["uniform"] for h in out["hints"])
