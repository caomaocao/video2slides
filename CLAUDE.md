# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repo is the codebase for **video2slides**: a Claude Code skill that turns a video (YouTube / Bilibili / local file) into a self-contained **video index document** (`video_index.json` + `frames/` — the outline↔transcript↔frames mapping as a versioned public contract, spec v0.5), rendered downstream into a `frontend-slides`-style HTML deck and/or markdown notes, with keyframes/clips that jump back to the source video's timestamp.

The full design is written up in `docs/video2slides-spec-v0.5.md` (Chinese; v0.5 是 2026-07-13 拷问式 review 定稿的「制品升格」决议版 — v0.4/v0.3 kept as historical snapshots). **Read it before making architectural decisions** — it is the source of truth; the summary below exists so you don't have to re-read all ~450 lines just to get oriented. Implementation status: slice 1 (subtitled slide-driven online video → outline → frames → HTML end-to-end), slice 2 (ASR three families + local file input) and slice 3 (long-video per-chapter outlines, merged 2026-07-13, 150 tests) are implemented, review-closed and merged to main. The 27 verified test sources plus all production findings live in `docs/test-videos.md`. Next in the backlog: **索引文档升格切片**(spec v0.5 §13:`storyboard.py export` + `schemas/video_index.schema.json` + dedup 标注化 + 交互点形态扩展 + `scripts/notes.py` 笔记渲染器),then dedup criteria upgrade (P2 — deliberately sequenced *after* dedup annotation lands, so the later upgrade only swaps the signature algorithm without touching the contract).

> 语言约定：本仓库的**代码注释、commit message、文档（含 `docs/` 与新建 `.md`）一律用中文**。本文件除顶部固定前缀外，正文也用中文。

## Commands

- Runtime: Python 3.12, pinned via pyenv (`.python-version`), managed with `uv` (`pyproject.toml` / `uv.lock`).
- `uv sync` — install/sync the venv from the lockfile
- `uv add <pkg>` / `uv remove <pkg>` — manage dependencies (see Dependency policy below before adding anything to the runtime path)
- `uv run pytest` — run tests (pytest is a dev-only dependency; runtime stays stdlib-only)

## Target architecture (per the spec)

Core invariant driving every design decision: **transcript → outline (content keys) → related frames (targeted per-node frame selection) → video_index (exported index document) → renderer family (slides / notes / …)**. Since spec v0.5, the index document is the first-class deliverable and slides are one downstream view of it.

Pipeline (deterministic scripts do the heavy/reproducible work; host Claude does semantic judgment; they hand off through structured artifacts, script stdout feeding directly into Claude's next step):

1. **Fetch layer** (`scripts/fetch.py`, deterministic) — `yt-dlp` pulls a low-res proxy stream (~360p) used for *all* analysis, plus subtitles/chapters/heatmap/danmaku/metadata. ASR is a pluggable fallback in three families (`ASR_BACKEND`, implemented in `scripts/transcribe.py` as a PRESETS table): the **transcriptions** protocol family (whisper-style multipart, native segment timestamps — `groq|openai|api` presets, `api` configured via `ASR_API_BASE`/`ASR_API_KEY`/`ASR_MODEL`); the **chat** protocol family (chat/completions with base64 audio, no native timestamps — `mimo|qwen` presets, timestamps degrade to 45s chunk granularity, which SKILL.md compensates for at the outline/QA level); `funasr` — local subprocess in its own venv (`FUNASR_VENV`), sentence-level timestamps, works on arm64/x86_64 Macs; and `none` (exit 3 = "needs ASR config"). Audio is chunked at silence midpoints (ffmpeg silencedetect) before upload, with per-chunk failure isolation. API keys live in `~/.config/video2slides/.env` (0600, never in git). mlx-whisper/whisper.cpp are reserved subprocess slots (P2). `--transcript <path>` (direct transcript supply) is a future capability, **not implemented — never reference it in user-facing guidance or emit text** (a review finding; three such references were removed).
2. **Signal layer** (`scripts/signals.py`) — one `ffmpeg` metadata pass over the proxy stream produces a per-frame scene-change-score timeline, persisted as `scene_scores.json`. Five downstream consumers all read this one array instead of each re-invoking ffmpeg: the visual-form probe, the page-boundary prior, in-window peak picking, clip placement, and the whiteboard end-frame rule.
3. **Analysis layer** (host Claude) — classifies two orthogonal axes: **visual_form** (axis A: slide-driven / screen-recording / talking-head / cinematic, read off the scene-score curve shape + edge density) and **genre** (axis B: from transcript + metadata). Generates a hierarchical outline where every node must cite a verbatim evidence quote (anti-hallucination check against the transcript text). For slide-driven segments, node boundaries snap to page boundaries (scene-score spikes = slide changes).
4. **Frame layer** (`scripts/frames.py` + a Claude final pass) — every leaf node's selection window (after alignment correction — windows get pre/post-expanded because the best frame often falls outside the literal spoken-time window) is merged into a single compound ffmpeg `select` expression and extracted in one decode pass. Candidates go through RGB sliding-window dedup (last 4 kept frames, to catch A-B-A cutaways) and blur/text-density scoring, pruned to top-3 per point. Candidates are tiled into contact sheets so Claude does one `Read` per chapter instead of reading every frame. Output: `storyboard.json`, with every leaf node holding proxy-resolution media (`finalized: false`).
5. **Render layer** (host Claude + the `frontend-slides` skill) — user picks a target page-count/depth; shallow outline nodes aggregate top-k media from their leaf descendants by pure sorting over `storyboard.json` (no re-analysis needed to change granularity). `scripts/frames.py --finalize` then lazily re-fetches high-res frames/clips *only* for media that actually makes the page. `frontend-slides` renders the final fixed 1920×1080 HTML deck; timestamp badges deep-link to `youtube.com/watch?v=…&t=…` or `bilibili.com/video/BV…?t=…`.

Key artifacts:
- **`storyboard.json`** — since v0.5 the *internal working format* (lives in `.work/`, free to evolve; carries render-side bookkeeping like `on_page`/`final_path`; full schema in spec §6). Cross-node dedup is **annotation-based** (`dedup_group`/`dedup_primary`), not deletion — "one frame per page" is a slide-view policy, not a data fact.
- **`video_index.json` + `frames/`** — the exported public contract (spec §6.5, **not yet implemented — next slice**): single JSON embedding full transcript segments (`timestamp_granularity` made explicit) + outline tree + proxy-quality selected frames, relative paths, validated against `schemas/video_index.schema.json`, `schema_version` field. All renderers' semantic input comes from this document only; it's read-only after export.
- **`scene_scores.json`** — the shared per-frame signal basis (spec §8.0), computed once and consumed five ways.
- **`frames_proxy/`** — proxy-resolution candidate/selected frames from the analysis pass, pre-finalization.

Two-stage media lifecycle: analysis fills in `proxy_path` / `finalized: false`; only the render-time "lazy finalize" step fills `final_path` / `finalized: true` (this is what makes changing page-count granularity cheap — it never re-triggers analysis).

Key v0.4 decisions (details in spec):
- **Interaction contract**: zero interruptions during analysis; the single interaction point is the pre-render granularity question (merged with frontend-slides Phase 1 "Length"). Style is auto-mapped from genre (axis B), skipping frontend-slides Phase 2; the user can re-render with a different style at zero re-analysis cost (spec §9).
- **Resume**: every intermediate artifact lives in `.work/` under the output dir and is kept by default; each layer skips itself if its artifact exists and is newer than upstream (`--force` to re-run) (spec §3).
- **Long videos**: >30min outlines are generated per chapter, then globally merged (spec §7). Output language follows the video's language (`--lang` overrides); evidence quotes stay verbatim.
- **Local file input**: timestamp badges open an embedded `<video src="file://…">` overlay and seek via JS (no external URL to link to); a same-name `.json` sidecar supplies title/uploader/duration when present (ffprobe fallback otherwise); the proxy is an orientation-aware ffmpeg downscale, and `--finalize` grabs final frames directly from the original file. Local input requires an ASR backend (spec §9, §10).

Skill layout (implemented at repo root; vertical-slice scope per SKILL.md):
```
video2slides/
├── SKILL.md            # orchestration contract: precheck → fetch → signals → analyze → select frames → render
├── scripts/
│   ├── setup.py        # precheck (--json/--check) + idempotent installer + .env scaffold
│   ├── fetch.py
│   ├── transcribe.py   # VTT/SRT parsing + audio chunking + two ASR protocol families + danmaku density histogram
│   ├── funasr_runner.py # runs only inside FUNASR_VENV via subprocess; JSON on real stdout (dependency noise redirected to stderr)
│   ├── signals.py
│   ├── frames.py       # candidate extraction + dedup + scoring + contact sheets + --finalize
│   └── storyboard.py   # schema/timestamp/quote-existence/cross-node-dedup validation
# (rendering calls the frontend-slides skill directly — no bundled render code)
```

## Dependency policy

The shipped skill is designed for **zero pip runtime dependencies** (stdlib only) plus exactly two required external binaries: `ffmpeg`/`ffprobe` and `yt-dlp`. `tesseract` is optional (OCR density scoring; degrades to an ffmpeg edge-density proxy if absent). PIL/opencv/paddleocr are explicitly excluded by design (spec §10.1, §15) — all image work goes through ffmpeg (rawvideo pipes, `tile` filter, `edgedetect`/`blurdetect`), not Python imaging libraries. Adding something to the runtime dependency path is a spec change, not just a `uv add`. The optional local FunASR backend runs in its own separate venv via subprocess specifically to keep its dependency tree out of this project.

Note: `yt-dlp` is `uv add`-ed into this dev repo for version pinning/convenience — that's fine and doesn't violate the above. The invariant that actually matters is code-level: `scripts/fetch.py` must shell out to the `yt-dlp` CLI via subprocess, never `import yt_dlp`. This repo's `uv.lock` pinning the tool's version is orthogonal to the shipped skill's own `setup.py` precheck/installer, which still needs to get `yt-dlp`/`ffmpeg` onto an end user's machine as system binaries (brew/pipx) — skill users won't be running `uv sync` inside this dev repo.

`yt-dlp` needs `node` or `deno` on `PATH` to solve YouTube's JS challenge (EJS) — recent YouTube extractors fail without one of these available.

## Prerequisite skill

`frontend-slides` is a required dependency skill: rendering must go through its `SKILL.md` contract (fixed 1920×1080 stage, zero runtime deps, anti-"AI slop" aesthetic) rather than reimplementing a trimmed-down version here.

## Non-goals (MVP)

No standalone CLI/service (the "LLM" in the pipeline is the host Claude, not a self-dialed API), no pptx output, no picture-in-picture region detection, no batch/queue processing, no shot-language/editing-rhythm analysis.
