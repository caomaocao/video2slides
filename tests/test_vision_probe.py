"""跨平台可移植性 票02:视觉探针 checker——宿主读图后报出的文字在此比对。

明文答案永不落地(只存归一化后的 sha256),防「纯文本宿主读 SKILL/源码后直接回显答案」的作弊。
"""
import vision_probe as vp


def test_normalize_strips_case_space_punct():
    assert vp.normalize("zebra compass 58") == "ZEBRACOMPASS58"
    assert vp.normalize("ZEBRA-COMPASS-58") == "ZEBRACOMPASS58"
    assert vp.normalize("Zebra, Compass  58!") == "ZEBRACOMPASS58"


def test_check_accepts_correct_token_various_forms():
    # OCR/casing 抖动容忍:归一化后一致即算命中(宿主确实看到了图)
    for claim in ["ZEBRA-COMPASS-58", "zebra compass 58", "Zebra-Compass-58"]:
        assert vp.check(claim) is True


def test_check_rejects_wrong_or_empty():
    # 纯文本宿主:要么答不出(空),要么幻觉编造(错词)——都必须判否
    assert vp.check("") is False
    assert vp.check("我看不到图片") is False
    assert vp.check("APPLE-BANANA-99") is False


def test_main_exit_codes(capsys):
    assert vp.main(["--claim", "ZEBRA-COMPASS-58"]) == 0        # 命中 → 视觉模式
    assert vp.main(["--claim", "made up nonsense"]) == 1        # 未命中 → 无视觉模式


def test_expected_hash_never_stores_plaintext():
    # 源码里不得出现明文答案(含归一化形态),否则回显作弊可绕过探针
    src = __import__("inspect").getsource(vp)
    assert "ZEBRACOMPASS58" not in src and "ZEBRA-COMPASS-58" not in src


def test_main_persists_verdict_to_host_caps(tmp_path):
    """给 --work 时落 host_caps.json,续跑/新会话可复用判决(票02),不必重读探针图。"""
    import json
    work = tmp_path / ".work"
    assert vp.main(["--claim", "ZEBRA-COMPASS-58", "--work", str(work)]) == 0
    assert json.loads((work / "host_caps.json").read_text(encoding="utf-8")) == {"vision": True}
    assert vp.main(["--claim", "看不见", "--work", str(work)]) == 1
    assert json.loads((work / "host_caps.json").read_text(encoding="utf-8")) == {"vision": False}
