"""notes.py 笔记渲染器测试(切片4 票03,spec v0.5 §9.5)。

fixture 刻意由 export 产物构造并删除 .work/ —— 「只读导出文档活着」的跨 seam
契约完备性验收(spec v0.5 §12)直接编码进测试环境。
"""
import re
import shutil

import pytest

import notes as notes_mod
import storyboard as sb_mod
from common import load_json, save_json


@pytest.fixture
def doc_fixture(export_work):
    """export 产物构造 + 删除 .work/ ——「只读文档活着」的验收环境(共享工厂见 conftest)。"""
    def _make(base, **kw):
        out, work = export_work(base, **kw)
        assert sb_mod.export_index(work) == 0
        shutil.rmtree(work)                             # 无 .work 环境:渲染器只能靠文档活着
        return out
    return _make


def test_notes_renders_from_doc_only(tmp_path, doc_fixture):
    out = doc_fixture(tmp_path)
    assert notes_mod.render_notes(out / "video_index.json", depth=2) == 0
    md = (out / "notes.md").read_text(encoding="utf-8")
    assert "# 测试片" in md
    assert "\n## " in md and "\n### " in md             # depth=2:L1+L2 标题层级
    assert "frames/1_3.0.jpg" in md                     # 配图相对路径
    assert "https://www.youtube.com/watch?v=x&t=3s" in md   # badge 链接,整数秒
    assert "Token 到底是什么" in md                      # evidence 原文引用
    for p in re.findall(r"\]\((frames/[^)]+)\)", md):   # 引用的帧资产全部存在
        assert (out / p).exists()


def test_notes_depth_controls_levels(tmp_path, doc_fixture):
    out = doc_fixture(tmp_path)
    assert notes_mod.render_notes(out / "video_index.json", depth=1) == 0
    md = (out / "notes.md").read_text(encoding="utf-8")
    assert "开场" in md and "细节" not in md            # L2 被 depth=1 折叠


def test_notes_local_platform_degrades_timestamps(tmp_path, doc_fixture):
    out = doc_fixture(tmp_path, platform="local")
    assert notes_mod.render_notes(out / "video_index.json", depth=2) == 0
    md = (out / "notes.md").read_text(encoding="utf-8")
    assert "](http" not in md                           # 无跳转 URL
    assert "00:03" in md                                # 时间戳退化为 mm:ss 纯文本


def test_notes_fails_fast_on_missing_contract_field(tmp_path, capsys, doc_fixture):
    out = doc_fixture(tmp_path)
    doc = load_json(out / "video_index.json")
    doc.pop("transcript")
    save_json(out / "video_index.json", doc)
    assert notes_mod.render_notes(out / "video_index.json", depth=2) == 5
    assert not (out / "notes.md").exists()              # 不产出残缺笔记
    assert "transcript" in capsys.readouterr().out      # 指明缺失项


def test_notes_fails_on_missing_frame_asset(tmp_path, capsys, doc_fixture):
    out = doc_fixture(tmp_path)
    (out / "frames" / "1_3.0.jpg").unlink()
    assert notes_mod.render_notes(out / "video_index.json", depth=2) == 5
    assert "1_3.0.jpg" in capsys.readouterr().out


def test_notes_keeps_dedup_annotation_visible(tmp_path, doc_fixture):
    out = doc_fixture(tmp_path)
    doc = load_json(out / "video_index.json")
    doc["outline"][0]["media"][0].update(dedup_group="g1", dedup_primary=False)
    doc["outline"][0]["children"][0]["media"][0].update(dedup_group="g1", dedup_primary=True)
    save_json(out / "video_index.json", doc)
    assert notes_mod.render_notes(out / "video_index.json", depth=2) == 0
    md = (out / "notes.md").read_text(encoding="utf-8")
    assert "frames/1_3.0.jpg" in md and "g1" in md      # 非 primary 不被丢弃,标注可见
