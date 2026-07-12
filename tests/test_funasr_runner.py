"""funasr_runner 的纯逻辑测试(在主 venv 跑,不依赖 funasr/torch——用注入替身)。

真实 funasr 推理在 FUNASR_VENV 里由子进程执行,不在此单测范围;这里锁定
设备选择优先级与 GPU→CPU 回退契约。
"""
import types

import pytest

import funasr_runner


def _torch(cuda=False, mps=False):
    return types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: cuda),
        backends=types.SimpleNamespace(
            mps=types.SimpleNamespace(is_available=lambda: mps)),
    )


def test_pick_device_prefers_cuda():
    assert funasr_runner.pick_device(env={}, torch_mod=_torch(cuda=True, mps=True)) == "cuda:0"


def test_pick_device_mps_on_apple_silicon():
    assert funasr_runner.pick_device(env={}, torch_mod=_torch(cuda=False, mps=True)) == "mps"


def test_pick_device_cpu_when_no_accelerator():
    assert funasr_runner.pick_device(env={}, torch_mod=_torch(cuda=False, mps=False)) == "cpu"


def test_pick_device_env_override_wins():
    # FUNASR_DEVICE 强制优先于自动检测(即便 GPU 可用也听命)
    assert funasr_runner.pick_device(
        env={"FUNASR_DEVICE": "cpu"}, torch_mod=_torch(cuda=True, mps=True)) == "cpu"


def test_pick_device_detection_error_degrades_not_crash():
    # 某些 torch 构建访问 backends.mps.is_available() 会抛异常 → 当作不可用,落 cpu
    def boom():
        raise RuntimeError("mps backend not built")
    t = types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False),
        backends=types.SimpleNamespace(mps=types.SimpleNamespace(is_available=boom)),
    )
    assert funasr_runner.pick_device(env={}, torch_mod=t) == "cpu"


class _FakeModel:
    def __init__(self, res=None, raises=None):
        self._res, self._raises = res, raises

    def generate(self, **kw):
        if self._raises:
            raise self._raises
        return self._res


def test_transcribe_falls_back_to_cpu_on_gpu_failure():
    calls = []

    def build(dev):
        calls.append(dev)
        if dev == "cpu":
            return _FakeModel(res=[{"sentence_info": [{"start": 0, "end": 1000, "text": "你好"}]}])
        return _FakeModel(raises=RuntimeError("MPS op not implemented"))

    logs = []
    segs = funasr_runner.transcribe_with_fallback(build, "a.mp3", "mps", log=logs.append)
    assert calls == ["mps", "cpu"]          # 先试 GPU,失败后回退 CPU
    assert segs == [{"t_start": 0.0, "t_end": 1.0, "text": "你好"}]
    assert logs and "回退 cpu" in logs[0]


def test_transcribe_no_fallback_when_cpu_itself_fails():
    # device 已是 cpu 时无处可退,异常应原样抛出
    def build(dev):
        return _FakeModel(raises=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        funasr_runner.transcribe_with_fallback(build, "a.mp3", "cpu")


def test_transcribe_gpu_success_does_not_touch_cpu():
    calls = []

    def build(dev):
        calls.append(dev)
        return _FakeModel(res=[{"sentence_info": [{"start": 500, "end": 2500, "text": "ok"}]}])

    segs = funasr_runner.transcribe_with_fallback(build, "a.mp3", "mps")
    assert calls == ["mps"]                 # GPU 成功则不再建 CPU 模型
    assert segs == [{"t_start": 0.5, "t_end": 2.5, "text": "ok"}]


def test_extract_segments_fallback_whole_text_when_no_sentence_info():
    res = [{"text": "整段无句级信息"}]
    assert funasr_runner._extract_segments(res) == [
        {"t_start": 0.0, "t_end": 0.0, "text": "整段无句级信息"}]
