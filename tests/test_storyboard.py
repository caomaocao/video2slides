import pytest

import storyboard as sb_mod


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
