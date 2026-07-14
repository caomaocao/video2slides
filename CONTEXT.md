# Cuepoint

The ubiquitous language for **Cuepoint** — a portable agent skill that turns a video into a self-contained, replayable video index document and renders it into slides or notes. This file is a glossary only; design rationale lives in `docs/` and ADRs live in `docs/adr/`.

## Language

**Cuepoint**:
The project/skill itself. Written **Cuepoint** in prose (proper noun, one word); the repo and skill slug are lowercase `cuepoint`. Formerly named video2slides. The public deliverable is the skill, not a service.
_Avoid_: Cue Point (two words), CuePoint (camelCase), v2s; the old name video2slides in new prose.

**Agent skill**:
What Cuepoint *is* — a set of instructions + deterministic scripts that a host agent invokes (via `SKILL.md` / `AGENTS.md`). It has no standalone entry point of its own; the host agent supplies the semantic judgment.
_Avoid_: CLI, tool, app, service, library

**Host agent**:
The LLM runtime that runs the skill and does the semantic work (outline, classification, frame choice) — Claude Code or another agent runtime. The "brain" of the pipeline.
_Avoid_: the model, the LLM, server, backend

**Video index document**:
The exported public contract — `video_index.json` (transcript + outline tree + selected proxy frames) plus `frames/`. Since spec v0.5 this is the first-class deliverable; slides and notes are downstream views of it.
_Avoid_: the export, the JSON, the dump, output file

**Renderer**:
A downstream consumer that turns a video index document into a human-facing view — the slides renderer (via the `frontend-slides` skill) or the notes renderer (`scripts/notes.py`).
_Avoid_: generator, builder, exporter
