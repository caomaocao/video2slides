# tests/ · AGENTS.md

pytest 测试套件。`pytest` 是**仅 dev 依赖**,运行期代码保持 stdlib-only(测试里也别 import 运行期禁用的库,如 PIL/opencv/yt_dlp)。

## 跑测试

```
uv run pytest          # 全量
uv run pytest tests/test_transcribe.py -q   # 单文件
```

## 约定

- **TDD**:先写会失败的 RED 断言,再实现。修 bug 也先补一条能复现的防回归测试(仓库里多次这么做,如 `_PUNCT` 弯引号、HINT_MERGE 边界)。
- **一一对应**:`scripts/X.py` 对应 `tests/test_X.py`;`common.py` → `test_common.py`。
- **离线**:测试**不触网、不真调 ffmpeg/ASR**。走 monkeypatch(例:`transcribe._http_post` 是 HTTP 座的替换点)+ `tests/fixtures/` 里的样本喂输入。
- `conftest.py` 放共享 fixture。

## fixtures/ 里有什么(样本输入,勿当产物删)

- 字幕样本:`sample.vtt`、`sample.srt`
- yt-dlp 元数据:`ytdlp_info_youtube.json`、`ytdlp_info_bilibili.json`
- ASR 响应:`asr_chat_resp.json`、`asr_verbose_json.json`
- ffmpeg 输出文本:`scene_metadata.txt`、`silencedetect.txt`
- 本地 sidecar:`sidecar_wechat.json`

> 注:`.gitignore` 只忽略流水线的 `.work/` 产物,**不**忽略这些 fixture,放心提交。
