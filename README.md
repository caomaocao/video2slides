<div align="center">

# video2slides

**Turn any video into a self-contained, replayable slide deck — every frame and quote deep-linked back to the exact moment in the source.**

A portable **agent skill** (Claude Code & other agent runtimes) that *watches the video for you*: it transcribes, outlines with cited evidence, curates the key frames, and renders a slide deck or navigable notes you can click straight back into the video.

English | [中文](./README.zh-CN.md)

![license](https://img.shields.io/badge/license-MIT-blue)
![python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)
![tests](https://img.shields.io/badge/tests-192%20passing-brightgreen)
![runtime deps](https://img.shields.io/badge/pip%20runtime%20deps-0-success)
![platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)
![agent skill](https://img.shields.io/badge/agent%20skill-Claude%20Code%20%7C%20portable-8A2BE2)

<br/>

<!-- Live demos are hosted on GitHub Pages; the images below link to the interactive decks. -->
[<img src="./assets/demo-token.png" width="46%" alt="slide-driven deck demo"/>](https://caomaocao.github.io/video2slides/token/)
[<img src="./assets/demo-nlp.png" width="46%" alt="screen-recording deck demo"/>](https://caomaocao.github.io/video2slides/nlp/)

**▶ Live demos:** [slide-driven lecture](https://caomaocao.github.io/video2slides/token/) · [screen-recording course](https://caomaocao.github.io/video2slides/nlp/) — real decks; click any timestamp badge to jump into the source video.

</div>

---

## Why video2slides

A good technical video is dense — a 40-minute lecture is a slide deck, a transcript, and a dozen "look at *this* frame" moments, all trapped in a timeline you have to scrub. Skimming it means dragging the playhead; citing it means screenshotting by hand; turning it into notes means pausing every ten seconds.

**video2slides collapses that into one pass.** Point it at a URL or a file and it produces a deck (or notes) where:

- every page is a real point the speaker made, backed by a **verbatim quote** from the transcript — no hallucinated summaries;
- every **frame** is the *right* frame for that point, pulled from the video and de-duplicated, not a random thumbnail;
- every **timestamp badge** deep-links back to that exact second in the original video.

It is not a captioning tool and not a summarizer bolted onto YouTube. It builds a **video index document** — a durable, self-contained mapping of `outline ↔ transcript ↔ frames` — and renders slides and notes as *views* of that document.

## Features

- **📥 Any source** — YouTube, Bilibili (single video and multi-part `?p=` collections), or a local file (`file://` playback with in-page seeking).
- **🗣️ Subtitles *or* ASR** — uses existing captions when present (**no API key needed**); otherwise falls back to speech-to-text in three pluggable backend families (whisper-style transcription APIs, chat/base64-audio APIs, or fully-local **FunASR**).
- **🧭 Two-axis understanding** — classifies **visual form** (slide-driven / screen-recording / talking-head / cinematic) and **genre**, reading the scene-change curve, edge density, transcript, and platform metadata.
- **🔖 Evidence-cited outline** — every outline node must quote a real line from the transcript; unverifiable nodes degrade to text rather than inventing content.
- **🖼️ Smart frame curation** — targeted per-node extraction in a single ffmpeg decode pass, RGB sliding-window dedup (catches A-B-A cutaways), blur/text-density scoring, and contact sheets so the host reads one image per chapter instead of hundreds.
- **📄 A real deliverable, not just a render** — exports `video_index.json` + `frames/`: a self-contained, versioned, **schema-validated** index document. Slides and notes are downstream views; the document is the product.
- **🎞️ Two renderers** — a fixed 1920×1080 HTML **slide deck** (via the [`frontend-slides`](https://github.com/zarazhangrui/frontend-slides) skill) and/or navigable **markdown notes** (`scripts/notes.py`, zero extra deps).
- **⏱️ Deep-links everywhere** — badges jump to `youtube.com/watch?v=…&t=`, `bilibili.com/video/BV…?p=n&t=`, or an embedded `<video>` overlay for local files.
- **📚 Long-video aware** — videos over 30 min are outlined chapter-by-chapter, then merged globally.
- **♻️ Resumable** — every intermediate artifact lives under `.work/`; each stage skips itself if its output is newer than its inputs (`--force` to re-run).
- **🌐 Degrades gracefully** — a text-only (non-multimodal) host still produces the full index + notes; only the slide view needs an image-reading model.
- **🪶 Near-zero dependencies** — stdlib-only Python; the only required binaries are `ffmpeg`/`ffprobe` and `yt-dlp`. No PIL, OpenCV, or PaddleOCR — all image work goes through ffmpeg.

## How it works

Deterministic scripts do the heavy, reproducible work; the **host agent** does the semantic judgment. They hand off through structured artifacts — one script's stdout feeds the agent's next decision.

```
                 YouTube  ·  Bilibili  ·  local file
                                │
                        ┌───────▼───────┐
                        │   fetch.py    │  yt-dlp → ~360p proxy stream
                        └───────┬───────┘  + subtitles · chapters · heatmap · danmaku · metadata
                                │
                 ┌──────────────┴──────────────┐
                 ▼                              ▼
         ┌───────────────┐              ┌───────────────┐
         │ transcribe.py │              │  signals.py   │
         │ subtitles/ASR │              │ one ffmpeg pass
         └───────┬───────┘              │ → scene-score timeline
                 │                      └───────┬───────┘
                 └──────────────┬───────────────┘
                                ▼
                       ┌─────────────────┐
                       │   host agent    │  axis A: visual form   axis B: genre
                       │    (analysis)   │  outline where every node cites a verbatim quote
                       └────────┬────────┘
                                ▼
                        ┌───────────────┐
                        │   frames.py   │  per-node frames · dedup · blur/text scoring
                        └───────┬───────┘  · contact sheets → host picks the best
                                ▼
                 ╔══════════════════════════════╗
                 ║      video_index.json        ║   the public contract:
                 ║          +  frames/          ║   transcript ↔ outline ↔ frames
                 ╚═══════════════╤══════════════╝   (self-contained · versioned · schema-checked)
                        ┌────────┴────────┐
                        ▼                 ▼
               ┌─────────────────┐  ┌─────────────┐
               │ frontend-slides │  │   notes.py  │
               │   HTML deck     │  │  markdown   │
               └────────┬────────┘  └──────┬──────┘
                        └────────┬─────────┘
                                 ▼
              timestamp badges deep-link back to the exact second in the source
```

The pipeline is **zero-interruption**: analysis runs start-to-finish without asking you anything. There is exactly one interaction point — after the index document is exported, before rendering — where the skill asks for output form, length, and language.

## Quick start

### 1. Prerequisites

| Requirement | Why | Install |
|---|---|---|
| **ffmpeg / ffprobe** ≥ 5.1 | proxy stream, scene signals, frame extraction | macOS: `brew install ffmpeg` · Linux: distro package manager |
| **yt-dlp** ≥ 2026.7 | fetching online video + subtitles | macOS: `brew install yt-dlp` · Linux: `pipx install yt-dlp` |
| **node** or **deno** | only for YouTube (solves its JS challenge) | `brew install node`, or your distro / `deno` installer |
| **tesseract** *(optional)* | text-density frame scoring (falls back to an edge-density proxy if absent) | `brew install tesseract` |

> **Platform:** macOS (Apple Silicon / Intel) and Linux (arm64 / x86_64). **Native Windows is not supported** — use WSL2 (which reports as Linux and runs fine).

Run the built-in precheck any time to see exactly what's missing, with platform-aware install hints:

```bash
python3 scripts/setup.py
```

### 2. Install as a skill

video2slides is an **agent skill**, not a standalone CLI — a host agent invokes it. Drop the repo into your agent's skills directory and the skill triggers on its `description`:

- **Claude Code / Desktop** — place the folder in your skills directory.
- **Codex** — `~/.agents/skills/video2slides/` (or a repo-local `.agents/skills/`).
- **OpenClaw** — `~/.agents/skills/video2slides/`; `SKILL.md` must be a real copy (the symlink-escape guard rejects links), while `scripts/`/`schemas/`/`assets/` may be symlinked.

Then just ask your agent, e.g. *"turn this video into slides: `<url>`"*.

### 3. Optional: the slide renderer

The **slide** output is rendered through the separate [`frontend-slides`](https://github.com/zarazhangrui/frontend-slides) skill (a zero-dependency, anti-"AI-slop" 1920×1080 deck generator). Install it if you want decks. **Without it, video2slides still produces the full `video_index.json` + navigable markdown notes** — you just skip the slide view.

### 4. Optional: an ASR backend (for videos with no subtitles)

Videos that already have subtitles need **no API key**. For the rest, configure one backend in `~/.config/video2slides/.env` (mode `0600`, never committed):

```bash
ASR_BACKEND=funasr          # fully local, no key; or: groq | openai | api | mimo | qwen
# API families also read: ASR_API_BASE / ASR_API_KEY / ASR_MODEL
# funasr reads: FUNASR_VENV  (its own isolated venv, kept out of this project)
```

## Usage

Once installed, you drive it in natural language through your agent:

> *"Make slides from this lecture: https://www.youtube.com/watch?v=…"*
> *"Turn `/path/to/talk.mp4` into notes."*

The skill runs the whole pipeline unattended, then asks **once**:

- **Form** — slides · markdown notes · both · index-document only *(default: slides)*
- **Length** — short (5–10) · medium (10–20) · long (20+) — a depth dial shared by both renderers
- **Language** — defaults to the video's language; override at will (evidence quotes always stay verbatim)

Output lands in `~/Desktop/video2slides/<title>_<date>/` by default: a self-contained folder (`video_index.json`, `frames/`, `index.html` and/or `notes.md`) you can move or share as-is.

## Output: the video index document

The first-class deliverable is **`video_index.json` + `frames/`** — a single JSON embedding the full transcript (with explicit `timestamp_granularity`), the outline tree, and the selected proxy-resolution frames (relative paths, dedup annotations). It is validated against [`schemas/video_index.schema.json`](./schemas/video_index.schema.json) and carries a `schema_version` so consumers can check compatibility.

Everything downstream — slides, notes, or your own tooling — reads only this document. Re-render with a different style, length, or language at **zero re-analysis cost**; the analysis never runs twice.

Full design rationale: [`docs/video2slides-spec-v0.5.md`](./docs/video2slides-spec-v0.5.md).

## Configuration: ASR backends

| Family | Presets | Timestamps | Notes |
|---|---|---|---|
| **transcriptions** | `groq` · `openai` · `api` | native segment | whisper-style multipart upload; `api` is configured via `ASR_API_BASE`/`ASR_API_KEY`/`ASR_MODEL` |
| **chat** | `mimo` · `qwen` | 45 s chunk granularity | chat/completions with base64 audio; the outline/QA layer compensates for coarse timestamps |
| **funasr** | *(local)* | sentence-level | runs in its own venv via subprocess (`FUNASR_VENV`); works on arm64 / x86_64 Macs, no API key |
| **none** | — | — | subtitled videos only; anything needing ASR stops with a clear message |

Audio is chunked at silence midpoints before upload, with per-chunk failure isolation. Bilibili subtitles are AI tracks that require a login cookie (`--cookies-from-browser chrome`, or an exported `cookies.txt` on headless hosts).

## Acknowledgements

- [`frontend-slides`](https://github.com/zarazhangrui/frontend-slides) by [@zarazhangrui](https://github.com/zarazhangrui) — the slide renderer this skill hands off to.
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) and [`ffmpeg`](https://ffmpeg.org/) — the two binaries that do all the fetching and media work.
- [FunASR](https://github.com/modelscope/FunASR) — the local speech-recognition backend.

## License

[MIT](./LICENSE) © 2026 caomaocao.

> The demo decks linked above are built from third-party videos and are shown for illustration only; the copyright in that footage belongs to the original creators.
