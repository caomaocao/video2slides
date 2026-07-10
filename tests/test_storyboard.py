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


def test_quote_ok_strips_cjk_curly_quotes_and_fullwidth_parens():
    assert sb_mod.quote_ok("反向传播其实很简单", "他说“反向传播”其实很简单(示例)")


def test_quote_ok_fuzzy_matches_short_quote_in_long_segment():
    """段内短语带一字 ASR 噪声应通过;凭空捏造仍拒绝。"""
    seg = "今天我们把链式法则拆到计算图的每一条边上来理解反向传播的本质"
    assert sb_mod.quote_ok("链式法责拆到计算图", seg)          # 一字之差
    assert not sb_mod.quote_ok("量子纠缠的基本原理", seg)


def test_dedup_drops_all_mutual_dups_without_crash(tmp_path):
    imgs = []
    for i in range(3):
        p = tmp_path / f"r{i}.jpg"; _mkimg(p, "red"); imgs.append(str(p))
    sb = {"outline": [_node("1", imgs[0], 0.9), _node("2", imgs[1], 0.8), _node("3", imgs[2], 0.7)]}
    rep = sb_mod.dedup_across_nodes(sb, candidates=[])
    assert rep["dropped"] == ["2", "3"] and rep["replaced"] == []
    assert sb["outline"][0]["media"] and not sb["outline"][1]["media"] and not sb["outline"][2]["media"]


def test_dedup_replacement_rechecked_against_kept(tmp_path):
    r1 = tmp_path / "r1.jpg"; _mkimg(r1, "red")
    r2 = tmp_path / "r2.jpg"; _mkimg(r2, "red")
    r3 = tmp_path / "r3.jpg"; _mkimg(r3, "red")     # 节点2的备选也是红→必须被拒
    b1 = tmp_path / "b1.jpg"; _mkimg(b1, "blue")
    sb = {"outline": [_node("1", str(r1), 0.9), _node("2", str(r2), 0.8)]}
    cands_red = [{"node_id": "2", "file": str(r3), "t": 5.0, "reason": "scene-peak", "score": 0.5, "dup": False}]
    rep = sb_mod.dedup_across_nodes(sb, cands_red)
    assert rep["dropped"] == ["2"] and rep["replaced"] == []
    # 蓝色备选则替换成功
    sb2 = {"outline": [_node("1", str(r1), 0.9), _node("2", str(r2), 0.8)]}
    cands_blue = [{"node_id": "2", "file": str(b1), "t": 5.0, "reason": "scene-peak", "score": 0.5, "dup": False}]
    rep2 = sb_mod.dedup_across_nodes(sb2, cands_blue)
    assert len(rep2["replaced"]) == 1 and sb2["outline"][1]["media"][0]["proxy_path"] == str(b1)
