# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

This repo is the not-yet-implemented codebase for **video2slides**: a planned Claude Code skill that turns a video (YouTube / Bilibili / local file) into a `frontend-slides`-style HTML deck, with slides carrying embedded keyframes/clips that jump back to the source video's timestamp.

The full design is written up in `docs/video2slides-spec-v0.4.md` (Chinese; v0.4 is the reviewed, decision-final version — v0.3 is kept as a historical snapshot). **Read it before making architectural decisions** — it is the source of truth; the summary below exists so you don't have to re-read all ~400 lines just to get oriented. Right now the repo itself is just the `uv`-generated scaffold (`main.py` is a placeholder) — none of the pipeline described below has been implemented yet. Implementation proceeds as a vertical slice: subtitled slide-driven online video → outline → frames → HTML end-to-end first (spec §13).

> 语言约定：本仓库的**代码注释、commit message、文档（含 `docs/` 与新建 `.md`）一律用中文**。本文件除顶部固定前缀外，正文也用中文。

## Commands

- Runtime: Python 3.12, pinned via pyenv (`.python-version`), managed with `uv` (`pyproject.toml` / `uv.lock`).
- `uv sync` — install/sync the venv from the lockfile
- `uv run python main.py` — run the current entry point
- `uv add <pkg>` / `uv remove <pkg>` — manage dependencies (see Dependency policy below before adding anything to the runtime path)
- `uv run pytest` — run tests (pytest is a dev-only dependency; runtime stays stdlib-only)

## Target architecture (per the spec)

Core invariant driving every design decision: **transcript → outline (content keys) → related frames (targeted per-node frame selection) → slide**.

Pipeline (deterministic scripts do the heavy/reproducible work; host Claude does semantic judgment; they hand off through structured artifacts, script stdout feeding directly into Claude's next step):

1. **Fetch layer** (`scripts/fetch.py`, deterministic) — `yt-dlp` pulls a low-res proxy stream (~360p) used for *all* analysis, plus subtitles/chapters/heatmap/danmaku/metadata. ASR is a pluggable fallback in three families (`ASR_BACKEND=groq|openai|api` — one OpenAI-compatible client configured via `ASR_API_BASE`/`ASR_API_KEY`/`ASR_MODEL`; `funasr` — local subprocess venv, works on both arm64/x86_64 Macs; `none`; mlx-whisper/whisper.cpp are reserved subprocess slots, P2); `--transcript <path>` can bypass subtitle/ASR entirely.
2. **Signal layer** (`scripts/signals.py`) — one `ffmpeg` metadata pass over the proxy stream produces a per-frame scene-change-score timeline, persisted as `scene_scores.json`. Five downstream consumers all read this one array instead of each re-invoking ffmpeg: the visual-form probe, the page-boundary prior, in-window peak picking, clip placement, and the whiteboard end-frame rule.
3. **Analysis layer** (host Claude) — classifies two orthogonal axes: **visual_form** (axis A: slide-driven / screen-recording / talking-head / cinematic, read off the scene-score curve shape + edge density) and **genre** (axis B: from transcript + metadata). Generates a hierarchical outline where every node must cite a verbatim evidence quote (anti-hallucination check against the transcript text). For slide-driven segments, node boundaries snap to page boundaries (scene-score spikes = slide changes).
4. **Frame layer** (`scripts/frames.py` + a Claude final pass) — every leaf node's selection window (after alignment correction — windows get pre/post-expanded because the best frame often falls outside the literal spoken-time window) is merged into a single compound ffmpeg `select` expression and extracted in one decode pass. Candidates go through RGB sliding-window dedup (last 4 kept frames, to catch A-B-A cutaways) and blur/text-density scoring, pruned to top-3 per point. Candidates are tiled into contact sheets so Claude does one `Read` per chapter instead of reading every frame. Output: `storyboard.json`, with every leaf node holding proxy-resolution media (`finalized: false`).
5. **Render layer** (host Claude + the `frontend-slides` skill) — user picks a target page-count/depth; shallow outline nodes aggregate top-k media from their leaf descendants by pure sorting over `storyboard.json` (no re-analysis needed to change granularity). `scripts/frames.py --finalize` then lazily re-fetches high-res frames/clips *only* for media that actually makes the page. `frontend-slides` renders the final fixed 1920×1080 HTML deck; timestamp badges deep-link to `youtube.com/watch?v=…&t=…` or `bilibili.com/video/BV…?t=…`.

Key artifacts:
- **`storyboard.json`** — the enforced contract between the analysis and render layers (full schema in spec §6). Either side can be re-implemented independently as long as this contract holds.
- **`scene_scores.json`** — the shared per-frame signal basis (spec §8.0), computed once and consumed five ways.
- **`frames_proxy/`** — proxy-resolution candidate/selected frames from the analysis pass, pre-finalization.

Two-stage media lifecycle: analysis fills in `proxy_path` / `finalized: false`; only the render-time "lazy finalize" step fills `final_path` / `finalized: true` (this is what makes changing page-count granularity cheap — it never re-triggers analysis).

Key v0.4 decisions (details in spec):
- **Interaction contract**: zero interruptions during analysis; the single interaction point is the pre-render granularity question (merged with frontend-slides Phase 1 "Length"). Style is auto-mapped from genre (axis B), skipping frontend-slides Phase 2; the user can re-render with a different style at zero re-analysis cost (spec §9).
- **Resume**: every intermediate artifact lives in `.work/` under the output dir and is kept by default; each layer skips itself if its artifact exists and is newer than upstream (`--force` to re-run) (spec §3).
- **Long videos**: >30min outlines are generated per chapter, then globally merged (spec §7). Output language follows the video's language (`--lang` overrides); evidence quotes stay verbatim.
- **Local file input**: timestamp badges open an embedded `<video>` overlay and seek via JS (no external URL to link to); local input requires an ASR backend or `--transcript` (spec §9, §10).

Planned skill layout (does not exist yet):
```
video2slides/
├── SKILL.md            # orchestration contract: precheck → fetch → signals → analyze → select frames → render
├── scripts/
│   ├── setup.py        # precheck (--json/--check) + idempotent installer + .env scaffold
│   ├── fetch.py
│   ├── transcribe.py   # VTT/SRT parsing + pluggable ASR backends + danmaku density histogram
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
