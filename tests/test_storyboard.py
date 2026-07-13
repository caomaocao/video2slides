import subprocess
from pathlib import Path

import pytest

import storyboard as sb_mod


def _mkimg(path: Path, color: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi",
                    "-i", f"color={color}:s=64x64:d=0.1", "-frames:v", "1", "-y", str(path)],
                   check=True)


def _node(nid: str, img: str, score: float) -> dict:
    return {"id": nid, "level": 2, "title": "t", "summary": "", "t_start": 0.0, "t_end": 10.0,
            "evidence": [{"segment_id": 0, "quote": "q"}], "children": [],
            "media": [{"type": "frame", "proxy_path": img, "final_path": None,
                       "finalized": False, "t": 1.0, "reason": "scene-peak", "score": score}]}


TRANSCRIPT = {"segments": [
    {"id": 0, "t_start": 0.0, "t_end": 4.0, "text": "大家好,欢迎来到本期视频。"},
    {"id": 1, "t_start": 4.0, "t_end": 9.0, "text": "今天我们聊 Token 到底是什么东西"},
]}


def _sb(quote="Token 到底是什么", seg=1):
    return {"video": {"duration": 600.0},
            "outline": [{"id": "1", "level": 1, "title": "开场", "summary": "",
                         "t_start": 0.0, "t_end": 30.0,
                         "evidence": [{"segment_id": seg, "quote": quote}],
                         "media": [], "children": []}]}


def test_quote_ok_substring_ignores_punct_and_space():
    assert sb_mod.quote_ok("Token到底是什么", "今天我们聊 Token 到底是什么东西")
    assert sb_mod.quote_ok("token 到底是什么", "今天我们聊 Token 到底是什么东西")


def test_quote_ok_rejects_fabricated():
    assert not sb_mod.quote_ok("量子纠缠的原理", "今天我们聊 Token 到底是什么东西")
    assert not sb_mod.quote_ok("", "任意")


def test_validate_pass_and_quote_failure():
    ok = sb_mod.validate(_sb(), TRANSCRIPT, 600.0)
    assert ok["ok"] and ok["quote_failures"] == []
    bad = sb_mod.validate(_sb(quote="根本没说过的话"), TRANSCRIPT, 600.0)
    assert not bad["ok"] and bad["quote_failures"] == ["1"]


def test_validate_schema_and_time():
    s = _sb(); s["outline"][0].pop("evidence")
    r = sb_mod.validate(s, TRANSCRIPT, 600.0)
    assert r["schema_errors"]
    s2 = _sb(); s2["outline"][0]["t_end"] = 9999.0
    assert sb_mod.validate(s2, TRANSCRIPT, 600.0)["time_errors"]


def test_aggregate_media_topk_from_leaves():
    outline = [{"id": "1", "level": 1, "t_start": 0, "t_end": 60, "title": "", "summary": "",
                "evidence": [{"segment_id": 0, "quote": "大家好"}],
                "media": [],
                "children": [
                    {"id": "1.1", "level": 2, "t_start": 0, "t_end": 30, "title": "", "summary": "",
                     "evidence": [{"segment_id": 0, "quote": "大家好"}], "children": [],
                     "media": [{"type": "frame", "proxy_path": "a.jpg", "score": 0.9,
                                "t": 3.0, "finalized": False, "final_path": None}]},
                    {"id": "1.2", "level": 2, "t_start": 30, "t_end": 60, "title": "", "summary": "",
                     "evidence": [{"segment_id": 1, "quote": "Token"}], "children": [],
                     "media": [{"type": "frame", "proxy_path": "b.jpg", "score": 0.95,
                                "t": 40.0, "finalized": False, "final_path": None}]},
                ]}]
    agg = sb_mod.aggregate_media(outline, depth=1, k=1)
    assert [m["proxy_path"] for m in agg["1"]] == ["b.jpg"]     # 取子树最高分


def test_norm_text_strips_curly_quotes_directly():
    # 防回归:直接断言弯引号(U+201C/201D)被剥离,不经过 quote_ok 的 fuzzy 兜底
    # (Task 4 曾把 _PUNCT 里的弯引号误改成直引号,fuzzy 兜底掩盖了该回归)
    assert sb_mod.norm_text("他说“反向传播”其实很简单（示例）") == "他说反向传播其实很简单示例"


def test_quote_ok_strips_cjk_curly_quotes_and_fullwidth_parens():
    assert sb_mod.quote_ok("反向传播其实很简单", "他说“反向传播”其实很简单（示例）")
    assert sb_mod.quote_ok("模型一次能处理的最大信息量", "模型一次能处理的最大信息量，就叫上下文窗口！")
    assert sb_mod.quote_ok("你好世界", "你好，世界，很高兴认识你")   # 全角标点在匹配片段中间:旧正则会误杀(真 RED 守护)


def test_quote_ok_fuzzy_matches_short_quote_in_long_segment():
    """段内短语带一字 ASR 噪声应通过;凭空捏造仍拒绝。"""
    seg = "今天我们把链式法则拆到计算图的每一条边上来理解反向传播的本质"
    assert sb_mod.quote_ok("链式法责拆到计算图", seg)          # 一字之差
    assert not sb_mod.quote_ok("量子纠缠的基本原理", seg)


# 切片4 票01:dedup 标注化——重复组打标注,不删除不替换(spec v0.5 §6)
def test_dedup_annotates_groups_without_deletion(tmp_path):
    imgs = []
    for i in range(3):
        p = tmp_path / f"r{i}.jpg"; _mkimg(p, "red"); imgs.append(str(p))
    sb = {"outline": [_node("1", imgs[0], 0.9), _node("2", imgs[1], 0.8), _node("3", imgs[2], 0.7)]}
    rep = sb_mod.dedup_across_nodes(sb)
    # media 总数不变:任何节点不被降级纯文字
    assert all(nd["media"] for nd in sb["outline"])
    # 同组一致,恰一个 primary 且落在最高分节点
    ms = [nd["media"][0] for nd in sb["outline"]]
    assert len({m["dedup_group"] for m in ms}) == 1 and ms[0]["dedup_group"] is not None
    assert [m["dedup_primary"] for m in ms] == [True, False, False]
    assert len(rep["groups"]) == 1
    assert [x["node"] for x in rep["groups"][0]["members"]] == ["1", "2", "3"]


def test_dedup_singletons_get_null_group_and_primary_true(tmp_path):
    r1 = tmp_path / "r1.jpg"; _mkimg(r1, "red")
    r2 = tmp_path / "r2.jpg"; _mkimg(r2, "red")
    b1 = tmp_path / "b1.jpg"; _mkimg(b1, "blue")
    sb = {"outline": [_node("1", str(r1), 0.9), _node("2", str(r2), 0.8), _node("3", str(b1), 0.5)]}
    rep = sb_mod.dedup_across_nodes(sb)
    m1, m2, m3 = (nd["media"][0] for nd in sb["outline"])
    assert m1["dedup_group"] == m2["dedup_group"] and m1["dedup_group"] is not None
    assert m1["dedup_primary"] and not m2["dedup_primary"]
    assert m3["dedup_group"] is None and m3["dedup_primary"]    # 无重复:组 null、自身即 primary
    assert len(rep["groups"]) == 1


def test_validate_checks_dedup_primary_uniqueness(tmp_path):
    img = tmp_path / "a.jpg"; _mkimg(img, "red")
    def annotated(p1: bool, p2: bool) -> dict:
        s = {"outline": [_node("1", str(img), 0.9), _node("2", str(img), 0.8)]}
        s["outline"][0]["media"][0].update(dedup_group="g1", dedup_primary=p1)
        s["outline"][1]["media"][0].update(dedup_group="g1", dedup_primary=p2)
        s["outline"][0]["evidence"] = [{"segment_id": 0, "quote": "大家好"}]
        s["outline"][1]["evidence"] = [{"segment_id": 0, "quote": "欢迎来到本期视频"}]
        return s
    assert sb_mod.validate(annotated(True, False), TRANSCRIPT, 600.0)["ok"]     # 正确标注通过
    r = sb_mod.validate(annotated(True, True), TRANSCRIPT, 600.0)               # 双 primary 被拦
    assert not r["ok"] and any("primary" in e for e in r["schema_errors"])


# Task 4: 分章校验测试
def _plan(chs):
    return {"source": "hints", "chapters": chs}


def _l1(spans):
    return [{"id": f"c{i}", "title": f"章{i}", "t_start": a, "t_end": b,
             "evidence": [{"segment_id": "s0", "quote": "q"}]}
            for i, (a, b) in enumerate(spans, 1)]


def test_chapter_plan_ok():
    plan = _plan([{"idx": 1, "title": "A", "t_start": 0.0, "t_end": 600.0},
                  {"idx": 2, "title": "B", "t_start": 600.0, "t_end": 1200.0}])
    assert sb_mod.validate_chapter_plan(plan, _l1([(0.0, 600.0), (600.0, 1200.0)]), 1200.0) == []


def test_chapter_plan_gap_overlap_coverage():
    plan = _plan([{"idx": 1, "title": "A", "t_start": 5.0, "t_end": 500.0},     # 首章未从 0 起
                  {"idx": 2, "title": "B", "t_start": 520.0, "t_end": 1100.0}])  # 缝 20s;末章未到 1200
    errs = sb_mod.validate_chapter_plan(plan, _l1([(5.0, 500.0), (520.0, 1100.0)]), 1200.0)
    assert len(errs) == 3


def test_chapter_plan_l1_mismatch():
    plan = _plan([{"idx": 1, "title": "A", "t_start": 0.0, "t_end": 600.0},
                  {"idx": 2, "title": "B", "t_start": 600.0, "t_end": 1200.0}])
    # level-1 只有一个节点 → 数量不一致
    errs = sb_mod.validate_chapter_plan(plan, _l1([(0.0, 1200.0)]), 1200.0)
    assert any("level-1" in e for e in errs)
    # 数量一致但时间窗偏差超容差(30s)
    errs2 = sb_mod.validate_chapter_plan(plan, _l1([(0.0, 640.0), (640.0, 1200.0)]), 1200.0)
    assert any("偏差" in e for e in errs2)


def test_validate_cli_without_chapter_plan_unchanged(tmp_path):
    # chapter_plan 缺失:validate 行为与现状一致(既有测试已覆盖通过路径,这里锁"不因缺失报错")
    sb = {"outline": [{"id": "1", "title": "t", "t_start": 0.0, "t_end": 10.0,
                       "evidence": [{"segment_id": "s0", "quote": "你好世界"}]}]}
    tr = {"segments": [{"id": "s0", "t_start": 0.0, "t_end": 10.0, "text": "你好世界"}]}
    r = sb_mod.validate(sb, tr, 10.0)
    assert r["ok"] and "chapter_errors" not in r
