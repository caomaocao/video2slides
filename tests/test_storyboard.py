import shutil
from pathlib import Path

import pytest

import storyboard as sb_mod
from common import load_json, save_json, wp


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
def test_dedup_annotates_groups_without_deletion(tmp_path, fake_rgb_signature):
    imgs = []
    for i in range(3):
        p = tmp_path / f"r{i}.jpg"; p.write_bytes(b"red"); imgs.append(str(p))
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


def test_dedup_singletons_get_null_group_and_primary_true(tmp_path, fake_rgb_signature):
    r1 = tmp_path / "r1.jpg"; r1.write_bytes(b"red")
    r2 = tmp_path / "r2.jpg"; r2.write_bytes(b"red")
    b1 = tmp_path / "b1.jpg"; b1.write_bytes(b"blue")
    sb = {"outline": [_node("1", str(r1), 0.9), _node("2", str(r2), 0.8), _node("3", str(b1), 0.5)]}
    rep = sb_mod.dedup_across_nodes(sb)
    m1, m2, m3 = (nd["media"][0] for nd in sb["outline"])
    assert m1["dedup_group"] == m2["dedup_group"] and m1["dedup_group"] is not None
    assert m1["dedup_primary"] and not m2["dedup_primary"]
    assert m3["dedup_group"] is None and m3["dedup_primary"]    # 无重复:组 null、自身即 primary
    assert len(rep["groups"]) == 1


# 跨平台可移植性 票03:dedup --no-vision 抬合并门 → 宁欠勿并(无视觉宿主降级,spec §视觉能力处理 6a)
def test_dedup_no_vision_under_merges(monkeypatch, tmp_path):
    """diff 落在 [NO_VISION, DUP) 之间的两帧:正常模式合并,--no-vision 不合并(宁欠勿并)。"""
    monkeypatch.setattr(sb_mod, "rgb_signature", lambda p: b"\x00" * 768)
    # 0.07 夹在 DUP_RATIO_NO_VISION(0.05)与 DUP_RATIO(0.10)之间,恰能验出阈值翻转
    monkeypatch.setattr(sb_mod, "sig_diff_ratio", lambda a, b, **k: 0.07)

    def _two():
        p1 = tmp_path / "a.jpg"; p1.write_bytes(b"a")
        p2 = tmp_path / "b.jpg"; p2.write_bytes(b"b")
        return {"outline": [_node("1", str(p1), 0.9), _node("2", str(p2), 0.8)]}

    rep_n = sb_mod.dedup_across_nodes(_two())                      # 默认视觉模式
    assert len(rep_n["groups"]) == 1                              # 0.07<0.10 → 并成一组

    sb_nv = _two()
    rep_v = sb_mod.dedup_across_nodes(sb_nv, no_vision=True)       # 无视觉:抬门(降阈)
    assert len(rep_v["groups"]) == 0                              # 0.07≥0.05 → 不并,各自单帧
    ms = [nd["media"][0] for nd in sb_nv["outline"]]
    assert all(m["dedup_group"] is None and m["dedup_primary"] for m in ms)  # 单帧组 null/primary


def test_validate_checks_dedup_primary_uniqueness(tmp_path):
    img = tmp_path / "a.jpg"; img.write_bytes(b"img")   # validate 只查存在性,纯字节即可
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


# 切片4 票02:export 导出契约(spec v0.5 §6.5)——组装/校验/自包含/schema 对拍
def test_export_produces_self_contained_doc(tmp_path, export_work):
    out, work = export_work(tmp_path)
    assert sb_mod.export_index(work) == 0
    doc = load_json(out / "video_index.json")
    assert doc["schema_version"] and doc["video"]["platform"] == "youtube"
    assert "signals" not in doc["video"]                       # .work 内部指针不外泄
    assert doc["transcript"]["timestamp_granularity"] == "segment"
    assert [s["id"] for s in doc["transcript"]["segments"]] == [0, 1]   # 全量转写内嵌
    frame = doc["outline"][0]["media"][0]
    assert frame["path"].startswith("frames/") and (out / frame["path"]).exists()
    assert frame["resolution"] and frame["dedup_primary"] is True
    clip = doc["outline"][0]["media"][1]
    assert clip["poster"] == frame["path"]                     # poster 复用同一份导出帧
    assert "proxy_path" not in frame and "finalized" not in frame       # 内部字段不外泄
    shutil.rmtree(work)                                        # 自包含:删 .work 不断链
    assert (out / frame["path"]).exists()
    assert (out / doc["outline"][0]["children"][0]["media"][0]["path"]).exists()


def test_export_granularity_mapping(tmp_path, export_work):
    for src, expect in [("asr:mimo", "chunk-45s"), ("asr:qwen", "chunk-45s"),
                        ("asr:funasr", "sentence"), ("asr:groq", "segment")]:
        out, work = export_work(tmp_path / src.replace(":", "_"), tr_source=src)
        assert sb_mod.export_index(work) == 0
        assert load_json(out / "video_index.json")["transcript"]["timestamp_granularity"] == expect


def test_export_blocks_on_bad_quote(tmp_path, capsys, export_work):
    out, work = export_work(tmp_path, quote="根本没说过的话")
    assert sb_mod.export_index(work) == 5
    assert not (out / "video_index.json").exists()             # 校验不过不产出
    assert "quote" in capsys.readouterr().out


def test_export_blocks_on_missing_frame(tmp_path, export_work):
    out, work = export_work(tmp_path)
    sb = load_json(wp(work, "storyboard"))
    sb["outline"][0]["media"][0]["proxy_path"] = str(work / "frames_proxy" / "nope.jpg")
    save_json(wp(work, "storyboard"), sb)
    assert sb_mod.export_index(work) == 5
    assert not (out / "video_index.json").exists()


def test_export_badge_template_contract(tmp_path, export_work):
    out, work = export_work(tmp_path)
    meta = load_json(wp(work, "meta"))
    meta["source"]["badge_url_template"] = "https://youtu.be/x"        # 缺 {t} 占位
    save_json(wp(work, "meta"), meta)
    assert sb_mod.export_index(work) == 5
    out2, work2 = export_work(tmp_path / "local", platform="local")
    assert sb_mod.export_index(work2) == 0
    d = load_json(out2 / "video_index.json")
    assert d["video"]["badge_url_template"] is None and d["video"]["platform"] == "local"
    assert d["video"]["source_url"] == "/abs/v.mp4"            # 本地:源路径即高清自取入口


def test_export_skips_when_fresh_and_forces(tmp_path, capsys, export_work):
    out, work = export_work(tmp_path)
    assert sb_mod.export_index(work) == 0
    capsys.readouterr()
    assert sb_mod.export_index(work) == 0
    assert "跳过" in capsys.readouterr().out                   # 续跑:新于上游即跳过
    before = (out / "video_index.json").read_bytes()
    assert sb_mod.export_index(work, force=True) == 0
    assert "跳过" not in capsys.readouterr().out
    assert (out / "video_index.json").read_bytes() == before   # 幂等:重复导出产物一致


def test_export_defaults_dedup_fields_when_missing(tmp_path, capsys, export_work):
    out, work = export_work(tmp_path)
    sb = load_json(wp(work, "storyboard"))
    for k in ("dedup_group", "dedup_primary"):
        sb["outline"][0]["media"][0].pop(k)
    save_json(wp(work, "storyboard"), sb)
    assert sb_mod.export_index(work) == 0                      # 未跑 dedup 的旧制品可导
    assert "无 dedup 标注" in capsys.readouterr().out          # 但不静默:stdout 提示补了默认值
    m = load_json(out / "video_index.json")["outline"][0]["media"][0]
    assert m["dedup_group"] is None and m["dedup_primary"] is True


def test_export_output_validates_against_json_schema(tmp_path, export_work):
    jsonschema = pytest.importorskip("jsonschema")             # 仅 dev 依赖,运行期零 pip 不破
    out, work = export_work(tmp_path)
    assert sb_mod.export_index(work) == 0
    schema = load_json(Path(__file__).resolve().parent.parent / "schemas" / "video_index.schema.json")
    doc = load_json(out / "video_index.json")
    jsonschema.validate(doc, schema)                           # 正例:导出物与规范一致
    bad = {k: v for k, v in doc.items() if k != "transcript"}
    with pytest.raises(jsonschema.exceptions.ValidationError):  # 负例:schema 真有牙齿
        jsonschema.validate(bad, schema)


def test_export_blocks_on_missing_resolution_and_clip_times(tmp_path, export_work):
    # 评审修复回归:validate_index 补齐 frame.t/resolution 与 clip 数值必选(schema required 对齐)
    out, work = export_work(tmp_path)
    assert sb_mod.export_index(work) == 0
    doc = load_json(out / "video_index.json")
    doc["outline"][0]["media"][0].pop("resolution")
    assert any("resolution" in e for e in sb_mod.validate_index(doc))
    doc2 = load_json(out / "video_index.json")
    doc2["outline"][0]["media"][1].pop("t_start")
    assert any("t_start" in e for e in sb_mod.validate_index(doc2))
