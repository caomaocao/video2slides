from pathlib import Path

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


def test_align_window_never_shrinks_forward():
    """边界因抖动落在 t_start 之后 0.5s 内时,起点保持不变(只前扩不后缩)。"""
    b = [{"n": 1, "t": 12.4, "score": 0.5}]
    assert frames.align_window(12.0, 30.0, b, 600.0) == (12.0, 30.0)


def test_plan_candidates_skips_trailing_edge_boundary():
    """窗尾放不下峰后稳定帧的边界不产候选(该页由下一节点前扩覆盖),回退窗中点。"""
    b = [{"n": 1, "t": 21.98, "score": 0.5}]
    leaf = {"id": "3.1", "win": (10.0, 22.0)}
    cs = frames.plan_candidates(leaf, b, 600.0)
    assert len(cs) == 1 and cs[0]["reason"] == "window-midpoint"


def test_t_to_frame_nearest():
    rows = [{"n": i, "t": i * 0.1, "score": 0} for i in range(100)]
    assert frames.t_to_frame(2.04, rows) == 20
    assert frames.t_to_frame(2.06, rows) == 21


def test_build_select_expr_sorted_unique():
    assert frames.build_select_expr([300, 60, 300]) == "select='eq(n,60)+eq(n,300)'"


def test_extract_and_dedup_on_synthetic(tmp_path):
    """红红蓝三帧候选:第二张红判重,蓝不判重。"""
    import subprocess
    import common
    work = tmp_path / ".work"; work.mkdir()
    proxy = common.wp(work, "proxy")
    subprocess.run(
        ["ffmpeg", "-v", "error",
         "-f", "lavfi", "-i", "color=red:s=320x180:r=10:d=2",
         "-f", "lavfi", "-i", "color=blue:s=320x180:r=10:d=2",
         "-filter_complex", "[0][1]concat=n=2:v=1:a=0,format=yuv420p", "-y", str(proxy)],
        check=True)
    rows = [{"n": i, "t": i / 10, "score": 0.0} for i in range(40)]
    cands = [
        {"node_id": "1", "t": 0.5, "reason": "scene-peak", "peak_score": 0.4},
        {"node_id": "2", "t": 1.5, "reason": "scene-peak", "peak_score": 0.4},   # 仍是红
        {"node_id": "3", "t": 3.0, "reason": "scene-peak", "peak_score": 0.4},   # 蓝
    ]
    out = frames.extract_candidates(work, cands, rows)
    assert all(Path(c["file"]).exists() for c in out)
    d = frames.dedup_candidates(out)
    assert [c.get("dup", False) for c in d] == [False, True, False]


def test_extract_candidates_keeps_all_same_frame_collisions(tmp_path):
    """两个不同节点的候选命中同一帧号:两条都保留(不因 by_n 合并丢弃),且共享同一抽帧文件
    (Task 8 review 遗留问题:同帧号候选被 setdefault 静默丢弃,导致某要点候选清零、下游不可恢复)。"""
    import subprocess
    import common
    work = tmp_path / ".work"; work.mkdir()
    proxy = common.wp(work, "proxy")
    subprocess.run(
        ["ffmpeg", "-v", "error",
         "-f", "lavfi", "-i", "color=red:s=320x180:r=10:d=2",
         "-y", str(proxy)],
        check=True)
    rows = [{"n": i, "t": i / 10, "score": 0.0} for i in range(20)]
    cands = [
        {"node_id": "1", "t": 1.0, "reason": "scene-peak", "peak_score": 0.4},
        {"node_id": "2", "t": 1.0, "reason": "scene-peak", "peak_score": 0.4},   # 与节点1同帧号
    ]
    out = frames.extract_candidates(work, cands, rows)
    assert len(out) == 2
    assert {c["node_id"] for c in out} == {"1", "2"}
    assert out[0]["file"] == out[1]["file"]
    assert Path(out[0]["file"]).exists()


def test_score_formula_with_and_without_text():
    cands = [{"node_id": "1", "dup": False, "peak_score": 0.5, "_edge": 0.4, "_text": 0.8},
             {"node_id": "1", "dup": False, "peak_score": 0.5, "_edge": 0.4, "_text": None},
             {"node_id": "1", "dup": True, "peak_score": 0.9, "_edge": 0.9, "_text": 0.9}]
    out = frames.apply_scores(cands)
    assert out[0]["score"] == pytest.approx(0.5 * 0.8 + 0.3 * 0.4 + 0.2 * 0.5)
    assert out[1]["score"] == pytest.approx(0.6 * 0.4 + 0.4 * 0.5)
    assert out[2]["score"] == 0.0


def test_prune_top3_keeps_best_dup_as_fallback():
    cands = [{"node_id": "1", "dup": True, "score": 0.0, "_raw": 0.9},
             {"node_id": "1", "dup": True, "score": 0.0, "_raw": 0.3}]
    sel = frames.prune_top3(cands)
    assert len(sel["1"]) == 1 and sel["1"][0]["_raw"] == 0.9


def test_make_sheets_caps_two_per_chapter(tmp_path):
    import subprocess
    import common
    work = tmp_path / ".work"
    fdir = common.wp(work, "frames_dir"); fdir.mkdir(parents=True)
    files = []
    for i in range(20):                                   # 20 帧 > 2 张 3x3 sheet 容量
        f = fdir / f"f_{i:05d}.jpg"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                        "-i", f"color=gray:s=320x180:d=0.1", "-frames:v", "1", "-y", str(f)],
                       check=True)
        files.append(f)
    selected = {"1": [{"node_id": "1", "t": float(i), "file": str(f), "score": 0.5}
                      for i, f in enumerate(files)]}
    sheets = frames.make_sheets(work, selected, chapters=[])
    assert len(sheets) == 2                               # 每章 ≤2 张(预算)
    assert sheets[0]["map"]["truncated"] is True
    assert Path(sheets[0]["sheet"]).exists()


def test_group_by_chapters_covers_gaps_and_tail():
    """章间缝隙与末章之后的候选必须归入最近的章,零丢帧。"""
    chapters = [{"title": "A", "t_start": 0.0, "t_end": 5.0},
                {"title": "B", "t_start": 5.0, "t_end": 10.0}]
    flat = [{"node_id": "1", "t": 2.0}, {"node_id": "2", "t": 12.0}]   # 12.0 在末章之后
    groups = frames._group_by_chapters(flat, chapters)
    all_ids = {c["node_id"] for _, g in groups for c in g}
    assert all_ids == {"1", "2"}
    assert groups[1][0] == "B" and groups[1][1][0]["t"] == 12.0


def test_cap_per_node_round_robin_no_starvation():
    """8 节点 × 3 候选,cap 18:每个节点至少 1 帧可见,无节点被整体截掉。"""
    g = [{"node_id": str(n), "t": n * 10.0 + r} for n in range(8) for r in range(3)]
    g.sort(key=lambda c: c["t"])
    picked, truncated, dropped = frames._cap_per_node(g, cap=18)
    assert truncated is True and dropped == []
    assert {c["node_id"] for c in picked} == {str(n) for n in range(8)}


def test_highres_selector():
    assert frames.highres_format_selector().startswith("bv*[height>=1080]")


def test_finalize_marks_quality_limited_on_failure(tmp_path, monkeypatch):
    import common
    work = tmp_path / ".work"
    fdir = common.wp(work, "frames_dir"); fdir.mkdir(parents=True)
    proxy_frame = fdir / "f_00001.jpg"; proxy_frame.write_bytes(b"fake")
    sb = {"video": {"duration": 100.0},
          "outline": [{"id": "1", "level": 1, "title": "x", "summary": "", "t_start": 0, "t_end": 50,
                       "evidence": [{"segment_id": 0, "quote": "q"}], "children": [],
                       "media": [{"type": "frame", "proxy_path": str(proxy_frame), "t": 3.0,
                                  "score": 0.5, "finalized": False, "final_path": None,
                                  "on_page": True}]}]}
    common.save_json(common.wp(work, "storyboard"), sb)
    common.save_json(common.wp(work, "meta"),
                     {"duration": 100.0, "source": {"canonical_url": "https://example.com/x",
                                                    "platform": "youtube"}})
    monkeypatch.setattr(frames, "_direct_url", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("网络失败")))
    rep = frames.finalize(work, cookies=None)
    out = common.load_json(common.wp(work, "storyboard"))
    m = out["outline"][0]["media"][0]
    assert m["finalized"] is True and m["quality_limited"] is True
    assert m["final_path"] == str(proxy_frame)
    assert rep["degraded"] == 1


def test_finalize_names_by_node_and_reuses_direct_url(tmp_path, monkeypatch):
    """文件名含 node_id 防跨节点同 t 覆盖;直链一批只取一次;clip 不处理。"""
    import common
    work = tmp_path / ".work"
    fdir = common.wp(work, "frames_dir"); fdir.mkdir(parents=True)
    p1 = fdir / "f_00001.jpg"; p1.write_bytes(b"a")
    p2 = fdir / "f_00002.jpg"; p2.write_bytes(b"b")

    def med(p):
        return {"type": "frame", "proxy_path": str(p), "t": 3.0, "score": 0.5,
                "finalized": False, "final_path": None, "on_page": True}

    sb = {"video": {"duration": 100.0}, "outline": [
        {"id": "1", "level": 1, "title": "x", "summary": "", "t_start": 0, "t_end": 50,
         "evidence": [{"segment_id": 0, "quote": "q"}], "children": [], "media": [med(p1)]},
        {"id": "2", "level": 1, "title": "y", "summary": "", "t_start": 50, "t_end": 100,
         "evidence": [{"segment_id": 0, "quote": "q"}], "children": [],
         "media": [med(p2), {"type": "clip", "on_page": True, "finalized": False,
                             "t_start": 1.0, "t_end": 3.0, "final_path": None}]}]}
    common.save_json(common.wp(work, "storyboard"), sb)
    common.save_json(common.wp(work, "meta"),
                     {"duration": 100.0,
                      "source": {"canonical_url": "https://example.com/x", "platform": "youtube"}})
    calls = []
    monkeypatch.setattr(frames, "_direct_url", lambda *a, **k: calls.append(1) or "fake://url")
    monkeypatch.setattr(frames, "grab_final_frame",
                        lambda url, t, out, referer=None: Path(out).write_bytes(b"hi"))
    rep = frames.finalize(work, cookies=None)
    assert rep["done"] == 2 and rep["degraded"] == 0
    out = common.load_json(common.wp(work, "storyboard"))
    assert out["outline"][0]["media"][0]["final_path"].endswith("final_1_3.0.jpg")
    assert out["outline"][1]["media"][0]["final_path"].endswith("final_2_3.0.jpg")
    assert len(calls) == 1                                        # 直链复用
    assert out["outline"][1]["media"][1].get("finalized") is False  # clip 不处理


def test_grab_final_frame_referer_header(monkeypatch, tmp_path):
    """B 站 CDN 直链需 Referer 头(裸拉 403,验收 #11 实测);无 referer 时不加头。"""
    seen = {}
    monkeypatch.setattr(frames, "run",
                        lambda cmd, timeout=300: seen.update(cmd=[str(c) for c in cmd]))
    frames.grab_final_frame("http://x/v.m4s", 1.0, tmp_path / "o.jpg",
                            referer="https://www.bilibili.com/")
    assert any("Referer: https://www.bilibili.com/" in c for c in seen["cmd"])
    frames.grab_final_frame("http://x/v.m4s", 1.0, tmp_path / "o2.jpg")
    assert not any("Referer" in c for c in seen["cmd"])
